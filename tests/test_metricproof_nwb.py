from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft202012Validator
from metricproof.schema import load_schema

from metricproof_nwb import (
    audit_nwb,
    hash_file,
    nwbinspector_validator,
    pynwb_validator,
)
from metricproof_nwb.report import render_json, render_text


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "session.nwb"
        self.path.write_bytes(b"minimal fixture")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_hash_file_is_streaming_and_stable(self):
        expected = hashlib.sha256(b"minimal fixture").hexdigest()
        self.assertEqual(hash_file(self.path), expected)

    def test_portable_artifact_uri_does_not_change_which_file_is_hashed(self):
        report = audit_nwb(
            self.path,
            validator=lambda path: [],
            artifact_uri="archive://study/session.nwb",
        )

        self.assertEqual(report.path, "archive://study/session.nwb")
        self.assertEqual(report.sha256, hash_file(self.path))

    def test_pass_report_contains_metadata_and_digest(self):
        report = audit_nwb(
            self.path,
            validator=lambda path: [],
            metadata_reader=lambda path: {"identifier": "session-01"},
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.status, "pass")
        self.assertEqual(report.metadata["identifier"], "session-01")
        self.assertEqual(report.exit_code, 0)
        payload = report.to_dict()
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["report_type"], "nwb-audit")
        self.assertEqual(payload["producer"], {
            "name": "metricproof-nwb",
            "version": "0.3.0",
        })
        self.assertEqual(payload["artifacts"][0]["sha256"], report.sha256)
        self.assertEqual(payload["context"]["nwb_metadata"]["identifier"], "session-01")
        self.assertEqual(payload["context"]["validators"], [
            {
                "name": "injected-pynwb-compatible-validator",
                "version": "unknown",
                "check_id": "pynwb-schema-validation",
                "configuration": {
                    "api": "pynwb.validate",
                    "injected_runner": True,
                },
            }
        ])
        Draft202012Validator(load_schema("evidence")).validate(payload)

    def test_custom_metadata_is_json_safe(self):
        report = audit_nwb(
            self.path,
            validator=lambda path: [],
            metadata_reader=lambda path: {
                "session_start_time": datetime(2025, 1, 2, tzinfo=timezone.utc),
                "nested": {"subject_count": 3},
            },
        )

        payload = json.loads(render_json(report))
        self.assertEqual(
            payload["context"]["nwb_metadata"]["session_start_time"],
            "2025-01-02T00:00:00+00:00",
        )
        self.assertEqual(payload["context"]["nwb_metadata"]["nested"], {"subject_count": 3})
        Draft202012Validator(load_schema("evidence")).validate(payload)

    def test_validation_failures_are_preserved(self):
        report = audit_nwb(
            self.path,
            validator=lambda path: ["missing session_start_time", {"id": "NWB-001"}],
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.validation_errors, [
            "missing session_start_time",
            "{'id': 'NWB-001'}",
        ])
        self.assertEqual(report.exit_code, 1)
        self.assertIn("Validation errors:", render_text(report))
        payload = json.loads(render_json(report))
        finding = payload["results"][-1]
        self.assertEqual(finding["check_id"], "pynwb-schema-validation")
        self.assertEqual(finding["observed"], {"findings": 2})
        self.assertEqual(finding["evidence"][1]["id"], "NWB-001")

    def test_validator_error_is_distinct_from_invalid_file(self):
        def unavailable(path):
            raise RuntimeError("PyNWB is required")

        report = audit_nwb(self.path, validator=unavailable)

        self.assertEqual(report.status, "error")
        self.assertEqual(report.exit_code, 2)
        payload = json.loads(render_json(report))
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["counts"]["error"], 1)
        self.assertIn("PyNWB is required", payload["results"][-1]["message"])

    def test_metadata_failure_is_a_non_blocking_warning(self):
        def broken_metadata(path):
            raise RuntimeError("metadata reader failed")

        report = audit_nwb(
            self.path,
            validator=lambda path: [],
            metadata_reader=broken_metadata,
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.status, "pass")
        self.assertEqual(report.exit_code, 0)
        self.assertEqual(len(report.warnings), 1)
        self.assertEqual(report.report.counts, {"pass": 1, "fail": 1, "error": 0})

    def test_validator_and_validators_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, "either validator or validators"):
            audit_nwb(
                self.path,
                validator=lambda path: [],
                validators=[pynwb_validator(runner=lambda path: [])],
            )

    def test_at_least_one_validator_is_required(self):
        with self.assertRaisesRegex(ValueError, "At least one validator"):
            audit_nwb(self.path, validators=[])

    def test_nwbinspector_findings_preserve_public_fields_and_importance(self):
        class Importance(Enum):
            BEST_PRACTICE_VIOLATION = 1

        class Severity(Enum):
            HIGH = 2

        finding = SimpleNamespace(
            message="Electrode locations are missing.",
            importance=Importance.BEST_PRACTICE_VIOLATION,
            severity=Severity.HIGH,
            check_function_name="check_electrode_location_exists",
            object_type="ElectrodesTable",
            object_name="electrodes",
            location="/general/extracellular_ephys/electrodes",
            file_path=str(self.path),
        )
        report = audit_nwb(
            self.path,
            validators=[
                pynwb_validator(runner=lambda path: []),
                nwbinspector_validator(runner=lambda path: [finding]),
            ],
            metadata_reader=lambda path: {"identifier": "session-01"},
            artifact_uri="archive://study/session.nwb",
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.status, "pass")
        self.assertEqual(len(report.inspector_findings), 1)
        preserved = report.inspector_findings[0]
        self.assertEqual(preserved["importance"], "BEST_PRACTICE_VIOLATION")
        self.assertEqual(preserved["severity"], "HIGH")
        self.assertEqual(
            preserved["check_function_name"],
            "check_electrode_location_exists",
        )
        self.assertEqual(preserved["file_path"], "archive://study/session.nwb")
        inspector_result = report.report.results[-1]
        self.assertEqual(inspector_result.status, "fail")
        self.assertEqual(inspector_result.severity, "warning")
        self.assertEqual(report.validators[-1]["name"], "nwbinspector")

    def test_critical_nwbinspector_finding_fails_audit(self):
        finding = {
            "message": "The file cannot be read safely.",
            "importance": "CRITICAL",
            "check_function_name": "check_readability",
        }
        report = audit_nwb(
            self.path,
            validators=[
                pynwb_validator(runner=lambda path: []),
                nwbinspector_validator(runner=lambda path: [finding]),
            ],
        )

        self.assertFalse(report.passed)
        self.assertEqual(report.status, "fail")
        self.assertEqual(report.exit_code, 1)
        self.assertEqual(report.report.results[-1].severity, "critical")

    def test_nwbinspector_adapter_calls_the_public_api(self):
        spec = nwbinspector_validator(importance_threshold="CRITICAL")

        findings = spec.normaliser(spec.runner(self.path))

        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0]["importance"], "ERROR")
        self.assertIn("message", findings[0])


class ExampleWorkflowTests(unittest.TestCase):
    def test_bundled_evidence_matches_the_realistic_nwb_artifact(self):
        example_dir = Path(__file__).parents[1] / "examples" / "academic_workflow"
        nwb_path = example_dir / "synthetic_ecephys_session.nwb"
        evidence = json.loads(
            (example_dir / "example-evidence.json").read_text(encoding="utf-8")
        )

        self.assertEqual(evidence["artifacts"][0]["sha256"], hash_file(nwb_path))
        self.assertEqual(evidence["artifacts"][0]["size_bytes"], nwb_path.stat().st_size)
        self.assertEqual(
            {item["name"] for item in evidence["context"]["validators"]},
            {"pynwb", "nwbinspector"},
        )
        self.assertEqual(
            {result["check_id"] for result in evidence["results"]},
            {"pynwb-schema-validation", "nwbinspector-best-practices"},
        )
        Draft202012Validator(load_schema("evidence")).validate(evidence)


if __name__ == "__main__":
    unittest.main()

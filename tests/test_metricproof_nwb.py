from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from metricproof.schema import load_schema

from metricproof_nwb import audit_nwb, hash_file
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
            "version": "0.2.0",
        })
        self.assertEqual(payload["artifacts"][0]["sha256"], report.sha256)
        self.assertEqual(payload["context"]["nwb_metadata"]["identifier"], "session-01")
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


if __name__ == "__main__":
    unittest.main()

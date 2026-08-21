import tempfile
import unittest
from pathlib import Path

from metricproof_nwb import (
    ValidatorSpec,
    audit_nwb,
    build_manifest,
    dandi_validator,
    render_html,
    run_session_checks,
    verify_manifest,
)


class SessionEvidenceTests(unittest.TestCase):
    def test_manifest_lineage_is_portable_and_verifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raw.bin").write_bytes(b"raw")
            (root / "derived.bin").write_bytes(b"derived")
            manifest = build_manifest(
                root,
                session={"session_id": "s-001"},
                artifact_specs=[
                    {"path": "raw.bin", "stage": "raw", "role": "recording"},
                    {"path": "derived.bin", "stage": "analysis", "role": "table", "parents": ["raw.bin"]},
                ],
            )
            payload = manifest.to_dict()
            self.assertEqual(payload["schema_version"], "0.3")
            derived = next(item for item in payload["artifacts"] if item["name"] == "derived.bin")
            self.assertEqual(derived["parents"], ["raw.bin"])
            self.assertEqual(verify_manifest(manifest, base_dir=root).status, "pass")
            (root / "raw.bin").write_bytes(b"changed")
            self.assertEqual(verify_manifest(manifest, base_dir=root).status, "fail")

    def test_session_checks_surface_timebase_and_curation_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "session.nwb").write_bytes(b"nwb")
            manifest = build_manifest(
                root,
                session={
                    "session_id": "s-001",
                    "timebases": [{"name": "lfp", "rate": 1000, "sample_count": 100, "start": 0, "stop": 0.2}],
                    "recording_durations": {"lfp.bin": 1.5},
                    "trials": [{"trial_id": "t1", "start_time": 2, "stop_time": 1, "node_path": ["start", "missing"]}],
                    "curation": {"human_reviewed": False, "recompute_required": True, "recomputed": False},
                },
                artifact_specs=[{"path": "session.nwb", "stage": "handoff", "role": "nwb"}],
                config={"node_ids": ["start", "goal"], "graph_edges": [["start", "goal"]], "expected_recording_durations": {"lfp.bin": 2.0}},
            )
            summary = run_session_checks(manifest)
            self.assertEqual(summary.status, "incomplete")
            check_ids = {result.check_id for result in summary.results}
            self.assertIn("session-timebases", check_ids)
            self.assertIn("session-trial-metadata", check_ids)
            self.assertIn("session-curation-gate", check_ids)

    def test_audit_embeds_manifest_and_html_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nwb = root / "session.nwb"
            nwb.write_bytes(b"synthetic")
            manifest = build_manifest(
                root,
                session={"session_id": "s-002"},
                artifact_specs=[{"path": "session.nwb", "stage": "handoff", "role": "nwb"}],
            )
            validator = ValidatorSpec(
                name="test-validator",
                version="1.0",
                check_id="test-validation",
                check_type="nwb_validation",
                runner=lambda path: [],
            )
            report = audit_nwb(
                nwb,
                validators=[validator],
                metadata_reader=lambda path: {"session_id": "s-002"},
                manifest=manifest,
            )
            self.assertEqual(report.session_status, "complete")
            self.assertEqual(report.exit_code, 0)
            self.assertIn("session-lineage", {result.check_id for result in report.report.results})
            html = render_html(report)
            self.assertIn("Artifact lineage", html)
            self.assertIn("session.nwb", html)

    def test_dandi_adapter_preserves_injected_findings(self):
        adapter = dandi_validator(runner=lambda path: [{"message": "archive warning", "severity": "warning"}])
        self.assertEqual(adapter.name, "injected-dandi-compatible-validator")
        self.assertEqual(adapter.normaliser(adapter.runner(Path("session.nwb")))[0]["message"], "archive warning")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from metricproof import REPORT_SCHEMA_VERSION
from metricproof.schema import load_schema

from metricproof_nwb import audit_nwb


class SharedEvidenceCompatibilityTests(unittest.TestCase):
    def test_nwb_report_matches_metricproof_evidence_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.nwb"
            path.write_bytes(b"compatibility fixture")
            report = audit_nwb(
                path,
                validator=lambda _: [],
                metadata_reader=lambda _: {"identifier": "compatibility-session"},
            )

        payload = report.to_dict()
        Draft202012Validator(load_schema("evidence")).validate(payload)
        self.assertEqual(payload["schema_version"], REPORT_SCHEMA_VERSION)
        self.assertEqual(payload["producer"]["name"], "metricproof-nwb")
        self.assertEqual(payload["report_type"], "nwb-audit")


if __name__ == "__main__":
    unittest.main()

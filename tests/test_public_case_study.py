"""Offline checks for the published case study's evidence and source guard."""

import json
import tempfile
import unittest
from pathlib import Path

from examples.public_dandi_case_study.run_case_study import SOURCE, run

CASE = Path(__file__).resolve().parents[1] / "examples/public_dandi_case_study/published"


class PublicCaseStudyTests(unittest.TestCase):
    def test_recorded_claims_match_evidence(self):
        summary = json.loads((CASE / "summary.json").read_text(encoding="utf-8"))
        baseline = json.loads((CASE / "baseline/evidence.json").read_text(encoding="utf-8"))
        shifted = json.loads((CASE / "shifted/evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline["artifacts"][0]["sha256"], SOURCE["sha256"])
        self.assertNotEqual(shifted["artifacts"][0]["sha256"], SOURCE["sha256"])
        self.assertEqual(baseline["results"], shifted["results"])
        self.assertEqual(summary["baseline_results"], baseline["results"])
        self.assertFalse(baseline["passed"])
        self.assertTrue(any(result["status"] == "error" for result in baseline["results"]))
        self.assertEqual(summary["verification"], {"unchanged": "pass", "missing": "incomplete", "shifted": "fail"})

    def test_rejects_wrong_source_before_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "wrong.nwb"
            source.write_bytes(b"not the pinned data")
            with self.assertRaisesRegex(ValueError, "does not match"):
                run(root / "output", source)
            self.assertFalse((root / "output/baseline/evidence.json").exists())

    def test_refuses_to_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                run(Path(directory))

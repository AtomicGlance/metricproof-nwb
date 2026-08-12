"""Verify that an evidence report still identifies the bundled NWB artifact."""

from __future__ import annotations

import json
from pathlib import Path

from metricproof import hash_file


def main() -> int:
    directory = Path(__file__).parent
    evidence_path = directory / "example-evidence.json"
    nwb_path = directory / "synthetic_ecephys_session.nwb"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    artifact = evidence["artifacts"][0]
    observed_digest = hash_file(nwb_path)

    if artifact["sha256"] != observed_digest:
        raise SystemExit(
            "Evidence does not match synthetic_ecephys_session.nwb: "
            f"expected {artifact['sha256']}, observed {observed_digest}"
        )

    validators = {
        (item["name"], item["version"])
        for item in evidence["context"]["validators"]
    }
    if not {"pynwb", "nwbinspector"}.issubset({name for name, _ in validators}):
        raise SystemExit("Evidence is missing PyNWB or NWBInspector provenance.")

    print(f"Verified SHA-256: {observed_digest}")
    print("Recorded validators:")
    for name, validator_version in sorted(validators):
        print(f"  {name} {validator_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

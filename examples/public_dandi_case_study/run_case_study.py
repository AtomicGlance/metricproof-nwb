"""Audit a pinned public NWB file and demonstrate the limits of validation."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import urllib.request
from pathlib import Path

import h5py
import numpy as np

from metricproof_nwb import (
    audit_nwb,
    hash_file,
    nwbinspector_validator,
    pynwb_validator,
    verify_evidence,
    write_html,
)

ASSET_ID = "f1b6ed8f-1e14-44fa-b4ee-240d0efe3759"
SOURCE = {
    "dandiset": "000006",
    "version": "0.220126.1855",
    "doi": "https://doi.org/10.48324/dandi.000006/0.220126.1855",
    "asset_id": ASSET_ID,
    "asset_path": "sub-anm372907/sub-anm372907_ses-20170613.nwb",
    "download_url": f"https://api.dandiarchive.org/api/assets/{ASSET_ID}/download/",
    "sha256": "974be4e6bb774eeef4075e4920db664cd2d9499d41278a953fc72e81ebaec846",
    "size_bytes": 258992,
    "license": "CC-BY-4.0",
    "citation": (
        "Economo, Michael N.; Svoboda, Karel (2022) Mouse anterior lateral motor "
        "cortex (ALM) in delay response task (Version 0.220126.1855) [Data set]. "
        "DANDI archive. https://doi.org/10.48324/dandi.000006/0.220126.1855"
    ),
}


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def download_verified(path):
    """Bound the download and verify the archive's independently published hash."""
    request = urllib.request.Request(SOURCE["download_url"], headers={"User-Agent": "MetricProof-NWB-case-study"})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read(SOURCE["size_bytes"] + 1)
    if len(content) != SOURCE["size_bytes"]:
        raise ValueError("Download size differs from the pinned asset")
    path.write_bytes(content)


def inspect_file(path):
    with h5py.File(path, "r") as handle:
        return {
            "nwb_version": str(handle.attrs["nwb_version"]),
            "unit_count": len(handle["units/id"]),
            "spike_count": len(handle["units/spike_times"]),
            "trial_count": len(handle["intervals/trials/id"]),
        }


def audit(path, destination):
    report = audit_nwb(
        path,
        artifact_uri="session.nwb",
        validators=[pynwb_validator(), nwbinspector_validator()],
        command="python examples/public_dandi_case_study/run_case_study.py",
    )
    payload = report.to_dict()
    payload["context"]["case_study_source"] = SOURCE
    write_json(destination / "evidence.json", payload)
    write_html(payload, destination / "evidence.html")
    if any(result["status"] == "error" and not result["evidence"] for result in payload["results"]):
        raise RuntimeError(f"Validator execution failed; inspect {destination / 'evidence.json'}")
    return payload


def run(output, source_cache=None):
    # Each run owns a new directory; never overwrite a prior scientific record.
    output.mkdir(parents=True, exist_ok=False)
    baseline = output / "baseline"
    shifted = output / "shifted"
    missing = output / "missing"
    for directory in (baseline, shifted, missing):
        directory.mkdir()
    original = baseline / "session.nwb"
    if source_cache is None:
        download_verified(original)
    else:
        shutil.copyfile(source_cache, original)
    if original.stat().st_size != SOURCE["size_bytes"] or hash_file(original) != SOURCE["sha256"]:
        raise ValueError("Source does not match the published asset; refusing to audit")

    write_json(output / "source.json", SOURCE)
    inventory = inspect_file(original)
    original_report = audit(original, baseline)
    unchanged = verify_evidence(original_report, base_dir=baseline)
    absent = verify_evidence(original_report, base_dir=missing)
    write_json(baseline / "verification.json", unchanged.to_dict())
    write_json(missing / "verification.json", absent.to_dict())

    altered = shifted / "session.nwb"
    shutil.copyfile(original, altered)
    with h5py.File(altered, "r+") as handle:
        times = handle["units/spike_times"]
        times[:] = times[:] + 0.25
    with h5py.File(original, "r") as before, h5py.File(altered, "r") as after:
        np.testing.assert_allclose(after["units/spike_times"][:] - before["units/spike_times"][:], 0.25)
        for column in ("start_time", "stop_time"):
            np.testing.assert_array_equal(before[f"intervals/trials/{column}"][:], after[f"intervals/trials/{column}"][:])
    changed = verify_evidence(original_report, base_dir=shifted)
    write_json(shifted / "verification-against-original.json", changed.to_dict())
    shifted_report = audit(altered, shifted)

    expected = {"unchanged": "pass", "missing": "incomplete", "shifted": "fail"}
    observed = {"unchanged": unchanged.status, "missing": absent.status, "shifted": changed.status}
    if observed != expected:
        raise AssertionError(f"Unexpected handoff verification: {observed}")
    if hash_file(original) != SOURCE["sha256"]:
        raise AssertionError("The original must remain unchanged")

    versions = {
        name: importlib.metadata.version(name)
        for name in ("metricproof", "metricproof-nwb", "pynwb", "nwbinspector", "h5py", "hdmf", "numpy")
    }
    environment = {"python": platform.python_version(), "platform": platform.platform(), "packages": versions}
    write_json(output / "environment.json", environment)
    requirements = sorted({
        f"{dist.metadata['Name']}=={dist.version}"
        for dist in importlib.metadata.distributions()
        if dist.metadata['Name'].lower() not in {"pip", "setuptools", "wheel"}
    })
    (output / "requirements.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
    summary = {
        "source": SOURCE,
        "inventory": inventory,
        "baseline_audit_passed": original_report["passed"],
        "shifted_audit_passed": shifted_report["passed"],
        "verification": observed,
        "controlled_change": "Added 0.25 seconds to all spike times; trial boundaries are unchanged. Educational copy only.",
        "baseline_results": original_report["results"],
        "shifted_results": shifted_report["results"],
        "validator_findings_identical": original_report["results"] == shifted_report["results"],
        "limitations": [
            "One small legacy NWB file is not representative of the archive or current acquisition workflows.",
            "A digest detects changed bytes, not the reason or scientific importance of a change.",
            "A fresh digest for a changed file is not evidence that its timing is scientifically correct.",
            "No independent synchronization reference or domain-specific alignment check is supplied.",
            "No DANDI validation, spike-sorting quality assessment, or biological replication was performed.",
        ],
    }
    write_json(output / "summary.json", summary)
    print(json.dumps({"inventory": inventory, "verification": observed, "environment": environment}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new, nonexistent output directory")
    parser.add_argument("--source-cache", type=Path, help="Optional offline source, verified against the pinned SHA-256")
    args = parser.parse_args()
    run(args.output, args.source_cache)

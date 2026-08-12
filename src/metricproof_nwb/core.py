"""NWB validation and provenance helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from metricproof import (
    ArtifactEvidence,
    CheckResult,
    EvidenceReport,
    ProducerInfo,
    hash_file,
)

from ._version import __version__
from .models import NWBProofReport
from .validators import Validator, ValidatorSpec, json_value, pynwb_validator

MetadataReader = Callable[[Path], Mapping[str, Any]]


def _default_metadata_reader(path: Path) -> Mapping[str, Any]:
    try:
        from pynwb import NWBHDF5IO
    except ImportError:
        return {}

    with NWBHDF5IO(str(path), "r", load_namespaces=False) as io:
        nwbfile = io.read()
        fields = (
            "identifier",
            "session_description",
            "session_start_time",
            "experimenter",
            "lab",
            "institution",
            "nwb_version",
        )
        metadata: dict[str, Any] = {}
        for field_name in fields:
            value = getattr(nwbfile, field_name, None)
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            if value is not None:
                metadata[field_name] = json_value(value)
        return metadata


def audit_nwb(
    path: str | Path,
    *,
    validator: Validator | None = None,
    validators: Iterable[ValidatorSpec] | None = None,
    metadata_reader: MetadataReader | None = None,
    artifact_uri: str | None = None,
) -> NWBProofReport:
    """Hash, inspect, and validate one NWB file.

    ``validator`` remains as a backwards-compatible way to replace PyNWB with
    one callable. New integrations should pass one or more ``ValidatorSpec``
    objects through ``validators`` so the report records the software version,
    configuration, and meaning of each result.
    """

    if validator is not None and validators is not None:
        raise ValueError("Pass either validator or validators, not both.")

    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"NWB file not found: {file_path}")

    digest = hash_file(file_path)
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    reader = metadata_reader or _default_metadata_reader
    try:
        metadata = dict(reader(file_path))
    except Exception as exc:  # metadata should not hide schema validation results
        warnings.append(f"Metadata could not be read: {exc}")

    artifact = ArtifactEvidence(
        name=file_path.name,
        uri=artifact_uri or str(file_path),
        sha256=digest,
        size_bytes=file_path.stat().st_size,
        media_type="application/x-hdf5",
        metadata=metadata,
    )
    results: list[CheckResult] = []
    if warnings:
        results.append(
            CheckResult(
                check_id="nwb-metadata",
                check_type="metadata_extraction",
                status="fail",
                severity="warning",
                message=warnings[0],
                observed={"warnings": len(warnings)},
                expected={"warnings": 0},
                evidence=[{"message": warning} for warning in warnings],
                why_it_matters="Metadata is part of a reproducible NWB evidence record.",
                suggested_fix="Confirm the file can be opened and its metadata can be read.",
            )
        )

    validator_specs = (
        list(validators)
        if validators is not None
        else [pynwb_validator(runner=validator)]
    )
    if not validator_specs:
        raise ValueError("At least one validator must be configured.")

    for spec in validator_specs:
        try:
            findings = spec.normaliser(spec.runner(file_path))
        except Exception as exc:
            results.append(
                CheckResult(
                    check_id=spec.check_id,
                    check_type=spec.check_type,
                    status="error",
                    severity="critical",
                    message=f"{spec.failure_label} could not run: {exc}",
                    observed={"exception": type(exc).__name__},
                    expected={"validation_completed": True},
                    why_it_matters=(
                        "An unexecuted validator leaves part of the NWB evidence "
                        "record unverified."
                    ),
                    suggested_fix=(
                        "Install the corresponding optional dependency and confirm "
                        "the file is readable."
                    ),
                )
            )
            continue

        if artifact_uri:
            for finding in findings:
                if "file_path" in finding:
                    finding["file_path"] = artifact_uri

        status = spec.status_for(findings)
        results.append(
            CheckResult(
                check_id=spec.check_id,
                check_type=spec.check_type,
                status=status,
                severity=spec.severity_for(findings),
                message=(
                    f"{spec.failure_label} reported {len(findings)} finding(s)."
                    if findings
                    else spec.pass_message
                ),
                observed={"findings": len(findings)},
                expected={"findings": 0},
                evidence=findings,
                why_it_matters=spec.why_it_matters,
                suggested_fix=spec.suggested_fix if findings else "",
            )
        )

    report = EvidenceReport(
        report_type="nwb-audit",
        title=f"NWB evidence report: {file_path.name}",
        results=results,
        artifacts=[artifact],
        producer=ProducerInfo(name="metricproof-nwb", version=__version__),
        context={
            "nwb_metadata": metadata,
            "warnings": warnings,
            "validators": [spec.provenance() for spec in validator_specs],
        },
    )
    return NWBProofReport(report=report)

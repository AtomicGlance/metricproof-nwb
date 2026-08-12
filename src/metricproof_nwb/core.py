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

Validator = Callable[[Path], Iterable[Any]]
MetadataReader = Callable[[Path], Mapping[str, Any]]


def _default_validator(path: Path) -> Iterable[Any]:
    try:
        from pynwb import validate
    except ImportError as exc:
        raise RuntimeError(
            "PyNWB is required for NWB validation; install metricproof-nwb[nwb]."
        ) from exc

    try:
        return validate(path=path)
    except TypeError:
        # Keep compatibility with PyNWB versions that still expose ``paths``.
        return validate(paths=[str(path)])


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


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
                metadata[field_name] = _json_value(value)
        return metadata


def _normalise_errors(errors: Iterable[Any] | Any) -> list[dict[str, Any]]:
    if errors is None:
        return []
    if isinstance(errors, (str, bytes)):
        return [{"message": str(errors)}]
    try:
        items = list(errors)
    except TypeError:
        items = [errors]
    findings: list[dict[str, Any]] = []
    for error in items:
        if isinstance(error, Mapping):
            finding = {str(key): _json_value(value) for key, value in error.items()}
            finding.setdefault("message", str(error))
        else:
            finding = {"message": str(error)}
            for name in ("name", "reason", "location", "path", "severity"):
                value = getattr(error, name, None)
                if value is not None:
                    finding[name] = _json_value(value)
        findings.append(finding)
    return findings


def audit_nwb(
    path: str | Path,
    *,
    validator: Validator | None = None,
    metadata_reader: MetadataReader | None = None,
) -> NWBProofReport:
    """Hash, inspect, and validate one NWB file.

    ``validator`` and ``metadata_reader`` are injectable so downstream projects
    can add checks without coupling their tests to a particular PyNWB release.
    """

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
        uri=str(file_path),
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

    try:
        errors = _normalise_errors((validator or _default_validator)(file_path))
    except Exception as exc:
        results.append(
            CheckResult(
                check_id="pynwb-schema-validation",
                check_type="nwb_validation",
                status="error",
                severity="critical",
                message=f"NWB validation could not run: {exc}",
                observed={"exception": type(exc).__name__},
                expected={"validation_completed": True},
                why_it_matters="An unexecuted validator leaves the NWB file unverified.",
                suggested_fix="Install the NWB extra and confirm the file is readable.",
            )
        )
    else:
        results.append(
            CheckResult(
                check_id="pynwb-schema-validation",
                check_type="nwb_validation",
                status="fail" if errors else "pass",
                severity="critical",
                message=(
                    f"PyNWB reported {len(errors)} validation finding(s)."
                    if errors
                    else "PyNWB schema validation passed."
                ),
                observed={"findings": len(errors)},
                expected={"findings": 0},
                evidence=errors,
                why_it_matters="Schema-valid NWB files are safer to exchange and reuse.",
                suggested_fix=(
                    "Correct the reported NWB schema findings and rerun the audit."
                    if errors
                    else ""
                ),
            )
        )

    report = EvidenceReport(
        report_type="nwb-audit",
        title=f"NWB evidence report: {file_path.name}",
        results=results,
        artifacts=[artifact],
        producer=ProducerInfo(name="metricproof-nwb", version=__version__),
        context={"nwb_metadata": metadata, "warnings": warnings},
    )
    return NWBProofReport(report=report)

"""Validator adapters and provenance for NWB evidence reports."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

Validator = Callable[[Path], Iterable[Any]]
FindingNormaliser = Callable[[Iterable[Any] | Any], list[dict[str, Any]]]
SeverityResolver = Callable[[list[dict[str, Any]]], str]
StatusResolver = Callable[[list[dict[str, Any]]], str]


def _package_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "not-installed"


def _enum_name(value: Any) -> Any:
    name = getattr(value, "name", None)
    return name if isinstance(name, str) else value


def json_value(value: Any) -> Any:
    """Convert validator output into values safe for an evidence document."""

    value = _enum_name(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    return str(value)


def normalise_findings(findings: Iterable[Any] | Any) -> list[dict[str, Any]]:
    """Preserve common fields from PyNWB and custom validator findings."""

    if findings is None:
        return []
    if isinstance(findings, (str, bytes)):
        return [{"message": str(findings)}]
    try:
        items = list(findings)
    except TypeError:
        items = [findings]

    normalised: list[dict[str, Any]] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, Mapping):
            finding = {str(key): json_value(value) for key, value in item.items()}
            finding.setdefault("message", str(item))
        else:
            finding = {"message": str(item)}
            for name in (
                "name",
                "reason",
                "location",
                "path",
                "severity",
            ):
                value = getattr(item, name, None)
                if value is not None:
                    finding[name] = json_value(value)
        normalised.append(finding)
    return normalised


def normalise_nwbinspector_findings(
    findings: Iterable[Any] | Any,
) -> list[dict[str, Any]]:
    """Preserve NWBInspector's public ``InspectorMessage`` fields."""

    if findings is None:
        return []
    try:
        items = list(findings)
    except TypeError:
        items = [findings]

    normalised: list[dict[str, Any]] = []
    fields = (
        "message",
        "importance",
        "severity",
        "check_function_name",
        "object_type",
        "object_name",
        "location",
        "file_path",
    )
    for item in items:
        if item is None:
            continue
        if isinstance(item, Mapping):
            finding = {str(key): json_value(value) for key, value in item.items()}
        else:
            finding = {
                name: json_value(getattr(item, name))
                for name in fields
                if getattr(item, name, None) is not None
            }
        finding.setdefault("message", str(item))
        normalised.append(finding)
    return normalised


def _nwbinspector_severity(findings: list[dict[str, Any]]) -> str:
    importance = {str(item.get("importance", "")) for item in findings}
    if importance & {"ERROR", "PYNWB_VALIDATION", "CRITICAL"}:
        return "critical"
    if "BEST_PRACTICE_VIOLATION" in importance:
        return "warning"
    return "info"


def _nwbinspector_status(findings: list[dict[str, Any]]) -> str:
    if any(item.get("importance") == "ERROR" for item in findings):
        return "error"
    return "fail" if findings else "pass"


@dataclass(frozen=True)
class ValidatorSpec:
    """Executable validator plus the provenance needed to interpret its result."""

    name: str
    version: str
    check_id: str
    check_type: str
    runner: Validator = field(repr=False)
    configuration: Mapping[str, Any] = field(default_factory=dict)
    failure_severity: str = "critical"
    pass_message: str = "Validation passed."
    failure_label: str = "Validation"
    why_it_matters: str = "Validation findings can affect reuse of the NWB file."
    suggested_fix: str = "Address the reported findings and rerun the audit."
    normaliser: FindingNormaliser = field(default=normalise_findings, repr=False)
    severity_resolver: SeverityResolver | None = field(default=None, repr=False)
    status_resolver: StatusResolver | None = field(default=None, repr=False)

    def provenance(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "check_id": self.check_id,
            "configuration": json_value(self.configuration),
        }

    def severity_for(self, findings: list[dict[str, Any]]) -> str:
        if not findings:
            return self.failure_severity
        if self.severity_resolver is not None:
            return self.severity_resolver(findings)
        return self.failure_severity

    def status_for(self, findings: list[dict[str, Any]]) -> str:
        if self.status_resolver is not None:
            return self.status_resolver(findings)
        return "fail" if findings else "pass"


def _run_pynwb(path: Path) -> Iterable[Any]:
    try:
        from pynwb import validate
    except ImportError as exc:
        raise RuntimeError(
            "PyNWB is required for NWB validation; install metricproof-nwb[nwb]."
        ) from exc

    try:
        return validate(path=path)
    except TypeError:
        # Compatibility with PyNWB versions that still expose ``paths``.
        return validate(paths=[str(path)])


def pynwb_validator(*, runner: Validator | None = None) -> ValidatorSpec:
    """Return the default PyNWB schema validator with explicit provenance."""

    injected = runner is not None
    return ValidatorSpec(
        name="pynwb" if not injected else "injected-pynwb-compatible-validator",
        version=_package_version("pynwb") if not injected else "unknown",
        check_id="pynwb-schema-validation",
        check_type="nwb_validation",
        runner=runner or _run_pynwb,
        configuration={
            "api": "pynwb.validate",
            "injected_runner": injected,
        },
        failure_severity="critical",
        pass_message="PyNWB schema validation passed.",
        failure_label="PyNWB",
        why_it_matters="Schema-valid NWB files are safer to exchange and reuse.",
        suggested_fix="Correct the reported NWB schema findings and rerun the audit.",
    )


def nwbinspector_validator(
    *,
    importance_threshold: str = "BEST_PRACTICE_SUGGESTION",
    ignore: Iterable[str] | None = None,
    select: Iterable[str] | None = None,
    config: Mapping[str, Any] | None = None,
    runner: Validator | None = None,
) -> ValidatorSpec:
    """Return an NWBInspector best-practice validator.

    PyNWB validation is deliberately skipped inside NWBInspector because the
    default audit already records PyNWB as a separate, independently versioned
    validator.
    """

    ignored = list(ignore or [])
    selected = list(select or [])
    inspector_config = dict(config or {})

    def run(path: Path) -> Iterable[Any]:
        try:
            from nwbinspector import inspect_nwbfile
        except ImportError as exc:
            raise RuntimeError(
                "NWBInspector is required; install metricproof-nwb[inspector]."
            ) from exc

        return inspect_nwbfile(
            nwbfile_path=path,
            skip_validate=True,
            importance_threshold=importance_threshold,
            ignore=ignored or None,
            select=selected or None,
            config=inspector_config or None,
        )

    return ValidatorSpec(
        name="nwbinspector",
        version=_package_version("nwbinspector") if runner is None else "unknown",
        check_id="nwbinspector-best-practices",
        check_type="nwb_best_practice",
        runner=runner or run,
        configuration={
            "api": "nwbinspector.inspect_nwbfile",
            "skip_validate": True,
            "importance_threshold": importance_threshold,
            "ignore": ignored,
            "select": selected,
            "config": inspector_config,
        },
        failure_severity="info",
        pass_message="NWBInspector reported no best-practice findings.",
        failure_label="NWBInspector",
        why_it_matters=(
            "NWBInspector findings highlight correctness and reuse risks that "
            "schema validation alone may not detect."
        ),
        suggested_fix="Review the NWBInspector findings and rerun the audit.",
        normaliser=normalise_nwbinspector_findings,
        severity_resolver=_nwbinspector_severity,
        status_resolver=_nwbinspector_status,
    )


__all__ = [
    "Validator",
    "ValidatorSpec",
    "json_value",
    "normalise_findings",
    "normalise_nwbinspector_findings",
    "nwbinspector_validator",
    "pynwb_validator",
]

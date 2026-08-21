"""Text and JSON renderers for NWB proof reports."""

from __future__ import annotations

import json

from .models import NWBProofReport


def render_text(report: NWBProofReport) -> str:
    lines = [
        "MetricProof-NWB",
        f"Result: {report.status.upper()}",
        f"File: {report.path}",
        f"SHA-256: {report.sha256}",
        f"Size: {report.size_bytes} bytes",
    ]
    if report.session_status:
        lines.append(f"Session handoff: {report.session_status}")
        lines.extend(f"Review gate: {reason}" for reason in report.review_reasons)
    if report.metadata:
        lines.append("Metadata:")
        lines.extend(f"  {key}: {value}" for key, value in report.metadata.items())
    if report.validators:
        lines.append("Validators:")
        for validator in report.validators:
            lines.append(f"  {validator['name']} {validator['version']}")
    if report.validation_errors:
        lines.append("Validation errors:")
        lines.extend(f"  - {error}" for error in report.validation_errors)
    if report.inspector_findings:
        lines.append("NWBInspector findings:")
        for finding in report.inspector_findings:
            importance = finding.get("importance", "UNSPECIFIED")
            lines.append(f"  - [{importance}] {finding['message']}")
    if report.error:
        lines.append(f"Error: {report.error}")
    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def render_json(report: NWBProofReport) -> str:
    """Render an evidence report with stable key ordering for reproducibility."""

    return (
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n"
    )

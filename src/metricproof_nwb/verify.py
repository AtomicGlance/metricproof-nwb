"""Verification helpers for MetricProof-NWB evidence JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .manifest import (
    ArtifactRecord,
    SessionManifest,
    VerificationReport,
    verify_manifest,
)


def manifest_from_evidence(payload: Mapping[str, Any]) -> SessionManifest:
    context = payload.get("context", {})
    workflow = context.get("metricproof_nwb", {}) if isinstance(context, Mapping) else {}
    candidate = workflow.get("manifest") if isinstance(workflow, Mapping) else None
    if isinstance(candidate, Mapping):
        return SessionManifest.from_dict(candidate)
    artifacts = tuple(
        ArtifactRecord.from_dict(item)
        for item in payload.get("artifacts", [])
        if isinstance(item, Mapping)
    )
    return SessionManifest(session={}, artifacts=artifacts)


def verify_evidence(
    payload: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
) -> VerificationReport:
    """Verify every local artifact referenced by a report or embedded manifest."""

    return verify_manifest(manifest_from_evidence(payload), base_dir=base_dir)


def verify_file(path: str | Path, *, base_dir: str | Path | None = None) -> VerificationReport:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Evidence JSON must contain an object")
    return verify_evidence(payload, base_dir=base_dir or source.parent)


__all__ = ["manifest_from_evidence", "verify_evidence", "verify_file"]

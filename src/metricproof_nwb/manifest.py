"""Portable session manifests and artifact lineage for NWB workflows.

The manifest is intentionally small and configuration-driven.  It records what
was present at a handoff, how artifacts relate to one another, and the digest
needed to verify that a later copy is the same file.  It does not assume a
particular lab's directory layout or acquisition system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

from metricproof import hash_file

from .validators import json_value

MANIFEST_SCHEMA_VERSION = "0.3"


def _media_type(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    return {
        ".csv": "text/csv",
        ".json": "application/json",
        ".jsonl": "application/jsonl",
        ".nwb": "application/x-hdf5",
        ".h5": "application/x-hdf5",
        ".hdf5": "application/x-hdf5",
        ".parquet": "application/vnd.apache.parquet",
        ".tsv": "text/tab-separated-values",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix)


def _portable_uri(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass(frozen=True)
class ArtifactRecord:
    """One file or externally referenced artifact in a session ledger."""

    name: str
    uri: str
    sha256: str
    size_bytes: int
    stage: str = "unknown"
    role: str = "artifact"
    parents: tuple[str, ...] = ()
    media_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "uri": self.uri,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "stage": self.stage,
            "role": self.role,
            "parents": sorted(set(self.parents)),
            "media_type": self.media_type,
            "metadata": json_value(dict(self.metadata)),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ArtifactRecord":
        return cls(
            name=str(payload.get("name") or Path(str(payload.get("uri", "artifact"))).name),
            uri=str(payload.get("uri", "")),
            sha256=str(payload.get("sha256", "")),
            size_bytes=int(payload.get("size_bytes", 0)),
            stage=str(payload.get("stage", "unknown")),
            role=str(payload.get("role", "artifact")),
            parents=tuple(str(item) for item in payload.get("parents", [])),
            media_type=payload.get("media_type"),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class SessionManifest:
    """A deterministic, JSON-serialisable inventory for one research session."""

    session: Mapping[str, Any]
    artifacts: tuple[ArtifactRecord, ...]
    config: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        artifacts = sorted(
            (artifact.to_dict() for artifact in self.artifacts),
            key=lambda item: (item["uri"], item["name"]),
        )
        return {
            "schema_version": self.schema_version,
            "session": json_value(dict(self.session)),
            "artifacts": artifacts,
            "config": json_value(dict(self.config)),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SessionManifest":
        artifacts = tuple(
            ArtifactRecord.from_dict(item)
            for item in payload.get("artifacts", [])
            if isinstance(item, Mapping)
        )
        manifest = cls(
            session=dict(payload.get("session", {})),
            artifacts=artifacts,
            config=dict(payload.get("config", {})),
            schema_version=str(payload.get("schema_version", MANIFEST_SCHEMA_VERSION)),
        )
        validate_lineage(manifest)
        return manifest

    def write_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def validate_lineage(manifest: SessionManifest) -> None:
    """Reject unknown parents and cycles before a manifest is handed off."""

    names = {artifact.name for artifact in manifest.artifacts}
    uris = {artifact.uri for artifact in manifest.artifacts}
    known = names | uris
    for artifact in manifest.artifacts:
        unknown = sorted(set(artifact.parents) - known)
        if unknown:
            raise ValueError(
                f"Artifact {artifact.name!r} references unknown parent(s): {', '.join(unknown)}"
            )

    by_key = {
        key: artifact
        for artifact in manifest.artifacts
        for key in (artifact.name, artifact.uri)
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise ValueError(f"Artifact lineage contains a cycle at {name!r}")
        if name in visited or name not in by_key:
            return
        visiting.add(name)
        for parent in by_key[name].parents:
            visit(parent)
        visiting.remove(name)
        visited.add(name)

    for artifact in manifest.artifacts:
        visit(artifact.name)


def _artifact_from_spec(spec: Mapping[str, Any], root: Path) -> ArtifactRecord:
    raw_path = Path(str(spec.get("path", spec.get("uri", "")))).expanduser()
    path = raw_path if raw_path.is_absolute() else root / raw_path
    uri = str(spec.get("uri") or _portable_uri(path, root))
    if path.is_file():
        digest = hash_file(path)
        size = path.stat().st_size
    else:
        # Remote objects can be declared up front and verified later when they
        # are available.  Local missing files remain explicit and incomplete.
        digest = str(spec.get("sha256", ""))
        size = int(spec.get("size_bytes", 0))
    return ArtifactRecord(
        name=str(spec.get("name") or Path(uri).name or "artifact"),
        uri=uri,
        sha256=digest,
        size_bytes=size,
        stage=str(spec.get("stage", "unknown")),
        role=str(spec.get("role", "artifact")),
        parents=tuple(str(item) for item in spec.get("parents", [])),
        media_type=spec.get("media_type") or _media_type(uri),
        metadata=dict(spec.get("metadata", {})),
    )


def build_manifest(
    root: str | Path,
    *,
    session: Mapping[str, Any] | None = None,
    artifact_specs: list[Mapping[str, Any]] | None = None,
    config: Mapping[str, Any] | None = None,
) -> SessionManifest:
    """Inventory a directory or file, preserving optional stage/lineage metadata."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Manifest root not found: {root_path}")
    inventory_root = root_path if root_path.is_dir() else root_path.parent
    if artifact_specs is None:
        paths = [root_path] if root_path.is_file() else [
            path
            for path in sorted(root_path.rglob("*"))
            if path.is_file() and ".git" not in path.parts
        ]
        artifact_specs = [
            {"path": str(path), "uri": _portable_uri(path, inventory_root)}
            for path in paths
        ]
    artifacts = tuple(_artifact_from_spec(spec, inventory_root) for spec in artifact_specs)
    manifest = SessionManifest(
        session=dict(session or {}),
        artifacts=artifacts,
        config=dict(config or {}),
    )
    validate_lineage(manifest)
    return manifest


def load_manifest(path: str | Path) -> SessionManifest:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Manifest JSON must contain an object")
    return SessionManifest.from_dict(payload)


def _local_path(uri: str, base_dir: Path) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme and parsed.scheme != "file":
        return None
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    candidate = Path(uri)
    return candidate if candidate.is_absolute() else base_dir / candidate


@dataclass(frozen=True)
class ArtifactVerification:
    name: str
    uri: str
    status: str
    message: str
    expected_sha256: str = ""
    observed_sha256: str = ""
    expected_size_bytes: int | None = None
    observed_size_bytes: int | None = None

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "uri": self.uri,
            "status": self.status,
            "message": self.message,
            "expected_sha256": self.expected_sha256,
            "observed_sha256": self.observed_sha256,
            "expected_size_bytes": self.expected_size_bytes,
            "observed_size_bytes": self.observed_size_bytes,
        }


@dataclass(frozen=True)
class VerificationReport:
    checks: tuple[ArtifactVerification, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    @property
    def status(self) -> str:
        if not self.checks:
            return "incomplete"
        if any(check.status == "fail" for check in self.checks):
            return "fail"
        if any(check.status == "incomplete" for check in self.checks):
            return "incomplete"
        if any(check.status == "needs_review" for check in self.checks):
            return "needs_review"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
        }


def verify_manifest(
    manifest: SessionManifest,
    *,
    base_dir: str | Path = ".",
) -> VerificationReport:
    """Rehash manifest inputs and report changed, missing, or remote artifacts."""

    base = Path(base_dir).expanduser().resolve()
    checks: list[ArtifactVerification] = []
    for artifact in manifest.artifacts:
        path = _local_path(artifact.uri, base)
        if path is None:
            checks.append(
                ArtifactVerification(
                    name=artifact.name,
                    uri=artifact.uri,
                    status="needs_review",
                    message="Remote artifact was recorded but not available locally.",
                    expected_sha256=artifact.sha256,
                    expected_size_bytes=artifact.size_bytes,
                )
            )
            continue
        if not path.is_file():
            checks.append(
                ArtifactVerification(
                    name=artifact.name,
                    uri=artifact.uri,
                    status="incomplete",
                    message=f"Artifact is missing: {path}",
                    expected_sha256=artifact.sha256,
                    expected_size_bytes=artifact.size_bytes,
                )
            )
            continue
        observed_digest = hash_file(path)
        observed_size = path.stat().st_size
        if not artifact.sha256:
            status = "needs_review"
            message = "Artifact exists but has no recorded SHA-256 digest."
        elif observed_digest != artifact.sha256:
            status = "fail"
            message = "Artifact SHA-256 does not match the manifest."
        elif artifact.size_bytes and observed_size != artifact.size_bytes:
            status = "fail"
            message = "Artifact size does not match the manifest."
        else:
            status = "pass"
            message = "Artifact digest and size match the manifest."
        checks.append(
            ArtifactVerification(
                name=artifact.name,
                uri=artifact.uri,
                status=status,
                message=message,
                expected_sha256=artifact.sha256,
                observed_sha256=observed_digest,
                expected_size_bytes=artifact.size_bytes,
                observed_size_bytes=observed_size,
            )
        )
    return VerificationReport(tuple(checks))


__all__ = [
    "ArtifactRecord",
    "ArtifactVerification",
    "MANIFEST_SCHEMA_VERSION",
    "SessionManifest",
    "VerificationReport",
    "build_manifest",
    "load_manifest",
    "validate_lineage",
    "verify_manifest",
]

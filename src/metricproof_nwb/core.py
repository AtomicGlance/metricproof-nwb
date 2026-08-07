"""NWB validation and provenance helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from .models import NWBProofReport

Validator = Callable[[Path], Iterable[Any]]
MetadataReader = Callable[[Path], Mapping[str, Any]]


def hash_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _normalise_errors(errors: Iterable[Any] | Any) -> list[str]:
    if errors is None:
        return []
    if isinstance(errors, (str, bytes)):
        return [str(errors)]
    try:
        return [str(error) for error in errors]
    except TypeError:
        return [str(errors)]


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

    try:
        errors = _normalise_errors((validator or _default_validator)(file_path))
    except Exception as exc:
        return NWBProofReport(
            path=str(file_path),
            status="error",
            sha256=digest,
            size_bytes=file_path.stat().st_size,
            metadata=metadata,
            warnings=warnings,
            error=str(exc),
        )

    return NWBProofReport(
        path=str(file_path),
        status="fail" if errors else "pass",
        sha256=digest,
        size_bytes=file_path.stat().st_size,
        metadata=metadata,
        validation_errors=errors,
        warnings=warnings,
    )

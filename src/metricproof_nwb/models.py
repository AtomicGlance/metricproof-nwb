"""Result models for NWB evidence reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class NWBProofReport:
    """A stable, machine-readable record of one NWB audit."""

    path: str
    status: str
    sha256: str
    size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def passed(self) -> bool:
        """Whether the file passed validation without an execution error."""

        return self.status == "pass"

    @property
    def exit_code(self) -> int:
        """Return a CI-friendly exit code: 0 pass, 1 invalid, 2 unable to run."""

        return 0 if self.status == "pass" else 2 if self.status == "error" else 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

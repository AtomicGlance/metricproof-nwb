"""Result models for NWB evidence reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metricproof import EvidenceReport


@dataclass(frozen=True)
class NWBProofReport:
    """NWB convenience API backed by MetricProof's stable evidence model."""

    report: EvidenceReport

    @property
    def artifact(self):
        return self.report.artifacts[0]

    @property
    def path(self) -> str:
        return self.artifact.uri

    @property
    def sha256(self) -> str:
        return self.artifact.sha256

    @property
    def size_bytes(self) -> int:
        return self.artifact.size_bytes

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self.report.context.get("nwb_metadata", {}))

    @property
    def warnings(self) -> list[str]:
        return list(self.report.context.get("warnings", []))

    @property
    def validation_errors(self) -> list[str]:
        findings: list[str] = []
        for result in self.report.results:
            if result.check_type != "nwb_validation" or result.status != "fail":
                continue
            findings.extend(str(item.get("message", item)) for item in result.evidence)
        return findings

    @property
    def error(self) -> str | None:
        result = next(
            (item for item in self.report.results if item.status == "error"), None
        )
        return result.message if result else None

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        return "pass" if self.report.passed else "fail"

    @property
    def passed(self) -> bool:
        """Whether the file passed validation without an execution error."""

        return self.report.passed

    @property
    def exit_code(self) -> int:
        """Return a CI-friendly exit code: 0 pass, 1 invalid, 2 unable to run."""

        return 2 if self.status == "error" else self.report.exit_code

    def to_dict(self) -> dict[str, Any]:
        return self.report.to_dict()

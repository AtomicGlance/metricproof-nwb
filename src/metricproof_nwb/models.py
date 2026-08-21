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
    def validators(self) -> list[dict[str, Any]]:
        """Software identities and configurations used to create the report."""

        return [dict(item) for item in self.report.context.get("validators", [])]

    @property
    def validation_errors(self) -> list[str]:
        findings: list[str] = []
        for result in self.report.results:
            if result.check_type != "nwb_validation" or result.status != "fail":
                continue
            findings.extend(str(item.get("message", item)) for item in result.evidence)
        return findings

    @property
    def inspector_findings(self) -> list[dict[str, Any]]:
        """Structured findings emitted by NWBInspector, if it was requested."""

        findings: list[dict[str, Any]] = []
        for result in self.report.results:
            if result.check_type != "nwb_best_practice":
                continue
            findings.extend(dict(item) for item in result.evidence)
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
        workflow_status = self.report.context.get("metricproof_nwb", {}).get(
            "session_status"
        )
        if self.report.passed and workflow_status in {"incomplete", "needs_review"}:
            return str(workflow_status)
        return "pass" if self.report.passed else "fail"

    @property
    def passed(self) -> bool:
        """Whether the file passed validation without an execution error."""

        return self.report.passed

    @property
    def exit_code(self) -> int:
        """Return 0 pass, 1 invalid, 2 execution error, or 3 review incomplete."""

        if self.status == "error":
            return 2
        if self.status in {"incomplete", "needs_review"}:
            return 3
        return self.report.exit_code

    @property
    def session_status(self) -> str | None:
        """Return the session handoff state when a manifest was audited."""

        value = self.report.context.get("metricproof_nwb", {}).get("session_status")
        return str(value) if value is not None else None

    @property
    def review_reasons(self) -> list[str]:
        value = self.report.context.get("metricproof_nwb", {}).get("review_reasons", [])
        return [str(item) for item in value]

    def to_dict(self) -> dict[str, Any]:
        return self.report.to_dict()

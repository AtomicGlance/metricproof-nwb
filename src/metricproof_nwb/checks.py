"""Configuration-driven session checks inspired by the HexMaze workflow.

These checks deliberately operate on declared session metadata and artifact
records.  They do not guess a lab's camera count, sample rate, graph topology,
or curation policy; those values belong in the manifest/configuration supplied
by the project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from metricproof import CheckResult

from .manifest import SessionManifest


@dataclass(frozen=True)
class SessionCheckSummary:
    """Checks plus a workflow-level status for a human handoff."""

    results: tuple[CheckResult, ...]
    status: str
    review_reasons: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return all(result.passed or result.severity in {"warning", "info"} for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "review_reasons": list(self.review_reasons),
            "results": [result.to_dict() for result in self.results],
        }


def _result(
    check_id: str,
    status: str,
    severity: str,
    message: str,
    *,
    observed: Any = None,
    expected: Any = None,
    evidence: list[dict[str, Any]] | None = None,
    why: str,
    fix: str,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type="session_integrity",
        status=status,
        severity=severity,
        message=message,
        observed=observed,
        expected=expected,
        evidence=evidence or [],
        why_it_matters=why,
        suggested_fix=fix,
    )


def _flatten_strings(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(value, Mapping):
        items: list[tuple[str, str]] = []
        for key, child in value.items():
            items.extend(_flatten_strings(child, f"{prefix}.{key}" if prefix else str(key)))
        return items
    if isinstance(value, (list, tuple)):
        items = []
        for index, child in enumerate(value):
            items.extend(_flatten_strings(child, f"{prefix}[{index}]"))
        return items
    return [(prefix, str(value))]


def _timebase_findings(timebases: Any, tolerance: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    if isinstance(timebases, Mapping):
        entries = [{"name": name, **(value if isinstance(value, Mapping) else {"rate": value})} for name, value in timebases.items()]
    elif isinstance(timebases, list):
        entries = [item for item in timebases if isinstance(item, Mapping)]
    else:
        entries = []
    for entry in entries:
        name = str(entry.get("name", "timebase"))
        rate = entry.get("rate", entry.get("sample_rate"))
        count = entry.get("sample_count", entry.get("count"))
        start = entry.get("start_time", entry.get("start"))
        stop = entry.get("stop_time", entry.get("stop", entry.get("end_time")))
        item = {"name": name, "rate": rate, "sample_count": count, "start": start, "stop": stop}
        observations.append(item)
        try:
            if float(rate) <= 0:
                failures.append({**item, "reason": "rate must be greater than zero"})
                continue
            if count is not None and int(count) < 0:
                failures.append({**item, "reason": "sample_count cannot be negative"})
                continue
            if start is not None and stop is not None and count is not None:
                duration = float(stop) - float(start)
                expected_duration = float(count) / float(rate)
                if abs(duration - expected_duration) > tolerance:
                    failures.append({**item, "duration": duration, "expected_duration": expected_duration, "reason": "duration does not match sample count/rate"})
        except (TypeError, ValueError):
            failures.append({**item, "reason": "rate, count, start, and stop must be numeric"})
    return failures, observations


def _graph_findings(trials: Any, node_ids: set[str], edges: set[tuple[str, str]], directed: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    if not isinstance(trials, list):
        return failures, observations
    for trial in trials:
        if not isinstance(trial, Mapping):
            failures.append({"trial": str(trial), "reason": "trial must be an object"})
            continue
        trial_id = trial.get("trial_id", trial.get("id", "trial"))
        path = trial.get("node_path", trial.get("graph_path", trial.get("path")))
        if not isinstance(path, list) or not path:
            continue
        path_values = [str(node) for node in path]
        item = {"trial_id": trial_id, "path": path_values}
        observations.append(item)
        unknown = [node for node in path_values if node_ids and node not in node_ids]
        bad_edges: list[tuple[str, str]] = []
        for left, right in zip(path_values, path_values[1:]):
            edge = (left, right)
            reverse = (right, left)
            if edges and edge not in edges and (not directed and reverse not in edges):
                bad_edges.append(edge)
        if unknown or bad_edges:
            failures.append({**item, "unknown_nodes": unknown, "invalid_edges": bad_edges})
    return failures, observations


def run_session_checks(
    manifest: SessionManifest,
    *,
    config: Mapping[str, Any] | None = None,
) -> SessionCheckSummary:
    """Run portable session checks and classify the handoff state.

    Configuration keys are optional: ``required_artifacts``, ``placeholder_values``,
    ``timebase_tolerance``, ``node_ids``, ``graph_edges``, ``graph_directed``,
    and ``expected_counts``.  Session-specific values can also live under the
    manifest's ``config`` mapping.
    """

    effective = dict(manifest.config)
    effective.update(dict(config or {}))
    session = dict(manifest.session)
    results: list[CheckResult] = []
    review_reasons: list[str] = []

    if manifest.artifacts:
        results.append(_result(
            "session-artifact-inventory", "pass", "critical",
            f"Manifest records {len(manifest.artifacts)} artifact(s).",
            observed={"artifacts": len(manifest.artifacts)}, expected={"artifacts": ">=1"},
            why="A session cannot be reproduced if its handoff inventory is empty.",
            fix="Record the raw, derived, and handoff artifacts before analysis.",
        ))
    else:
        results.append(_result(
            "session-artifact-inventory", "fail", "critical",
            "Manifest contains no artifacts.", observed={"artifacts": 0}, expected={"artifacts": ">=1"},
            why="There is no input identity to verify or hand back to another researcher.",
            fix="Build the manifest from the session directory or declare its artifacts explicitly.",
        ))

    required = effective.get("required_artifacts", [])
    if required:
        names = {artifact.name for artifact in manifest.artifacts} | {artifact.uri for artifact in manifest.artifacts}
        missing = [str(item) for item in required if str(item) not in names]
        results.append(_result(
            "session-required-artifacts", "fail" if missing else "pass", "critical" if missing else "warning",
            f"{len(missing)} required artifact(s) are missing." if missing else "All required artifacts are present.",
            observed={"missing": missing}, expected={"required": list(required)}, evidence=[{"artifact": item} for item in missing],
            why="A successful command is not evidence that every upstream input was present.",
            fix="Restore the missing artifact or update the manifest after documenting the exclusion.",
        ))
        if missing:
            review_reasons.append("required artifacts are missing")

    lineage_ok = True
    known = {artifact.name for artifact in manifest.artifacts} | {artifact.uri for artifact in manifest.artifacts}
    lineage_errors = []
    for artifact in manifest.artifacts:
        unknown = sorted(set(artifact.parents) - known)
        if unknown:
            lineage_ok = False
            lineage_errors.append({"artifact": artifact.name, "unknown_parents": unknown})
    results.append(_result(
        "session-lineage", "pass" if lineage_ok else "fail", "critical" if not lineage_ok else "warning",
        "Artifact parent references are resolvable." if lineage_ok else "Some artifact parents are not in the manifest.",
        observed={"errors": lineage_errors}, expected={"unknown_parents": 0}, evidence=lineage_errors,
        why="Lineage is what connects a report back to the raw recording and processing inputs.",
        fix="Add the parent artifact or correct the parent name before handoff.",
    ))

    placeholders = effective.get("placeholder_values", ["N/A", "unknown", "Person", "2019-01-01"])
    placeholder_hits = [
        {"field": field, "value": value}
        for field, value in _flatten_strings(session)
        if value.strip() in {str(item) for item in placeholders}
    ]
    results.append(_result(
        "session-metadata-placeholders", "fail" if placeholder_hits else "pass", "warning",
        f"Found {len(placeholder_hits)} placeholder metadata value(s)." if placeholder_hits else "No configured placeholder metadata values found.",
        observed={"matches": placeholder_hits}, expected={"matches": 0}, evidence=placeholder_hits,
        why="Placeholder identity and timing fields can make an otherwise valid NWB file scientifically ambiguous.",
        fix="Replace placeholders with the recorded experimental metadata or document why a field is unavailable.",
    ))
    if placeholder_hits:
        review_reasons.append("metadata contains placeholders")

    timebases = session.get("timebases", effective.get("timebases"))
    if timebases is not None:
        tolerance = float(effective.get("timebase_tolerance", 1e-6))
        timebase_failures, observations = _timebase_findings(timebases, tolerance)
        results.append(_result(
            "session-timebases", "fail" if timebase_failures else "pass", "critical" if timebase_failures else "warning",
            f"Found {len(timebase_failures)} time-base inconsistency(ies)." if timebase_failures else "Declared time bases are internally consistent.",
            observed={"timebases": observations, "failures": timebase_failures}, expected={"failures": 0}, evidence=timebase_failures,
            why="Sample-rate and duration drift can silently misalign behavior, video, and neural data.",
            fix="Recompute the relationship from the source clocks and record the effective rate and residual.",
        ))
        if timebase_failures:
            review_reasons.append("time-base checks need review")

    recording_durations = session.get("recording_durations", effective.get("recording_durations"))
    expected_durations = effective.get("expected_recording_durations", {})
    if recording_durations is not None or expected_durations:
        actual = dict(recording_durations or {})
        expected_duration_map = dict(expected_durations or {})
        duration_failures = []
        for name, expected_duration in expected_duration_map.items():
            observed_duration = actual.get(name)
            try:
                if observed_duration is None or abs(float(observed_duration) - float(expected_duration)) > float(effective.get("duration_tolerance", 1e-6)):
                    duration_failures.append({"name": str(name), "expected": expected_duration, "observed": observed_duration})
            except (TypeError, ValueError):
                duration_failures.append({"name": str(name), "expected": expected_duration, "observed": observed_duration})
        results.append(_result(
            "session-recording-durations", "fail" if duration_failures else "pass", "critical" if duration_failures else "warning",
            f"Found {len(duration_failures)} recording duration mismatch(es)." if duration_failures else "Declared recording durations match the configured expectations.",
            observed={"durations": actual}, expected={"durations": expected_duration_map}, evidence=duration_failures,
            why="A truncated or overlong recording can pass schema validation while invalidating alignment and trial coverage.",
            fix="Compare source export durations with the handoff and document intentional truncation or exclusion.",
        ))
        if duration_failures:
            review_reasons.append("recording durations need review")

    trials = session.get("trials")
    if trials is not None:
        required_fields = effective.get("trial_required_fields", ["trial_id", "start_time", "stop_time"])
        trial_failures = []
        for trial in trials if isinstance(trials, list) else []:
            if not isinstance(trial, Mapping):
                continue
            missing = [field for field in required_fields if field not in trial]
            bad_interval = False
            if "start_time" in trial and "stop_time" in trial:
                try:
                    bad_interval = float(trial["stop_time"]) <= float(trial["start_time"])
                except (TypeError, ValueError):
                    bad_interval = True
            if missing or bad_interval:
                trial_failures.append({"trial_id": trial.get("trial_id", trial.get("id")), "missing": missing, "bad_interval": bad_interval})
        node_ids = {str(item) for item in effective.get("node_ids", session.get("node_ids", []))}
        raw_edges = effective.get("graph_edges", session.get("graph_edges", []))
        edges = {tuple(str(part) for part in edge) for edge in raw_edges if isinstance(edge, (list, tuple)) and len(edge) == 2}
        graph_failures, graph_observations = _graph_findings(trials, node_ids, edges, bool(effective.get("graph_directed", False)))
        trial_failures.extend(graph_failures)
        results.append(_result(
            "session-trial-metadata", "fail" if trial_failures else "pass", "critical" if trial_failures else "warning",
            f"Found {len(trial_failures)} invalid trial record(s)." if trial_failures else "Trial intervals and declared graph paths are valid.",
            observed={"trials": len(trials) if isinstance(trials, list) else 0, "failures": trial_failures}, expected={"failures": 0}, evidence=trial_failures + graph_observations,
            why="Trial identity and graph paths are the join keys for behavior, video, and neural analyses.",
            fix="Repair trial metadata, node IDs, or adjacency before using the session for a cross-modal result.",
        ))
        if trial_failures:
            review_reasons.append("trial metadata or graph paths need review")

    expected_counts = effective.get("expected_counts", session.get("expected_counts", effective.get("expected_nwb_counts")))
    observed_counts = dict(session.get("counts", {}))
    if isinstance(session.get("nwb_counts"), Mapping):
        observed_counts.update({str(key): value for key, value in session["nwb_counts"].items()})
    if expected_counts:
        count_failures = [
            {"name": str(name), "expected": value, "observed": observed_counts.get(name)}
            for name, value in dict(expected_counts).items()
            if observed_counts.get(name) != value
        ]
        results.append(_result(
            "session-counts", "fail" if count_failures else "pass", "warning",
            f"Found {len(count_failures)} count mismatch(es)." if count_failures else "Declared counts match the expected counts.",
            observed={"counts": observed_counts}, expected={"counts": expected_counts}, evidence=count_failures,
            why="Unexpected file, unit, trial, or recording counts often indicate an incomplete handoff.",
            fix="Reconcile counts with the source export and document intentional exclusions.",
        ))
        if count_failures:
            review_reasons.append("declared counts do not match expectations")

    curation = session.get("curation")
    if isinstance(curation, Mapping):
        gates = []
        if curation.get("human_reviewed") is not True:
            gates.append("human curation review is not recorded")
        if curation.get("recompute_required") and curation.get("recomputed") is not True:
            gates.append("curated metrics were not recomputed")
        results.append(_result(
            "session-curation-gate", "fail" if gates else "pass", "warning",
            "; ".join(gates) if gates else "Curation review and recomputation gates are recorded.",
            observed=dict(curation), expected={"human_reviewed": True}, evidence=[{"gate": gate} for gate in gates],
            why="Automated extraction can propose units or paths, but a person must certify the final scientific handoff.",
            fix="Record the reviewer and recompute derived metrics after curation changes.",
        ))
        if gates:
            review_reasons.extend(gates)

    if any(result.status == "error" or (result.status == "fail" and result.severity == "critical") for result in results):
        status = "incomplete"
    elif review_reasons:
        status = "needs_review"
    else:
        status = "complete"
    return SessionCheckSummary(tuple(results), status, tuple(dict.fromkeys(review_reasons)))


__all__ = ["SessionCheckSummary", "run_session_checks"]

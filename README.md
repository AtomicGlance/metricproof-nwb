# MetricProof-NWB

[![Tests](https://github.com/AtomicGlance/metricproof-nwb/actions/workflows/tests.yml/badge.svg)](https://github.com/AtomicGlance/metricproof-nwb/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/metricproof-nwb.svg)](https://pypi.org/project/metricproof-nwb/)

Reproducible evidence reports for [NWB](https://www.nwb.org/) files.

MetricProof-NWB complements schema and best-practice validators by preserving
the evidence around an audit: the input path, SHA-256 digest, selected NWB
metadata, validation findings, warnings, and timestamp. That makes a result
easier to attach to a paper, archive submission, or CI run.

Version 0.3 can run PyNWB and NWBInspector as separate, independently versioned
validators. Reports preserve NWBInspector's check name, importance, object,
location, and message while recording each validator's version and effective
configuration. They use MetricProof's shared evidence envelope: producer
identity, artifact fingerprints, structured results, execution context, and
explicit schema versioning.

It also provides a session evidence ledger. A ledger inventories the files that
travel together, records parent/child lineage, and makes review gates explicit.
The checks are configuration-driven: sample rates, graph nodes, expected
counts, required files, and curation policy come from the session manifest,
not from hard-coded HexMaze or laboratory constants.

## Install

The base package depends only on MetricProof. Install the PyNWB extra for schema
validation, the Inspector extra for PyNWB plus NWBInspector, or all optional
validators:

```bash
python -m pip install "metricproof-nwb[nwb]"
python -m pip install "metricproof-nwb[inspector]"
python -m pip install "metricproof-nwb[all]"
```

## Usage

```bash
metricproof-nwb audit session.nwb
metricproof-nwb audit session.nwb --format json --output evidence.json
metricproof-nwb audit session.nwb \
  --nwbinspector \
  --artifact-uri archive://study/session.nwb \
  --format json \
  --output evidence.json
```

Create and use a session manifest:

```bash
metricproof-nwb manifest path/to/session --output session-manifest.json
metricproof-nwb audit path/to/session/session.nwb \
  --manifest session-manifest.json --format json --output proof.json
metricproof-nwb bundle proof.json --output proof.html
metricproof-nwb verify proof.json
```

`verify` rehashes every local artifact and distinguishes a changed file
(`fail`), a missing handoff (`incomplete`), and a remote or undigested object
that still needs a human check (`needs_review`). The HTML bundle is offline and
includes the artifact graph, exact hashes, validator findings, and review
reasons so it can be attached to a paper, archive submission, or CI artifact.

For session-specific checks, pass a JSON object to `--session-json` when
creating the manifest. For example:

```json
{
  "session": {
    "session_id": "hexmaze-2026-08-21-01",
    "timebases": [{"name": "lfp", "rate": 1500, "sample_count": 3000, "start": 0, "stop": 2}],
    "curation": {"human_reviewed": true, "recompute_required": true, "recomputed": true}
  },
  "config": {
    "required_artifacts": ["session.nwb"],
    "node_ids": ["start", "goal"],
    "graph_edges": [["start", "goal"]]
  }
}
```

The checks cover artifact inventory and lineage, placeholder metadata, timebase
consistency, recording durations, trial intervals and graph paths, declared
NWB/file/unit counts, and curation gates. A report can therefore be technically valid while still being marked
`needs_review` or `incomplete` when a human handoff is not evidenced.

The JSON document conforms to MetricProof's bundled evidence schema:

```bash
metricproof schema evidence
```

Its top-level `report_type` is `nwb-audit`; the audited file appears in
`artifacts`, each validator has a separate entry in `results`, selected NWB
metadata is stored in `context.nwb_metadata`, and software provenance is stored
in `context.validators`. JSON keys are sorted before writing, so equivalent
audits produce stable evidence files that are easier to diff and archive.

NWBInspector is called with `skip_validate=True` because MetricProof-NWB already
runs PyNWB separately. This avoids duplicate schema findings while retaining a
clear version and configuration for each validator. Best-practice suggestions
and violations are preserved but do not fail the audit; critical findings and
validator execution errors do.

The command exits with `0` for a valid file, `1` when PyNWB reports validation
findings, and `2` when the audit cannot run (for example, when PyNWB is not
installed or the file cannot be opened).

The Python API accepts injectable validator and metadata functions so projects
can add study-specific checks without coupling their tests to one PyNWB
release:

```python
from metricproof_nwb import (
    audit_nwb,
    nwbinspector_validator,
    pynwb_validator,
)

report = audit_nwb(
    "session.nwb",
    validators=[pynwb_validator(), nwbinspector_validator()],
)
print(report.sha256)
print(report.validators)
print(report.inspector_findings)
print(report.to_dict())
```

The compatibility properties (`status`, `sha256`, `size_bytes`,
`validation_errors`, and `exit_code`) remain available, while `report.report`
provides direct access to the underlying `metricproof.EvidenceReport`.

The Python API exposes the same ledger primitives:

```python
from metricproof_nwb import build_manifest, run_session_checks, verify_manifest

manifest = build_manifest("path/to/session", session={"session_id": "s-01"})
summary = run_session_checks(manifest)
verification = verify_manifest(manifest, base_dir="path/to/session")
print(summary.status, verification.status)
```

## Reproducible example

[`examples/academic_workflow`](https://github.com/AtomicGlance/metricproof-nwb/tree/main/examples/academic_workflow) contains a bundled,
synthetic extracellular-electrophysiology NWB file and the evidence JSON created
from that exact artifact. The workflow verifies the report's SHA-256 digest and
shows why validator versions matter when findings change over time.

See [Validator responsibilities](https://github.com/AtomicGlance/metricproof-nwb/blob/main/docs/validator-comparison.md) for a precise
comparison of PyNWB validation, NWBInspector, `dandi validate`, and
MetricProof-NWB.

## Development

```bash
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest discover -s tests -v
```

On macOS or Linux, use `export PYTHONPATH="$PWD/src"` instead.

## Scope

MetricProof-NWB does not replace PyNWB validation, NWBInspector, or DANDI
validation. It records their result alongside file identity and metadata so a
research workflow can show exactly what was checked. It also does not infer
scientific correctness from a complete manifest: a clean handoff is evidence of
traceability, not a substitute for experimental judgment or domain review.

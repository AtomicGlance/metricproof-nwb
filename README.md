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
research workflow can show exactly what was checked.

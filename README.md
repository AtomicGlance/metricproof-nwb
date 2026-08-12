# MetricProof-NWB

[![Tests](https://github.com/AtomicGlance/metricproof-nwb/actions/workflows/tests.yml/badge.svg)](https://github.com/AtomicGlance/metricproof-nwb/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/metricproof-nwb.svg)](https://pypi.org/project/metricproof-nwb/)

Reproducible evidence reports for [NWB](https://www.nwb.org/) files.

MetricProof-NWB complements schema and best-practice validators by preserving
the evidence around an audit: the input path, SHA-256 digest, selected NWB
metadata, validation findings, warnings, and timestamp. That makes a result
easier to attach to a paper, archive submission, or CI run.

Version 0.2 is built on MetricProof's shared evidence model. NWB reports now
use the same versioned envelope as analytical audits: producer identity,
artifact fingerprints, structured results, execution context, and explicit
schema versioning. Downstream tools can therefore ingest both report types
without maintaining separate parsers.

## Install

The base package depends only on MetricProof. Install the optional PyNWB extra
to validate real NWB files:

```bash
python -m pip install "metricproof-nwb[nwb]"
```

## Usage

```bash
metricproof-nwb audit session.nwb
metricproof-nwb audit session.nwb --format json --output evidence.json
```

The JSON document conforms to MetricProof's bundled evidence schema:

```bash
metricproof schema evidence
```

Its top-level `report_type` is `nwb-audit`; the audited file appears in
`artifacts`, PyNWB findings appear in `results`, and selected NWB metadata is
stored in `context.nwb_metadata`.

The command exits with `0` for a valid file, `1` when PyNWB reports validation
findings, and `2` when the audit cannot run (for example, when PyNWB is not
installed or the file cannot be opened).

The Python API accepts injectable validator and metadata functions so projects
can add study-specific checks without coupling their tests to one PyNWB
release:

```python
from metricproof_nwb import audit_nwb

report = audit_nwb("session.nwb")
print(report.sha256)
print(report.to_dict())
```

The compatibility properties (`status`, `sha256`, `size_bytes`,
`validation_errors`, and `exit_code`) remain available, while `report.report`
provides direct access to the underlying `metricproof.EvidenceReport`.

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

# MetricProof-NWB

[![Tests](https://github.com/AtomicGlance/metricproof-nwb/actions/workflows/tests.yml/badge.svg)](https://github.com/AtomicGlance/metricproof-nwb/actions/workflows/tests.yml)

Reproducible evidence reports for [NWB](https://www.nwb.org/) files.

MetricProof-NWB complements schema and best-practice validators by preserving
the evidence around an audit: the input path, SHA-256 digest, selected NWB
metadata, validation findings, warnings, and timestamp. That makes a result
easier to attach to a paper, archive submission, or CI run.

## Install

The core package has no runtime dependencies. Install the optional PyNWB extra
to validate real NWB files:

```bash
python -m pip install "metricproof-nwb[nwb]"
```

## Usage

```bash
metricproof-nwb audit session.nwb
metricproof-nwb audit session.nwb --format json --output evidence.json
```

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

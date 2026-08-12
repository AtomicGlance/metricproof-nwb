# Reproducible NWB evidence workflow

This directory contains a small but structurally realistic extracellular-
electrophysiology session. It is synthetic: no human or animal observations are
included. The file contains subject metadata, a device and electrode group,
four electrode rows, a two-second `ElectricalSeries`, and two trial intervals.

The committed artifacts are:

- `synthetic_ecephys_session.nwb`: the exact NWB file that was inspected.
- `example-evidence.json`: the MetricProof-NWB report generated for that file.
- `create_demo_nwb.py`: source code that documents how the NWB structure was built.
- `verify_evidence.py`: an independent check that the report's SHA-256 digest
  still identifies the committed NWB file and that validator provenance exists.

## Reproduce the audit

From the repository root:

```bash
python -m pip install -e ".[dev]"
metricproof-nwb audit examples/academic_workflow/synthetic_ecephys_session.nwb \
  --nwbinspector \
  --artifact-uri examples/academic_workflow/synthetic_ecephys_session.nwb \
  --format json \
  --output reproduced-evidence.json
python examples/academic_workflow/verify_evidence.py
```

PowerShell uses backticks instead of backslashes for line continuation, or the
audit command can be placed on one line.

The newly generated report will have a different `generated_at` timestamp. Its
artifact digest and validator configuration should agree with the committed
report when the bundled file and validator versions are unchanged. Findings can
change when PyNWB, NWBInspector, their checks, or the NWB schema changes; that is
why the report records validator versions and configuration rather than treating
validation as a timeless property of the file.

## Academic handoff

A minimal handoff can archive these together:

1. the NWB data artifact;
2. the JSON evidence report;
3. the analysis or acquisition code version; and
4. the environment lock file or container identifier.

A reviewer first verifies the digest, then reads each structured result in the
context of the recorded validator version. This does not prove scientific
correctness, but it makes the narrower claim "this exact artifact was checked by
these exact tools under this configuration" independently testable.

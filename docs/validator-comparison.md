# Validator responsibilities

MetricProof-NWB deliberately does not define another NWB standard. It records
the outputs of existing validators alongside the identity of the artifact and
the software/configuration that produced those outputs.

| Tool | Primary responsibility | Findings produced | Artifact fingerprint and durable evidence envelope |
| --- | --- | --- | --- |
| [PyNWB validation](https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/validate.html) | Validate an NWB file against the relevant NWB schema. | Schema validation errors with locations and reasons. | No; callers decide how results and file identity are persisted. |
| [NWBInspector](https://github.com/NeurodataWithoutBorders/nwbinspector) | Inspect NWB files for correctness and community best practices beyond schema validity. | Importance-ranked messages with check name, object, location, and file path. It can also invoke PyNWB validation. | No general-purpose evidence envelope; its report formats focus on inspection output. |
| [`dandi validate`](https://dandi.readthedocs.io/en/latest/cmdline/validate.html) | Decide whether files and datasets satisfy DANDI submission requirements, including layout, metadata, PyNWB, and NWBInspector-backed checks. | Versioned validation records with origin, severity, scope, paths, and validator information. | Designed for the DANDI submission workflow rather than a portable report for arbitrary research pipelines. |
| MetricProof-NWB | Preserve what was checked, against which exact file, using which validator versions/configuration; optionally run PyNWB, NWBInspector, and DANDI as separate adapters. | A MetricProof evidence result for each validator, retaining validator-native fields where possible, plus configurable session-integrity findings. | Yes: SHA-256, size, selected NWB metadata, producer identity, validator provenance, session artifact lineage, findings, review gates, and timestamp. |

## Why retain separate PyNWB and NWBInspector results?

NWBInspector normally has the option to run PyNWB validation itself. The
MetricProof-NWB adapter calls it with `skip_validate=True` because PyNWB already
runs as a separate validator. This avoids duplicate findings and lets the report
state exactly which PyNWB version performed schema validation.

## What the evidence does not prove

- A passing schema check does not establish that the measurements are
  scientifically correct.
- A SHA-256 digest identifies one file but does not automatically identify
  external resources, extension packages, containers, or the complete software
  environment.
- Validator results can change as checks and schemas evolve. The recorded
  versions make that change visible; they do not eliminate it.
- DANDI validation remains the authority for DANDI submission requirements.

Future support for dependency manifests can extend the artifact list to cached
namespaces and externally linked resources without changing the purpose of the
report.

# A neural-data handoff: unchanged bytes do not establish correct timing

This case study audits one **real, published mouse recording**, preserves the
findings, and tests a deliberately modified copy. It is a demonstration of
traceability, not a reanalysis of the associated paper or a claim that the
entire dataset has the same properties.

## Source and attribution

Economo, Michael N.; Svoboda, Karel (2022). *Mouse anterior lateral motor cortex
(ALM) in delay response task*, version `0.220126.1855`. DANDI archive.
[Dataset DOI](https://doi.org/10.48324/dandi.000006/0.220126.1855).
Data license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The dataset describes extracellular electrophysiology during a mouse delay
response task. Its metadata links to *Distinct descending motor cortex pathways
and their roles in movement* ([paper DOI](https://doi.org/10.1038/s41586-018-0642-9)).

We selected the smallest NWB asset for an inexpensive reproducible example:
`sub-anm372907/sub-anm372907_ses-20170613.nwb`, asset
`f1b6ed8f-1e14-44fa-b4ee-240d0efe3759`, **258,992 bytes**. It contains one unit,
1,284 stored spike times and 139 trial rows, and declares NWB 2.0.2.

The [published asset metadata](https://api.dandiarchive.org/api/dandisets/000006/versions/0.220126.1855/assets/f1b6ed8f-1e14-44fa-b4ee-240d0efe3759/)
supplies SHA-256:

```text
974be4e6bb774eeef4075e4920db664cd2d9499d41278a953fc72e81ebaec846
```

The runner checks that independent archive checksum before auditing. Neither
the original nor the modified data is committed here. All modifications occur
in a separate educational copy; they are not corrections to the source data.

## What actually happened

The recorded run used MetricProof-NWB 0.3.0, MetricProof 0.2.0, PyNWB 4.2.0 and
NWBInspector 0.7.2. See [the environment](published/environment.json) and
[the complete summary](published/summary.json).

| Scenario | Check performed | Recorded outcome |
| --- | --- | --- |
| Unchanged source | Rehash against original evidence | `pass` |
| File missing at handoff | Resolve original artifact in an empty directory | `incomplete` |
| All spike times shifted by +0.25 s, trial boundaries unchanged | Rehash modified copy against original evidence | `fail` |
| Fresh audit of shifted copy | PyNWB + NWBInspector | Same findings as original; no additional finding identified the shift |

**Neither original nor shifted audit passes.** PyNWB reports three schema/type
findings in electrode columns. NWBInspector records 20 findings: these include
descending spike times, missing subject age, unknown timing resolution, and
placeholder metadata. The duration check raises an indexing `TypeError`; this
is preserved as an `ERROR` finding and the Inspector result has status `error`.
The runtime also warns about all-NaN trial stop times. These are observations
under the recorded tools, not a verdict on the publication or every session.

The unchanged file's successful **hash verification** must not be confused with
a successful **validation audit**. It only establishes that the bytes match.
Validator execution errors with no findings stop the runner. An Inspector
check error emitted among other findings remains visible so the partial
inspection can be studied; it is never converted into a pass.

## Why preserve the evidence?

Imagine an analyst receives the NWB file with its original evidence. If a later
pipeline shifts spike times by 250 ms without shifting behavioral events, the
old fingerprint immediately shows that the artifact changed. This matters for
analyses relating firing to behavioral events, although this example does not
measure an effect on any published result.

A freshly generated fingerprint would simply identify the new file. In this
run, the standard validators returned identical findings before and after the
shift. Neither was supplied an independent synchronization reference, and one
Inspector check did not complete. This experiment therefore demonstrates a
limit of these particular audits, **not** that timing errors are undetectable by
all validation tools. A study-specific check against synchronization pulses or
an independently retained event clock would be needed to assess alignment.

MetricProof-NWB supplies the file identity, tool/configuration provenance,
structured findings, missing-file classification and portable evidence bundle.
PyNWB and NWBInspector supply the schema and best-practice checks. This example
does not run DANDI validation, infer good spike sorting, establish a mechanism,
or replicate a biological conclusion. A hash is also not an authenticated
signature: someone who replaces both file and evidence can create a new match.

## Reproduce

Use a fresh Python 3.13 environment for the recorded dependency set. From the
repository root, run these commands (one per line, on Windows or POSIX):

```text
python -m venv .venv-case-study
```

Activate it with `.venv-case-study\Scripts\Activate.ps1` in PowerShell or
`source .venv-case-study/bin/activate` in a POSIX shell, then:

```text
python -m pip install -r examples/public_dandi_case_study/published/requirements.txt
python examples/public_dandi_case_study/run_case_study.py --output examples/public_dandi_case_study/reproduced
```

The runner downloads only the pinned small asset. For offline reuse, supply
`--source-cache /path/to/the/downloaded.nwb`; it still verifies the archive hash.
Choose a new output directory each time: existing records are never overwritten.
PyNWB requires a writable user cache. A blocked cache or download fails the run.

Compare `summary.json`, artifact hashes, tool versions and finding content.
Timestamps and paths inside third-party tracebacks differ by environment;
byte-identical report JSON across machines is not claimed. Installing newer
validator versions is a separate experiment and may change the findings.

The output contains `baseline/evidence.json`, `baseline/evidence.html`, both
NWB copies, the shifted audit, each handoff verification, source citation and
checksums, a dependency snapshot, and a summary. The HTML is self-contained:
download [the original audit](published/baseline/evidence.html) and open it
locally. It is not an interactive GitHub Pages deployment.

The runner returns zero when the demonstration completes and its three handoff
expectations hold. That exit code **does not mean the NWB audits passed**; read
`baseline_audit_passed`, `shifted_audit_passed` and the structured findings.

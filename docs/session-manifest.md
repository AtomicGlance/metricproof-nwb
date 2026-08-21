# Session evidence ledger

MetricProof-NWB treats a research session as a traceable handoff rather than a
single `.nwb` file. The manifest is the small, reviewable record that connects
raw exports, synchronisation outputs, tracked paths, curated units, the NWB
file, and the final report.

## Manifest shape

```json
{
  "schema_version": "0.3",
  "session": {
    "session_id": "session-001",
    "timebases": [
      {"name": "lfp", "rate": 1500, "sample_count": 3000, "start": 0, "stop": 2}
    ],
    "curation": {"human_reviewed": true, "recomputed": true}
  },
  "artifacts": [
    {
      "name": "raw.bin",
      "uri": "raw.bin",
      "sha256": "...",
      "size_bytes": 123,
      "stage": "raw",
      "role": "recording",
      "parents": []
    },
    {
      "name": "session.nwb",
      "uri": "session.nwb",
      "sha256": "...",
      "size_bytes": 456,
      "stage": "handoff",
      "role": "nwb",
      "parents": ["raw.bin"]
    }
  ],
  "config": {
    "required_artifacts": ["session.nwb"],
    "node_ids": ["start", "goal"],
    "graph_edges": [["start", "goal"]]
  }
}
```

`uri` is relative to the session root when possible. Parent references use an
artifact name or URI. A manifest with an unknown parent is rejected before it
can be used as evidence; this prevents a report from claiming lineage it cannot
resolve.

## What is checked

The checks are intentionally declarative so a project can supply its own
sample rates, graph topology, expected counts, required files, and placeholder
policy:

- inventory and parent references;
- placeholder identity/metadata values;
- timebase rate, count, and duration consistency, plus configured recording-duration checks;
- trial identity, interval ordering, graph node IDs, and adjacency;
- expected NWB/file/unit/trial/recording counts; and
- curation gates, including human review and post-curation recomputation.

`complete` means the configured checks ran without a critical gap. `needs_review`
means the machine found a review gate such as a placeholder or unrecorded human
decision. `incomplete` means a critical input or integrity check is missing or
invalid. These workflow statuses supplement (rather than replace) the stable
MetricProof evidence result statuses `pass`, `fail`, and `error`.

## Verification and handoff

`metricproof-nwb verify proof.json` rehashes local artifacts. A changed digest is
a hard failure; a missing artifact is incomplete; a remote URI or an artifact
without a digest is needs-review. The command does not silently treat a missing
input as success.

The `bundle` command produces a self-contained HTML file. It is suitable for a
pull request, paper supplement, archive handoff, or CI artifact because it
contains the hashes, findings, provenance, lineage, and review reasons without
requiring a web service.

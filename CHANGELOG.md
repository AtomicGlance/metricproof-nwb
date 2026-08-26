# Changelog

## 0.3.0 - 2026-08-26

- Added independently versioned PyNWB, NWBInspector, and DANDI validator
  adapters with preserved native findings and effective configuration.
- Added session evidence manifests with artifact hashes, parent/child lineage,
  configurable integrity checks, and explicit curation review gates.
- Added deterministic JSON evidence rendering and offline HTML evidence bundles.
- Added evidence and manifest verification that distinguishes changed, missing,
  remote, and undigested artifacts for later handoffs.
- Kept MetricProof-NWB reports on MetricProof's shared evidence envelope while
  retaining the backwards-compatible convenience API.

## 0.2.0 - 2026-08-12

- Added the MetricProof shared evidence model and PyNWB validation adapter.
- Recorded NWB artifact identity, selected metadata, validation findings, and
  validator provenance in reproducible reports.

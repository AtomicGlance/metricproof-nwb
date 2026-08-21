"""Self-contained HTML evidence bundles for human review."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from .models import NWBProofReport


def _payload(value: Mapping[str, Any] | NWBProofReport) -> dict[str, Any]:
    if isinstance(value, NWBProofReport):
        return value.to_dict()
    return dict(value)


def render_html(value: Mapping[str, Any] | NWBProofReport) -> str:
    """Render a report as one offline HTML file with no external assets."""

    payload = _payload(value)
    context = payload.get("context", {})
    workflow = context.get("metricproof_nwb", {}) if isinstance(context, Mapping) else {}
    manifest = workflow.get("manifest", {}) if isinstance(workflow, Mapping) else {}
    artifacts = manifest.get("artifacts", payload.get("artifacts", [])) if isinstance(manifest, Mapping) else payload.get("artifacts", [])
    results = payload.get("results", [])
    status = workflow.get("session_status") or ("pass" if payload.get("passed") else "fail")
    status_class = "pass" if status in {"pass", "complete"} else "attention"
    title = html.escape(str(payload.get("title", "MetricProof-NWB evidence bundle")))
    safe_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).replace("<", "\\u003c")

    artifact_rows = []
    for artifact in artifacts if isinstance(artifacts, list) else []:
        if not isinstance(artifact, Mapping):
            continue
        parents = ", ".join(str(parent) for parent in artifact.get("parents", [])) or "—"
        artifact_rows.append(
            "<tr>"
            f"<td>{html.escape(str(artifact.get('name', '')))}</td>"
            f"<td>{html.escape(str(artifact.get('stage', '')))}</td>"
            f"<td>{html.escape(str(artifact.get('role', '')))}</td>"
            f"<td><code>{html.escape(str(artifact.get('uri', '')))}</code></td>"
            f"<td><code>{html.escape(str(artifact.get('sha256', '')))}</code></td>"
            f"<td>{html.escape(parents)}</td>"
            "</tr>"
        )
    result_rows = []
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, Mapping):
            continue
        result_rows.append(
            "<tr>"
            f"<td><span class=\"badge {html.escape(str(result.get('status', '')))}\">{html.escape(str(result.get('status', '')).upper())}</span></td>"
            f"<td>{html.escape(str(result.get('check_id', '')))}</td>"
            f"<td>{html.escape(str(result.get('message', '')))}</td>"
            f"<td>{html.escape(str(result.get('suggested_fix', '')))}</td>"
            "</tr>"
        )
    review_reasons = workflow.get("review_reasons", []) if isinstance(workflow, Mapping) else []
    review_html = "".join(f"<li>{html.escape(str(reason))}</li>" for reason in review_reasons) or "<li>No outstanding review gate recorded.</li>"
    generated = html.escape(str(payload.get("generated_at", "")))
    producer = payload.get("producer", {})
    producer_text = html.escape(f"{producer.get('name', '')} {producer.get('version', '')}".strip()) if isinstance(producer, Mapping) else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ margin: 2rem auto; max-width: 1100px; padding: 0 1rem; line-height: 1.45; }}
h1, h2 {{ line-height: 1.15; }}
.summary {{ display: flex; gap: .75rem; flex-wrap: wrap; margin: 1rem 0 2rem; }}
.card {{ border: 1px solid #8885; border-radius: .6rem; padding: .75rem 1rem; min-width: 10rem; }}
.status {{ font-weight: 700; letter-spacing: .04em; }}
.status.pass {{ color: #16803c; }} .status.attention {{ color: #b54708; }}
table {{ border-collapse: collapse; width: 100%; margin: .75rem 0 2rem; }}
th, td {{ border-bottom: 1px solid #8885; padding: .55rem; text-align: left; vertical-align: top; }}
th {{ font-size: .85rem; }} code {{ overflow-wrap: anywhere; font-size: .85em; }}
.badge {{ border-radius: 999px; padding: .15rem .45rem; font-size: .75rem; font-weight: 700; }}
.badge.pass {{ background: #16803c33; }} .badge.fail, .badge.error {{ background: #b4231833; }}
details {{ margin-top: 2rem; }} pre {{ overflow: auto; white-space: pre-wrap; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="summary">
  <div class="card"><div>Workflow status</div><div class="status {status_class}">{html.escape(str(status).upper())}</div></div>
  <div class="card"><div>Checks</div><div>{len(results)}</div></div>
  <div class="card"><div>Artifacts</div><div>{len(artifacts) if isinstance(artifacts, list) else 0}</div></div>
  <div class="card"><div>Producer</div><div>{producer_text}</div></div>
  <div class="card"><div>Generated</div><div>{generated}</div></div>
</div>
<h2>Review gates</h2>
<ul>{review_html}</ul>
<h2>Artifact lineage</h2>
<table><thead><tr><th>Name</th><th>Stage</th><th>Role</th><th>URI</th><th>SHA-256</th><th>Parents</th></tr></thead><tbody>{''.join(artifact_rows) or '<tr><td colspan="6">No artifacts recorded.</td></tr>'}</tbody></table>
<h2>Checks and findings</h2>
<table><thead><tr><th>Status</th><th>Check</th><th>Finding</th><th>Suggested fix</th></tr></thead><tbody>{''.join(result_rows) or '<tr><td colspan="4">No checks recorded.</td></tr>'}</tbody></table>
<details><summary>Machine-readable evidence</summary><pre id="evidence"></pre></details>
<script>document.getElementById('evidence').textContent = {json.dumps(safe_json)};</script>
</body>
</html>
"""


def write_html(value: Mapping[str, Any] | NWBProofReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(value), encoding="utf-8")


__all__ = ["render_html", "write_html"]

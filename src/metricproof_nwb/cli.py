"""Command-line interface for reproducible NWB evidence reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .bundle import render_html
from .core import audit_nwb
from .manifest import build_manifest
from .report import render_json, render_text
from .validators import dandi_validator, nwbinspector_validator, pynwb_validator
from .verify import verify_file


def _write_or_print(output: str, path: str | None, label: str) -> None:
    if path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Wrote {label} to {output_path}")
    else:
        print(output, end="")


def _load_json_object(path: str | None) -> dict:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="metricproof-nwb",
        description="Create reproducible evidence reports for NWB files and sessions.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Audit one NWB file.")
    audit.add_argument("path", help="Path to an NWB file.")
    audit.add_argument("--format", choices=("text", "json", "html"), default="text", help="Report format (default: text).")
    audit.add_argument("--nwbinspector", action="store_true", help="Also run NWBInspector best-practice checks.")
    audit.add_argument("--dandi", action="store_true", help="Also run the optional DANDI validator.")
    audit.add_argument(
        "--nwbinspector-importance",
        choices=("BEST_PRACTICE_SUGGESTION", "BEST_PRACTICE_VIOLATION", "CRITICAL"),
        default="BEST_PRACTICE_SUGGESTION",
        help="Lowest NWBInspector importance to include (default: suggestion).",
    )
    audit.add_argument("--artifact-uri", help="Portable URI recorded in evidence instead of the local absolute path.")
    audit.add_argument("--manifest", help="Optional session manifest JSON to include and check.")
    audit.add_argument("--session-config", help="Optional JSON object overriding manifest check configuration.")
    audit.add_argument("--output", help="Optional report output path.")

    manifest = subparsers.add_parser("manifest", help="Create a portable session artifact manifest.")
    manifest.add_argument("root", help="Session directory or one artifact file.")
    manifest.add_argument("--session-json", help="JSON object containing session metadata and optional config.")
    manifest.add_argument("--output", required=True, help="Manifest JSON output path.")

    bundle = subparsers.add_parser("bundle", help="Render an evidence JSON report as offline HTML.")
    bundle.add_argument("proof", help="Evidence JSON report.")
    bundle.add_argument("--output", required=True, help="HTML output path.")

    verify = subparsers.add_parser("verify", help="Rehash evidence inputs and detect changed artifacts.")
    verify.add_argument("proof", help="Evidence JSON report or manifest JSON.")
    verify.add_argument("--base-dir", help="Base directory for relative artifact URIs (default: proof directory).")
    verify.add_argument("--format", choices=("text", "json"), default="text")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "manifest":
            source = _load_json_object(args.session_json)
            session = source.get("session", source)
            config = source.get("config", {})
            artifact_specs = source.get("artifacts")
            manifest = build_manifest(
                args.root,
                session=session if isinstance(session, dict) else {},
                artifact_specs=artifact_specs if isinstance(artifact_specs, list) else None,
                config=config if isinstance(config, dict) else {},
            )
            manifest.write_json(args.output)
            print(f"Wrote manifest to {args.output}")
            return 0

        if args.command == "bundle":
            payload = json.loads(Path(args.proof).read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Evidence JSON must contain an object")
            _write_or_print(render_html(payload), args.output, "HTML bundle")
            return 0

        if args.command == "verify":
            verification = verify_file(args.proof, base_dir=args.base_dir)
            if args.format == "json":
                _write_or_print(json.dumps(verification.to_dict(), indent=2, sort_keys=True) + "\n", None, "verification")
            else:
                print(f"MetricProof-NWB verification: {verification.status.upper()}")
                for check in verification.checks:
                    print(f"[{check.status.upper():12}] {check.uri}: {check.message}")
            return 0 if verification.passed else 1

        validators = [pynwb_validator()]
        if args.nwbinspector:
            validators.append(nwbinspector_validator(importance_threshold=args.nwbinspector_importance))
        if args.dandi:
            validators.append(dandi_validator())
        session_config = _load_json_object(args.session_config) if args.session_config else None
        report = audit_nwb(
            args.path,
            validators=validators,
            artifact_uri=args.artifact_uri,
            manifest=args.manifest,
            session_config=session_config,
            command="metricproof-nwb " + " ".join(argv if argv is not None else sys.argv[1:]),
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"MetricProof-NWB configuration error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        output = render_json(report)
    elif args.format == "html":
        output = render_html(report)
    else:
        output = render_text(report)
    _write_or_print(output, args.output, f"{args.format} report")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

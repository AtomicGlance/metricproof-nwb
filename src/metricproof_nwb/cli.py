"""Command-line interface for reproducible NWB evidence reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import audit_nwb
from .report import render_json, render_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="metricproof-nwb",
        description="Create reproducible evidence reports for NWB files.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="Audit one NWB file.")
    audit.add_argument("path", help="Path to an NWB file.")
    audit.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format (default: text).",
    )
    audit.add_argument("--output", help="Optional report output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_nwb(args.path)
    except (OSError, ValueError) as exc:
        print(f"MetricProof-NWB configuration error: {exc}", file=sys.stderr)
        return 2

    output = render_json(report) if args.format == "json" else render_text(report)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Wrote {args.format} report to {output_path}")
    else:
        print(output, end="")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

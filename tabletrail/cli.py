"""Command line entry point; exit 0 = passed, 1 = findings, 2 = input/usage error."""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from . import __version__
from .compare import compare
from .contracts import load_contract
from .engine import analyze
from .errors import TableTrailError
from .report import render_html


def write_atomic(path, content):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _parser():
    parser = argparse.ArgumentParser(prog="tabletrail", description="Inspect CSV quality without sending data anywhere.")
    parser.add_argument("--version", action="version", version=f"TableTrail {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in (("profile", "Summarize a CSV"), ("validate", "Check a CSV against a contract"),
                              ("init", "Draft a contract from observed data"), ("compare", "Find changes between two CSVs")):
        sub = commands.add_parser(name, help=description)
        if name == "compare":
            sub.add_argument("baseline", type=Path)
            sub.add_argument("current", type=Path)
            sub.add_argument("--null-threshold", type=float, default=0.05)
            sub.add_argument("--mean-threshold", type=float, default=0.25)
            sub.add_argument("--row-threshold", type=float, default=0.5)
        else:
            sub.add_argument("source", type=Path)
        sub.add_argument("--delimiter", default=",", help="One character; use 'tab' for a TSV")
        sub.add_argument("--encoding", default="utf-8-sig")
        if name == "validate":
            sub.add_argument("--contract", type=Path, required=True)
            sub.add_argument("--max-issues", type=int, default=200, help="Stored examples only; totals remain exact")
        if name == "init":
            sub.add_argument("--output", type=Path, required=True)
        else:
            sub.add_argument("--json", type=Path, dest="json_output")
            sub.add_argument("--html", type=Path, dest="html_output")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        inputs = [getattr(args, name, None) for name in ("source", "baseline", "current", "contract")]
        outputs = [getattr(args, name, None) for name in ("output", "json_output", "html_output")]
        inputs = [p.resolve() for p in inputs if p]
        outputs = [p.resolve() for p in outputs if p]
        if len(set(outputs)) != len(outputs) or set(inputs) & set(outputs):
            raise TableTrailError("Output paths must be distinct and must not overwrite an input or contract")
        options = {"delimiter": "\t" if args.delimiter == "tab" else args.delimiter, "encoding": args.encoding}
        if args.command == "compare":
            result = compare(args.baseline, args.current, null_threshold=args.null_threshold,
                             mean_threshold=args.mean_threshold, row_threshold=args.row_threshold, **options)
        else:
            contract = load_contract(args.contract) if args.command == "validate" else None
            result = analyze(args.source, contract, max_issues=getattr(args, "max_issues", 200), **options)
        if args.command == "init":
            draft = {"version": 1, "name": args.source.stem + " contract", "allow_extra_columns": False,
                     "columns": {c["name"]: {"type": c["inferred_type"] if c["inferred_type"] not in ("mixed", "empty") else "string",
                                              "required": c["null_count"] == 0 and result["rows"] > 0}
                                 for c in result["columns"]}}
            write_atomic(args.output, json.dumps(draft, indent=2, ensure_ascii=True) + "\n")
            print(f"Draft saved to {args.output}. Review types and business rules before using it.")
            return 0
        if args.json_output:
            write_atomic(args.json_output, json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + "\n")
        if args.html_output:
            write_atomic(args.html_output, render_html(result))
        findings = result.get("change_count", result.get("issue_count", 0))
        print(f"{result['status'].upper()} | {result['source']} | {result['rows']} records | "
              f"{result['column_count']} columns | {findings} findings")
        if not args.json_output and not args.html_output:
            print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
        return 1 if result["status"] == "fail" else 0
    except (TableTrailError, OSError, sqlite3.Error) as exc:
        print(f"tabletrail: {exc}", file=sys.stderr)
        return 2

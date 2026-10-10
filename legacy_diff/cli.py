"""CLI for plan validation and supplied-candidate comparison."""
import argparse
import json
import sys
from pathlib import Path

import yaml

from .manifest import PlanError, load_plan
from .preflight import check_readiness
from .execution import run_comparison
from .suites import build_suite, check_suite


def main(argv=None):
    parser = argparse.ArgumentParser(prog="legacy-diff")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Validate a manifest and check local prerequisites")
    check.add_argument("manifest", type=Path)
    check.add_argument("--offline", action="store_true", help="Validate the contract without probing services; never means ready")
    check.add_argument("--output", type=Path, help="Save the JSON report to a new file")
    compare = commands.add_parser("compare", help="Compare one supplied Python candidate against COBOL; not final acceptance")
    compare.add_argument("manifest", type=Path)
    compare.add_argument("--candidate", required=True, type=Path)
    compare.add_argument("--output-dir", required=True, type=Path, help="New directory for evidence and reports")
    build = commands.add_parser("suite-build", help="Freeze independent cases and check every reference twice")
    build.add_argument("manifest", type=Path)
    build.add_argument("--output-dir", required=True, type=Path)
    suite = commands.add_parser("suite-check", help="Compare a candidate against a frozen regression suite")
    suite.add_argument("--suite-dir", required=True, type=Path)
    suite.add_argument("--candidate", required=True, type=Path)
    suite.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in ("suite-build", "suite-check"):
            report = build_suite(load_plan(args.manifest), args.output_dir) if args.command == "suite-build" else check_suite(args.suite_dir, args.candidate, args.output_dir)
            code = {"suite_ready": 0, "regression_match": 0, "mismatch": 6, "inconclusive": 7, "prerequisites_unavailable": 4}[report["outcome"]]
        elif args.command == "compare":
            plan = load_plan(args.manifest)
            report = run_comparison(plan, args.candidate, args.output_dir)
            code = {"match": 0, "mismatch": 6, "inconclusive": 7, "prerequisites_unavailable": 4}[report["outcome"]]
        else:
            plan = load_plan(args.manifest)
            observed, problems = ({}, []) if args.offline else check_readiness(plan)
            report = {"status": "prerequisites_unavailable" if problems else "contract_valid" if args.offline else "ready",
                      "readiness_checked": not args.offline, "plan": plan,
                      "observed": observed, "diagnostics": problems}
            code = 4 if problems else 0
    except PlanError as exc:
        report = {"status": exc.code, "diagnostics": [{"code": exc.code, "message": str(exc)}]}
        code = 3 if exc.code == "unsupported" else 2
    except (OSError, ValueError, TypeError, RecursionError, yaml.YAMLError) as exc:
        report = {"status": "invalid_manifest", "diagnostics": [{"code": "invalid_manifest", "message": str(exc)}]}
        code = 2
    text = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.command == "check" and args.output:
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
        except OSError as exc:
            print(f"Cannot save report (existing files are preserved): {exc}", file=sys.stderr)
            print(text, end="")
            return 5
    print(text, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

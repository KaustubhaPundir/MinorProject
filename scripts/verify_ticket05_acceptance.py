"""Opt-in end-to-end acceptance tests, including deliberate regression overfitting."""
import argparse
import json
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legacy_diff.acceptance import accept_candidate
from legacy_diff.manifest import load_plan
from legacy_diff.suites import build_suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    base = yaml.safe_load((ROOT / "manifest.yaml").read_text())
    # This fixture intentionally ignores its supplied record file. It exercises
    # input isolation, unseen case selection and overfitting detection, not a
    # claim about translating a complex COBOL business program.
    (root / "legacy.cbl").write_bytes((ROOT / "examples/check-plan/legacy.cbl").read_bytes())
    (root / "records.dat").write_bytes(b"005\n")
    base["program"]["source"] = "legacy.cbl"
    base["execution"]["inputs"] = [{"fixture": "records.dat", "sandbox_path": "records.dat"}]
    base["input_domain"] = {
        "description": "Transport fixture: the constant-output program ignores supplied fixed records.",
        "encoding": "ascii", "constraints": ["One ASCII record, three decimal digits, value 000 through 999."],
        "reviewed": True, "record_width_bytes": 3,
        "generator": {"kind": "fixed_records", "input": "records.dat", "record_count": {"min": 1, "max": 1},
                      "line_ending": "lf", "fields": [{"name": "amount", "offset": 0, "width": 3,
                      "type": "integer", "min": 0, "max": 999, "sign": "none"}]}}
    base["validation"] = {"regression_seed": 1234, "generated_cases": 2, "held_out_cases": 3}
    manifest = root / "manifest.yaml"
    manifest.write_text(yaml.safe_dump(base))
    plan = load_plan(manifest)
    suite = root / "suite"
    built = build_suite(plan, suite)
    if built["outcome"] != "suite_ready":
        raise RuntimeError("Live reference suite failed: " + built["outcome"])
    cases = json.loads((suite / "cases.json").read_text())
    seen = [bytes.fromhex(case["inputs"]["records.dat"]) if "records.dat" in case["inputs"] else None for case in cases]
    constant = root / "constant.py"
    constant.write_text("from pathlib import Path\nPath('report.dat').write_bytes(b'HELLO\\n')\n")
    overfit = root / "overfit.py"
    overfit.write_text("from pathlib import Path\ntry:\n    data=Path('records.dat').read_bytes()\nexcept FileNotFoundError:\n    data=None\n"
                       + f"seen={seen!r}\nPath('report.dat').write_bytes(b'HELLO\\n' if data in seen else b'HALLO\\n')\n")
    summary = []
    for name, candidate, expected in (("matching", constant, "accepted"), ("overfit", overfit, "rejected")):
        report = accept_candidate(plan, suite, candidate, root / name)
        passed = report["outcome"] == expected
        if name == "overfit":
            passed = passed and report["reason"] == "held_out_mismatch" and report["held_out"]["completed"] == 1 and report["held_out"]["skipped"] == 2
        else:
            passed = passed and report["held_out"]["completed"] == 3 and not report["held_out_policy"]["regression_overlap"]
        summary.append({"case": name, "passed": bool(passed), "outcome": report["outcome"], "reason": report["reason"]})
        print(json.dumps(summary[-1]), flush=True)
    (root / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0 if all(case["passed"] for case in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())

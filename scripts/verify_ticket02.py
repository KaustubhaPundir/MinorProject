"""Opt-in live Docker verification with controlled candidates, not model output."""
import argparse
import json
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legacy_diff.execution import run_comparison
from legacy_diff.manifest import load_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="A new directory; evidence is retained")
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / "fixtures"
    inputs.mkdir()
    base = load_plan(ROOT / "manifest.yaml")
    manifest_template = yaml.safe_load((ROOT / "manifest.yaml").read_text(encoding="utf-8"))
    empty_source = inputs / "empty.cbl"
    text = Path(base["program"]["source"]["path"]).read_text()
    (inputs / "legacy.cbl").write_text(text, encoding="utf-8")
    empty_source.write_text(text.replace('    move "HELLO" to report-line\n    write report-line\n', ''), encoding="utf-8")
    cases = [
        ("match", 'from pathlib import Path; Path("report.dat").write_bytes(b"HELLO\\n")', "match", None),
        ("byte", 'from pathlib import Path; Path("report.dat").write_bytes(b"HALLO\\n")', "mismatch", "byte_difference"),
        ("length", 'from pathlib import Path; Path("report.dat").write_bytes(b"HELLO")', "mismatch", "length_difference"),
        ("missing-empty", 'pass', "mismatch", "file_presence_difference"),
        ("exit-code", 'from pathlib import Path; Path("report.dat").write_bytes(b"HELLO\\n"); raise SystemExit(7)', "mismatch", "exit_code_difference"),
    ]
    summary = []
    for name, source, expected, difference in cases:
        candidate = inputs / (name + ".py")
        candidate.write_text(source + "\n", encoding="utf-8")
        manifest_template["program"]["source"] = "empty.cbl" if name == "missing-empty" else "legacy.cbl"
        case_manifest = inputs / (name + ".yaml")
        case_manifest.write_text(yaml.safe_dump(manifest_template), encoding="utf-8")
        plan = load_plan(case_manifest)
        report = run_comparison(plan, candidate, root / name)
        result = {"case": name, "expected": expected, "outcome": report["outcome"], "differences": report.get("differences", []), "diagnostics": report.get("diagnostics", [])}
        summary.append(result)
        print(json.dumps(result), flush=True)
        assert report["outcome"] == expected, result
        if difference:
            assert any(item["kind"] == difference for item in report["differences"]), result
        if name == "missing-empty":
            assert report["reference"]["files"]["report.dat"]["length"] == 0
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("All five real Docker comparisons verified; evidence retained at " + str(root), flush=True)


if __name__ == "__main__":
    main()

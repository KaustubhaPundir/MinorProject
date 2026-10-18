"""Live Docker follow-up verification with explicitly controlled generation."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legacy_diff.manifest import load_plan
from legacy_diff.preflight import DockerLinuxProbe
from legacy_diff.resume import resume, snapshot


class ControlledGeneration:
    def __init__(self, code):
        self.code = code
        self.requests = []

    def generate(self, request, evidence):
        self.requests.append(request)
        return {"model": request["model"], "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({"files": [
                    {"path": "main.py", "content": self.code}]})}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-dir", type=Path, required=True)
    parser.add_argument("--suite-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case", choices=("correct", "exposed-only"), required=True)
    args = parser.parse_args()
    plan = load_plan(args.manifest)
    observed, errors = DockerLinuxProbe().inspect(plan)
    if errors:
        raise RuntimeError(str(errors))
    before = snapshot(args.parent_dir.resolve())
    parent = json.loads((args.parent_dir / "report.json").read_text())
    original = Path(parent["candidate"]["path"]).read_text()
    held = json.loads((args.parent_dir / "private/held-out/cases.json").read_text())
    failed_id = next(c["id"] for c in parent["held_out"]["cases"] if c["outcome"] == "mismatch")
    exposed = next(c for c in held if c["id"] == failed_id)
    if args.case == "correct":
        code = "from pathlib import Path\nPath('report.dat').write_bytes(b'HELLO\\n')\n"
    else:
        marker = "Path('report.dat').write_bytes"
        if marker not in original:
            raise RuntimeError("Expected the controlled ticket-05 overfit fixture.")
        code = original.replace(marker, f"seen.append({bytes.fromhex(exposed['inputs']['records.dat'])!r})\n" + marker)
    adapter = ControlledGeneration(code)
    # Explicit fixture identity; never describe this as an observed Ollama call.
    model = {"endpoint": plan["generation"]["endpoint"], "model": plan["generation"]["model"],
             "digest": "controlled-generation-fixture"}
    with patch("legacy_diff.generation.check_readiness", return_value=({**observed, "ollama": model}, [])), \
         patch("legacy_diff.generation.probe_ollama", return_value=(model, [])):
        report = resume(plan, args.parent_dir, args.suite_dir, args.output_dir, adapter=adapter)
    expected = "accepted" if args.case == "correct" else "rejected"
    passed = report["outcome"] == expected and before == snapshot(args.parent_dir.resolve())
    if "acceptance" in report and report.get("held_out_suite_id"):
        fresh = json.loads((args.output_dir / "acceptance/private/held-out/cases.json").read_text())
        passed = passed and not ({c["case_sha256"] for c in held} & {c["case_sha256"] for c in fresh})
    else:
        passed = False
    if args.case == "exposed-only" and "acceptance" in report:
        passed = passed and report["acceptance"].get("reason") == "held_out_mismatch"
    summary = {"case": args.case, "passed": bool(passed), "outcome": report["outcome"],
               "diagnostic": report.get("diagnostic"), "model_transport": "controlled_fixture_no_ollama_inference",
               "attempts": report.get("generation", {}).get("attempt_count"),
               "promoted_failures": len(report.get("promoted_failures", [])),
               "parent_unchanged": before == snapshot(args.parent_dir.resolve())}
    (args.output_dir / "verification.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

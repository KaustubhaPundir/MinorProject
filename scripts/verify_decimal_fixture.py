"""Prepare live COBOL reference/regression evidence; accept serially afterward."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legacy_diff.manifest import load_plan
from legacy_diff.suites import build_suite, write
from legacy_diff.structured_report import translate_structured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fixture', choices=['add-truncate', 'subtract-rounded', 'multiply-size-error', 'divide-rounded'])
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    manifest = Path(__file__).resolve().parents[1] / 'examples/decimal-arithmetic' / args.fixture / 'manifest.yaml'
    plan = load_plan(manifest)
    print(args.fixture + ': building reference suite', flush=True)
    suite = build_suite(plan, root / 'suite')
    write(root / 'suite-result.json', suite)
    summary = {'fixture': args.fixture, 'suite': suite['outcome'], 'accepted': False}
    write(root / 'summary.json', summary)
    if suite['outcome'] != 'suite_ready':
        print(json.dumps(summary)); return 1
    print(args.fixture + ': structured decimal regression', flush=True)
    result = translate_structured(plan, root / 'suite', root / 'translation', frontend='decimal')
    summary.update(translation=result['outcome'], regression=result['regression'])
    write(root / 'summary.json', summary)
    print(json.dumps(summary))
    return 0 if result['outcome'] == 'awaiting_acceptance' else 1


if __name__ == '__main__':
    sys.exit(main())

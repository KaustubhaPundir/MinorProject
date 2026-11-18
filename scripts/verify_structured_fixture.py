"""Run real Docker regression/acceptance for one retained structured fixture."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legacy_diff.manifest import load_plan
from legacy_diff.suites import build_suite, write
from legacy_diff.structured_report import translate_structured
from legacy_diff.acceptance import accept_candidate
from legacy_diff.inspection import verified_acceptance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fixture', choices=['compact', 'wide', 'paginated', 'paginated-wide', 'page-heading', 'page-heading-wide'])
    parser.add_argument('--skip-acceptance', action='store_true', help='Prepare regression evidence; run accept separately to serialize evidence access')
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    manifest = Path(__file__).resolve().parents[1] / 'examples/structured-reports' / args.fixture / 'manifest.yaml'
    plan = load_plan(manifest)
    suite = root / 'suite'
    print(args.fixture + ': building stable reference suite', flush=True)
    result = build_suite(plan, suite)
    summary = {'fixture': args.fixture, 'suite': result['outcome'], 'accepted': False}
    write(root / 'summary.json', summary)
    if result['outcome'] != 'suite_ready':
        print(json.dumps(summary)); return 1
    print(args.fixture + ': validating structured translation', flush=True)
    result = translate_structured(plan, suite, root / 'translation')
    summary['translation'] = result['outcome']
    summary['regression'] = result['regression']
    write(root / 'summary.json', summary)
    if result['outcome'] != 'awaiting_acceptance':
        print(json.dumps(summary)); return 1
    if args.skip_acceptance:
        print(json.dumps(summary)); return 0
    print(args.fixture + ': independent held-out acceptance', flush=True)
    result = accept_candidate(plan, suite, Path(result['candidate']['path']), root / 'acceptance')
    summary.update(acceptance=result['outcome'], accepted=result['accepted'])
    if result['accepted']:
        verified_acceptance(root / 'acceptance', suite)
        summary['integrity_verified'] = True
        summary['held_out_completed'] = result['held_out']['completed']
    write(root / 'summary.json', summary)
    print(json.dumps(summary))
    return 0 if summary['accepted'] else 1


if __name__ == '__main__':
    sys.exit(main())

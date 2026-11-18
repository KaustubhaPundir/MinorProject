"""Run real model IR generation, Docker regression and independent acceptance serially."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legacy_diff.ai_ir import translate_ai_ir
from legacy_diff.acceptance import accept_candidate
from legacy_diff.inspection import verified_acceptance
from legacy_diff.manifest import load_plan
from legacy_diff.suites import build_suite, verify_suite, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--frontend', choices=['report', 'decimal', 'console'], default='report')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--suite-dir', type=Path, help='Reuse an existing sealed suite with the same manifest contract')
    args = parser.parse_args()
    root = args.output_dir.resolve(); root.mkdir(parents=True, exist_ok=False)
    plan = load_plan(args.manifest)
    summary = {'accepted': False, 'frontend': args.frontend, 'model': plan['generation']['model']}
    write(root / 'summary.json', summary)
    suite_dir = args.suite_dir.resolve() if args.suite_dir else root / 'suite'
    if args.suite_dir:
        print('Verifying existing sealed reference suite', flush=True)
        seal, frozen, _, _ = verify_suite(suite_dir)
        if frozen['contract_sha256'] != plan['contract_sha256']:
            raise ValueError('Manifest differs from the existing suite contract.')
        suite = {'outcome': 'suite_ready', 'suite_id': seal['suite_id'], 'reused': True}
    else:
        print('Building stable COBOL reference suite', flush=True)
        suite = build_suite(plan, suite_dir)
    write(root / 'suite-result.json', suite)
    summary['suite'] = suite['outcome']; write(root / 'summary.json', summary)
    if suite['outcome'] != 'suite_ready': return 1
    print('Requesting AI-proposed IR and checking visible regression', flush=True)
    result = translate_ai_ir(plan, suite_dir, root / 'translation', frontend=args.frontend)
    summary.update(translation=result['outcome'], stop_reason=result.get('stop_reason'),
                   attempt_count=result.get('attempt_count', 0))
    write(root / 'summary.json', summary)
    if result['outcome'] != 'awaiting_acceptance':
        print(json.dumps(summary)); return 1
    print('Running independent acceptance after model generation ends', flush=True)
    accepted = accept_candidate(plan, suite_dir, Path(result['candidate']['path']), root / 'acceptance')
    summary['acceptance'] = accepted['outcome']
    if accepted.get('accepted'):
        verified_acceptance(root / 'acceptance', suite_dir)
        summary.update(accepted=True, integrity_verified=True)
    write(root / 'summary.json', summary); print(json.dumps(summary))
    return 0 if summary['accepted'] else 1


if __name__ == '__main__':
    sys.exit(main())

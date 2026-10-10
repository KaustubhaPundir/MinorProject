from pathlib import Path
import collections, hashlib, json, shutil, subprocess, zipfile, re, importlib.util
import yaml

root = Path(__file__).resolve().parent
source = root / 'matt-pocock-plugin'
target = root / 'plugins' / 'matt-pocock-all-skills'
target.mkdir(parents=True, exist_ok=True)
commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
inventory = []
for entry in sorted((source / 'skills').rglob('SKILL.md')):
    bucket = entry.parent.parent.name
    destination = target / 'skills' / entry.parent.name
    if any(item['name'] == entry.parent.name for item in inventory):
        raise RuntimeError(f'Duplicate skill: {destination.name}')
    shutil.copytree(entry.parent, destination, dirs_exist_ok=True)
    inventory.append({'name': entry.parent.name, 'bucket': bucket, 'source': entry.relative_to(source).as_posix()})
shutil.copy2(source / 'LICENSE', target / 'LICENSE')
manifest = {
    '$schema': 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
    'name': 'matt-pocock-all-skills', 'version': '1.0.0',
    'description': "Unofficial complete snapshot of Matt Pocock's skills, including miscellaneous and experimental workflows.",
    'license': 'MIT',
    'extensions': {'com.openai': {
        'interface': {'displayName': 'Matt Pocock All Skills (Unofficial)', 'shortDescription': 'Engineering, productivity and experimental skills'},
        'onboardingSkill': './skills/setup-matt-pocock-skills/SKILL.md'
    }}
}
def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
write_json(target / 'plugin.json', manifest)
write_json(target / '.codex-plugin' / 'plugin.json', {
    'name': manifest['name'], 'version': manifest['version'],
    'description': manifest['description'], 'skills': './skills/'
})
write_json(target / 'SOURCE.json', {'repository': 'https://github.com/mattpocock/skills', 'commit': commit, 'skills': inventory})
write_json(root / '.agents' / 'plugins' / 'marketplace.json', {
    'name': 'matt-pocock-local', 'interface': {'displayName': 'Matt Pocock Local Skills'},
    'plugins': [{'name': manifest['name'], 'source': {'source': 'local', 'path': './plugins/matt-pocock-all-skills'},
                 'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]
})
counts = collections.Counter(item['bucket'] for item in inventory)
notes = [
    '# Matt Pocock All Skills (Unofficial)', '',
    f'Includes all {len(inventory)} skills under the upstream skills directory at commit `{commit}`.',
    'Source: https://github.com/mattpocock/skills', '',
    'This is a personal snapshot, not an official release by Matt Pocock. Instruction bodies and supporting files are preserved. Claude-specific frontmatter is converted for Codex; explicit invocation is preserved through agents/openai.yaml. Skill folders are flattened for portable plugin discovery. MIT attribution is retained in LICENSE.', '',
    'The official plugin ships engineering and productivity skills. This bundle additionally includes miscellaneous and in-progress skills because all skills were requested. Those workflows can be experimental or specific to Claude Code, Bash, or Matt\'s own projects; bundling does not make them native Windows or Codex compatible.', '',
    '## Install', '',
    'The workspace marketplace is at `.agents/plugins/marketplace.json`. Restart Codex, open the Plugins Directory, select Matt Pocock Local Skills, and install Matt Pocock All Skills (Unofficial). If the workspace source is not detected, register this workspace using `codex plugin marketplace add "' + str(root) + '"`, then install through the app.', '',
    'After installing, start a new chat and invoke `$setup-matt-pocock-skills` once per project. Use `$ask-matt` to choose a workflow. This snapshot does not update automatically.', '',
    '## Included skills', ''
]
for bucket, count in sorted(counts.items()):
    notes.append(f'- {bucket}: {count}')
notes.append('')
for item in inventory:
    notes.append(f"- [{item['name']}](skills/{item['name']}/SKILL.md) ({item['bucket']})")
(target / 'README.md').write_text('\n'.join(notes) + '\n', encoding='utf-8')
for entry in (source / 'skills').rglob('*'):
    if entry.is_file() and any(p.name == 'SKILL.md' for p in entry.parent.glob('SKILL.md')):
        copied = target / 'skills' / entry.parent.name / entry.name
        assert hashlib.sha256(entry.read_bytes()).digest() == hashlib.sha256(copied.read_bytes()).digest()
validator_path = Path('C:/Users/kaust/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
spec = importlib.util.spec_from_file_location('skill_validator', validator_path)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
validation = []
for entry in sorted((target / 'skills').glob('*/SKILL.md')):
    original = entry.read_text(encoding='utf-8')
    match = re.match(r'^---\n(.*?)\n---', original, re.DOTALL)
    data = yaml.safe_load(match.group(1))
    explicit = data.pop('disable-model-invocation', False)
    hint = data.pop('argument-hint', None)
    if hint:
        data.setdefault('metadata', {})['original-argument-hint'] = str(hint)
    entry.write_text('---\n' + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip() + '\n---' + original[match.end():], encoding='utf-8')
    if explicit:
        policy_path = entry.parent / 'agents' / 'openai.yaml'
        policy = yaml.safe_load(policy_path.read_text(encoding='utf-8')) if policy_path.exists() else {}
        policy = policy or {}
        policy.setdefault('policy', {})['allow_implicit_invocation'] = False
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(yaml.safe_dump(policy, sort_keys=False, allow_unicode=True), encoding='utf-8')
    valid, message = validator.validate_skill(entry.parent)
    validation.append({'skill': entry.parent.name, 'passed': valid, 'result': message})
    assert valid, f'{entry.parent.name}: {message}'
write_json(target / 'VALIDATION.json', validation)
archive = root / 'matt-pocock-all-skills.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for entry in sorted(target.rglob('*')):
        if entry.is_file():
            bundle.write(entry, entry.relative_to(target))
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    assert len([name for name in bundle.namelist() if name.endswith('/SKILL.md')]) == len(inventory)
print(json.dumps({'skills': len(inventory), 'buckets': counts, 'commit': commit, 'archive': str(archive)}, indent=2))

"""Reviewed stdin domains, independent of generated code and model output."""
import random
from .manifest import PlanError, mapping, number, string


def validate(domain, destinations):
    generator = domain['generator']
    mapping(generator, 'stdin generator', ('kind', 'fields'))
    if domain['encoding'].lower() != 'ascii': raise PlanError('stdin_lines requires ASCII.')
    fields = generator['fields']
    if not isinstance(fields, list) or not 1 <= len(fields) <= 32: raise PlanError('Declare 1..32 stdin lines.')
    names = set()
    for field in fields:
        kind = field.get('type') if isinstance(field, dict) else None
        required = ('name', 'type', 'min', 'max') if kind == 'integer' else ('name', 'type', 'choices')
        mapping(field, 'stdin field', required)
        name = string(field['name'], 'stdin field name')
        if name in names: raise PlanError('Duplicate stdin field name.')
        names.add(name)
        if kind == 'integer':
            for key in ('min', 'max'): number(field[key], key, minimum=-10**12, maximum=10**12)
            if field['min'] > field['max']: raise PlanError('stdin min exceeds max.')
        elif kind == 'choice':
            choices = field['choices']
            if not isinstance(choices, list) or not 1 <= len(choices) <= 64: raise PlanError('Declare 1..64 stdin choices.')
            if any(not isinstance(v, str) or not v.isascii() or len(v) > 256 or any(c in v for c in '\r\n\x00') for v in choices):
                raise PlanError('stdin choices must be single ASCII lines up to 256 characters.')
        else: raise PlanError('stdin line type must be integer or choice.')
    return generator


def construct(plan, inputs):
    from .cases import digest
    fields = plan['input_domain']['generator']['fields']
    requested = plan['validation']['generated_cases']
    cases, seen = [], set()
    def add(values, tags):
        stdin = ('\n'.join(map(str, values)) + '\n').encode('ascii')
        identity = digest({'inputs': {k: digest_bytes(v) for k, v in sorted(inputs.items())},
                           'stdin': digest_bytes(stdin), 'args': plan['execution']['args'], 'environment': plan['execution']['environment']})
        if identity in seen: return False
        seen.add(identity)
        cases.append({'id': f'case-{len(cases)+1:04d}', 'case_sha256': identity, 'inputs': dict(inputs), 'stdin': stdin,
                      'tags': tags, 'classification': 'in_domain'})
        if len(cases) > 256 or sum(sum(map(len, c['inputs'].values())) + len(c['stdin']) for c in cases) > 64 * 1024 * 1024:
            raise PlanError('stdin suite exceeds 256 cases or 64 MiB of inputs.', 'unsupported')
        return True
    defaults = [f['min'] if f['type'] == 'integer' else f['choices'][0] for f in fields]
    add(defaults, ['stdin_baseline'])
    for index, field in enumerate(fields):
        values = sorted({field['min'], field['max'], *([0] if field['min'] <= 0 <= field['max'] else [])}) if field['type'] == 'integer' else [field['choices'][0], field['choices'][-1]]
        for value in values:
            changed = defaults.copy(); changed[index] = value; add(changed, ['stdin_boundary', field['name']])
    # Exercise simultaneous upper bounds as well as per-field boundaries.
    add([f['max'] if f['type'] == 'integer' else f['choices'][-1] for f in fields], ['stdin_upper_bounds'])
    rng = random.Random(plan['validation']['regression_seed']); generated = 0
    for _ in range(requested * 20):
        if generated >= requested or len(cases) >= 256: break
        values = [rng.randint(f['min'], f['max']) if f['type'] == 'integer' else rng.choice(f['choices']) for f in fields]
        generated += add(values, ['random_valid_stdin'])
    return cases, {'requested_random': requested, 'generated_random': generated,
                   'reason': 'Reviewed stdin lines; fresh acceptance seed selects unseen valid inputs when available.'}


def digest_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()

"""Strict DISPLAY fixed-point arithmetic subset; no floating-point operations."""
import hashlib
import re

from .structured_report import require, match, NAME, STRING
from .manifest import relative_path


NUMERIC = r's?9\(\d+\)(?:v9\(\d+\)|v9+)?'
OPERAND = rf'(?:{NAME}|[+-]?\d+(?:\.\d+)?)'


def numeric(pic, sign):
    signed = pic.lower().startswith('s')
    require(bool(sign) == signed, 'signed fields require SIGN LEADING SEPARATE')
    integer = int(re.search(r'9\((\d+)\)', pic).group(1))
    fraction = pic.lower().split('v')[1] if 'v' in pic.lower() else ''
    scale = int(fraction[2:-1]) if '(' in fraction else len(fraction)
    require(1 <= integer <= 9 and 0 <= scale <= 6 and integer + scale <= 12, 'numeric PIC outside decimal subset bounds')
    return {'integer_digits': integer, 'scale': scale, 'signed': signed,
            'width': integer + scale + signed}


def extract(source, plan):
    require(plan['program']['source_format'] == 'fixed' and not plan['program']['copybooks'], 'decimal frontend requires fixed source without copybooks')
    require(plan['toolchains']['cobol']['version'] == '3.1.2.0' and set(plan['program']['compiler_flags']) <= {'-Wall'}, 'decimal profile requires GnuCOBOL 3.1.2.0 with only -Wall')
    require(plan['target']['language'] == 'python' and not plan['target']['dependencies'], 'standalone Python required')
    lines = []
    for line in source.splitlines():
        if not line.strip(): continue
        require(len(line) >= 7, 'invalid fixed source')
        if line[6] in '*/': continue
        require(line[6] == ' ' and not line[72:].strip(), 'unsupported fixed-format continuation')
        lines.append(line[7:72].strip())
    parts = re.split(r'("[^"\r\n]*"|\'[^\'\r\n]*\')', ' '.join(lines))
    text = ''.join(re.sub(r'\s+', ' ', value) if i % 2 == 0 else value for i, value in enumerate(parts))
    declaration = re.match(
        rf'identification division\. program-id\. ({NAME})\. environment division\. input-output section\. '
        rf'file-control\. select ({NAME}) assign to ({STRING}) organization is line sequential\. '
        rf'select ({NAME}) assign to ({STRING}) organization is line sequential\. '
        rf'data division\. file section\. fd ({NAME})\. 01 ({NAME})\. ', text, re.I)
    require(declaration is not None, 'unsupported decimal program declarations')
    program, input_name, input_path, output_name, output_path, input_fd, input_record = declaration.groups()
    require(input_name.lower() == input_fd.lower(), 'input FD mismatch')
    input_path, output_path = input_path[1:-1], output_path[1:-1]
    relative_path(input_path, 'decimal.input');relative_path(output_path, 'decimal.output')
    require(input_path != output_path and [v['sandbox_path'] for v in plan['execution']['inputs']] == [input_path]
            and plan['execution']['outputs'] == [output_path] and not plan['execution']['args']
            and 'stdin' not in plan['execution'], 'decimal execution contract mismatch')
    remaining = text[declaration.end():]
    fields, offset = [], 0
    while remaining.lower().startswith('05 '):
        f = re.match(rf'05 ({NAME}) pic ({NUMERIC})( sign leading separate)?\.\s*', remaining, re.I)
        require(f is not None, 'unsupported decimal input PIC')
        name, pic, sign = f.groups()
        field = {'name': name.lower(), 'offset': offset, **numeric(pic, sign)}
        fields.append(field);offset += field['width'];remaining = remaining[f.end():]
    require(fields and len({f['name'] for f in fields}) == len(fields), 'duplicate/empty input fields')
    output = re.match(rf'fd {re.escape(output_name)}\. 01 ({NAME})\. 05 ({NAME}) pic ({NUMERIC})( sign leading separate)?\. '
                      rf'05 ({NAME}) pic x\. working-storage section\. 01 ({NAME}) pic a value \'N\'\. '
                      rf'88 ({NAME}) value \'Y\'\. procedure division\. ', remaining, re.I)
    require(output is not None, 'unsupported decimal result/status/EOF declarations')
    output_record, result_name, pic, sign, status_name, switch, eof = output.groups()
    result = {'name': result_name.lower(), **numeric(pic, sign)}
    require(len({f['name'] for f in fields} | {result_name.lower(), status_name.lower(), switch.lower(), eof.lower()}) == len(fields) + 4,
            'duplicate data names')
    remaining = remaining[output.end():]
    flow = match(rf'{NAME}\. open input {re.escape(input_name)} output {re.escape(output_name)} '
                 rf'perform until {re.escape(eof)} read {re.escape(input_name)} at end set {re.escape(eof)} to true '
                 rf'not at end (.+?) write {re.escape(output_record)} end-read end-perform '
                 rf'close {re.escape(input_name)} {re.escape(output_name)} goback\. end program {re.escape(program)}\.', remaining)
    statements = flow[1]
    start = re.match(rf'move "N" to {re.escape(status_name)}\s+', statements, re.I)
    require(start is not None, 'status must be initialized to N per record')
    statements = statements[start.end():]
    operations = []
    names = {f['name'] for f in fields} | {result_name.lower()}
    def operand(value):
        literal = re.fullmatch(r'[+-]?\d+(?:\.\d+)?', value)
        require(value.lower() in names or (literal and sum(c.isdigit() for c in value) <= 18), 'unknown/oversized arithmetic operand')
        return value.lower()
    while statements.strip():
        statements = statements.strip()
        move = re.match(rf'move ({OPERAND}) to {re.escape(result_name)}(?:\s+|$)', statements, re.I)
        if move:
            operations.append({'op': 'move', 'a': operand(move[1]), 'rounded': False, 'size_error': False})
            statements = statements[move.end():];continue
        arithmetic = re.match(rf'(add|subtract) ({OPERAND}) (to|from) {re.escape(result_name)}( rounded)? '
                              rf'(on size error move "E" to {re.escape(status_name)} )?end-(add|subtract)(?:\s+|$)', statements, re.I)
        if arithmetic:
            op, value, direction, rounded, error, ending = arithmetic.groups()
            require(op.lower() == ending.lower() and direction.lower() == ('to' if op.lower() == 'add' else 'from'), 'arithmetic delimiter/direction mismatch')
            operations.append({'op': op.lower(), 'a': operand(value), 'rounded': bool(rounded), 'size_error': bool(error)})
            statements = statements[arithmetic.end():];continue
        compute = re.match(rf'compute {re.escape(result_name)}( rounded)? = ({OPERAND}) ([+*/-]) ({OPERAND}) '
                           rf'(on size error move "E" to {re.escape(status_name)} )?end-compute(?:\s+|$)', statements, re.I)
        require(compute is not None, 'unsupported arithmetic statement or expression')
        rounded, a, operator, b, error = compute.groups()
        if operator == '/':
            require(re.fullmatch(r'\+?\d+(?:\.\d+)?', b) and any(c in '123456789' for c in b), 'division requires a positive nonzero literal divisor')
        operations.append({'op': 'compute', 'a': operand(a), 'b': operand(b), 'operator': operator,
                           'rounded': bool(rounded), 'size_error': bool(error)})
        statements = statements[compute.end():]
    require(operations and operations[0]['op'] in ('move', 'compute') and len(operations) <= 16, 'initialize result each record; at most 16 operations')
    require(not operations[0]['size_error'], 'initialize result before a preserving SIZE ERROR handler')
    require(operations[0]['a'] != result_name.lower() and operations[0].get('b') != result_name.lower(), 'first operation cannot depend on prior record result')
    domain = plan['input_domain'];generator = domain.get('generator', {})
    require(domain['encoding'] == 'ascii' and domain.get('record_width_bytes') == offset
            and generator.get('kind') == 'fixed_records', 'ASCII implied-decimal fixed records required')
    generated_fields = generator.get('fields', [])
    require(len(generated_fields) == len(fields), 'generator must describe every numeric input field')
    for declared, generated in zip(fields, generated_fields):
        require(generated.get('type') == 'integer' and generated.get('offset') == declared['offset']
                and generated.get('width') == declared['width']
                and generated.get('sign') == ('leading' if declared['signed'] else 'none'),
                'generator must use scaled integer units matching each numeric PIC/sign')
    return {'schema_version': 1, 'frontend': 'strict-decimal-subset-v1',
            'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'serialization_profile': 'gnucobol-3.1.2-linux-display-decimal-v1',
            'input': {'name': input_name, 'path': input_path, 'width': offset, 'fields': fields},
            'output': {'name': output_name, 'path': output_path, 'result': result},
            'operations': operations}


def emit(ir):
    from .readable import decimal
    return decimal(ir)

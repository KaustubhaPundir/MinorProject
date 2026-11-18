"""Strict frontend and deterministic emitter for a small COBOL report subset.

This is not a general COBOL parser. Every supported section and reachable
statement is consumed; an unknown construct is an error, never guessed away.
"""
import hashlib
import re

from .manifest import PlanError, relative_path


def require(condition, message):
    if not condition:
        raise PlanError('Structured report: ' + message, 'unsupported')


def match(pattern, text):
    result = re.fullmatch(pattern, text.strip(), re.I)
    require(result is not None, 'unsupported syntax: ' + text[:100])
    return result


NAME = r'[a-z][a-z0-9-]*'
PIC = r'(?:9\(\d+\)|x\(\d+\)|9+|x+|zz9)'
STRING = r'"[^"\r\n]*"'


def width(pic):
    if '(' in pic:
        size = int(pic[pic.index('(') + 1:-1])
    else:
        size = len(pic)
    require(1 <= size <= 256, 'PIC width outside 1..256 bytes')
    return size


def extract(source, plan):
    require(plan['program']['source_format'] == 'fixed' and not plan['program']['copybooks'],
            'only fixed-format source without copybooks is supported')
    require(plan['toolchains']['cobol']['version'] == '3.1.2.0',
            'serialization profile requires GnuCOBOL 3.1.2.0')
    require(plan['target']['language'] == 'python', 'Python target required')
    require(set(plan['program']['compiler_flags']) <= {'-Wall'}, 'semantic compiler flags unsupported')
    require(not plan['target']['dependencies'], 'target dependencies unsupported')
    lines = []
    for line in source.splitlines():
        if not line.strip():
            continue
        require(len(line) >= 7, 'invalid fixed-format line')
        if line[6] in '*/':
            continue
        require(line[6] == ' ' and not line[72:].strip(), 'continuations/debug lines or text after column 72')
        lines.append(line[7:72].strip())
    text = ' '.join(lines)
    # Normalize separators without changing literal contents.
    pieces = re.split(r'("[^"\r\n]*"|\'[^\'\r\n]*\')', text)
    text = ''.join(re.sub(r'\s+', ' ', piece) if i % 2 == 0 else piece
                   for i, piece in enumerate(pieces))
    sections = re.split(r'\b(file section|working-storage section|report section|procedure division)\.', text, flags=re.I)
    require(len(sections) == 9, 'expected one file, working-storage, report and procedure section')
    prefix, _, files, _, working, _, report, _, procedure = sections
    declaration = match(
        rf'identification division\. program-id\. ({NAME})\. environment division\. '
        rf'input-output section\. file-control\. select ({NAME}) assign to ({STRING}) '
        rf'organization is line sequential\. select ({NAME}) assign to ({STRING})\. data division\.', prefix)
    program, input_name, input_path, output_name, output_path = declaration.groups()
    input_path, output_path = input_path[1:-1], output_path[1:-1]
    relative_path(input_path, 'structured.input')
    relative_path(output_path, 'structured.output')
    require(input_path != output_path, 'input and output must differ')
    require([v['sandbox_path'] for v in plan['execution']['inputs']] == [input_path]
            and plan['execution']['outputs'] == [output_path]
            and not plan['execution']['args'] and 'stdin' not in plan['execution'],
            'source file contract does not match manifest')
    f = match(rf'fd {re.escape(input_name)}\. 01 ({NAME})\. (.+?) fd {re.escape(output_name)} report is ({NAME})\.', files)
    record_name, fields_text, report_name = f.groups()
    fields, offset = [], 0
    while fields_text.strip():
        field = re.match(rf'\s*05 ({NAME}) pic ({PIC})\.', fields_text, re.I)
        require(field is not None, 'unsupported input field declaration')
        name, pic = field.groups()
        require(pic.lower() != 'zz9', 'edited input PIC unsupported')
        fields.append({'name': name.lower(), 'offset': offset, 'width': width(pic),
                       'numeric': pic.lower().startswith('9')})
        offset += width(pic)
        fields_text = fields_text[field.end():]
    require(fields and len({f['name'] for f in fields}) == len(fields), 'duplicate or empty input fields')
    w = match(rf"01 ({NAME}) pic a value 'N'\. 88 ({NAME}) value 'Y'\. 88 ({NAME}) value 'N'\.", working)
    switch, eof, _ = w.groups()
    r = match(rf'rd {re.escape(report_name)} page limit is (\d+) heading is (\d+) first detail (\d+) '
              rf'last detail (\d+) footing (\d+)\. 01 ({NAME}) type (report|page) heading\. (.+?) '
              rf'01 ({NAME}) type detail line plus 1\. (.+)', report)
    page, heading, first, last, footing = map(int, r.groups()[:5])
    _, heading_kind, headers_text, detail_name, details_text = r.groups()[5:]
    require(heading == 1 and 1 < first <= last < footing <= page <= 200, 'invalid or unsupported page bounds')
    domain = plan['input_domain']
    generator = domain.get('generator', {})
    require(domain.get('encoding') == 'ascii' and domain.get('record_width_bytes') == offset
            and generator.get('kind') == 'fixed_records'
            and generator.get('record_count', {}).get('max', 1000) <= 200,
            'requires an ASCII fixed-record domain with at most 200 records')
    headers = []
    blocks = re.split(r'05 line (\d+)\s*', headers_text, flags=re.I)
    require(not blocks[0].strip() and len(blocks) >= 3, 'unsupported heading')
    for index in range(1, len(blocks), 2):
        line_no, block = int(blocks[index]), blocks[index + 1].lstrip('. ')
        require(1 <= line_no < first, 'heading overlaps detail region')
        while block.strip():
            h = re.match(rf'\s*(?:10 )?column (\d+) pic ({PIC}) (?:value ({STRING})|source (page-counter))\.', block, re.I)
            require(h is not None, 'unsupported heading field')
            column, pic, literal, counter = h.groups()
            require((counter and pic.lower() == 'zz9') or (literal and pic.lower().startswith('x')),
                    'unsupported heading PIC/source')
            value = literal[1:-1] if literal else None
            if value is not None:
                require(value.isascii() and len(value) <= width(pic), 'heading value exceeds ASCII PIC')
            headers.append({'line': line_no, 'column': int(column), 'width': width(pic), 'literal': value})
            block = block[h.end():]
    details = []
    by_name = {f['name']: f for f in fields}
    while details_text.strip():
        d = re.match(rf'\s*05 column (\d+) pic ({PIC}) source ({NAME})\.', details_text, re.I)
        require(d is not None, 'unsupported detail field')
        column, pic, name = d.groups()
        field = by_name.get(name.lower())
        require(field is not None and width(pic) == field['width']
                and pic.lower().startswith('9') == field['numeric'], 'detail PIC/source mismatch')
        details.append({'column': int(column), 'field': name.lower(), 'width': width(pic)})
        details_text = details_text[d.end():]
    require(details, 'no detail fields')
    for group in ([h for h in headers if h['line'] == n] for n in range(1, first)):
        validate_columns(group)
    validate_columns(details)
    q = lambda name: re.escape(name)
    flow = match(
        rf'{NAME}\. display ({STRING}) move \'N\' to {q(switch)} '
        rf'open input {q(input_name)} output {q(output_name)} display ({STRING}) initiate {q(report_name)} '
        rf'perform until {q(eof)} read {q(input_name)} at end set {q(eof)} to true end-read '
        rf'display ({STRING}) generate {q(detail_name)} end-perform '
        rf'display ({STRING}) terminate {q(report_name)} close {q(input_name)} {q(output_name)} '
        rf'display ({STRING}) goback\. (.*?)end program {q(program)}\.', procedure)
    *messages, tail = flow.groups()
    # A single unreachable append paragraph is permitted only in this exact form.
    if tail.strip():
        match(rf'{NAME}\. open extend {q(input_name)} write {q(record_name)} close {q(input_name)} exit paragraph\.', tail)
    require(all(m[1:-1].isascii() for m in messages), 'non-ASCII DISPLAY unsupported')
    return {'schema_version': 1, 'frontend': 'strict-report-subset-v1',
            'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'serialization_profile': 'gnucobol-3.1.2-linux-report-v1',
            'input': {'name': input_name, 'path': input_path, 'record_width': offset, 'fields': fields},
            'output': {'name': output_name, 'path': output_path},
            'page': {'limit': page, 'first_detail': first, 'last_detail': last, 'footing': footing},
            'headers': headers, 'details': details, 'messages': [m[1:-1] for m in messages],
            'heading_kind': heading_kind.lower(),
            'control_flow': {'generate_after_read_at_end': True, 'retain_record_on_eof': True}}


def validate_columns(fields):
    occupied = set()
    for field in fields:
        start, size = field['column'], field['width']
        require(1 <= start and start + size <= 1025, 'column outside supported byte range')
        cells = set(range(start, start + size))
        require(not occupied & cells, 'overlapping report fields')
        occupied.update(cells)


def emit(ir):
    """Emit from extracted data only; no model, answers or reference invocation."""
    from .readable import report
    return report(ir)


def translate_structured(plan, suite, output, frontend='report'):
    from pathlib import Path
    from .generation import screen_candidate
    from .suites import verify_suite, new_root, check_suite, write
    suite, output = suite.resolve(), output.resolve()
    require(not output.is_relative_to(suite) and not suite.is_relative_to(output), 'suite/output overlap')
    seal, frozen, _, _ = verify_suite(suite)
    require(plan['contract_sha256'] == frozen['contract_sha256'], 'manifest differs from sealed suite')
    source_bytes = (suite / 'source/legacy.cbl').read_bytes()
    if frontend == 'decimal':
        from .structured_decimal import extract as extract_source, emit as emit_source
    elif frontend == 'console':
        from .structured_console import extract as extract_source, emit as emit_source
    else:
        require(frontend == 'report', 'unknown frontend')
        extract_source, emit_source = extract, emit
    ir = extract_source(source_bytes.decode('utf-8'), frozen)
    ir['source_sha256'] = hashlib.sha256(source_bytes).hexdigest()
    code = emit_source(ir)
    require(not screen_candidate(code), 'emitted candidate failed independence screening')
    root = new_root(output)
    write(root / 'ir.json', ir)
    artifact = root / 'candidate' / plan['target']['entrypoint']
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(code.encode())
    result = check_suite(suite, artifact, root / 'validation')
    report = {'schema_version': 1, 'outcome': 'awaiting_acceptance' if result['outcome'] == 'regression_match' else result['outcome'],
              'accepted': False, 'suite_id': seal['suite_id'], 'contract_sha256': plan['contract_sha256'],
              'provenance': {'method': 'deterministic_structured_' + frontend, 'model_calls': 0,
                             'source_sha256': ir['source_sha256'],
                             'ir_sha256': hashlib.sha256((root / 'ir.json').read_bytes()).hexdigest(),
                             'serialization_profile': ir['serialization_profile']},
              'candidate': {'path': str(artifact), 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()},
              'regression': {'outcome': result['outcome'], 'completed': result.get('completed', 0),
                             'failed_cases': sum(c['outcome'] != 'match' for c in result.get('cases', []))},
              'claim': 'Structured ' + frontend + ' subset translation, not LLM-generation success. Held-out acceptance has not run.'}
    if 'diagnostics' in result:
        report['diagnostics'] = result['diagnostics']
        report['observed'] = result.get('observed', {})
    require(verify_suite(suite)[0] == seal, 'suite changed during structured translation')
    write(root / 'report.json', report)
    return report

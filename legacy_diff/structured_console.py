"""Bounded literal DISPLAY console subset, with no input or file operations."""
import hashlib
import json
import re

from .structured_report import require

LITERAL = r'''(?:"(?:[^"\r\n]|"")*"|'(?:[^'\r\n]|'')*')'''


def source_format(source):
    fixed = False
    for line in source.splitlines():
        if not line.strip() or line.lstrip().startswith('*>'): continue
        prefix = line[:6].strip()
        if len(line) < 7 or (prefix and not prefix.isdigit()) or line[6] not in ' */-dD':
            return 'free'
        fixed = True
    return 'fixed' if fixed else 'free'


def extract(source, plan):
    require(not plan['program']['copybooks'] and set(plan['program']['compiler_flags']) <= {'-Wall'}, 'console copybooks/compiler flags unsupported')
    require(plan['toolchains']['cobol']['version'] == '3.1.2.0', 'console profile requires GnuCOBOL 3.1.2.0')
    require(plan['target']['language'] == 'python' and not plan['target']['dependencies'], 'standalone Python required')
    require(not plan['execution']['inputs'] and not plan['execution']['outputs'] and not plan['execution']['args']
            and 'stdin' not in plan['execution'] and plan['input_domain']['generator']['kind'] == 'none', 'console literal programs consume no input')
    lines = []
    for line in source.splitlines():
        if not line.strip(): continue
        if plan['program']['source_format'] == 'fixed':
            require(len(line) >= 7, 'invalid fixed console source')
            if line[6] in '*/': continue
            require(line[6] == ' ' and not line[72:].strip(), 'console continuations or text beyond column 72 unsupported')
            line = line[7:72]
        # Remove inline comments only outside literals.
        pieces = re.split('(' + LITERAL + ')', line)
        clean = ''
        for index, piece in enumerate(pieces):
            if index % 2 == 0 and '*>' in piece:
                clean += piece.split('*>', 1)[0]; break
            clean += piece
        lines.append(clean.strip())
    text = ' '.join(lines)
    header = re.match(r'(?:identification|id) division\.\s*program-id\.\s*([a-z][a-z0-9-]*)\.\s*(?:data division\.\s*)?procedure division\.\s*', text, re.I)
    require(header is not None, 'expected a simple console PROGRAM-ID and PROCEDURE DIVISION')
    remaining = text[header.end():].strip()
    paragraph = re.match(r'(?!display\b|stop\b|goback\b|move\b)[a-z][a-z0-9-]*\.\s*', remaining, re.I)
    if paragraph: remaining = remaining[paragraph.end():]
    displays = []
    while re.match(r'display\b', remaining, re.I):
        statement = re.match(r'display\s+(' + LITERAL + r'(?:\s+' + LITERAL + r')*)(\s+with no advancing)?\s*\.?\s*', remaining, re.I)
        require(statement is not None, 'console DISPLAY supports ASCII literals only')
        literals = re.findall(LITERAL, statement[1])
        value = ''.join(item[1:-1].replace(item[0] * 2, item[0]) for item in literals)
        require(value.isascii() and '\x00' not in value and len(value) <= 512, 'console literal outside bounds')
        displays.append({'text': value, 'newline': not bool(statement[2])})
        remaining = remaining[statement.end():].strip()
    exit_code = 0
    code = re.match(r'move\s+(\d+)\s+to\s+return-code\s*\.?\s*', remaining, re.I)
    if code: exit_code = int(code[1]); remaining = remaining[code.end():]
    require(0 <= exit_code <= 255, 'console RETURN-CODE must be 0..255')
    terminal = re.fullmatch(r'(?:stop run|goback)\s*\.\s*(?:end program\s+' + re.escape(header[1]) + r'\s*\.)?\s*', remaining, re.I)
    require(terminal is not None and 1 <= len(displays) <= 64, 'only literal DISPLAYs followed by STOP RUN/GOBACK are supported')
    return {'schema_version': 1, 'frontend': 'strict-console-subset-v1',
            'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'serialization_profile': 'gnucobol-3.1.2-linux-console-v1', 'displays': displays, 'exit_code': exit_code}


def emit(ir):
    lines = ['import sys', ''] if ir['exit_code'] else []
    for item in ir['displays']:
        literal = json.dumps(item['text'], ensure_ascii=True)
        options = '' if item['newline'] else ', end=""'
        lines.append(f'print({literal}{options})')
    if ir['exit_code']:
        lines.extend(['', f'sys.exit({ir["exit_code"]})'])
    return '\n'.join(lines) + '\n'

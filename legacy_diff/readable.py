"""Emit direct Python statements from validated report and decimal IR."""


def variable(name):
    return 'field_' + name.lower().replace('-', '_')


def missing_input(ir):
    name, path = ir['input']['name'], ir['input']['path']
    return ("libcob: error: READ/START not allowed, file not open for input (status = 47) for file "
            + name + " ('" + path.replace('.', '_') + "' => " + path + ")\n"
            + "libcob: warning: implicit CLOSE of " + ir['output']['name'] + " ('" + ir['output']['path'] + "')\n")


def report(ir):
    page = ir['page']; fields = {f['name']: f for f in ir['input']['fields']}
    initial = b''.join((b'0' if f['numeric'] else b' ') * f['width'] for f in fields.values())
    lines = ["import sys", "from pathlib import Path", "", "",
             "def write_at(row, column, value):", "    end = column - 1 + len(value)",
             "    row.extend(b' ' * max(0, end - len(row)))", "    row[column - 1:end] = value", "", "",
             "def main():", f"    print({ir['messages'][0]!r})", "    try:",
             f"        data = Path({ir['input']['path']!r}).read_bytes()", "    except FileNotFoundError:",
             f"        Path({ir['output']['path']!r}).write_bytes(b'')", f"        print({ir['messages'][1]!r})",
             f"        sys.stderr.write({missing_input(ir)!r})", "        return 1",
             f"    print({ir['messages'][1]!r})", "    records = data.split(b'\\n')",
             "    if records and records[-1] == b'':", "        records.pop()",
             f"    current_record = {initial!r}", "    pages = []", "    page_number = 0", "    lines = []",
             f"    line_number = {page['last_detail'] + 1}", "    for index in range(len(records) + 1):",
             "        if index < len(records):", f"            current_record = records[index].rstrip(b'\\r')[:{ir['input']['record_width']}].ljust({ir['input']['record_width']}, b' ')",
             f"        if line_number > {page['last_detail']}:", "            if lines:",
             "                # The pinned COBOL runtime consumes the boundary line between pages.",
             "                pages.extend(bytes(row).rstrip(b' ') for row in lines[:-1])",
             "            page_number += 1", f"            lines = [bytearray() for _ in range({page['limit']})]"]
    indent = '            '
    if ir['heading_kind'] == 'report':
        lines.append('            if page_number == 1:'); indent += '    '
    for header in ir['headers']:
        value = repr(header['literal'].ljust(header['width']).encode('ascii')) if header['literal'] is not None else f"str(page_number).rjust({header['width']}).encode('ascii')"
        lines.append(f"{indent}write_at(lines[{header['line'] - 1}], {header['column']}, {value})")
    if not ir['headers'] and ir['heading_kind'] == 'report': lines.append(indent + 'pass')
    lines += [f"            line_number = {page['first_detail']}", f"        print({ir['messages'][2]!r})"]
    for detail in ir['details']:
        field = fields[detail['field']]; name = variable(field['name'])
        expression = f"current_record[{field['offset']}:{field['offset'] + field['width']}]"
        if field['numeric']: expression += ".replace(b' ', b'0')"
        lines += [f"        {name} = {expression}", f"        write_at(lines[line_number - 1], {detail['column']}, {name})"]
    lines += ["        line_number += 1", "    pages.extend(bytes(row).rstrip(b' ') for row in lines)",
              f"    print({ir['messages'][3]!r})", f"    Path({ir['output']['path']!r}).write_bytes(b'\\n'.join(pages) + b'\\n')",
              f"    print({ir['messages'][4]!r})", "    return 0", "", "", "if __name__ == '__main__':", "    sys.exit(main())", ""]
    return '\n'.join(lines)


DECIMAL_HELPERS = '''
def decode_display(raw, signed, scale):
    sign = -1 if signed and raw[:1] == b'-' else 1
    digits = raw[1:] if signed else raw
    # Preserve the pinned GnuCOBOL runtime's malformed DISPLAY behavior.
    if digits[:1] == b'\\xff':
        return Decimal(10 ** len(digits)).scaleb(-scale)
    if digits[:1] == b'\\x00':
        return -Decimal(10 ** len(digits)).scaleb(-scale)
    magnitude = 0
    for byte in digits:
        magnitude = (magnitude * 10 + byte - 48) % (1 << 64)
    return Decimal(sign * magnitude).scaleb(-scale)


def move_display(raw, sender_digits, sender_scale, sender_signed, receiver_digits, receiver_scale, receiver_signed):
    sign = b'-' if sender_signed and raw[:1] == b'-' else b'+'
    digits = raw[1:] if sender_signed else raw
    integer = digits[:sender_digits][-receiver_digits:].rjust(receiver_digits, b'0')
    fraction = digits[sender_digits:][:receiver_scale].ljust(receiver_scale, b'0')
    return (sign if receiver_signed else b'') + integer + fraction
'''


def decimal(ir):
    target = ir['output']['result']; digits = target['integer_digits'] + target['scale']
    fields = {f['name']: f for f in ir['input']['fields']}; all_fields = {**fields, target['name']: target}
    receiver = f"{target['integer_digits']}, {target['scale']}, {target['signed']}"
    lines = ['import sys', 'from pathlib import Path', 'from decimal import Decimal, localcontext, ROUND_DOWN, ROUND_HALF_UP', '',
             DECIMAL_HELPERS, '', 'def main():', '    try:', f"        data = Path({ir['input']['path']!r}).read_bytes()",
             '    except FileNotFoundError:', f"        Path({ir['output']['path']!r}).write_bytes(b'')",
             f"        sys.stderr.write({missing_input(ir)!r})", '        return 1',
             "    records = data.split(b'\\n')", '    if records and not records[-1]:', '        records.pop()',
             f"    quantum = Decimal(1).scaleb(-{target['scale']})", f"    factor = Decimal(10) ** {target['scale']}",
             f"    modulus = {10 ** digits}", '    output = []',
             f"    result_raw = {((b'+' if target['signed'] else b'') + b'0' * digits)!r}",
             '    with localcontext() as context:', '        context.prec = 64', '        for record in records:',
             f"            record = record.rstrip(b'\\r')[:{ir['input']['width']}].ljust({ir['input']['width']}, b' ')"]
    for name, field in fields.items():
        var = variable(name)
        lines += [f"            raw_{var} = record[{field['offset']}:{field['offset'] + field['width']}]",
                  f"            {var} = decode_display(raw_{var}, {field['signed']}, {field['scale']})"]
    lines.append("            status = b'N'")
    def operand(name):
        if name == target['name']: return f"decode_display(result_raw, {target['signed']}, {target['scale']})"
        return variable(name) if name in fields else f'Decimal({name!r})'
    for operation in ir['operations']:
        op, a = operation['op'], operation['a']
        if op == 'move' and a in all_fields:
            sender = all_fields[a]; raw = 'result_raw' if a == target['name'] else 'raw_' + variable(a)
            lines.append(f"            result_raw = move_display({raw}, {sender['integer_digits']}, {sender['scale']}, {sender['signed']}, {receiver})")
            continue
        if op == 'move': expression = operand(a)
        elif op in ('add', 'subtract'):
            expression = f"{operand(target['name'])} {'+' if op == 'add' else '-'} {operand(a)}"
        else: expression = f"{operand(a)} {operation['operator']} {operand(operation['b'])}"
        lines += [f'            computed = {expression}',
                  f"            assigned = computed.quantize(quantum, rounding={'ROUND_HALF_UP' if operation['rounded'] else 'ROUND_DOWN'})",
                  '            units = int(abs(assigned) * factor)']
        indent = '            '
        if operation['size_error']:
            lines += ['            if units >= modulus:', "                status = b'E'", '            else:']; indent += '    '
        sign = "(b'-' if assigned < 0 else b'+')" if target['signed'] else "b''"
        lines += [indent + 'units %= modulus', indent + f"result_raw = {sign} + str(units).zfill({digits}).encode('ascii')"]
    lines += ['            output.append(result_raw + status)',
              f"    Path({ir['output']['path']!r}).write_bytes(b'\\n'.join(output) + (b'\\n' if output else b''))",
              '    return 0', '', '', "if __name__ == '__main__':", '    sys.exit(main())', '']
    return '\n'.join(lines)

"""Human-authored diagnostic control, never evidence of AI generation success.

Implements this example's declared 0..3 ASCII fixed-record input domain.
No reference executable, suite, or expected-output tables are consulted.
"""
from pathlib import Path


def main():
    print('Starting test report program.')
    data = Path('input.txt').read_bytes()
    print('Init test report.')
    records = data.splitlines()
    last = b'000000' + b' ' * 23 + b'00'
    lines = [b' ' * 43 + b'Customer Order Report', b' ' * 99 + b'PAGE   1', b'', b'', b'']
    for index in range(len(records) + 1):
        if index < len(records):
            last = records[index][:31].ljust(31, b' ')
        print('Generate report line.')
        row = bytearray(b' ' * 47)
        for column, value in ((4, last[:6]), (15, last[6:26]), (40, last[26:29]), (46, last[29:31])):
            row[column - 1:column - 1 + len(value)] = value
        lines.append(bytes(row).rstrip(b' '))
    print('Terminate report.')
    lines.extend([b''] * max(0, 66 - len(lines)))
    Path('report.txt').write_bytes(b'\n'.join(lines) + b'\n')
    print('Done.')


if __name__ == '__main__':
    main()

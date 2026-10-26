"""Refresh regression cells in the statistical-table source from CSV outputs."""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'extended_analysis/full_statistical_outputs.tex'
MAPPING = {1: 2, 3: 11, 5: 10, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7}


def stars(p):
    return '***' if p < .001 else '**' if p < .01 else '*' if p < .05 else ''


def main():
    table = 0
    row_index = 0
    rows = []
    output = []
    for line in PATH.read_text().splitlines():
        if line.startswith(r'\caption{'):
            table += 1
            row_index = 0
            rows = []
            if table in MAPPING:
                with (ROOT / f'outputs/tables/table_s{MAPPING[table]}.csv').open() as f:
                    rows = list(csv.DictReader(f))
        if rows and ' & ' in line:
            label = line.split(' & ')[0]
            if label.startswith(('(Intercept)', 'Projected Warming', 'Unit Condition', 'Warming $', 'Republican (')):
                row = rows[row_index]
                row_index += 1
                value = lambda key: float(row[key])
                decimals = 2 if table == 3 else 3
                cells = [label, f'{value("estimate"):.{decimals}f}' + stars(value('p.value')),
                         f'{value("std.error"):.{decimals}f}']
                if table in (6, 7, 8, 9, 10):
                    cells.append(f'{value("statistic"):.3f}')
                cells.append(f'$[{value("conf.low"):.2f}, {value("conf.high"):.2f}]$')
                if table in (6, 7, 8, 9, 10):
                    cells.append('$<0.001$' if value('p.value') < .001 else f'{value("p.value"):.3f}')
                line = ' & '.join(cells) + r' \\'
        output.append(line)
    assert table == 12
    with (ROOT / 'outputs/tables/table_s9.csv').open() as f:
        parties = list(csv.DictReader(f))
    ci = 'Intercept 95\\% CI & ' + ' & '.join(
        f'$[{float(row["Intercept CI low"]):.2f}, {float(row["Intercept CI high"]):.2f}]$'
        for row in parties
    ) + r' \\'
    output = [ci if line.startswith('Intercept 95\\% CI & ') else line for line in output]
    PATH.write_text('\n'.join(output) + '\n')


if __name__ == '__main__':
    main()

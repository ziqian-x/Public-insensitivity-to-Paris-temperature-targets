"""Generate all twelve statistical tables from machine-readable analysis outputs."""
import argparse
import csv
import math
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'extended_analysis/full_statistical_outputs.tex'
MODELS = ['MPNet-Base', 'MiniLM-L6', 'E5-Large', 'BGE-Large', 'Mxbai-Large']
TERMS = {
    '(Intercept)': 'Intercept', 'temp_numeric_c': r'Projected warming ($^\circ$C)',
    'temp_numeric': r'Projected warming ($^\circ$C)',
    'temp_centered_c': 'Projected warming (centered)',
    'unit_conditionF': 'Fahrenheit (vs. Celsius)',
    'temp_centered_c:unit_conditionF': r'Warming $\times$ Fahrenheit',
    'party_binaryRepublican': 'Republican (vs. Democrat)',
    'temp_numeric_c:party_binaryRepublican': r'Warming $\times$ Republican',
}

def read(number):
    with (ROOT / f'outputs/tables/table_s{number}.csv').open() as f:
        return list(csv.DictReader(f))


def num(value, digits=3):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f'Nonfinite table cell: {value}')
    return f'{value:.{digits}f}'


def pval(value):
    return r'$<0.001$' if float(value) < .001 else num(value)


def row(cells):
    return ' & '.join(map(str, cells)) + r' \\'


def heading(title):
    return r'\captionof{table}{' + title + r'}\label{tab:' + str(len(TITLES)+1) + '}\n'


TITLES = []

def table(title, headers, rows, note, spec=None):
    prefix = heading(title)
    TITLES.append(title)
    n = len(headers)
    spec = spec or ('X' + 'r' * (n-1))
    return prefix + '\n'.join([
        r'\begingroup\small',
        r'\begin{tabularx}{\textwidth}{@{}' + spec + r'@{}}',
        r'\toprule', row(headers), r'\midrule', *[row(r) for r in rows],
        r'\bottomrule\end{tabularx}', r'\par\smallskip',
        r'{\footnotesize\textit{Note.} ' + note + r'\par}',
        r'\endgroup\bigskip', '',
    ])


def regression(number, title, note):
    data = read(number)
    if len({(r['N'], r['R_squared'], r['adjusted_R_squared']) for r in data}) != 1:
        raise ValueError('Inconsistent model-fit fields')
    rows = [[TERMS[r['term']], num(r['estimate']), num(r['std.error']),
             num(r['statistic']), f'[{num(r["conf.low"],2)}, {num(r["conf.high"],2)}]',
             pval(r['p.value'])] for r in data]
    fit = data[0]
    rows += [['Observations', str(int(float(fit['N']))), '', '', '', ''],
             [r'$R^2$', num(fit['R_squared']), '', '', '', ''],
             [r'Adjusted $R^2$', num(fit['adjusted_R_squared']), '', '', '', '']]
    return table(title, ['Predictor', r'$b$', 'SE', r'$t$', r'95\% CI', r'$p$'], rows,
                 'Unstandardized OLS coefficients; two-sided tests and 95\% confidence intervals. ' + note)


def generate():
    TITLES.clear()
    text = r'''\documentclass[11pt,a4paper]{article}
\usepackage[margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{times,booktabs,tabularx,longtable,caption,hyperref}
\usepackage{setspace}
\setstretch{1.1}
\captionsetup{labelfont=bf,textfont=rm,labelsep=period,justification=raggedright,singlelinecheck=false}
\renewcommand{\thetable}{\arabic{table}}
\setlength{\tabcolsep}{4pt}
\setlength{\parindent}{0pt}
\begin{document}
\begin{center}
{\Large\bfseries Statistical Tables}\\[0.5em]
Public Insensitivity to the Paris Temperature Targets\\[0.5em]
Ziqian Xia, Rachit Dubey, and Sara M. Constantino
\end{center}
\bigskip
'''
    text += regression(2, 'Main-study regression of the Worry Index on projected warming.',
                       'The Worry Index averages three 0--100 items. Warming is in Celsius-equivalent units.')
    pairs = read(8)
    if len(pairs) != 45 or len({(r['Group1'],r['Group2']) for r in pairs}) != 45:
        raise ValueError('Expected 45 unique contrasts')
    text += '\\clearpage\n' + heading("Pairwise comparisons across warming levels with Holm correction.")
    TITLES.append('Pairwise comparisons')
    text += r'''\begingroup\small\setstretch{1.0}
\setlength{\LTleft}{\fill}\setlength{\LTright}{\fill}
\begin{longtable}{@{}rrrrrrrr@{}}
\toprule
Group 1 & Group 2 & $N_1$ & $N_2$ & $t$ & df & $p$ & $p_{\mathrm{Holm}}$\\
\midrule\endfirsthead
\multicolumn{8}{l}{Table 2 (continued)}\\
\toprule
Group 1 & Group 2 & $N_1$ & $N_2$ & $t$ & df & $p$ & $p_{\mathrm{Holm}}$\\
\midrule\endhead
\bottomrule\endfoot
'''
    for r in pairs:
        text += row([r['Group1'], r['Group2'], r['N1'], r['N2'], num(r['t'],4), num(r['df'],4),
                     pval(r['p']), pval(r['p_adj'])])+'\n'
    text += r'''\end{longtable}
{\footnotesize\textit{Note.} Warming levels are in Celsius-equivalent units, pooling the Celsius and Fahrenheit conditions. Two-sided Welch tests; Holm correction across all 45 contrasts.\par}
\endgroup\clearpage
'''
    center = num(read(11)[0]['centering_value'])
    text += regression(11, 'Interaction between projected warming and unit framing.',
                       'Warming is centered at the main-sample mean (' + center + r'$^\circ$C). Celsius is the reference unit.')
    emb = read(12)
    lookup = {(r['Model'],r['Version']):r for r in emb}
    if len(lookup) != 10 or len(emb) != 10:
        raise ValueError('Expected ten unique embedding results')
    rows=[]
    for m in MODELS:
        for version in ['RAW','CLEAN']:
            r=lookup[m,version]
            rows.append([m,version.title(),num(r['Within_Mean'],5),num(r['Between_Mean'],5),
                         num(r['Delta_Obs'],5),pval(r['P_Value'])])
    text += table('Semantic similarity across five embedding models.',
                  ['Model','Input','Within','Between',r'$\Delta$',r'$p$'], rows,
                  r'$N=986$. $\Delta$ is mean within-condition minus between-condition cosine similarity. Two-sided permutation tests use 1,000 label permutations (seed 123); $p$-values are unadjusted. Clean input removes numeric and temperature cues as described in SI Section S5.')
    text += '\\clearpage\n'
    text += regression(10, 'Interaction between projected warming and political party.',
                       'Democrats are the reference group. Self-identified partisans are coded directly; Independents, Other party, and No preference respondents are classified using the leaning question. Respondents without a Democratic or Republican affiliation or lean are excluded. Table 11 reports separate within-party fits.')
    text += '\\clearpage\n'
    text += regression(3, 'Pilot 1: regression of worry on projected warming.', 'Worry uses a 1--7 scale; warming is in $^\circ$C.')
    text += regression(4, 'Pilot 2: regression of worry on projected warming.', 'Worry uses a 0--100 scale; warming is in $^\circ$C.')
    text += '\\clearpage\n'
    for n,title in [(5,'worry about assigned warming'),(6,'harm to people in the United States'),(7,'personal harm')]:
        text += regression(n,'Main-study item-level regression: '+title+'.',
                           'The outcome uses a 0--100 scale; warming is in Celsius-equivalent units. Each item is fitted separately on the main analytic sample.')
    text += '\\clearpage\n'
    parties=read(9)
    if [r['Party'] for r in parties] != ['Democrat','Republican']:
        raise ValueError('Unexpected party order')
    rows=[]
    for r in parties:
        rows.append([r'\textit{'+r['Party']+'}', '', '', '', '', ''])
        for key,se,t,p,lo,hi in [('Intercept','Intercept SE','Intercept t','Intercept p','Intercept CI low','Intercept CI high'),
                               ('Projected warming','Projected warming SE','Projected warming t','p-value','Projected warming CI low','Projected warming CI high')]:
            rows.append([key,num(r[key]),num(r[se]),num(r[t]),f'[{num(r[lo],2)}, {num(r[hi],2)}]',pval(r[p])])
        rows += [['Observations',r['N'],'','','',''],[r'$R^2$',num(r['R-squared']),'','','',''],
                 [r'Adjusted $R^2$',num(r['Adjusted R-squared']),'','','','']]
    text += table('Within-party regressions of the Worry Index on projected warming.',
                  ['Predictor',r'$b$','SE',r'$t$',r'95\% CI',r'$p$'],rows,
                  'Separate OLS models within party, including leaners. Warming is in Celsius-equivalent units. Each fit estimates its own residual variance; its standard errors need not equal those in the pooled interaction model (Table 5).')
    text += '\\clearpage\n'
    sens=read(13); a=[r for r in sens if r['panel']=='A']; b=[r for r in sens if r['panel']=='B']
    if len(a)!=1 or len(b)!=10: raise ValueError('Unexpected sensitivity results')
    rows=[]
    for prefix,label in [('full','Full sample'),('exclusion','Excluding matched accounts')]:
        r=a[0]; rows.append([label,r[prefix+'_N'],num(r[prefix+'_estimate']),num(r[prefix+'_SE']),pval(r[prefix+'_p']),num(r[prefix+'_R_squared'])])
    text+=table('Sensitivity analyses excluding accounts matched to the post hoc LLM-check export.',
                ['Sample',r'$N$',r'$b$','SE',r'$p$',r'$R^2$'], rows,
                'Primary OLS regression of the Worry Index on warming. Archived aggregate results after excluding 19 matched accounts; reproducing the exclusion requires the nonpublic participant-level classification.')
    lookup={(r['model'],r['input']):r for r in b}
    text+=r'\textbf{Table 12 (continued). Embedding sensitivity}\par\smallskip'+'\n'
    text+=r'\begingroup\small\begin{tabularx}{\textwidth}{@{}Xlrrrr@{}}\toprule'+'\n'
    text+=row(['Model','Input',r'Full $\Delta$',r'Full $p$',r'Exclusion $\Delta$',r'Exclusion $p$'])+'\n\\midrule\n'
    for m in MODELS:
        for v in ['Raw','Clean']:
            r=lookup[m,v]
            text+=row([m,v,num(r['full_estimate'],5),pval(r['full_p']),num(r['exclusion_estimate'],5),pval(r['exclusion_p'])])+'\n'
    text+=r'''\bottomrule\end{tabularx}
\par\smallskip{\footnotesize\textit{Note.} Full sample: $N=986$; exclusion sample: $N=967$. $\Delta$ is within-condition minus between-condition cosine similarity. Two-sided permutation tests use 1,000 label permutations (seed 123); $p$-values are unadjusted.\par}
\endgroup
\end{document}
'''
    assert len(TITLES)==12
    return text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',help='Check source against all CSV outputs without writing')
    parser.add_argument('--compile',action='store_true',help='Compile PDF with latexmk')
    args=parser.parse_args()
    source=generate()
    if args.check:
        if PATH.read_text()!=source: raise SystemExit('Statistical-table source is stale')
        print('All twelve table sources match CSV outputs.')
    else:
        PATH.write_text(source)
    if args.compile:
        with tempfile.TemporaryDirectory(prefix='statistical-tables-') as build:
            subprocess.run(['latexmk','-pdf','-interaction=nonstopmode','-halt-on-error',
                            '-outdir='+build,PATH.name],cwd=PATH.parent,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            log=(Path(build)/'full_statistical_outputs.log').read_text()
            if 'Overfull \\hbox' in log or 'Overfull \\vbox' in log:
                raise RuntimeError('Statistical tables overflow; inspect LaTeX layout')
            PATH.with_suffix('.pdf').write_bytes((Path(build)/'full_statistical_outputs.pdf').read_bytes())

if __name__=='__main__':
    main()

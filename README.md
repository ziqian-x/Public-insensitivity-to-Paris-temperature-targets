# Public insensitivity to the Paris temperature targets

Data and analysis code for the main study (N = 986), Pilot 1 (N = 493), and Pilot 2 (N = 498).

## Run the analyses

Tested with R 4.5.2 and Python 3.9.6. Install the R packages listed in `r-package-versions.csv` and the Python dependencies:

```bash
python3 -m pip install -r requirements-lock.txt
Rscript run_all.R
```

The report is written to `outputs/reports/Main_SI_All.html`; figures and CSV tables are in `outputs/`. R Markdown requires Pandoc.

The default text analysis uses archived embedding results. To recompute all five models with 1,000 permutations:

```bash
python3 text_embedding/run_text_embedding.py --recompute --n-perm 1000
Rscript run_all.R
```

Model revisions are listed in `text_embedding/model_revisions.csv`.

## Files

- `data/`: analysis data for the three studies, with participant identifiers removed.
- `Main_SI_All.Rmd`: scalar analyses and Figure 1.
- `text_embedding/`: text analysis and Figure 2.
- `extended_analysis/`: statistical tables and their LaTeX source.
- `scripts/`: data preparation, table export, and numerical checks.
- `validation/`: R session information.

The CSV table numbering predates the final SI; `extended_analysis/README.md` maps the files to the statistical tables. The final SI contains Methods Sections S1-S6.

Post hoc Prolific LLM-check sensitivity results are provided as aggregates in `outputs/tables/table_s13.csv`. The participant-level classification is not public, so that exclusion analysis cannot be reconstructed from these files alone.

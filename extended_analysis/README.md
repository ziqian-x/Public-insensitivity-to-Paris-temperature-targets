# Statistical tables

`full_statistical_outputs.pdf` contains Tables 1-12. Run `Rscript run_all.R` from the repository root to regenerate the analyses and this PDF. To rebuild only the tables from existing CSV outputs, run `python3 scripts/sync_statistical_tables.py --compile`.

Tables 1, 3, and 5-11 report unstandardized coefficients, standard errors, t-statistics, 95% confidence intervals, p-values, sample sizes, and model fit. Table 2 reports Welch tests and Holm-adjusted p-values across 45 contrasts; its CSV also includes signed Cohen's d. Table 12 contains archived sensitivity summaries.

CSV files corresponding to each table are listed below:

| PDF table | Analysis | CSV in `outputs/tables/` |
| --- | --- | --- |
| 1 | Main regression | `table_s2.csv` |
| 2 | Pairwise comparisons | `table_s8.csv` |
| 3 | Unit interaction | `table_s11.csv` |
| 4 | Embedding results | `table_s12.csv` |
| 5 | Party interaction | `table_s10.csv` |
| 6 | Pilot 1 | `table_s3.csv` |
| 7 | Pilot 2 | `table_s4.csv` |
| 8 | Worry item | `table_s5.csv` |
| 9 | Harm to US people | `table_s6.csv` |
| 10 | Personal harm | `table_s7.csv` |
| 11 | Within-party regressions | `table_s9.csv` |
| 12 | Post hoc sensitivity | `table_s13.csv` |

`table_s1.csv` reports participant flow. The journal SI contains Methods Sections S1-S6 rather than these statistical tables.

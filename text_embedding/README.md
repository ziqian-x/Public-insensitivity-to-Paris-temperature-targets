# Text analysis

From the repository root:

```bash
python3 text_embedding/run_text_embedding.py
```

This generates Figure 2 and `outputs/tables/table_s12.csv` from the archived results for 986 responses.

To recompute embeddings and permutation tests:

```bash
python3 text_embedding/run_text_embedding.py --recompute --n-perm 1000
```

The script uses the model revisions in `model_revisions.csv` and seed 123. Fresh runs can have small numerical differences across hardware and library versions.

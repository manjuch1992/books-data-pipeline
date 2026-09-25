# Data pipeline artifact layout

Run `python data_pipeline/data_pipeline.py` from the repository root. It creates:

- `books_cleaned_final.csv`
- `books_database.db`
- all SQL query files and CSV outputs in `query_outputs/`

The generator uses the repository's existing `raw_books.csv` and cleaning logic,
so the generated artifacts are reproducible and remain consistent with the
original pipeline.

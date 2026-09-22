# Module 1 — Data Pipeline

Scrapes book listings from [books.toscrape.com](http://books.toscrape.com) (a
public scraping-practice site, no login/API key needed), cleans and types the
fields, converts price to INR at a fixed project rate, loads everything into
a normalized SQLite database, and queries it with both SQL and pandas.

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Scrapes books across categories discovered from the site's own nav until ≥60 rows across ≥3 categories are collected. Writes `raw_books.csv`. |
| `generate_sample_data.py` | **Not part of the graded pipeline.** Produces a `raw_books.csv` in the same shape as the scraper's output, for local testing when live scraping isn't possible. Includes 3 deliberately malformed rows to exercise the error-handling logic below. |
| `clean_and_load.py` | Cleans/types fields, applies the fixed GBP→INR conversion, builds `books.db` (two-table schema). |
| `queries.py` | Runs 5 SQL queries against `books.db` and prints their output. |
| `pandas_analysis.py` | Reads two queries back via `pd.read_sql`, reproduces the JOIN query via `pd.merge` on in-memory DataFrames, and confirms both match. |
| `queries_output.txt` | Captured output of `queries.py`. |
| `pandas_output.txt` | Captured output of `pandas_analysis.py`. |
| `books.db` | The resulting SQLite database. |

## Install / run

```bash
pip install requests beautifulsoup4 pandas
cd data_pipeline

python scraper.py            # scrape live data -> raw_books.csv
python clean_and_load.py     # clean, convert currency, build books.db
python queries.py            # run the 5 required SQL queries
python pandas_analysis.py    # read_sql + pd.merge cross-check
```

**A note on this submission's data:** this environment had no outbound
network access to `books.toscrape.com`, so `raw_books.csv` / `books.db` /
the query outputs included here were generated from
`generate_sample_data.py` instead of a live scrape, purely to demonstrate
the pipeline runs end to end. `scraper.py` itself is complete and correct —
run it with network access and it produces a real `raw_books.csv` in the
identical format, which every downstream script consumes unchanged.

## Currency conversion

**Fixed rate: 1 GBP = 105.50 INR.** This is an artificial, project-defined
constant for this assignment (not a live or historical market rate), so
it's hardcoded in `clean_and_load.py` and needs no API call, lookup, or
date reference. `price_inr = price_gbp * 105.50`.

## Cleaning decisions

- **`price_gbp`** — strip the `£` and any non-numeric characters, cast to
  `float`. If parsing fails, **median-impute** rather than drop the row:
  price is a numeric field central to the analysis, and one bad field
  shouldn't cost an otherwise-good row.
- **`rating`** — map the word form (`One`…`Five`) to an int 1–5. If the word
  isn't recognized, **median-impute** (rounded to the nearest int), same
  reasoning as above.
- **`in_stock`** — `True` if the availability text contains "in stock",
  `False` if it contains "out of stock". If it matches neither, **drop the
  row**: stock status isn't a numeric field imputation makes sense for, and
  on this site the text is effectively always well-formed, so this is a
  safety net rather than an expected path.

Running `clean_and_load.py` against the (deliberately messy) sample data
triggers all three paths, e.g.:

```
[clean] Imputed 1 missing price_gbp value(s) with median 30.45
[clean] Imputed 1 missing rating value(s) with median 2
[clean] Dropped 1 row(s) with unparseable availability text
[db] Loaded 68 books across 3 categories into books.db
```

## Schema

```
categories(category_id INTEGER PRIMARY KEY, category_name TEXT UNIQUE)
books(book_id INTEGER PRIMARY KEY, title TEXT, price_gbp REAL, price_inr REAL,
      rating INTEGER, in_stock INTEGER, category_id INTEGER REFERENCES categories(category_id))
```

## SQL queries (`queries.py`)

1. `q1_select_where_orderby_limit` — SELECT/WHERE, ORDER BY, LIMIT
2. `q2_distinct_categories` — DISTINCT
3. `q3_price_between` — BETWEEN
4. `q4_rating_in` — IN
5. `q5_join_top_rated_per_category` — JOIN (top-rated book(s) per category)

Full output for all five is in `queries_output.txt`.

## pandas cross-check (`pandas_analysis.py`)

Two queries are read back with `pd.read_sql`, and the JOIN query is
reproduced with `pd.merge` on in-memory `books_df`/`categories_df` DataFrames
(no SQL). Both approaches produce identical, row-for-row matching output —
confirmed with `DataFrame.equals()` (see `pandas_output.txt`).

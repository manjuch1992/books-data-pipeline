"""Build the complete books data-pipeline deliverable directory.

Run from the repository root:
    python data_pipeline/data_pipeline.py

The script reuses the project's scraper-compatible raw_books.csv and writes all
cleaned data, the SQLite database, SQL files, and CSV query outputs beneath
this directory.
"""

from pathlib import Path
import sqlite3
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(__file__).resolve().parent
QUERY_DIR = OUTPUT_DIR / "query_outputs"

# Allow the existing, tested cleaning implementation to remain the source of
# truth while making this directory independently runnable from the repo root.
sys.path.insert(0, str(ROOT))
from clean_and_load import build_database, load_and_clean  # noqa: E402


QUERIES = {
    "query_1_select_where": """SELECT title, price_gbp, rating
FROM books
WHERE in_stock = 1
ORDER BY price_gbp DESC
LIMIT 10;""",
    "query_2_order_by_limit": """SELECT title, price_gbp
FROM books
ORDER BY price_gbp DESC
LIMIT 10;""",
    "query_3_distinct": """SELECT DISTINCT category_name
FROM categories
ORDER BY category_name;""",
    "query_4_between": """SELECT title, price_gbp, price_inr
FROM books
WHERE price_gbp BETWEEN 20 AND 40
ORDER BY price_gbp ASC;""",
    "query_5_in": """SELECT title, rating
FROM books
WHERE rating IN (4, 5)
ORDER BY rating DESC, title ASC
LIMIT 15;""",
    "query_6_join": """SELECT c.category_name, b.title, b.rating, b.price_gbp
FROM books AS b
JOIN categories AS c ON b.category_id = c.category_id
WHERE b.rating = (
    SELECT MAX(b2.rating)
    FROM books AS b2
    WHERE b2.category_id = b.category_id
)
ORDER BY c.category_name, b.title;""",
}


def write_query_outputs(connection: sqlite3.Connection) -> None:
    QUERY_DIR.mkdir(parents=True, exist_ok=True)
    for name, sql in QUERIES.items():
        (QUERY_DIR / f"{name}.sql").write_text(sql + "\n", encoding="utf-8")
        pd.read_sql_query(sql, connection).to_csv(
            QUERY_DIR / f"{name}_output.csv", index=False
        )

    high_rated = pd.read_sql_query(
        "SELECT title, rating FROM books WHERE rating >= 4 ORDER BY rating DESC, title;",
        connection,
    )
    high_rated.to_csv(QUERY_DIR / "pd_read_sql_high_rated.csv", index=False)

    expensive = pd.read_sql_query(
        "SELECT title, price_gbp, price_inr FROM books ORDER BY price_gbp DESC LIMIT 10;",
        connection,
    )
    expensive.to_csv(QUERY_DIR / "pd_read_sql_expensive.csv", index=False)

    books = pd.read_sql_query("SELECT * FROM books;", connection)
    categories = pd.read_sql_query("SELECT * FROM categories;", connection)
    merged = books.merge(categories, on="category_id", how="inner")
    max_rating = merged.groupby("category_id")["rating"].transform("max")
    pandas_join = merged.loc[merged["rating"].eq(max_rating), [
        "category_name", "title", "rating", "price_gbp"
    ]].sort_values(["category_name", "title"])
    pandas_join.to_csv(QUERY_DIR / "pandas_merge_join_output.csv", index=False)

    sql_join = pd.read_sql_query(QUERIES["query_6_join"], connection)
    sql_join.to_csv(QUERY_DIR / "sql_join_comparison.csv", index=False)
    pandas_join.to_csv(QUERY_DIR / "pandas_join_comparison.csv", index=False)


def main() -> None:
    raw_csv = ROOT / "raw_books.csv"
    cleaned = load_and_clean(raw_csv)
    cleaned.to_csv(OUTPUT_DIR / "books_cleaned_final.csv", index=False)

    database = OUTPUT_DIR / "books_database.db"
    build_database(cleaned, database)
    with sqlite3.connect(database) as connection:
        write_query_outputs(connection)

    print(f"Wrote pipeline artifacts to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

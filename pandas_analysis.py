"""
pandas_analysis.py
-------------------
- Reads two of the queries from queries.py back into pandas DataFrames via
  pd.read_sql(...).
- Reproduces the JOIN query's result using pd.merge(...) directly on
  in-memory DataFrames (no SQL), and shows both approaches match.

Run:
    python pandas_analysis.py
"""

import sqlite3
import tempfile
from pathlib import Path

import pandas as pd


def choose_output_dir():
    candidates = [
        Path(r"D:\masai_capstone"),
        Path(r"E:\masai_capstone"),
        Path(tempfile.gettempdir()) / "masai_capstone",
        Path(__file__).resolve().parent,
    ]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / ".write_test"
            with open(test_file, "w", encoding="utf-8") as handle:
                handle.write("ok")
            test_file.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    return Path(__file__).resolve().parent


OUTPUT_DIR = choose_output_dir()


def main(db_path="books.db"):
    db_path = Path(db_path)
    if not db_path.is_absolute():
        db_path = OUTPUT_DIR / db_path.name
    conn = sqlite3.connect(db_path)

    df_instock_top = pd.read_sql(
        """
        SELECT title, price_gbp, rating
        FROM books
        WHERE in_stock = 1
        ORDER BY price_gbp DESC
        LIMIT 10;
        """,
        conn,
    )
    df_distinct_cats = pd.read_sql(
        "SELECT DISTINCT category_name FROM categories ORDER BY category_name;",
        conn,
    )

    print("=== pd.read_sql: top 10 in-stock books by price ===")
    print(df_instock_top.to_string(index=False))
    print("\n=== pd.read_sql: distinct categories ===")
    print(df_distinct_cats.to_string(index=False))

    sql_join_query = """
        SELECT c.category_name, b.title, b.rating, b.price_gbp
        FROM books b
        JOIN categories c ON b.category_id = c.category_id
        WHERE b.rating = (
            SELECT MAX(b2.rating) FROM books b2 WHERE b2.category_id = b.category_id
        )
        ORDER BY c.category_name, b.title;
    """
    df_sql_join = pd.read_sql(sql_join_query, conn).sort_values(
        ["category_name", "title"]
    ).reset_index(drop=True)

    books_df = pd.read_sql("SELECT * FROM books;", conn)
    categories_df = pd.read_sql("SELECT * FROM categories;", conn)

    merged = books_df.merge(categories_df, on="category_id", how="inner")
    max_rating_per_category = merged.groupby("category_id")["rating"].transform("max")
    df_pandas_join = (
        merged[merged["rating"] == max_rating_per_category][
            ["category_name", "title", "rating", "price_gbp"]
        ]
        .sort_values(["category_name", "title"])
        .reset_index(drop=True)
    )

    print("\n=== JOIN result via pd.read_sql (SQL JOIN) ===")
    print(df_sql_join.to_string(index=False))
    print("\n=== JOIN result via pd.merge (no SQL) ===")
    print(df_pandas_join.to_string(index=False))

    are_equal = df_sql_join.equals(df_pandas_join)
    print(f"\nSQL JOIN result matches pd.merge result: {are_equal}")
    assert are_equal, "pd.read_sql and pd.merge results diverged!"

    conn.close()

    output_path = OUTPUT_DIR / "pandas_output.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=== pd.read_sql: top 10 in-stock books by price ===\n")
        f.write(df_instock_top.to_string(index=False) + "\n\n")
        f.write("=== pd.read_sql: distinct categories ===\n")
        f.write(df_distinct_cats.to_string(index=False) + "\n\n")
        f.write("=== JOIN result via pd.read_sql (SQL JOIN) ===\n")
        f.write(df_sql_join.to_string(index=False) + "\n\n")
        f.write("=== JOIN result via pd.merge (no SQL) ===\n")
        f.write(df_pandas_join.to_string(index=False) + "\n\n")
        f.write(f"SQL JOIN result matches pd.merge result: {are_equal}\n")

    print(f"\n✓ Output saved to {output_path}")


if __name__ == "__main__":
    main()

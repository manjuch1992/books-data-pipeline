"""
clean_and_load.py
------------------
Reads raw_books.csv (produced by scraper.py), cleans/types each field,
converts price to INR using the project's fixed baseline rate, and loads
the result into a normalized SQLite database (books.db) with a two-table
categories / books schema sharing a PK/FK relationship.

Fixed conversion rate (see README): 1 GBP = 105.50 INR.
This is an artificial, project-defined constant for this assignment —
not a live or historical market rate — so it is hardcoded below and
requires no API call, no lookup, and no date reference.

Row-level error handling (see README for justification):
  - price_gbp fails to parse  -> median-impute (numeric, central to the
    analysis; dropping would lose an otherwise-good row over one field).
  - rating fails to parse     -> median-impute, rounded to nearest int.
  - availability text doesn't match either known pattern -> row dropped
    (not a meaningfully numeric field, so imputation doesn't apply, and
    on this site such text is effectively always well-formed, so this
    path is a safety net rather than an expected occurrence).

Run:
    python clean_and_load.py
"""

import re
import sqlite3

import pandas as pd

FIXED_RATE_GBP_TO_INR = 105.50  # project-defined fixed baseline rate

RATING_WORD_TO_INT = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def clean_price(price_text):
    try:
        cleaned = re.sub(r"[^\d.]", "", str(price_text))
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def clean_rating(star_word):
    return RATING_WORD_TO_INT.get(str(star_word).strip(), None)


def clean_availability(avail_text):
    if not isinstance(avail_text, str):
        return None
    text = avail_text.lower()
    if "in stock" in text:
        return True
    if "out of stock" in text:
        return False
    return None  # unrecognized text -> treated as a parse failure


def load_and_clean(csv_path="raw_books.csv") -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    df["price_gbp"] = df["price"].apply(clean_price)
    df["rating"] = df["star_rating"].apply(clean_rating)
    df["in_stock"] = df["availability"].apply(clean_availability)

    # --- price_gbp: median-impute ---
    if df["price_gbp"].isna().any():
        median_price = df["price_gbp"].median()
        n_bad = int(df["price_gbp"].isna().sum())
        df["price_gbp"] = df["price_gbp"].fillna(median_price)
        print(f"[clean] Imputed {n_bad} missing price_gbp value(s) with median {median_price:.2f}")

    # --- rating: median-impute (rounded) ---
    if df["rating"].isna().any():
        median_rating = int(round(df["rating"].median()))
        n_bad = int(df["rating"].isna().sum())
        df["rating"] = df["rating"].fillna(median_rating)
        print(f"[clean] Imputed {n_bad} missing rating value(s) with median {median_rating}")
    df["rating"] = df["rating"].astype(int)

    # --- in_stock: drop unparseable rows ---
    before = len(df)
    df = df.dropna(subset=["in_stock"])
    dropped = before - len(df)
    if dropped:
        print(f"[clean] Dropped {dropped} row(s) with unparseable availability text")
    df["in_stock"] = df["in_stock"].astype(int)

    # --- currency conversion (required fixed-rate baseline) ---
    df["price_inr"] = df["price_gbp"] * FIXED_RATE_GBP_TO_INR

    return df[["title", "price_gbp", "price_inr", "rating", "in_stock", "category"]].reset_index(drop=True)


def build_database(df: pd.DataFrame, db_path="books.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS books;
        DROP TABLE IF EXISTS categories;

        CREATE TABLE categories (
            category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE books (
            book_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            price_gbp   REAL NOT NULL,
            price_inr   REAL NOT NULL,
            rating      INTEGER NOT NULL,
            in_stock    INTEGER NOT NULL,
            category_id INTEGER NOT NULL REFERENCES categories(category_id)
        );
        """
    )

    category_ids = {}
    for name in sorted(df["category"].unique()):
        cur.execute("INSERT INTO categories (category_name) VALUES (?)", (name,))
        category_ids[name] = cur.lastrowid

    rows = [
        (r.title, r.price_gbp, r.price_inr, r.rating, r.in_stock, category_ids[r.category])
        for r in df.itertuples(index=False)
    ]
    cur.executemany(
        """
        INSERT INTO books (title, price_gbp, price_inr, rating, in_stock, category_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    conn.commit()
    conn.close()
    print(f"[db] Loaded {len(df)} books across {len(category_ids)} categories into {db_path}")


if __name__ == "__main__":
    cleaned = load_and_clean()
    build_database(cleaned)

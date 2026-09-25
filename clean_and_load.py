

import re
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

FIXED_RATE_GBP_TO_INR = 105.50  # project-defined fixed baseline rate

RATING_WORD_TO_INT = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
RATING_WORD_TO_INT_LOWER = {key.lower(): value for key, value in RATING_WORD_TO_INT.items()}


def clean_price(price_text):
    if price_text is None or (isinstance(price_text, float) and pd.isna(price_text)):
        return None

    text = str(price_text).strip()
    if not text:
        return None

    cleaned = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    if cleaned in {"", ".", "-", "-.", ".-", "--"}:
        return None

    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def clean_rating(star_word):
    if star_word is None or (isinstance(star_word, float) and pd.isna(star_word)):
        return None

    normalized = str(star_word).strip().lower()
    return RATING_WORD_TO_INT_LOWER.get(normalized, None)


def clean_availability(avail_text):
    if avail_text is None or (isinstance(avail_text, float) and pd.isna(avail_text)):
        return None

    if not isinstance(avail_text, str):
        text = str(avail_text)
    else:
        text = avail_text

    text = text.strip().lower()
    if "in stock" in text:
        return True
    if "out of stock" in text:
        return False
    return None  # unrecognized text -> treated as a parse failure


def load_and_clean(csv_path="raw_books.csv") -> pd.DataFrame:
    csv_path = Path(csv_path)
    if not csv_path.is_absolute():
        csv_path = OUTPUT_DIR / csv_path.name
    df = pd.read_csv(csv_path)

    required_columns = {"title", "price", "star_rating", "availability", "category"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {missing_columns}")

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
    df = df.copy()
    db_path = Path(db_path)
    if not db_path.is_absolute():
        db_path = OUTPUT_DIR / db_path.name
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
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
        for name in sorted(df["category"].dropna().unique()):
            cur.execute("INSERT INTO categories (category_name) VALUES (?)", (str(name),))
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
        print(f"[db] Loaded {len(df)} books across {len(category_ids)} categories into {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    raw_csv = OUTPUT_DIR / "raw_books.csv"
    db_path = OUTPUT_DIR / "books.db"
    cleaned = load_and_clean(raw_csv)
    build_database(cleaned, db_path)

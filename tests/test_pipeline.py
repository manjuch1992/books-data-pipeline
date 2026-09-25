import pandas as pd

from clean_and_load import (
    FIXED_RATE_GBP_TO_INR,
    build_database,
    clean_availability,
    clean_price,
    clean_rating,
    load_and_clean,
)


def test_clean_helpers():
    assert clean_price("£12.50") == 12.5
    assert clean_price("not available") is None
    assert clean_rating("Five") == 5
    assert clean_rating("Unknown") is None
    assert clean_availability("In stock (3 available)") is True
    assert clean_availability("Out of stock") is False
    assert clean_availability("Ask in store") is None


def test_load_and_build_database(tmp_path):
    csv_path = tmp_path / "raw_books.csv"
    pd.DataFrame(
        [
            {
                "title": "Book A",
                "price": "£10.00",
                "star_rating": "Five",
                "availability": "In stock (2 available)",
                "category": "Fiction",
            },
            {
                "title": "Book B",
                "price": "bad price",
                "star_rating": "Unknown",
                "availability": "Out of stock",
                "category": "Fiction",
            },
            {
                "title": "Invalid",
                "price": "£20.00",
                "star_rating": "Three",
                "availability": "Ask in store",
                "category": "Fiction",
            },
        ]
    ).to_csv(csv_path, index=False)

    cleaned = load_and_clean(csv_path)
    assert len(cleaned) == 2
    assert cleaned["price_inr"].iloc[0] == 10 * FIXED_RATE_GBP_TO_INR
    assert cleaned["rating"].between(1, 5).all()

    db_path = tmp_path / "books.db"
    build_database(cleaned, db_path)
    with __import__("sqlite3").connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 1

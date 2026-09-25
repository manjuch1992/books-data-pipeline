import sqlite3
import tempfile
from pathlib import Path


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

QUERIES = {
    "q1_select_where_orderby_limit": """
        SELECT title, price_gbp, rating
        FROM books
        WHERE in_stock = 1
        ORDER BY price_gbp DESC
        LIMIT 10;
    """,
    "q2_distinct_categories": """
        SELECT DISTINCT category_name
        FROM categories
        ORDER BY category_name;
    """,
    "q3_price_between": """
        SELECT title, price_gbp, price_inr
        FROM books
        WHERE price_gbp BETWEEN 20 AND 40
        ORDER BY price_gbp ASC;
    """,
    "q4_rating_in": """
        SELECT title, rating
        FROM books
        WHERE rating IN (4, 5)
        ORDER BY rating DESC, title ASC
        LIMIT 15;
    """,
    "q5_join_top_rated_per_category": """
        SELECT c.category_name, b.title, b.rating, b.price_gbp
        FROM books b
        JOIN categories c ON b.category_id = c.category_id
        WHERE b.rating = (
            SELECT MAX(b2.rating) FROM books b2 WHERE b2.category_id = b.category_id
        )
        ORDER BY c.category_name, b.title;
    """,
}


def run_queries(db_path="books.db"):
    db_path = Path(db_path)
    if not db_path.is_absolute():
        db_path = OUTPUT_DIR / db_path.name
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    results = {}

    for name, sql in QUERIES.items():
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        results[name] = (cols, rows)

        print(f"\n=== {name} ===")
        print(sql.strip())
        print(f"columns: {cols}")
        for row in rows:
            print(row)

    conn.close()
    return results


if __name__ == "__main__":
    run_queries()

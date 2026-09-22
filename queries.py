"""
queries.py
----------
Runs >= 5 SQL queries against books.db, collectively covering:
SELECT/WHERE, ORDER BY, LIMIT, DISTINCT, IN/BETWEEN, and a JOIN.

Prints each query's SQL and its output (also usable programmatically via
run_queries(), which returns {name: (columns, rows)}).

Run:
    python queries.py
"""

import sqlite3

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

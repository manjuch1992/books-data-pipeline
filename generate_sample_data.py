"""
generate_sample_data.py
------------------------
NOT part of the graded pipeline. This only exists to produce a raw_books.csv
in the exact same shape scraper.py would produce, for local testing of
clean_and_load.py / queries.py / pandas_analysis.py in environments where
live scraping isn't possible (e.g. no network access).

It fabricates plausible book rows across 3 categories (>=60 total) and
deliberately injects a few malformed rows so the error-handling paths in
clean_and_load.py (median-impute vs. drop) are actually exercised.

Run:
    python generate_sample_data.py
"""

import csv
import random

random.seed(7)

CATEGORIES = {
    "Travel": 22,
    "Mystery": 24,
    "Classics": 20,
}
STAR_WORDS = ["One", "Two", "Three", "Four", "Five"]

TITLE_PARTS_A = [
    "The Silent", "A Journey", "Whispers of", "Shadows in", "The Lost",
    "Beneath the", "Echoes of", "The Hidden", "Return to", "Letters from",
    "The Last", "A Quiet", "Fragments of", "The Forgotten", "Into the",
]
TITLE_PARTS_B = [
    "Harbor", "Mountains", "Winter", "the City", "Garden", "River", "Kingdom",
    "Coast", "Valley", "Night", "Horizon", "Library", "Village", "Ocean", "Woods",
]

rows = []
for category, count in CATEGORIES.items():
    for i in range(count):
        title = f"{random.choice(TITLE_PARTS_A)} {random.choice(TITLE_PARTS_B)}"
        price = round(random.uniform(10.0, 58.0), 2)
        star = random.choice(STAR_WORDS)
        in_stock_count = random.randint(0, 30)
        availability = (
            f"In stock ({in_stock_count} available)" if in_stock_count > 0 else "Out of stock"
        )
        rows.append(
            {
                "title": title,
                "price": f"£{price:.2f}",
                "star_rating": star,
                "availability": availability,
                "category": category,
            }
        )

# --- Inject a few deliberately messy rows to exercise clean_and_load.py's
#     error-handling (median-impute for price/rating, drop for availability) ---
rows.append({
    "title": "A Book With Bad Price",
    "price": "price unavailable",       # will fail float parse -> median-impute
    "star_rating": "Three",
    "availability": "In stock (5 available)",
    "category": "Travel",
})
rows.append({
    "title": "A Book With Bad Rating",
    "price": "£19.99",
    "star_rating": "Zero",              # not in RATING_WORD_TO_INT -> median-impute
    "availability": "In stock (2 available)",
    "category": "Mystery",
})
rows.append({
    "title": "A Book With Bad Availability",
    "price": "£25.50",
    "star_rating": "Two",
    "availability": "Ask in store",     # unparseable -> row dropped
    "category": "Classics",
})

random.shuffle(rows)

with open("raw_books.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "price", "star_rating", "availability", "category"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} sample rows (incl. 3 deliberately messy) to raw_books.csv")

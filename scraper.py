"""
scraper.py
----------
Scrapes book data from books.toscrape.com (a public scraping-practice site,
no login/API key required) across at least 3 categories, until at least
MIN_BOOKS rows have been collected.

For each book we capture the raw, as-listed fields (no cleaning here —
cleaning/typing happens in clean_and_load.py):
    title         : str
    price         : str, e.g. "£51.77"
    star_rating   : str, e.g. "Three"  (word form, as encoded in the HTML class)
    availability  : str, e.g. "In stock (22 available)"
    category      : str, e.g. "Travel"

Categories are discovered dynamically from the site's own sidebar navigation
(rather than hardcoded URLs/IDs), so the script keeps working even if the
site's internal category ordering or IDs change.

Output: raw_books.csv in the same directory.

Run:
    python scraper.py
"""

import csv
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://books.toscrape.com/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; scraping-practice-bot/1.0)"}
MIN_BOOKS = 60
MIN_CATEGORIES = 3
POLITE_DELAY_SECONDS = 0.3  # be gentle with the practice site


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_categories():
    """Return [(category_name, category_url), ...] from the homepage sidebar."""
    soup = get_soup(BASE_URL)
    links = soup.select("div.side_categories ul li ul li a")
    categories = []
    for a in links:
        name = a.text.strip()
        url = BASE_URL + a["href"]
        categories.append((name, url))
    return categories


def scrape_category(name: str, start_url: str):
    """Scrape every book on every paginated page of one category."""
    books = []
    page_url = start_url
    while True:
        soup = get_soup(page_url)
        for article in soup.select("article.product_pod"):
            title = article.h3.a["title"].strip()
            price_text = article.select_one("p.price_color").text.strip()
            rating_classes = article.select_one("p.star_rating")["class"]
            star_word = next(c for c in rating_classes if c != "star_rating")
            availability = article.select_one("p.instock.availability").text.strip()
            books.append(
                {
                    "title": title,
                    "price": price_text,
                    "star_rating": star_word,
                    "availability": availability,
                    "category": name,
                }
            )

        next_link = soup.select_one("li.next a")
        if not next_link:
            break
        # category page URLs are relative to the category's own directory
        page_url = page_url.rsplit("/", 1)[0] + "/" + next_link["href"]
        time.sleep(POLITE_DELAY_SECONDS)

    return books


def main():
    categories = get_categories()
    all_books = []
    used_categories = []

    for name, url in categories:
        if len(all_books) >= MIN_BOOKS and len(used_categories) >= MIN_CATEGORIES:
            break
        books = scrape_category(name, url)
        if books:
            all_books.extend(books)
            used_categories.append(name)
        time.sleep(POLITE_DELAY_SECONDS)

    print(f"Scraped {len(all_books)} books across {len(used_categories)} categories: {used_categories}")

    out_path = "raw_books.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["title", "price", "star_rating", "availability", "category"]
        )
        writer.writeheader()
        writer.writerows(all_books)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

SELECT title, price_gbp, rating
FROM books
WHERE in_stock = 1
ORDER BY price_gbp DESC
LIMIT 10;

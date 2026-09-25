SELECT title, price_gbp, price_inr
FROM books
WHERE price_gbp BETWEEN 20 AND 40
ORDER BY price_gbp ASC;

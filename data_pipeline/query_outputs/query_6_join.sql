SELECT c.category_name, b.title, b.rating, b.price_gbp
FROM books AS b
JOIN categories AS c ON b.category_id = c.category_id
WHERE b.rating = (
    SELECT MAX(b2.rating)
    FROM books AS b2
    WHERE b2.category_id = b.category_id
)
ORDER BY c.category_name, b.title;

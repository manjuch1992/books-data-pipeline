SELECT title, rating
FROM books
WHERE rating IN (4, 5)
ORDER BY rating DESC, title ASC
LIMIT 15;

-- Independent verification queries. These are written by hand, NOT by the
-- agent, and define the expected answer for each test question.
-- Revenue counts only delivered + shipped orders (cancelled and refunded
-- orders are excluded) and uses order_items.unit_price * quantity.

\echo '--- Q1 total revenue'
SELECT SUM(oi.quantity * oi.unit_price) AS total_revenue
FROM order_items oi JOIN orders o ON o.order_id = oi.order_id
WHERE o.status IN ('delivered', 'shipped');

\echo '--- Q2 cancelled orders'
SELECT COUNT(*) AS cancelled_orders FROM orders WHERE status = 'cancelled';

\echo '--- Q3 customers who never ordered'
SELECT COUNT(*) AS never_ordered
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id);

\echo '--- Q4 city with the most customers (NULL city ignored)'
SELECT city, COUNT(*) AS customers
FROM customers WHERE city IS NOT NULL
GROUP BY city ORDER BY 2 DESC LIMIT 3;

\echo '--- Q5 average order value (delivered + shipped orders)'
SELECT ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status IN ('delivered', 'shipped');

\echo '--- Q6 category with the most revenue'
SELECT p.category, SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status IN ('delivered', 'shipped')
GROUP BY p.category ORDER BY 2 DESC LIMIT 3;

\echo '--- Q7 top 5 customers by total spend'
SELECT c.customer_id, c.name, SUM(oi.quantity * oi.unit_price) AS spend
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status IN ('delivered', 'shipped')
GROUP BY c.customer_id, c.name ORDER BY spend DESC LIMIT 5;

\echo '--- Q8 total revenue in 2025'
SELECT SUM(oi.quantity * oi.unit_price) AS revenue_2025
FROM order_items oi JOIN orders o ON o.order_id = oi.order_id
WHERE o.status IN ('delivered', 'shipped')
  AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01';

\echo '--- Q9 total payments received for delivered orders'
SELECT SUM(p.amount) AS payments_delivered
FROM payments p JOIN orders o ON o.order_id = p.order_id
WHERE o.status = 'delivered';

\echo '--- Q10 orders that used a discount code'
SELECT COUNT(*) AS orders_with_discount FROM orders WHERE discount_code IS NOT NULL;
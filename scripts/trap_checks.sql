-- TRAP 1: naive revenue includes cancelled/refunded orders.
SELECT 'naive' AS version, SUM(quantity * unit_price) AS revenue
FROM order_items
UNION ALL
SELECT 'correct', SUM(oi.quantity * oi.unit_price)
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status NOT IN ('cancelled', 'refunded');

-- TRAP 2: current product price vs the price actually paid.
SELECT 'naive (products.price)' AS version, SUM(oi.quantity * p.price) AS revenue
FROM order_items oi
JOIN orders o   ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status NOT IN ('cancelled', 'refunded')
UNION ALL
SELECT 'correct (unit_price)', SUM(oi.quantity * oi.unit_price)
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status NOT IN ('cancelled', 'refunded');

-- TRAP 3: joining items to payments duplicates rows of split-payment orders.
SELECT 'naive (join payments)' AS version, SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN payments pay   ON pay.order_id = o.order_id
WHERE o.status NOT IN ('cancelled', 'refunded')
UNION ALL
SELECT 'correct (no join)', SUM(oi.quantity * oi.unit_price)
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status NOT IN ('cancelled', 'refunded');
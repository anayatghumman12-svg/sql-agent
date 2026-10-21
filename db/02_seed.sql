-- Deterministic seed: same random sequence on every fresh start.
SELECT setseed(0.42);

-- 2,000 customers. ~10% have NULL city.
INSERT INTO customers (name, email, city, signup_date)
SELECT 'Customer ' || g,
       'customer' || g || '@example.com',
       CASE WHEN random() < 0.10 THEN NULL
            ELSE (ARRAY['Lahore','Karachi','Islamabad','Rawalpindi',
                        'Faisalabad','Multan','Peshawar','Quetta'])
                 [1 + floor(random() * 8)::int]
       END,
       DATE '2024-01-01' + floor(random() * 600)::int
FROM generate_series(1, 2000) AS g;

-- 200 products. Categories overlap on purpose:
-- Electronics/Gadgets and Home/'Home & Kitchen' mean the same thing.
INSERT INTO products (name, category, price)
SELECT 'Product ' || g,
       (ARRAY['Electronics','Gadgets','Home','Home & Kitchen',
              'Clothing','Books','Sports','Beauty'])
       [1 + floor(random() * 8)::int],
       round((5 + random() * 495)::numeric, 2)
FROM generate_series(1, 200) AS g;

-- 20,000 orders. Only customers 1..1700 order, so ~300 never ordered.
-- Status mix: 70% delivered, 10% shipped, 12% cancelled, 8% refunded.
-- The subquery draws ONE random number per row, so the CASE branches
-- use a consistent value (random() inside CASE would redraw each time).
INSERT INTO orders (customer_id, order_date, status, discount_code)
SELECT 1 + floor(random() * 1700)::int,
       DATE '2025-01-01' + floor(random() * 658)::int,
       CASE WHEN r < 0.70 THEN 'delivered'
            WHEN r < 0.80 THEN 'shipped'
            WHEN r < 0.92 THEN 'cancelled'
            ELSE 'refunded'
       END,
       CASE WHEN random() < 0.15
            THEN (ARRAY['SAVE10','WELCOME','FESTIVE'])[1 + floor(random() * 3)::int]
       END                                   -- no ELSE => NULL
FROM (SELECT random() AS r FROM generate_series(1, 20000)) AS t;

-- Order items: 1-4 per order (~50,000 total).
-- unit_price differs from the current product price for ~30% of rows
-- (simulates price changes over time) => trap 2.
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT t.order_id,
       t.product_id,
       t.quantity,
       round((p.price * CASE WHEN random() < 0.30
                             THEN 0.8 + random() * 0.4
                             ELSE 1
                        END)::numeric, 2)
FROM (
    SELECT o.order_id,
           1 + floor(random() * 200)::int AS product_id,
           1 + floor(random() * 3)::int   AS quantity
    FROM orders o
    CROSS JOIN LATERAL generate_series(1, 1 + floor(random() * 4)::int) AS s(n)
) AS t
JOIN products p ON p.product_id = t.product_id;

-- Payments. Cancelled orders have no payment.
-- ~20% of the other orders are paid in TWO partial payments => trap 3
-- (joining orders to payments duplicates those orders).
CREATE TEMP TABLE pay_plan AS
SELECT o.order_id,
       o.order_date,
       SUM(oi.quantity * oi.unit_price) AS total,
       (random() < 0.20) AS is_split
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status <> 'cancelled'
GROUP BY o.order_id, o.order_date;

INSERT INTO payments (order_id, amount, method, paid_at)
SELECT order_id,
       total,
       (ARRAY['card','cash','bank_transfer'])[1 + floor(random() * 3)::int],
       order_date + (random() * 86400)::int * INTERVAL '1 second'
FROM pay_plan
WHERE NOT is_split;

-- Split orders: first half, then the remainder (so the two sum to the total).
INSERT INTO payments (order_id, amount, method, paid_at)
SELECT order_id,
       round(total / 2, 2),
       (ARRAY['card','cash','bank_transfer'])[1 + floor(random() * 3)::int],
       order_date + (random() * 86400)::int * INTERVAL '1 second'
FROM pay_plan
WHERE is_split
UNION ALL
SELECT order_id,
       total - round(total / 2, 2),
       (ARRAY['card','cash','bank_transfer'])[1 + floor(random() * 3)::int],
       order_date + (random() * 86400)::int * INTERVAL '1 second'
FROM pay_plan
WHERE is_split;
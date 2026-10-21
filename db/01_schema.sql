-- Core tables. Foreign keys enforce real relationships between tables.

CREATE TABLE customers (
    customer_id  SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL,
    city         TEXT,                       -- nullable on purpose (messiness)
    signup_date  DATE NOT NULL
);

CREATE TABLE products (
    product_id  SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,               -- overlapping names on purpose
    price       NUMERIC(10,2) NOT NULL       -- CURRENT price only
);

CREATE TABLE orders (
    order_id       SERIAL PRIMARY KEY,
    customer_id    INT NOT NULL REFERENCES customers(customer_id),
    order_date     DATE NOT NULL,
    status         TEXT NOT NULL,            -- delivered/shipped/cancelled/refunded
    discount_code  TEXT                      -- mostly NULL
);

CREATE TABLE order_items (
    item_id     SERIAL PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES orders(order_id),
    product_id  INT NOT NULL REFERENCES products(product_id),
    quantity    INT NOT NULL,
    unit_price  NUMERIC(10,2) NOT NULL       -- price PAID at purchase time
);

CREATE TABLE payments (
    payment_id  SERIAL PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES orders(order_id),
    amount      NUMERIC(10,2) NOT NULL,
    method      TEXT NOT NULL,
    paid_at     TIMESTAMP NOT NULL
);
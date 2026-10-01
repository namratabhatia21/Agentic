#!/bin/sh
# Runs once, on first start of an empty Postgres volume.
# Creates the read-only role used by the query_database tool and seeds demo data.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v ro_password="$READONLY_PASSWORD" <<'SQL'
CREATE ROLE agent_readonly LOGIN PASSWORD :'ro_password';

CREATE SCHEMA analytics;

CREATE TABLE analytics.regions (
    id    serial PRIMARY KEY,
    name  text NOT NULL UNIQUE
);

CREATE TABLE analytics.products (
    id        serial PRIMARY KEY,
    name      text NOT NULL,
    category  text NOT NULL,
    price_eur numeric(10, 2) NOT NULL
);

CREATE TABLE analytics.customers (
    id         serial PRIMARY KEY,
    name       text NOT NULL,
    region_id  int NOT NULL REFERENCES analytics.regions(id),
    signed_up  date NOT NULL
);

CREATE TABLE analytics.orders (
    id           serial PRIMARY KEY,
    customer_id  int NOT NULL REFERENCES analytics.customers(id),
    product_id   int NOT NULL REFERENCES analytics.products(id),
    quantity     int NOT NULL,
    ordered_at   timestamptz NOT NULL
);

INSERT INTO analytics.regions (name)
VALUES ('Europe'), ('North America'), ('Asia Pacific'), ('Latin America'), ('Middle East & Africa');

INSERT INTO analytics.products (name, category, price_eur) VALUES
    ('Starter plan', 'subscription', 29),
    ('Team plan', 'subscription', 99),
    ('Enterprise plan', 'subscription', 499),
    ('Onboarding workshop', 'services', 1200),
    ('API credits pack', 'usage', 50),
    ('Premium support', 'services', 300);

-- Deterministic pseudo-random demo data covering the last two years.
SELECT setseed(0.42);

INSERT INTO analytics.customers (name, region_id, signed_up)
SELECT 'Customer ' || g,
       1 + floor(random() * 5)::int,
       (now() - (random() * 730 || ' days')::interval)::date
FROM generate_series(1, 400) g;

INSERT INTO analytics.orders (customer_id, product_id, quantity, ordered_at)
SELECT 1 + floor(random() * 400)::int,
       1 + floor(random() * 6)::int,
       1 + floor(random() * 5)::int,
       now() - (random() * 730 || ' days')::interval
FROM generate_series(1, 5000);

CREATE VIEW analytics.order_revenue AS
SELECT o.id AS order_id, o.ordered_at, r.name AS region, p.name AS product, p.category,
       o.quantity, o.quantity * p.price_eur AS revenue_eur
FROM analytics.orders o
JOIN analytics.customers c ON c.id = o.customer_id
JOIN analytics.regions r ON r.id = c.region_id
JOIN analytics.products p ON p.id = o.product_id;

-- The read-only role can see only the analytics schema.
-- Tables in "public" (conversations, documents) grant nothing to PUBLIC by default,
-- so this role cannot read chat history.
GRANT USAGE ON SCHEMA analytics TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO agent_readonly;
ALTER ROLE agent_readonly SET default_transaction_read_only = on;
ALTER ROLE agent_readonly SET statement_timeout = '5s';
ALTER ROLE agent_readonly SET search_path = analytics;
SQL

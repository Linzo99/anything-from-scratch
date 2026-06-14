# Data Modeling & Schema Design

> Normalization keeps your data honest by storing every fact once. Denormalization makes it fast by storing facts where you'll read them. Real schemas need both, on purpose.

**Type:** Build
**Languages:** SQL
**Prerequisites:** Phase 2, Lesson 03 — ACID & Transactions
**Time:** ~50 minutes

## Learning Objectives

- Model a domain as normalized tables with primary and foreign keys
- Explain the anomalies normalization prevents and the joins it requires
- Denormalize deliberately for read-heavy access and name the cost
- Recognize the star schema pattern for analytics
- Translate access patterns into a concrete schema

## The Problem

A schema is a set of decisions you'll live with for years, and the default mistakes are symmetric. Under-structure the data — cram everything into one wide table with repeated values — and you get *anomalies*: the same customer's address stored in a thousand order rows, so a single address change means updating a thousand rows (and missing some). Over-structure it — split everything into perfectly normalized tables — and every read becomes a five-way join that's slow under load.

Good schema design is the deliberate navigation between these. **Normalization** is the discipline of storing each fact exactly once, eliminating redundancy and the update anomalies it causes. It's the right default: correct, compact, and flexible. But normalization resolves relationships with joins at read time, and at scale joins get expensive. So you sometimes **denormalize** — reintroduce controlled redundancy — to make hot reads fast, accepting that you now have multiple copies to keep in sync.

The key word is *deliberate*. Accidental redundancy is a bug; intentional denormalization for a known read pattern is engineering. This lesson builds a normalized schema, shows the anomalies it prevents, then denormalizes specific parts for specific reasons.

## The Concept

### Normalization: store every fact once

Consider an orders system stored as one flat table:

```
orders_flat
order_id | customer_name | customer_email   | product | price | qty
1        | Ada           | ada@example.com  | Book    | 20    | 2
2        | Ada           | ada@example.com  | Pen     | 3     | 5
```

Ada's name and email repeat in every order. Problems (the classic **anomalies**):

- **Update anomaly**: Ada changes her email → you must update every order row, and any you miss creates contradictory data.
- **Insertion anomaly**: you can't record a customer until they place an order.
- **Deletion anomaly**: delete Ada's only order and you lose her contact info entirely.

Normalization splits this into tables, each describing one kind of thing, linked by keys:

```mermaid
erDiagram
  CUSTOMERS ||--o{ ORDERS : places
  ORDERS ||--|{ ORDER_ITEMS : contains
  PRODUCTS ||--o{ ORDER_ITEMS : "appears in"
  CUSTOMERS { int id PK; text name; text email }
  ORDERS { int id PK; int customer_id FK; text created }
  PRODUCTS { int id PK; text name; int price }
  ORDER_ITEMS { int order_id FK; int product_id FK; int qty }
```

Now Ada's email lives in exactly one row. Change it once, and every order referencing her sees the update. The cost: to show an order with customer and product details, you **join** across tables.

### Keys

- **Primary key**: uniquely identifies a row (e.g. `customers.id`). One per table.
- **Foreign key**: a column referencing another table's primary key (e.g. `orders.customer_id` → `customers.id`). It enforces referential integrity — you can't create an order for a customer who doesn't exist.

### The normal forms (briefly)

Normalization is formalized in "normal forms." You don't need the theory memorized; the practical core:

- **1NF**: no repeating groups; each cell holds one value.
- **2NF**: every non-key column depends on the *whole* primary key.
- **3NF**: no non-key column depends on another non-key column.

In practice, "3NF" ≈ "every fact stored once, in the table it belongs to." That's the default target.

### Denormalization: store facts where you read them

Joins are correct but cost time, especially across large tables or shards. When a read is hot and the data rarely changes, you can **denormalize** — store redundant, pre-joined data to skip the join:

```
Normalized: SELECT o.*, c.name FROM orders o JOIN customers c ...
Denormalized: orders table also stores customer_name directly → no join
```

Common denormalization moves:

- **Redundant columns**: copy `customer_name` into `orders` so order lists need no join.
- **Precomputed aggregates**: store `comment_count` on a post instead of `COUNT(*)`-ing comments every read.
- **Materialized views**: a maintained, pre-joined table the database refreshes.

The cost is always the same: **you now have copies to keep consistent.** Change a customer's name and you must update it everywhere it's duplicated. You're trading write complexity (and risk of drift) for read speed. Do it only where the read pattern justifies it and the data is relatively stable.

### The star schema (analytics)

Analytical systems (data warehouses) deliberately denormalize into a **star schema**: a central *fact* table (one row per event, e.g. a sale) surrounded by *dimension* tables (product, date, customer). This shape makes aggregate queries ("total sales by product by month") fast, trading the write-time normalization of transactional systems for read-time analytical speed.

```
        dim_date
            |
dim_product — fact_sales — dim_customer
            |
        dim_store
```

### A common misconception

"Denormalize for performance" is repeated like a universal rule, but premature denormalization is a frequent source of bugs and data drift. Normalize first — it's correct, flexible, and a well-indexed join on a normal database is fast for the vast majority of applications. Denormalize only when you've identified a *specific* hot read that's measurably too slow, and you understand the consistency burden you're taking on. The opposite mistake exists too: never denormalizing and forcing seven-way joins on a hot path. Both extremes are wrong; the schema should follow the access patterns.

## Build It

You'll create a normalized schema, query it with joins, then add a denormalized column. Run `code/schema_demo.sql`.

### Step 1 — Normalized tables

```sql
-- Run: sqlite3 shop.db < schema_demo.sql
DROP TABLE IF EXISTS order_items; DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products; DROP TABLE IF EXISTS customers;

CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT);
CREATE TABLE products  (id INTEGER PRIMARY KEY, name TEXT, price INTEGER);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER REFERENCES customers(id),
  created TEXT
);
CREATE TABLE order_items (
  order_id   INTEGER REFERENCES orders(id),
  product_id INTEGER REFERENCES products(id),
  qty        INTEGER
);
```

### Step 2 — Seed data (each fact once)

```sql
INSERT INTO customers VALUES (1,'Ada','ada@example.com'),(2,'Bob','bob@example.com');
INSERT INTO products  VALUES (1,'Book',20),(2,'Pen',3);
INSERT INTO orders    VALUES (1,1,'2024-05-01'),(2,1,'2024-05-02');
INSERT INTO order_items VALUES (1,1,2),(1,2,5),(2,2,1);
```

### Step 3 — Read with joins

```sql
SELECT o.id AS order_id, c.name, p.name AS product, oi.qty, p.price * oi.qty AS line_total
FROM orders o
JOIN customers c   ON c.id = o.customer_id
JOIN order_items oi ON oi.order_id = o.id
JOIN products p     ON p.id = oi.product_id
ORDER BY o.id;
```

### Step 4 — Update once, see it everywhere (no anomaly)

```sql
UPDATE customers SET email = 'ada@newmail.com' WHERE id = 1;
-- every order referencing customer 1 now reflects the new email; one row changed
```

### Step 5 — Denormalize a hot read deliberately

```sql
-- Precompute an aggregate: total items per order, stored on the order
ALTER TABLE orders ADD COLUMN item_count INTEGER DEFAULT 0;
UPDATE orders SET item_count = (
  SELECT COALESCE(SUM(qty),0) FROM order_items WHERE order_id = orders.id
);
SELECT id, item_count FROM orders;   -- now readable with no join/aggregation
```

### Step 6 — Run it

```bash
sqlite3 shop.db < schema_demo.sql
```

Compare to `outputs/expected.md`. Note the join assembles the full picture from normalized parts, and the denormalized `item_count` is then readable without aggregating.

## Exercises

1. **Run it.** Confirm the join produces the order lines and the single email update is reflected without touching order rows.

2. **Cause an anomaly.** Imagine the flat `orders_flat` table from the lesson. Write the UPDATE you'd need to change Ada's email there, and explain why it's error-prone.

3. **Enforce integrity.** Try inserting an `order` with a `customer_id` that doesn't exist (enable foreign keys with `PRAGMA foreign_keys=ON;`). What happens, and which guarantee is that?

4. **Keep denormalized data fresh.** After adding `item_count`, insert a new `order_item`. Is `item_count` still correct? Write the trigger or update needed to keep it in sync — this is the cost of denormalization.

5. **Design a star schema.** Sketch a fact table and three dimensions for "track every product view on a website." What aggregate query does this shape make fast?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Normalization | "No duplicate data" | Structuring tables so each fact is stored exactly once, eliminating update anomalies |
| Denormalization | "Pre-join for speed" | Deliberately adding redundant data to skip joins on hot reads, at a consistency cost |
| Primary key | "Row's unique ID" | A column uniquely identifying each row in a table |
| Foreign key | "Link to another table" | A column referencing another table's primary key, enforcing referential integrity |
| Anomaly | "Data inconsistency" | An update/insert/delete problem caused by redundant, unnormalized data |
| Join | "Combine tables" | Resolving a relationship at query time by matching keys across tables |
| Star schema | "Analytics layout" | A central fact table surrounded by dimension tables, optimized for aggregate queries |
| Materialized view | "Saved pre-joined result" | A maintained table holding a precomputed query result, refreshed by the database |

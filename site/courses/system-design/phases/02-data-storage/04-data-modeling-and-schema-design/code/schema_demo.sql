-- Run: sqlite3 shop.db < schema_demo.sql
-- Normalized schema, joins, single-point update, then deliberate denormalization.

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

INSERT INTO customers VALUES (1,'Ada','ada@example.com'),(2,'Bob','bob@example.com');
INSERT INTO products  VALUES (1,'Book',20),(2,'Pen',3);
INSERT INTO orders    VALUES (1,1,'2024-05-01'),(2,1,'2024-05-02');
INSERT INTO order_items VALUES (1,1,2),(1,2,5),(2,2,1);

.headers on
.mode column

.print '--- Read with joins (assemble from normalized parts) ---'
SELECT o.id AS order_id, c.name, p.name AS product, oi.qty,
       p.price * oi.qty AS line_total
FROM orders o
JOIN customers c    ON c.id = o.customer_id
JOIN order_items oi ON oi.order_id = o.id
JOIN products p     ON p.id = oi.product_id
ORDER BY o.id, p.name;

.print ''
.print '--- Update email ONCE; every order reflects it (no anomaly) ---'
UPDATE customers SET email = 'ada@newmail.com' WHERE id = 1;
SELECT id, name, email FROM customers WHERE id = 1;

.print ''
.print '--- Deliberate denormalization: precompute item_count per order ---'
ALTER TABLE orders ADD COLUMN item_count INTEGER DEFAULT 0;
UPDATE orders SET item_count = (
  SELECT COALESCE(SUM(qty),0) FROM order_items WHERE order_id = orders.id
);
SELECT id, item_count FROM orders ORDER BY id;

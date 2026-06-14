-- Run: sqlite3 demo.db < indexing_demo.sql
-- Demonstrates how an index turns a full scan into an indexed search.

DROP TABLE IF EXISTS users;
CREATE TABLE users (
  id      INTEGER PRIMARY KEY,
  email   TEXT,
  city    TEXT,
  created TEXT
);

-- Generate 200,000 rows using a recursive CTE
INSERT INTO users (email, city, created)
WITH RECURSIVE seq(n) AS (
  SELECT 1 UNION ALL SELECT n + 1 FROM seq WHERE n < 200000
)
SELECT
  'user' || n || '@example.com',
  'city' || (n % 100),
  '2024-01-' || printf('%02d', (n % 28) + 1)
FROM seq;

.print '--- 1. Plan for email lookup BEFORE index (expect SCAN) ---'
EXPLAIN QUERY PLAN
SELECT * FROM users WHERE email = 'user150000@example.com';

.print ''
.print '--- 2. Create the index ---'
CREATE INDEX idx_users_email ON users(email);

.print '--- 3. Plan for the SAME query AFTER index (expect SEARCH USING INDEX) ---'
EXPLAIN QUERY PLAN
SELECT * FROM users WHERE email = 'user150000@example.com';

.print ''
.print '--- 4. Composite index for filter + sort ---'
CREATE INDEX idx_users_city_created ON users(city, created);
EXPLAIN QUERY PLAN
SELECT * FROM users WHERE city = 'city42' ORDER BY created DESC;

.print ''
.print '--- 5a. Leftmost prefix used (filter on city) ---'
EXPLAIN QUERY PLAN SELECT * FROM users WHERE city = 'city42';

.print '--- 5b. Leftmost prefix skipped (filter only on created -> SCAN) ---'
EXPLAIN QUERY PLAN SELECT * FROM users WHERE created = '2024-01-15';

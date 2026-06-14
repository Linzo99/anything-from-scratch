# Indexing & Query Performance

> A query that scans a million rows and a query that jumps straight to the one you want run the same SQL — the only difference is whether an index exists. That difference is often 1000×.

**Type:** Build
**Languages:** SQL
**Prerequisites:** Phase 2, Lesson 01 — SQL vs NoSQL
**Time:** ~50 minutes

## Learning Objectives

- Explain what a database index is and the B-tree structure behind it
- Read a query plan with `EXPLAIN QUERY PLAN` to see scan vs index use
- Create single-column and composite indexes and measure the speedup
- Understand the write cost indexes impose, so you don't over-index
- Recognize when an index helps and when the database ignores it

## The Problem

A database table is, by default, an unordered heap of rows. To answer `SELECT * FROM users WHERE email = 'x'`, the database has no choice but to look at *every row* and check — a **full table scan**. With a thousand rows that's instant. With ten million, it's a disk-grinding crawl, and it gets worse linearly as the table grows. The exact same query that was fast in development becomes the production incident that takes the site down under load.

Indexes are the fix, and they're the single highest-leverage performance tool in a relational database. An index is a separate, sorted data structure that lets the database find matching rows without scanning — turning an O(n) scan into an O(log n) lookup. The speedup at scale is dramatic: a query that scanned 10 million rows in seconds can return in under a millisecond with the right index.

But indexes aren't free. Each one is extra data the database must keep sorted, which means every insert, update, and delete has to update every relevant index too. Over-index a write-heavy table and you've traded read speed for write slowness and disk bloat. Indexing well means knowing *which* queries matter and indexing exactly for them — which requires reading query plans, the skill this lesson builds.

## The Concept

### What an index actually is

An index is a sorted copy of one or more columns, plus a pointer back to the full row. Most databases implement it as a **B-tree** (balanced tree): a structure that stays shallow even for huge datasets, so any value is reachable in a few hops.

```
Full table scan (no index)        B-tree index lookup
--------------------------        -------------------
row 1: email=z@.. ✗               find 'm@..':
row 2: email=a@.. ✗                        [m]
row 3: email=m@.. ✓  (found!)             /   \
... check all N rows ...               [d]     [t]
                                       / \     / \
O(n) — grows with table size        [a][f]  [p][z]
                                    O(log n) — a few hops
```

Because the index is sorted, the database can binary-search it instead of scanning. A B-tree of 10 million entries is only about 3–4 levels deep, so a lookup touches a handful of nodes instead of millions of rows.

### Reading the query plan

You never have to guess whether an index is used — the database tells you. `EXPLAIN QUERY PLAN` (SQLite; `EXPLAIN ANALYZE` in Postgres) shows how a query will execute:

```sql
EXPLAIN QUERY PLAN SELECT * FROM users WHERE email = 'a@example.com';
```

- **`SCAN users`** → full table scan. Bad for large tables; means no usable index.
- **`SEARCH users USING INDEX ...`** → the database is using an index. Good.

Learning to read these two phrases is most of practical indexing: write a query, check the plan, add an index if it's scanning, confirm the plan flips to a search.

### Composite indexes and column order

An index can cover multiple columns. A composite index on `(user_id, created_at)` is sorted first by `user_id`, then by `created_at` within each user — perfect for "this user's rows, newest first." But column order matters: this index helps queries that filter on `user_id` (or `user_id` + `created_at`), but **not** a query that filters only on `created_at`. The rule of thumb (the "leftmost prefix"): an index can be used for any query that filters on a leftmost prefix of its columns.

```
Index on (user_id, created_at) helps:
  WHERE user_id = 5                         ✓ (leftmost prefix)
  WHERE user_id = 5 AND created_at > '...'   ✓ (full)
  WHERE created_at > '...'                    ✗ (skips the leftmost column)
```

### The write cost

Every index must be kept in sync. Insert a row, and the database inserts into the table *and* into every index on it. A table with five indexes makes every write roughly five times more index-maintenance work. This is the core tradeoff:

```
More indexes  →  faster reads, slower writes, more disk
Fewer indexes →  slower reads, faster writes, less disk
```

So you don't index everything — you index the columns your important queries filter and sort on, and you leave write-heavy tables lean. Measuring the read benefit (this lesson) against the write cost is the job.

### A common misconception

"Add an index and every query gets faster." No — an index only helps queries that filter or sort on its columns, and the database may *ignore* an index if it estimates a scan is cheaper (e.g. when a query matches most rows anyway, scanning is faster than millions of index lookups). Indexes also don't help with leading wildcards (`LIKE '%foo'`) because the sorted order is useless when you don't know the prefix. Always verify with the query plan rather than assuming.

## Build It

You'll build a table, fill it with rows, and watch a query go from scan to index. Run `code/indexing_demo.sql` with SQLite, or follow along. Create the file and run `sqlite3 demo.db < indexing_demo.sql`.

### Step 1 — Create a table and generate rows

```sql
-- Run: sqlite3 demo.db < indexing_demo.sql
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
```

### Step 2 — Look at the plan WITHOUT an index

```sql
EXPLAIN QUERY PLAN
SELECT * FROM users WHERE email = 'user150000@example.com';
```

You'll see `SCAN users` — a full scan of 200,000 rows.

### Step 3 — Add an index and re-check the plan

```sql
CREATE INDEX idx_users_email ON users(email);

EXPLAIN QUERY PLAN
SELECT * FROM users WHERE email = 'user150000@example.com';
```

Now you'll see `SEARCH users USING INDEX idx_users_email` — the scan is gone.

### Step 4 — A composite index for filter + sort

```sql
CREATE INDEX idx_users_city_created ON users(city, created);

EXPLAIN QUERY PLAN
SELECT * FROM users WHERE city = 'city42' ORDER BY created DESC;
```

The plan uses the composite index for both the filter and the ordering.

### Step 5 — Show the leftmost-prefix rule

```sql
-- Uses idx_users_city_created (filters on leftmost column 'city')
EXPLAIN QUERY PLAN SELECT * FROM users WHERE city = 'city42';

-- Does NOT use it (filters only on 'created', skipping 'city')
EXPLAIN QUERY PLAN SELECT * FROM users WHERE created = '2024-01-15';
```

### Step 6 — Run the whole thing

```bash
sqlite3 demo.db < indexing_demo.sql
```

Compare the plan output to `outputs/expected.md`. The key observation: identical queries, but `SCAN` becomes `SEARCH ... USING INDEX` once the right index exists.

## Exercises

1. **Run it.** Confirm the email query flips from `SCAN` to `SEARCH USING INDEX` after `CREATE INDEX`. That flip is the whole point.

2. **Time it.** In the SQLite shell run `.timer on`, then run the email query before and after creating the index (drop it first with `DROP INDEX`). Record both times.

3. **Break the prefix.** Write a query that filters only on `created` and confirm from the plan that the composite index is *not* used. Then add an index on `(created)` and re-check.

4. **Measure the write cost.** Time inserting 50,000 more rows with zero indexes vs with three indexes present. Quantify the slowdown.

5. **Trick the optimizer.** Write a query matching ~90% of rows (e.g. `WHERE id > 0`). Does the database use an index or scan? Explain why a scan can be the smarter plan here.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Index | "Makes queries fast" | A sorted auxiliary structure (usually a B-tree) enabling O(log n) lookups instead of full scans |
| Full table scan | "Checking every row" | Reading all rows to find matches; O(n), fine for small tables, deadly for large ones |
| B-tree | "Balanced tree" | The shallow, sorted tree most indexes use; reachable in a few hops even for millions of rows |
| Query plan | "EXPLAIN output" | The database's description of how it will run a query — scan or index, join order, etc. |
| Composite index | "Multi-column index" | An index on several columns, usable for queries filtering a leftmost prefix of them |
| Leftmost prefix | "Column order matters" | Rule that a composite index helps only queries filtering its first column(s) in order |
| Over-indexing | "Too many indexes" | Adding indexes that slow writes and bloat disk without serving important queries |

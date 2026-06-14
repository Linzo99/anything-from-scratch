# Expected Output

Running `sqlite3 demo.db < indexing_demo.sql` should produce:

```
--- 1. Plan for email lookup BEFORE index (expect SCAN) ---
QUERY PLAN
`--SCAN users

--- 2. Create the index ---
--- 3. Plan for the SAME query AFTER index (expect SEARCH USING INDEX) ---
QUERY PLAN
`--SEARCH users USING INDEX idx_users_email (email=?)

--- 4. Composite index for filter + sort ---
QUERY PLAN
`--SEARCH users USING INDEX idx_users_city_created (city=?)

--- 5a. Leftmost prefix used (filter on city) ---
QUERY PLAN
`--SEARCH users USING INDEX idx_users_city_created (city=?)
--- 5b. Leftmost prefix skipped (filter only on created -> SCAN) ---
QUERY PLAN
`--SCAN users
```

The whole lesson is in the difference between steps 1 and 3: the **identical query**
goes from `SCAN users` (reading all 200,000 rows) to `SEARCH users USING INDEX`
(jumping straight to the match) — purely because the index now exists.

Step 5b confirms the leftmost-prefix rule: a query filtering only on `created`
cannot use the `(city, created)` index and falls back to a scan.

Common issues:
- **`Parse error` on `.print`:** the `.print` lines are SQLite dot-commands and
  only work in the `sqlite3` CLI, not when pasted into another tool. Run the file
  with `sqlite3 demo.db < indexing_demo.sql`.
- **Row generation is slow:** 200,000 rows via a recursive CTE takes a second or
  two — that's expected.
- **Want timings?** Start `sqlite3 demo.db`, run `.timer on`, then run the queries
  manually before/after creating the index to see the millisecond difference.
- Delete `demo.db` between runs for a clean slate.

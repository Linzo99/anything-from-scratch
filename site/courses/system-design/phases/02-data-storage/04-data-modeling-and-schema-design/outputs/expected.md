# Expected Output

Running `sqlite3 shop.db < schema_demo.sql` should produce:

```
--- Read with joins (assemble from normalized parts) ---
order_id  name  product  qty  line_total
--------  ----  -------  ---  ----------
1         Ada   Book     2    40
1         Ada   Pen      5    15
2         Ada   Pen      1    3

--- Update email ONCE; every order reflects it (no anomaly) ---
id  name  email
--  ----  ---------------
1   Ada   ada@newmail.com

--- Deliberate denormalization: precompute item_count per order ---
id  item_count
--  ----------
1   7
2   1
```

What to notice:
- The **join** reconstructs the full order picture (customer name, product,
  line total) from four normalized tables — each fact stored once.
- The **email update** touched a single `customers` row, yet every order for Ada
  now reflects the new address. That's the payoff of normalization: no update
  anomaly.
- The **denormalized `item_count`** (7 = 2 + 5 for order 1, 1 for order 2) is now
  readable directly with no join or aggregation — faster reads, but you've taken
  on the job of keeping it in sync when items change (Exercise 4).

Common issues:
- **Column formatting differs:** harmless — it depends on your sqlite3 version's
  `.mode column` rendering. The values are what matter.
- **`item_count` is 0:** the `ALTER TABLE` adds the column with default 0; the
  following `UPDATE` populates it. Make sure both run (use the file, not
  copy-paste of partial statements).
- Delete `shop.db` before re-running for a clean slate.

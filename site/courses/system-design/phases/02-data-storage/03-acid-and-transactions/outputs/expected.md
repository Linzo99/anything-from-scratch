# Expected Output

Running `sqlite3 bank.db < transactions_demo.sql` should produce:

```
--- Initial balances ---
Alice|500
Bob|100

--- Committed transfer: Alice -> Bob 100 ---
Alice|400
Bob|200

--- Rolled-back transfer: discarded, balances unchanged ---
Alice|400
Bob|200

--- Atomic increment (safe under concurrency): Bob +50 ---
Alice|400
Bob|250
```

What to notice:
- The **committed** transfer changes both balances together (Alice 500→400,
  Bob 100→200) — atomicity: both updates land as one unit.
- The **rolled-back** transfer leaves balances exactly as they were (still
  400/200) — the debit was discarded by `ROLLBACK` as if it never ran.
- The **atomic increment** (`SET balance = balance + 50`) is the safe way to
  modify a value under concurrency, because the database serializes the single
  statement and no lost update can occur.

Common issues:
- **`.print` errors:** those are sqlite3 CLI dot-commands; run the file with the
  `sqlite3 bank.db < ...` form, not by pasting into another tool.
- **Balances look wrong on a re-run:** delete `bank.db` first — the script
  recreates the table, but a leftover file from a half-run can confuse you.
- To see a lost update for real, open two `sqlite3` sessions and do a
  read-modify-write in each (Exercise 3).

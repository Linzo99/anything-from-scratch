-- Run: sqlite3 bank.db < transactions_demo.sql
-- Demonstrates atomicity: commit sticks, rollback vanishes.

DROP TABLE IF EXISTS accounts;
CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER);
INSERT INTO accounts VALUES (1, 'Alice', 500), (2, 'Bob', 100);

.print '--- Initial balances ---'
SELECT name, balance FROM accounts;

.print ''
.print '--- Committed transfer: Alice -> Bob 100 ---'
BEGIN;
  UPDATE accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
SELECT name, balance FROM accounts;

.print ''
.print '--- Rolled-back transfer: discarded, balances unchanged ---'
BEGIN;
  UPDATE accounts SET balance = balance - 1000 WHERE id = 1;  -- mistake
ROLLBACK;
SELECT name, balance FROM accounts;

.print ''
.print '--- Atomic increment (safe under concurrency): Bob +50 ---'
UPDATE accounts SET balance = balance + 50 WHERE id = 2;
SELECT name, balance FROM accounts;

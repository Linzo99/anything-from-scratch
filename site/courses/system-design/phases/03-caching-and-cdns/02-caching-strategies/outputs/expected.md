# Expected Output

Running `python caching_strategies.py` should produce:

```
Cache-aside:
  read1: ('Ada', 'MISS')
  read2: ('Ada', 'HIT')
  read3: ('Ada Lovelace', 'MISS')
  DB reads=2 writes=1

Write-back:
  cache value: Grace
  DB value (pre-flush): Ada
  DB value (post-flush): Grace
  >> if the cache died before flush, 'Grace' would be LOST
```

What to notice:
- **Cache-aside**: read1 is a MISS (cold cache → loads from DB), read2 is a HIT
  (served from cache, no DB read), and read3 is a **MISS again** — because the
  write *invalidated* (deleted) the entry rather than updating it, forcing a fresh
  read. Two DB reads total, one DB write.
- **Write-back**: the cache shows the new value ("Grace") immediately, but the DB
  still shows the old value ("Ada") until `flush()` runs. This lag is the whole
  point — and the danger: a cache crash before flush loses the write entirely.

Common issues:
- **read3 shows HIT:** then your `write` is updating the cache instead of deleting
  it. Cache-aside must `delete` on write so the next read re-loads.
- **DB shows 'Grace' before flush:** then write-back is writing to the DB
  synchronously — it must only touch the cache and defer the DB write to `flush()`.

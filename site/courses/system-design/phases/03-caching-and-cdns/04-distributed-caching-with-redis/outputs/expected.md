# Expected Output

Running `python stampede.py` should produce:

```
Naive cache-aside  100 concurrent requests -> 100 DB queries
Lock-protected     100 concurrent requests -> 1 DB queries

The lock collapses the stampede to a single DB query.
```

What to notice:
- **Naive cache-aside**: 100 concurrent requests hit a cold (missing) key, all
  miss, and all run the expensive DB query — **100 identical queries** for one
  key. That's the thundering herd: a single missing key generates a flood.
- **Lock-protected**: only the first thread acquires the per-key lock and queries
  the DB; the other 99 wait, then read the value it cached — **1 DB query** total.
  This is request coalescing (single-flight).

This is the difference between a cache that protects the database and one that, at
the worst moment (expiry / cold start), becomes the trigger that overloads it.

Common issues:
- **Naive shows fewer than 100:** timing-dependent — if the first query finishes
  before some threads check the cache, they'll hit. On most machines the 50ms
  sleep keeps it near 100. The exact number isn't the point; "many vs one" is.
- **Lock-protected shows more than 1:** check that the double-check (`cache.get`
  inside the lock) is present, so waiters return the freshly-cached value instead
  of querying again.
- **Numbers vary run to run:** concurrency is inherently nondeterministic; the
  naive count may be 98–100 and the protected count should be 1.

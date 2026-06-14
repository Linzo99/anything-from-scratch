# Expected Output

Running `python lru_cache.py` should produce:

```
Workload length: 24, cache size: 3, hot keys: 1,2,3

LRU : hits= 6  misses=18  evictions=15
FIFO: hits= 4  misses=20  evictions=17

LRU keeps the reused hot keys resident; FIFO evicts them by age.
```

What to notice:
- **LRU gets more hits (6 vs 4)** on the same workload and cache size. The
  workload interleaves the hot keys 1, 2, 3 with one-off keys 4–8. Each time a
  one-off key arrives, something must be evicted.
- **LRU** evicts the genuinely least-recently-used entry, so it tends to keep the
  constantly-reused hot keys around — more hits.
- **FIFO** evicts by insertion age, so it sometimes throws out a hot key that was
  just accessed simply because it was inserted earlier — fewer hits.

The gap is modest here because the cache (size 3) and hot set (3 keys) are tiny
and the one-off keys keep forcing evictions. With a larger gap between hot-set
size and cache size, the difference grows.

Common issues:
- **LRU and FIFO show identical numbers:** your FIFO is probably reordering on
  `get` (making it act like LRU). FIFO must NOT move an entry on access — only on
  insertion.
- **LRU hits are lower than FIFO:** check that `get` moves the node to the front
  (MRU) and that eviction removes `self.tail.prev` (the LRU end).

# Expected Output

Running `python consistent_hashing.py` should produce:

```
Adding a 5th node to 4 (10000 keys):
  Modulo hashing:      8027 keys moved (80.3%)
  Consistent hashing:  1832 keys moved (18.3%)
  (ideal minimum is about 1/5 = 20%)

Consistent hashing distribution over 5 nodes (vnodes=150):
  node A:  2067  (20.7%)
  node B:  2264  (22.6%)
  node C:  1967  (19.7%)
  node D:  1870  (18.7%)
  node E:  1832  (18.3%)
```

What to notice:
- **Modulo moves ~80%** of keys just to add ONE node (going 4→5). For a cache
  this is a near-total miss storm; for a datastore it's moving almost all your
  data over the network.
- **Consistent hashing moves ~18%** — essentially the ideal minimum of 1/5 (20%).
  Only the keys the new node should take actually move; everyone else keeps their
  owner.
- **Distribution is roughly even** (~20% per node) thanks to 150 virtual nodes per
  physical node. Note that node E (the new one) ends up owning ~18% — exactly the
  keys that moved.

Common issues:
- **Consistent hashing also moves ~80%:** you're probably re-creating the ring
  from scratch instead of calling `add_node("E")` on the existing ring. The whole
  point is incremental addition.
- **Very uneven distribution:** lower `vnodes` (try `vnodes=1`) makes the ring
  lopsided — that's the lesson of Exercise 3. With vnodes=150 it should be within
  a few percent of even.
- **Exact counts identical to the byte:** they're deterministic (md5-based) for
  these inputs, so your run should match closely.

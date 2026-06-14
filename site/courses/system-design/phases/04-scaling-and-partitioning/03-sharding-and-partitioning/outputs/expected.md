# Expected Output

Running `python sharding.py` should produce:

```
Hash partitioning, sequential unique keys (even):
  shard 0:  2486  #########
  shard 1:  2495  #########
  shard 2:  2558  ##########
  shard 3:  2461  #########

Range partitioning, name-skewed keys (HOT shard 0):
  shard 0:  8000  ##################################
  shard 1:   500  ##
  shard 2:   500  ##
  shard 3:   200

Hash partitioning, KEY=country (HOT: low cardinality):
  shard 0:   700  ##
  shard 1:     0
  shard 2:  8700  ##################################
  shard 3:   600  ##

Hash partitioning, KEY=user_id (even, high cardinality):
  shard 0:  2486  #########
  shard 1:  2495  #########
  shard 2:  2558  ##########
  shard 3:  2461  #########
```

What to notice:
- **Hash + unique keys → even** (~2500 each). Hashing scrambles even sequential
  keys across shards.
- **Range + name-skew → hot shard 0** (8000 of 9200). All the 'a' names fall into
  the first range bucket. Range partitioning is only as even as the key distribution.
- **Hash + KEY=country → still hot** (shard 2 has 8700). Hashing doesn't help when
  the *key itself* has low cardinality: every "US" row hashes to the same shard, so
  the 80%-US skew concentrates regardless. (Shard 1 is empty — no country hashed there.)
- **Hash + KEY=user_id → even.** A high-cardinality, unskewed key is what actually
  spreads load.

The lesson: **the partition key, not the hashing, determines balance.** Hashing
fixes skew from *sequential* keys but not from a *low-cardinality* key.

Common issues:
- **All four look even:** the country case must use the country string as the key
  (few distinct values). If you keyed by a unique id, you'd lose the hotspot demo.
- **Exact counts differ:** hash bucketing depends on md5; with these inputs the
  numbers above are deterministic. The shape (even vs hot) is the point.

# Sharding & Partitioning

> Replication scales reads but not writes — every write still hits one leader. When that leader can't keep up, you split the data itself across machines. Now the question is: split it *how*?

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 4, Lesson 02 — Database Replication
**Time:** ~50 minutes

## Learning Objectives

- Explain why sharding is required to scale writes and storage
- Implement range-based and hash-based partitioning
- Expose and reason about the hot-shard (hotspot) problem
- Choose a partition key that distributes load evenly
- Recognize the operations sharding makes hard: joins, transactions, rebalancing

## The Problem

Replication (Lesson 02) gives every machine the *full* dataset, which is great for reads but useless for two limits: **write throughput** (every write still funnels through the single leader) and **storage** (the whole dataset must fit on each machine). When you have more writes than one leader can handle, or more data than one disk can hold, copying isn't enough — you have to *divide*. **Sharding** (horizontal partitioning) splits the dataset into pieces and puts each piece on a different machine, so each shard handles only its slice of the writes and stores only its slice of the data.

This is the heavy artillery of scaling, and it's painful precisely because it breaks the illusion of one database. Once `users` lives on five shards, a query for "all users in city X" might have to hit all five; a join between `users` and `orders` only works if related rows landed on the same shard; a transaction spanning shards needs distributed coordination. You take on this complexity only when you must — but for the largest systems, you must.

The single most important decision in sharding is the **partition key**: the attribute that determines which shard a row lands on. Choose well and load spreads evenly across shards. Choose badly and one shard gets all the traffic — a **hot shard** — while the others idle, leaving you with all the complexity of sharding and none of the benefit. This lesson builds both partitioning schemes and shows exactly how a bad key creates a hotspot.

## The Concept

### Sharding vs replication

```
Replication: every node has ALL the data
   Node A: [1 2 3 4 5 6]   Node B: [1 2 3 4 5 6]   (copies)

Sharding: each node has SOME of the data
   Shard A: [1 2]   Shard B: [3 4]   Shard C: [5 6]   (slices)
```

They're complementary and usually combined: shard for write/storage scale, then replicate each shard for read scale and availability. A real system has, say, 8 shards, each with a leader and two followers.

### Range-based partitioning

Assign contiguous ranges of the key to shards: users A–H on shard 1, I–P on shard 2, Q–Z on shard 3.

```
Key range    Shard
---------    -----
A - H        Shard 1
I - P        Shard 2
Q - Z        Shard 3
```

Pro: **range queries are efficient** — "all keys between M and O" hits one shard. Used by systems that need ordered scans (e.g. time-ranges). Con: ranges are easily uneven — if most usernames start with common letters, those shards are overloaded. And sequential keys (timestamps, auto-increment IDs) are pathological: all *new* writes go to the last shard, making it a permanent hotspot.

### Hash-based partitioning

Hash the key and assign by the hash (e.g. `shard = hash(key) % N`). The hash scrambles keys, so even sequential or skewed keys spread evenly.

```
shard = hash(key) % num_shards
"user42"  -> hash -> 0x8f3a... -> % 4 -> shard 2
"user43"  -> hash -> 0x1c7e... -> % 4 -> shard 1   (adjacent keys, different shards)
```

Pro: **even distribution** even for sequential keys — solves the hotspot-from-skew problem. Con: **range queries are destroyed** — adjacent keys land on different shards, so "keys between M and O" must hit *every* shard. Also, plain `% N` makes adding a shard catastrophic (almost every key remaps) — which is why consistent hashing exists (next lesson).

### The hot-shard problem

Even with hashing, load can concentrate if the **partition key itself is skewed**. The classic example: sharding by `country` when 80% of users are in one country — hashing the country name still sends all those users to one shard, because they share a key value. Or sharding social data by `celebrity_id` when one celebrity has 100M followers: that shard melts.

```
Bad key (country):                 Good key (user_id):
Shard 1: [US users] ████████ 80%   Shard 1: ██ 25%
Shard 2: [other]    █ 7%           Shard 2: ██ 25%
Shard 3: [other]    █ 7%           Shard 3: ██ 25%
Shard 4: [other]    █ 6%           Shard 4: ██ 25%
```

The fix is a high-cardinality, uniformly-accessed partition key — usually a per-entity ID (user_id), sometimes a composite key — so no single value dominates. Choosing the partition key is the core sharding skill.

### What sharding makes hard

```
Operation         Problem when sharded
----------------  --------------------------------------------------
Cross-shard join  related rows on different shards; join must gather
                  from many shards (slow) — avoid by co-locating data
Transactions      a transaction spanning shards needs distributed
                  commit (2PC) — slow and complex; avoid if possible
Range queries     hash sharding scatters ranges across all shards
Rebalancing       adding/removing a shard means moving data (next lesson)
Unique IDs        auto-increment doesn't work across shards; need
                  global ID generation (snowflake, UUIDs)
```

The design goal is to keep most operations *within a single shard* by choosing a key that co-locates related data (e.g. shard by `user_id` so all of a user's data is on one shard).

### A common misconception

"Sharding multiplies your capacity by the number of shards." Only if the load is *evenly distributed*. With a skewed partition key, one hot shard becomes the bottleneck and the others sit idle — you get the complexity of N shards with the throughput of one. Sharding doesn't create even load; the partition key does. The second misconception is reaching for sharding too early: it's the last resort after vertical scaling, read replicas, and caching, because it permanently complicates every query, join, and transaction. Shard when you genuinely can't scale writes or storage any other way.

## Build It

You'll implement both partitioning schemes and visualize how key choice causes hotspots. Create `sharding.py`.

### Step 1 — A simple sharded store

```python
# Run: python sharding.py
import hashlib

class ShardedStore:
    def __init__(self, num_shards, strategy):
        self.num_shards = num_shards
        self.strategy = strategy
        self.shards = [dict() for _ in range(num_shards)]

    def _shard_for(self, key):
        if self.strategy == "hash":
            h = int(hashlib.md5(str(key).encode()).hexdigest(), 16)
            return h % self.num_shards
        elif self.strategy == "range":
            # range by first character bucket (A-Z mapped across shards)
            first = str(key)[0].lower()
            bucket = (ord(first) - ord('a')) if first.isalpha() else 0
            return min(bucket * self.num_shards // 26, self.num_shards - 1)

    def put(self, key, value):
        self.shards[self._shard_for(key)][key] = value

    def distribution(self):
        return [len(s) for s in self.shards]
```

### Step 2 — Distribute uniform keys with hashing

```python
def show(title, store):
    dist = store.distribution()
    total = sum(dist)
    print(f"\n{title}")
    for i, n in enumerate(dist):
        bar = "#" * (n * 40 // max(total, 1))
        print(f"  shard {i}: {n:5}  {bar}")

# 10,000 sequential user ids, hashed -> even
hash_store = ShardedStore(4, "hash")
for i in range(10000):
    hash_store.put(f"user{i}", i)
show("Hash partitioning, sequential keys (even):", hash_store)
```

### Step 3 — Show range partitioning struggling with skew

```python
# Range partitioning with names skewed toward early letters
import random
random.seed(0)
names = (["alice", "adam", "aaron", "amy"] * 2000 +   # many 'a' names
         ["mike", "nina"] * 500 + ["zoe"] * 200)
range_store = ShardedStore(4, "range")
for i, n in enumerate(names):
    range_store.put(f"{n}{i}", i)
show("Range partitioning, name-skewed keys (HOT shard 0):", range_store)
```

### Step 4 — Show a bad partition key (country) creating a hotspot even with hashing

```python
# Sharding by COUNTRY: 80% US -> all US on one shard despite hashing
country_store = ShardedStore(4, "hash")
countries = ["US"] * 8000 + ["FR"] * 700 + ["JP"] * 700 + ["BR"] * 600
for i, c in enumerate(countries):
    country_store.put(c, i)          # KEY is the country -> few distinct keys!
show("Hash partitioning, KEY=country (HOT: low cardinality):", country_store)
```

### Step 5 — Contrast with a good high-cardinality key

```python
good_store = ShardedStore(4, "hash")
for i in range(10000):
    good_store.put(f"user{i}", i)    # KEY is unique per user -> even
show("Hash partitioning, KEY=user_id (even, high cardinality):", good_store)
```

### Step 6 — Run it

```bash
python sharding.py
```

Watch hashing spread unique keys evenly, range partitioning pile up on shard 0 under name skew, and a low-cardinality key (country) create a hotspot even *with* hashing. Compare with `outputs/expected.md`.

## Exercises

1. **Run and diagnose.** Which configurations produce an even spread and which a hot shard? For each hotspot, name the root cause (skew vs low cardinality).

2. **Fix the country hotspot.** Change the key from `country` to `country + ":" + user_id` and re-run. Why does adding the user id fix the distribution while keeping country queryable?

3. **Break hashing's range queries.** With the hash store, write the keys for `user1`..`user5` and find which shard each is on. Why would "users 1 through 5" be a cross-shard query?

4. **Sequential key pathology.** Use range partitioning with keys `"2024-01-01"`, `"2024-01-02"`, ... (timestamps). Which shard gets all *new* writes, and why is this the worst case?

5. **Co-location.** Explain how sharding by `user_id` keeps all of one user's orders on the same shard, and why that avoids cross-shard joins for per-user queries.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Sharding | "Split the data" | Horizontal partitioning: dividing a dataset across machines, each holding a slice |
| Partition key | "Shard key" | The attribute that decides which shard a row goes to; determines load balance |
| Range partitioning | "Split by ranges" | Assigning contiguous key ranges to shards; good for range queries, prone to skew |
| Hash partitioning | "Split by hash" | Assigning by hash of the key; even distribution, but scatters range queries |
| Hot shard / hotspot | "Overloaded shard" | A shard receiving disproportionate load from a skewed or low-cardinality key |
| Cardinality | "Number of distinct values" | High-cardinality keys (user_id) spread well; low-cardinality (country) cause hotspots |
| Cross-shard query | "Hits many shards" | A query that must contact multiple shards; slow, avoided by co-locating data |
| Co-location | "Keep related data together" | Choosing a key so related rows land on the same shard, keeping operations local |

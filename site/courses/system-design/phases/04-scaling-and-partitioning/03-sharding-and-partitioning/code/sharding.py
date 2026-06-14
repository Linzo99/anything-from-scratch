# Run: python sharding.py
# Range vs hash partitioning, and how a bad partition key causes hot shards.
import hashlib
import random


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
            first = str(key)[0].lower()
            bucket = (ord(first) - ord('a')) if first.isalpha() else 0
            return min(bucket * self.num_shards // 26, self.num_shards - 1)

    def put(self, key, value):
        # allow many rows per shard even with repeated keys (use a counter list)
        self.shards[self._shard_for(key)][f"{key}#{value}"] = value

    def distribution(self):
        return [len(s) for s in self.shards]


def show(title, store):
    dist = store.distribution()
    total = sum(dist)
    print(f"\n{title}")
    for i, n in enumerate(dist):
        bar = "#" * (n * 40 // max(total, 1))
        print(f"  shard {i}: {n:5}  {bar}")


# 1. Hash partitioning, sequential unique keys -> even
hash_store = ShardedStore(4, "hash")
for i in range(10000):
    hash_store.put(f"user{i}", i)
show("Hash partitioning, sequential unique keys (even):", hash_store)

# 2. Range partitioning, name-skewed keys -> hot shard 0
random.seed(0)
names = (["alice", "adam", "aaron", "amy"] * 2000 +
         ["mike", "nina"] * 500 + ["zoe"] * 200)
range_store = ShardedStore(4, "range")
for i, n in enumerate(names):
    range_store.put(f"{n}{i}", i)
show("Range partitioning, name-skewed keys (HOT shard 0):", range_store)

# 3. Hash partitioning but KEY=country (low cardinality) -> hotspot anyway
country_store = ShardedStore(4, "hash")
countries = ["US"] * 8000 + ["FR"] * 700 + ["JP"] * 700 + ["BR"] * 600
for i, c in enumerate(countries):
    country_store.put(c, i)
show("Hash partitioning, KEY=country (HOT: low cardinality):", country_store)

# 4. Good high-cardinality key -> even
good_store = ShardedStore(4, "hash")
for i in range(10000):
    good_store.put(f"user{i}", i)
show("Hash partitioning, KEY=user_id (even, high cardinality):", good_store)

print("\nEven load needs a high-cardinality, unskewed partition key.")

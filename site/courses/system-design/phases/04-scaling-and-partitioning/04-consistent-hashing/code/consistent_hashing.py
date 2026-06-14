# Run: python consistent_hashing.py
# Consistent hashing ring with virtual nodes vs modulo hashing.
import hashlib
import bisect
from collections import Counter


class ConsistentHashRing:
    def __init__(self, nodes=None, vnodes=150):
        self.vnodes = vnodes
        self.ring = {}            # ring position -> physical node
        self.sorted_keys = []     # sorted ring positions
        for n in (nodes or []):
            self.add_node(n)

    def _hash(self, key):
        return int(hashlib.md5(str(key).encode()).hexdigest(), 16)

    def add_node(self, node):
        for v in range(self.vnodes):
            pos = self._hash(f"{node}#{v}")
            self.ring[pos] = node
            bisect.insort(self.sorted_keys, pos)

    def remove_node(self, node):
        for v in range(self.vnodes):
            pos = self._hash(f"{node}#{v}")
            del self.ring[pos]
            self.sorted_keys.remove(pos)

    def get_node(self, key):
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect(self.sorted_keys, h) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]   # first node clockwise


def modulo_node(key, nodes):
    h = int(hashlib.md5(str(key).encode()).hexdigest(), 16)
    return nodes[h % len(nodes)]


keys = [f"key{i}" for i in range(10000)]
nodes4 = ["A", "B", "C", "D"]
nodes5 = ["A", "B", "C", "D", "E"]

# Modulo: movement when adding a node
before = {k: modulo_node(k, nodes4) for k in keys}
after = {k: modulo_node(k, nodes5) for k in keys}
moved_mod = sum(1 for k in keys if before[k] != after[k])

# Consistent: movement when adding a node
ring = ConsistentHashRing(nodes4)
before_c = {k: ring.get_node(k) for k in keys}
ring.add_node("E")
after_c = {k: ring.get_node(k) for k in keys}
moved_con = sum(1 for k in keys if before_c[k] != after_c[k])

print(f"Adding a 5th node to 4 ({len(keys)} keys):")
print(f"  Modulo hashing:     {moved_mod:5} keys moved ({100*moved_mod/len(keys):.1f}%)")
print(f"  Consistent hashing: {moved_con:5} keys moved ({100*moved_con/len(keys):.1f}%)")
print(f"  (ideal minimum is about 1/5 = 20%)\n")

dist = Counter(after_c.values())
print("Consistent hashing distribution over 5 nodes (vnodes=150):")
for node in sorted(dist):
    n = dist[node]
    print(f"  node {node}: {n:5}  ({100*n/len(keys):.1f}%)")

# Run: python lru_cache.py
# An O(1) LRU cache (hash map + doubly linked list) compared with FIFO.
from collections import OrderedDict


class Node:
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key=None, val=None):
        self.key, self.val = key, val
        self.prev = self.next = None


class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.map = {}                      # key -> Node
        self.head, self.tail = Node(), Node()  # sentinels: head=MRU, tail=LRU
        self.head.next, self.tail.prev = self.tail, self.head
        self.hits = self.misses = self.evictions = 0

    def _remove(self, node):
        node.prev.next, node.next.prev = node.next, node.prev

    def _add_front(self, node):            # insert right after head (MRU)
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key):
        if key in self.map:
            node = self.map[key]
            self._remove(node)
            self._add_front(node)          # mark most-recently-used
            self.hits += 1
            return node.val
        self.misses += 1
        return None

    def put(self, key, val):
        if key in self.map:
            node = self.map[key]
            node.val = val
            self._remove(node)
            self._add_front(node)
            return
        node = Node(key, val)
        self.map[key] = node
        self._add_front(node)
        if len(self.map) > self.cap:       # over capacity -> evict LRU
            lru = self.tail.prev
            self._remove(lru)
            del self.map[lru.key]
            self.evictions += 1


class FIFOCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.store = OrderedDict()
        self.hits = self.misses = self.evictions = 0

    def get(self, key):
        if key in self.store:
            self.hits += 1
            return self.store[key]          # note: does NOT reorder
        self.misses += 1
        return None

    def put(self, key, val):
        if key not in self.store and len(self.store) >= self.cap:
            self.store.popitem(last=False)  # evict oldest inserted
            self.evictions += 1
        self.store[key] = val


def run(cache, accesses):
    for k in accesses:
        if cache.get(k) is None:
            cache.put(k, f"val{k}")
    return cache


# Skewed workload: keys 1-3 are hot, reused often; 4-8 appear once each
workload = [1, 2, 3, 1, 2, 4, 1, 2, 3, 5, 1, 2, 3, 6, 1, 2, 7, 1, 2, 3, 8, 1, 2, 3]

lru = run(LRUCache(3), workload)
fifo = run(FIFOCache(3), workload)
print(f"Workload length: {len(workload)}, cache size: 3, hot keys: 1,2,3\n")
print(f"LRU : hits={lru.hits:2}  misses={lru.misses:2}  evictions={lru.evictions:2}")
print(f"FIFO: hits={fifo.hits:2}  misses={fifo.misses:2}  evictions={fifo.evictions:2}")
print("\nLRU keeps the reused hot keys resident; FIFO evicts them by age.")

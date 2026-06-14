# Run: python stampede.py
# Demonstrates a cache stampede (thundering herd) and a lock-based fix.
# Pure-Python simulation of a shared cache — no Redis server needed.
import threading
import time

db_queries = 0
db_lock = threading.Lock()


class SharedCache:
    def __init__(self):
        self.store = {}            # key -> (value, expires_at)

    def get(self, k):
        item = self.store.get(k)
        if item and item[1] > time.time():
            return item[0]
        return None

    def set(self, k, v, ttl):
        self.store[k] = (v, time.time() + ttl)


def expensive_db_query():
    global db_queries
    with db_lock:
        db_queries += 1
    time.sleep(0.05)               # simulate a slow query
    return "trending-data"


def naive_read(cache, key):
    v = cache.get(key)
    if v is not None:
        return v
    v = expensive_db_query()       # every concurrent misser does this!
    cache.set(key, v, ttl=1)
    return v


recompute_locks = {}
guard = threading.Lock()


def protected_read(cache, key):
    v = cache.get(key)
    if v is not None:
        return v
    with guard:
        lock = recompute_locks.setdefault(key, threading.Lock())
    with lock:                     # only ONE thread recomputes at a time
        v = cache.get(key)         # double-check: someone may have filled it
        if v is not None:
            return v
        v = expensive_db_query()
        cache.set(key, v, ttl=1)
        return v


def hammer(read_fn, label):
    global db_queries, recompute_locks
    db_queries = 0
    recompute_locks = {}
    cache = SharedCache()          # cold cache -> key missing
    threads = [threading.Thread(target=read_fn, args=(cache, "trending"))
               for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"{label:18} 100 concurrent requests -> {db_queries} DB queries")


hammer(naive_read, "Naive cache-aside")
hammer(protected_read, "Lock-protected")
print("\nThe lock collapses the stampede to a single DB query.")

# Run: python caching_strategies.py
# Implements cache-aside, write-through, and write-back against a simulated DB.


class Database:
    def __init__(self):
        self.store = {"user:1": "Ada"}
        self.reads = 0
        self.writes = 0

    def read(self, k):
        self.reads += 1
        return self.store.get(k)

    def write(self, k, v):
        self.writes += 1
        self.store[k] = v


class Cache:
    def __init__(self):
        self.store = {}

    def get(self, k):
        return self.store.get(k)

    def set(self, k, v):
        self.store[k] = v

    def delete(self, k):
        self.store.pop(k, None)


class CacheAside:
    def __init__(self, db, cache):
        self.db, self.cache = db, cache

    def read(self, k):
        v = self.cache.get(k)
        if v is not None:
            return v, "HIT"
        v = self.db.read(k)          # miss -> load from DB
        if v is not None:
            self.cache.set(k, v)     # populate
        return v, "MISS"

    def write(self, k, v):
        self.db.write(k, v)          # write DB
        self.cache.delete(k)         # invalidate (NOT update)


class WriteThrough:
    def __init__(self, db, cache):
        self.db, self.cache = db, cache

    def read(self, k):
        v = self.cache.get(k)
        return (v, "HIT") if v is not None else (self.db.read(k), "MISS")

    def write(self, k, v):
        self.cache.set(k, v)         # cache first
        self.db.write(k, v)          # then DB, synchronously


class WriteBack:
    def __init__(self, db, cache):
        self.db, self.cache = db, cache
        self.dirty = {}              # pending flushes

    def read(self, k):
        v = self.cache.get(k)
        return (v, "HIT") if v is not None else (self.db.read(k), "MISS")

    def write(self, k, v):
        self.cache.set(k, v)         # ack immediately
        self.dirty[k] = v            # DB not updated yet!

    def flush(self):
        for k, v in self.dirty.items():
            self.db.write(k, v)
        self.dirty.clear()


def demo():
    db, cache = Database(), Cache()
    ca = CacheAside(db, cache)
    print("Cache-aside:")
    print("  read1:", ca.read("user:1"))   # MISS -> loads
    print("  read2:", ca.read("user:1"))   # HIT
    ca.write("user:1", "Ada Lovelace")
    print("  read3:", ca.read("user:1"))   # MISS again (invalidated)
    print(f"  DB reads={db.reads} writes={db.writes}")

    db2, cache2 = Database(), Cache()
    wb = WriteBack(db2, cache2)
    wb.write("user:1", "Grace")
    print("\nWrite-back:")
    print("  cache value:", cache2.get("user:1"))            # Grace
    print("  DB value (pre-flush):", db2.store["user:1"])    # still Ada!
    wb.flush()
    print("  DB value (post-flush):", db2.store["user:1"])   # Grace
    print("  >> if the cache died before flush, 'Grace' would be LOST")


demo()

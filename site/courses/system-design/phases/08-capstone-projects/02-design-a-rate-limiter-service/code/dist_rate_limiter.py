# Run: python dist_rate_limiter.py
# Per-instance counting leaks the limit; a shared atomic counter fixes it.
import threading
import time


class RedisLike:
    """Simulates Redis: atomic INCR with TTL, shared across 'servers'."""
    def __init__(self):
        self.store = {}                  # key -> (count, expires_at)
        self.lock = threading.Lock()     # stands in for Redis's atomicity

    def incr_with_ttl(self, key, ttl):
        with self.lock:                  # ATOMIC: the whole op is serialized
            now = time.time()
            count, exp = self.store.get(key, (0, now + ttl))
            if now > exp:                # window expired -> reset
                count, exp = 0, now + ttl
            count += 1
            self.store[key] = (count, exp)
            return count


class PerInstanceLimiter:
    def __init__(self, limit):
        self.limit = limit
        self.count = 0                   # LOCAL to this "server"
        self.lock = threading.Lock()

    def allow(self):
        with self.lock:
            self.count += 1
            return self.count <= self.limit


class SharedLimiter:
    def __init__(self, redis, limit, window):
        self.redis, self.limit, self.window = redis, limit, window

    def allow(self, client_id):
        count = self.redis.incr_with_ttl(client_id, self.window)
        return count <= self.limit       # atomic INCR -> no race


LIMIT = 100
NUM_SERVERS = 5
REQUESTS = 500

# Per-instance: each server has its own limiter (the BUG)
servers = [PerInstanceLimiter(LIMIT) for _ in range(NUM_SERVERS)]
allowed_naive = 0
for i in range(REQUESTS):
    srv = servers[i % NUM_SERVERS]       # load balancer spreads across servers
    if srv.allow():
        allowed_naive += 1

# Shared counter: all servers hit the SAME count
redis = RedisLike()
shared = SharedLimiter(redis, LIMIT, window=60)
allowed_shared = 0
for i in range(REQUESTS):
    if shared.allow("client:42"):
        allowed_shared += 1

print(f"Limit = {LIMIT} per window, {NUM_SERVERS} servers, {REQUESTS} requests\n")
print(f"Per-instance limiter: {allowed_naive} allowed "
      f"(~{NUM_SERVERS}x the limit -- LEAK!)")
print(f"Shared atomic limiter: {allowed_shared} allowed (exactly the limit)")

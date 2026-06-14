# Run: python rate_limiter.py
# Token-bucket and sliding-window rate limiters.
import time
from collections import deque


class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.refill_rate = refill_rate      # tokens per second
        self.tokens = capacity
        self.last = time.monotonic()

    def allow(self):
        now = time.monotonic()
        self.tokens = min(self.capacity,
                          self.tokens + (now - self.last) * self.refill_rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class SlidingWindow:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self.timestamps = deque()

    def allow(self):
        now = time.monotonic()
        while self.timestamps and self.timestamps[0] <= now - self.window:
            self.timestamps.popleft()
        if len(self.timestamps) < self.limit:
            self.timestamps.append(now)
            return True
        return False


def test_token_bucket():
    tb = TokenBucket(capacity=5, refill_rate=2)   # burst 5, then 2/sec
    print("Token bucket (capacity=5, refill=2/sec):")
    allowed = sum(tb.allow() for _ in range(10))
    print(f"  10 instant requests -> {allowed} allowed (burst of 5)")
    time.sleep(1.0)
    allowed = sum(tb.allow() for _ in range(10))
    print(f"  after 1s, 10 more    -> {allowed} allowed (~2 refilled)")


def test_sliding_window():
    sw = SlidingWindow(limit=5, window_seconds=1)
    print("\nSliding window (limit=5 per 1s):")
    allowed = sum(sw.allow() for _ in range(10))
    print(f"  10 instant requests -> {allowed} allowed")
    time.sleep(1.0)
    allowed = sum(sw.allow() for _ in range(10))
    print(f"  after 1s, 10 more    -> {allowed} allowed (window cleared)")


test_token_bucket()
test_sliding_window()
print("\nBoth cap sustained rate; token bucket permits an initial burst.")

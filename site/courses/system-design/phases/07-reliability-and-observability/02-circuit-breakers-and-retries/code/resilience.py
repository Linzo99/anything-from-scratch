# Run: python resilience.py
# Exponential backoff with jitter, and a circuit breaker that fails fast.
import random
import time

random.seed(1)


class FlakyService:
    def __init__(self, fail_until):
        self.calls = 0
        self.fail_until = fail_until      # fails for the first N calls

    def call(self):
        self.calls += 1
        if self.calls <= self.fail_until:
            raise ConnectionError("dependency down")
        return "ok"


def retry_with_backoff(fn, max_attempts=5, base=0.01, cap=0.5):
    for attempt in range(max_attempts):
        try:
            return fn(), attempt + 1
        except Exception:
            if attempt == max_attempts - 1:
                raise
            delay = min(cap, random.uniform(0, base * (2 ** attempt)))  # full jitter
            time.sleep(delay)
    raise RuntimeError("unreachable")


class CircuitBreaker:
    def __init__(self, threshold=3, cooldown=0.2):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.state = "closed"
        self.opened_at = 0
        self.rejected = 0

    def call(self, fn):
        if self.state == "open":
            if time.monotonic() - self.opened_at >= self.cooldown:
                self.state = "half-open"
            else:
                self.rejected += 1
                raise RuntimeError("circuit OPEN - failing fast")
        try:
            result = fn()
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.state = "open"
                self.opened_at = time.monotonic()
            raise
        self.failures = 0
        self.state = "closed"
        return result


svc = FlakyService(fail_until=2)                  # fails twice, then works
result, attempts = retry_with_backoff(svc.call)
print(f"Retry with backoff: '{result}' after {attempts} attempts "
      f"(failed {svc.fail_until}x, then recovered)")

print("\nCircuit breaker (threshold=3):")
dead = FlakyService(fail_until=999)               # permanently down
cb = CircuitBreaker(threshold=3, cooldown=10)
outcomes = []
for i in range(8):
    try:
        cb.call(dead.call)
        outcomes.append("ok")
    except RuntimeError:
        outcomes.append("FAST-FAIL")              # rejected without calling dependency
    except ConnectionError:
        outcomes.append("fail")                   # actually tried and failed
print(f"  outcomes: {outcomes}")
print(f"  dependency was actually called {dead.calls} times out of 8 requests")
print(f"  ({cb.rejected} requests fast-failed without touching the dead dependency)")

# Expected Output

Running `python rate_limiter.py` should produce (the "~2 refilled" line may show
2 or 3 depending on exact timing):

```
Token bucket (capacity=5, refill=2/sec):
  10 instant requests -> 5 allowed (burst of 5)
  after 1s, 10 more    -> 2 allowed (~2 refilled)

Sliding window (limit=5 per 1s):
  10 instant requests -> 5 allowed
  after 1s, 10 more    -> 5 allowed (window cleared)

Both cap sustained rate; token bucket permits an initial burst.
```

What to notice:
- **Token bucket**: the first 10 instant requests get **5 allowed** — the full
  bucket permits a burst of 5, then the bucket is empty. After 1 second the refill
  rate of 2/sec has added ~2 tokens, so ~2 of the next 10 are allowed. It permits
  bursts but caps the sustained rate.
- **Sliding window**: a flat **5 allowed** in any 1-second window — no burst beyond
  the limit. After the window slides past the first batch (1s later), 5 more are
  allowed. Smoother, no edge burst.

Common issues:
- **"after 1s" shows 3 instead of 2:** timing jitter — `time.sleep(1.0)` plus the
  refill math can yield 2 or 3 tokens. That's expected; the point is "a small number
  matching the refill rate," not an exact value.
- **First burst isn't 5:** check the bucket starts full (`self.tokens = capacity`)
  and the sliding window drops timestamps older than the window before counting.
- **Timing-sensitive:** this script uses real sleeps, so it's slightly
  nondeterministic at the edges; the burst-of-5 and the steady cap are the
  reliable observations.

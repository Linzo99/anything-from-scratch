# Expected Output

Running `python dist_rate_limiter.py` should produce:

```
Limit = 100 per window, 5 servers, 500 requests

Per-instance limiter: 500 allowed (~5x the limit -- LEAK!)
Shared atomic limiter: 100 allowed (exactly the limit)
```

What to notice:
- **Per-instance limiter allows all 500.** The 500 requests are spread evenly across
  5 servers (100 each), and each server's *local* counter allows up to 100 — so every
  request passes. The client got 5× its intended global limit. This is the bug that
  makes per-instance rate limiting useless behind a load balancer.
- **Shared atomic limiter allows exactly 100.** Every server increments the *same*
  Redis counter via an atomic operation, so the 101st request anywhere in the fleet
  is correctly denied. One global limit, honored no matter which server handles the
  request.

The two ingredients that matter: **shared state** (one counter) AND **atomicity**
(the increment can't be interleaved). Shared-but-non-atomic would still overshoot
under concurrency — the distributed version of Phase 2's lost-update bug.

Common issues:
- **Per-instance shows 100, not 500:** check that each server has its own
  `PerInstanceLimiter` and the loop spreads requests across them (`i % NUM_SERVERS`).
- **Shared shows more than 100:** the atomicity (the lock standing in for Redis INCR)
  isn't protecting the read-modify-write — Exercise 2 explores removing it to see the
  race.

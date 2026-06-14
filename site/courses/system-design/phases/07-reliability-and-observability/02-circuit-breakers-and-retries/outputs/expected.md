# Expected Output

Running `python resilience.py` should produce:

```
Retry with backoff: 'ok' after 3 attempts (failed 2x, then recovered)

Circuit breaker (threshold=3):
  outcomes: ['fail', 'fail', 'fail', 'FAST-FAIL', 'FAST-FAIL', 'FAST-FAIL', 'FAST-FAIL', 'FAST-FAIL']
  dependency was actually called 3 times out of 8 requests
  (5 requests fast-failed without touching the dead dependency)
```

What to notice:
- **Retry with backoff** recovers a transient failure: the service fails twice,
  then the 3rd attempt succeeds. Between attempts the client waited (with jitter),
  giving the dependency room — instead of hammering it.
- **Circuit breaker**: the first 3 calls actually hit the dead dependency and fail.
  At 3 failures (the threshold) the breaker trips **Open**, so the remaining 5
  requests **fast-fail** without ever calling the dependency.
- **Only 3 of 8 requests reached the dead dependency.** That's the protection: a
  broken dependency isn't hammered, and callers don't waste seconds waiting on
  timeouts for a service that's clearly down.

Common issues:
- **All 8 show 'fail' (none FAST-FAIL):** the breaker isn't tripping — check the
  failure count reaches `threshold` and flips `state` to `"open"`, and that the
  Open branch raises before calling `fn`.
- **'after N attempts' differs:** `fail_until=2` plus a successful 3rd call means 3
  attempts; if you change `fail_until`, the count changes accordingly.
- **Backoff timing varies:** jitter uses `random` (seeded), but the *number* of
  attempts is deterministic here.

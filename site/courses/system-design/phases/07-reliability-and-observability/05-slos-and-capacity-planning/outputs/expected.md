# Expected Output

Running `python slo_calculator.py` should produce:

```
Latency (ms):
  p50   =    49.9 ms
  p95   =    67.8 ms
  p99   =   105.8 ms
  p99.9 =  4798.5 ms
  average =    86.7 ms  <- hides the tail!

Latency SLO: p99 <= 200ms
  990/1000 within SLO (99.0%)

Error budget (SLO 99.9% over 100,000,000 req/mo):
  allowed failures = 100,000 per month
  failed so far    = 62,000 (62% of budget used)
  remaining budget = 38,000
  -> SHIP features (budget left)

Capacity planning:
  peak 50,000 QPS / 2,000 per server / 70% util
  -> 36 servers needed (incl. headroom for spikes & failures)
  (at 100% utilization: 25 servers -> no slack: latency spikes at saturation, no room to absorb a failure)
```

What to notice:
- **The average (~87ms) lies.** The p50 is ~50ms (the typical experience) but the
  average is dragged up by a 1% slow tail. The tail fully reveals itself at p99.9
  (~4.8 seconds!). An SLO on the average would look healthy while real users hit
  multi-second responses — always use percentiles.
- **Error budget as currency.** 99.9% over 100M requests allows 100,000 failures.
  Having used 62,000 (62%), there's budget left → ship features. If it were
  exhausted, the rule is freeze and fix reliability.
- **Capacity with headroom.** Peak 50,000 QPS at 2,000/server needs 25 servers at
  100% — but you provision 36 (70% utilization) so latency doesn't explode at
  saturation and a server can fail without overloading the rest.

Common issues:
- **Percentiles differ slightly:** the data uses a seeded RNG, so values should
  match; small differences mean a different Python version's `random`. The *shape*
  (p50 ~50ms, p99.9 in seconds, average between) is the lesson.
- **Servers = 25 instead of 36:** you skipped the `target_util` division —
  forgetting headroom is exactly the mistake the last line warns about.

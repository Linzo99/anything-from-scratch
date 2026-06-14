# Expected Output

Running `python load_balancer.py` should produce exactly:

```
=== Round-robin (ignores weight) (1200 requests) ===
  A        weight=1  handled=  400  (33.3%)
  B        weight=1  handled=  400  (33.3%)
  C        weight=3  handled=  400  (33.3%)

=== Weighted (C has weight 3) (1200 requests) ===
  A        weight=1  handled=  240  (20.0%)
  B        weight=1  handled=  240  (20.0%)
  C        weight=3  handled=  720  (60.0%)

=== Least-connections (A starts with 50 active) ===
  A        handled=   67  final_active=117
  B        handled=  117  final_active=117
  C        handled=  116  final_active=116
```

What to notice:
- **Round-robin** splits evenly (33.3% each) even though C is 3x bigger — its
  extra capacity is wasted.
- **Weighted** gives C 60% (weight 3 of total 5), matching its capacity.
- **Least-connections** sends very little to A at first (it started with 50
  active connections) until B and C catch up to the same level — it self-balances.

Common issues:
- **Counts differ:** the simulation is fully deterministic, so any difference
  means the file was edited. Round-robin must be exactly even when request count
  divides evenly by server count.
- **`min()` ties:** Python's `min` returns the first minimum, so least-connections
  is deterministic here.

# Expected Output

Running `python estimator.py` with the default assumptions should produce:

```
=== Capacity Estimate ===
DAU:                 10,000,000
Requests/day:        200,000,000
Average load:        2,315 QPS
Peak load (x5):     11,574 QPS
Write load:          231 QPS
Storage/day:         9,536.7 GB
Storage/year:        3,399.3 TB
Read bandwidth:      0.99 GB/s

Design implications:
  - Need load balancer + multiple app servers
  - Need object storage (S3) + CDN
  - Need a CDN to offload read bandwidth
```

If your output matches, you're good. The key reading: ~11.5K peak QPS and
petabytes/year — both far past what one machine handles, which is why all three
implications fire.

Common issues:
- **Numbers slightly off:** make sure storage uses binary units (`1024`), not
  `1000`. Using powers of ten gives ~2% different numbers — fine for a real
  estimate, but won't match this file exactly.
- **`SyntaxError` on the number literals:** underscores in numbers
  (`10_000_000`) require Python 3.6+. Check `python --version`.
- **Implications don't flip when you edit assumptions:** confirm you saved the
  file before re-running. Try `avg_object_size_kb = 5000` and watch yearly
  storage jump ~10×.

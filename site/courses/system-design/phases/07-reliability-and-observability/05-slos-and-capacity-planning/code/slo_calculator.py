# Run: python slo_calculator.py
# Percentiles, error budget, and capacity planning from raw data.
import math
import random

random.seed(3)


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


# 990 fast requests (~50ms) plus a 1% slow tail (2-5s)
latencies = [random.gauss(50, 10) for _ in range(990)] + \
            [random.uniform(2000, 5000) for _ in range(10)]
latencies.sort()

print("Latency (ms):")
for p in (50, 95, 99, 99.9):
    print(f"  p{p:<4} = {percentile(latencies, p):7.1f} ms")
print(f"  average = {sum(latencies)/len(latencies):7.1f} ms  <- hides the tail!")

SLO_LATENCY_MS = 200
SLO_SUCCESS = 0.999

within = sum(1 for x in latencies if x <= SLO_LATENCY_MS)
print(f"\nLatency SLO: p99 <= {SLO_LATENCY_MS}ms")
print(f"  {within}/{len(latencies)} within SLO ({100*within/len(latencies):.1f}%)")

monthly_requests = 100_000_000
allowed_failures = int((1 - SLO_SUCCESS) * monthly_requests)
print(f"\nError budget (SLO {SLO_SUCCESS*100}% over {monthly_requests:,} req/mo):")
print(f"  allowed failures = {allowed_failures:,} per month")

failed_so_far = 62_000
remaining = allowed_failures - failed_so_far
pct_used = 100 * failed_so_far / allowed_failures
print(f"  failed so far    = {failed_so_far:,} ({pct_used:.0f}% of budget used)")
print(f"  remaining budget = {remaining:,}")
print(f"  -> {'SHIP features (budget left)' if remaining > 0 else 'FREEZE: budget exhausted'}")

peak_qps = 50_000
per_server_qps = 2_000
target_util = 0.70
servers = math.ceil(peak_qps / per_server_qps / target_util)
print(f"\nCapacity planning:")
print(f"  peak {peak_qps:,} QPS / {per_server_qps:,} per server / {target_util:.0%} util")
print(f"  -> {servers} servers needed (incl. headroom for spikes & failures)")

no_headroom = math.ceil(peak_qps / per_server_qps)
print(f"  (at 100% utilization: {no_headroom} servers -> no slack: "
      f"latency spikes at saturation, no room to absorb a failure)")

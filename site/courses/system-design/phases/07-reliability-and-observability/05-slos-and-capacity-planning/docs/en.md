# SLOs & Capacity Planning

> "Make it reliable" is not a target. "99.9% of requests succeed under 200ms" is — and from that single number falls a budget for failure, a trigger for alerts, and a plan for how many servers to buy.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 7, Lesson 04 — Monitoring & Observability
**Time:** ~50 minutes

## Learning Objectives

- Define SLI, SLO, and error budget and how they relate
- Compute percentile latency (p50, p99) from raw request data
- Calculate an error budget and reason about spending it
- Plan capacity from load estimates and headroom
- Use these numbers to make reliability decisions instead of guessing

## The Problem

Reliability without a number is an argument. One engineer says "we need to stop shipping features and fix stability"; another says "it's fine, let's keep building." Without an agreed target, this is just opinions, and the loudest voice wins. Worse, "as reliable as possible" is the wrong goal — perfect reliability is impossibly expensive and pointless (users can't tell 99.99% from 99.999% for most products, and the last nine costs more than all the others combined). What you need is an *explicit, measured target* that turns reliability into a decision you can make with data.

That's what **SLOs (Service Level Objectives)** provide. An SLO is a precise, measurable goal — "99.9% of requests succeed within 200ms over 30 days" — and it does three things at once. It defines *good enough*, so you stop over- or under-investing. It gives you an **error budget** (the 0.1% you're allowed to fail), which becomes a *currency*: as long as you're within budget, you ship features; when you've burned it, you stop and fix reliability. And it grounds your **alerts** (Lesson 04) in user impact: page when the budget is burning, not on arbitrary thresholds. The SLO turns vague reliability debates into arithmetic.

The other half of running a service is **capacity planning**: how many servers do you need? Provision too little and you fall over at peak; too much and you waste money. This is the estimation of Phase 0 applied to your real, measured load plus growth — and it's deeply tied to your SLO, because "enough capacity" means "enough to meet the latency SLO at peak." This lesson computes percentiles, error budgets, and capacity from raw data so reliability becomes numbers, not opinions.

## The Concept

### SLI, SLO, SLA

Three related terms, easy to confuse:

```
SLI (Indicator)  — the measured number.   "99.93% of requests succeeded last month."
SLO (Objective)  — the internal target.   "≥ 99.9% should succeed."  (team commitment)
SLA (Agreement)  — the contract + penalty. "≥ 99.5% or we refund you."  (customer-facing)
```

The SLI is reality (what you measured), the SLO is the goal you hold yourselves to, and the SLA is the (usually looser) promise to customers with consequences attached. You set the SLO stricter than the SLA so you have a safety margin before breaking a contract.

### Percentiles, not averages

To define a latency SLO you must measure latency correctly — and averages lie. If 99 requests take 10ms and one takes 5 seconds, the average is ~60ms (looks fine!) but a real user hit 5 seconds. **Percentiles** capture the tail:

```
p50 (median): half of requests are faster than this  -> typical experience
p95:          95% are faster                          -> most users
p99:          99% are faster (the slow 1%)            -> the tail that hurts
p99.9:        the worst 0.1%                           -> rare but real
```

A latency SLO is almost always stated at a percentile ("p99 < 200ms"), because the tail is what users complain about — and in a fan-out request (Phase 4), one slow dependency at p99 can dominate the whole request. You'll compute these from raw samples.

### Error budget

If your SLO is 99.9% success, then 0.1% is your **error budget** — the amount of failure you're *allowed* over the window. Make it concrete:

```
SLO 99.9% over 30 days, 100M requests/month:
  allowed failures = 0.1% × 100,000,000 = 100,000 failed requests
  -> that's your budget to "spend" on risky deploys, experiments, incidents
```

The error budget reframes reliability as a *currency*, which resolves the feature-vs-stability fight:

- **Budget remaining** → you can take risks: ship the feature, run the experiment. A little failure is allowed and even healthy.
- **Budget exhausted** → freeze risky changes and focus on reliability until you're back in budget.

This is the core of Google's SRE model: the error budget aligns dev (wants to ship) and ops (wants stability) on one number instead of arguing.

### Burn rate and alerting

How fast you're consuming the budget is the **burn rate**. Burning the whole month's budget in an hour is an emergency (alert now); a slow burn is fine. Modern alerting pages on burn rate (Lesson 04) — "at this rate you'll exhaust the budget in 2 hours" — which is far more meaningful than "error rate > 1%."

### Capacity planning

How many servers to provision? Combine measured per-server capacity, peak load, and headroom:

```
servers_needed = peak_QPS / per_server_capacity / target_utilization

Example:
  peak = 50,000 QPS
  one server handles 2,000 QPS at the latency SLO
  target utilization = 70% (leave 30% headroom for spikes/failures)
  -> 50,000 / 2,000 / 0.70 = 35.7 -> 36 servers
```

The **headroom** (running at 70%, not 100%) matters: at 100% utilization, latency explodes (queueing theory — a system near saturation has wildly growing wait times) and a single server failure has nowhere to shed its load. You provision for *peak plus failures plus growth*, not average — connecting back to Phase 0's estimation, Phase 7's redundancy, and the latency SLO that defines "fast enough."

### A common misconception

"Aim for 100% reliability." Wrong goal — it's impossibly expensive and unnecessary; the error budget exists precisely because *some* failure is acceptable and chasing zero wastes enormous effort for imperceptible gain. The second misconception is measuring latency by average — the average hides the tail that actually drives user pain and SLO breaches; always use percentiles. Third, capacity-planning to *average* load guarantees you fall over at peak: traffic is bursty (Phase 0's peak factor), so you size for peak with headroom. The unifying idea: pick an explicit target, measure against it honestly with percentiles, and let the error budget and capacity math drive decisions instead of opinions.

## Build It

You'll compute percentiles, an error budget, and required capacity from raw data. Create `slo_calculator.py`.

### Step 1 — Percentiles from raw latency samples

```python
# Run: python slo_calculator.py
def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

# 1000 fast requests (~50ms) plus a slow tail (some at 2-5s)
import random
random.seed(3)
latencies = [random.gauss(50, 10) for _ in range(990)] + \
            [random.uniform(2000, 5000) for _ in range(10)]   # 1% slow tail
latencies.sort()

print("Latency (ms):")
for p in (50, 95, 99, 99.9):
    print(f"  p{p:<4} = {percentile(latencies, p):7.1f} ms")
print(f"  average = {sum(latencies)/len(latencies):7.1f} ms  <- hides the tail!")
```

### Step 2 — SLO compliance and error budget

```python
SLO_LATENCY_MS = 200
SLO_SUCCESS = 0.999          # 99.9%

within = sum(1 for x in latencies if x <= SLO_LATENCY_MS)
print(f"\nLatency SLO: p99 <= {SLO_LATENCY_MS}ms")
print(f"  {within}/{len(latencies)} within SLO "
      f"({100*within/len(latencies):.1f}%)")
```

### Step 3 — Error budget arithmetic

```python
monthly_requests = 100_000_000
allowed_failures = int((1 - SLO_SUCCESS) * monthly_requests)
print(f"\nError budget (SLO {SLO_SUCCESS*100}% over {monthly_requests:,} req/mo):")
print(f"  allowed failures = {allowed_failures:,} per month")

# Suppose we've already failed some this month
failed_so_far = 62_000
remaining = allowed_failures - failed_so_far
pct_used = 100 * failed_so_far / allowed_failures
print(f"  failed so far    = {failed_so_far:,} ({pct_used:.0f}% of budget used)")
print(f"  remaining budget = {remaining:,}")
print(f"  -> {'SHIP features (budget left)' if remaining > 0 else 'FREEZE: budget exhausted'}")
```

### Step 4 — Capacity planning

```python
peak_qps = 50_000
per_server_qps = 2_000          # measured at the latency SLO
target_util = 0.70              # 30% headroom
import math
servers = math.ceil(peak_qps / per_server_qps / target_util)
print(f"\nCapacity planning:")
print(f"  peak {peak_qps:,} QPS / {per_server_qps:,} per server / {target_util:.0%} util")
print(f"  -> {servers} servers needed (incl. headroom for spikes & failures)")
```

### Step 5 — Show why headroom matters

```python
no_headroom = math.ceil(peak_qps / per_server_qps)        # run at 100%
print(f"  (at 100% utilization: {no_headroom} servers -> no slack: "
      f"latency spikes at saturation, no room to absorb a failure)")
```

### Step 6 — Run it

```bash
python slo_calculator.py
```

See how the average is inflated by a tail that only fully shows at p99.9 (in the seconds), how much error budget you have left, and how many servers peak load demands with headroom. Compare with `outputs/expected.md`.

## Exercises

1. **Run and read.** Compare the average latency to p99.9. The average (~87ms) is dragged well above the p50 (~50ms) by the slow tail, and p99.9 is in the seconds. Why would an SLO based on the average pass while the tail users suffer?

2. **Tighten the SLO.** Change `SLO_SUCCESS` to 99.99%. How does the allowed monthly failure count change, and what does that imply for how cautious deploys must be?

3. **Burn-rate alert.** You've used 62% of the budget on the 10th of a 30-day month. Are you burning too fast? Compute the safe daily burn and compare.

4. **Capacity for growth.** Recompute servers needed if peak QPS will grow 40% next year. How early should you provision?

5. **Headroom reasoning.** Explain, referencing queueing behavior, why running servers at 95%+ utilization is dangerous even if "the math says it fits."

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| SLI | "The measured number" | Service Level Indicator — the actual measured metric (observed success/latency) |
| SLO | "The target" | Service Level Objective — the internal goal the team commits to (e.g. 99.9%) |
| SLA | "The contract" | Service Level Agreement — a customer promise with penalties; looser than the SLO |
| Error budget | "Allowed failure" | The amount of unreliability the SLO permits; spent on risk, gates releases |
| Burn rate | "Budget consumption speed" | How fast the error budget is being used; basis for meaningful alerts |
| Percentile | "p50/p99" | The value below which a given % of measurements fall; captures the tail |
| Headroom | "Spare capacity" | Provisioned capacity above expected load to absorb spikes and failures |
| Capacity planning | "How many servers" | Sizing infrastructure for peak load plus headroom and growth |

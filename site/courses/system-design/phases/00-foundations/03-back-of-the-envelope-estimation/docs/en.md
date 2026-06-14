# Back-of-the-Envelope Estimation

> Before you choose a database, you should be able to say "this needs 12,000 writes per second and 40 TB in year one" — out loud, from a few assumptions, in under two minutes.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 0, Lesson 02 — Requirements & Tradeoffs
**Time:** ~50 minutes

## Learning Objectives

- Convert daily active users into peak queries per second (QPS)
- Estimate storage growth from object size and write rate
- Estimate bandwidth from request size and request rate
- Memorize the powers-of-two and latency numbers every engineer reasons with
- Build a reusable Python estimator that produces defensible capacity numbers

## The Problem

Every design decision rests on numbers, and in a design discussion you rarely have a calculator and a spreadsheet — you have a whiteboard and two minutes. If someone proposes storing every event in a relational database, the right reflex is to estimate: "that's 1 billion writes a day, ~12K writes per second sustained, ~30K at peak — a single Postgres instance won't take that, so we need sharding or a different store." That conclusion comes from arithmetic you can do in your head, and it changes the entire design.

Engineers who skip estimation make two opposite mistakes. Some over-build — designing a globally sharded system for a service that will see 50 requests per second, drowning in complexity for load that never comes. Others under-build — picking a single database for a firehose of writes, then scrambling when it falls over in production. Both are avoidable with five minutes of estimation up front.

The goal isn't precision. Back-of-the-envelope numbers are deliberately rough — round everything, use powers of two, accept being off by 2×. What matters is the *order of magnitude*: is this 100 QPS or 100,000 QPS? 1 GB or 1 PB? Those answers point to completely different designs, and you can get them from a handful of assumptions.

## The Concept

### The numbers to memorize

You can't estimate without a few reference points burned into memory.

**Powers of two (for storage):**

```
2^10 = 1 Thousand   → 1 KB
2^20 = 1 Million    → 1 MB
2^30 = 1 Billion    → 1 GB
2^40 = 1 Trillion   → 1 TB
2^50 = 1 Quadrillion→ 1 PB
```

**Time, for QPS math:**

```
1 day  = 86,400 seconds  (round to ~100,000 = 10^5 for fast mental math)
1 month ≈ 2.5 million seconds
1 year  ≈ 31.5 million seconds (~3 x 10^7)
```

**Latency numbers every programmer should know (rounded):**

```
Operation                          Time        Relative
---------------------------------  ----------  ----------
L1 cache reference                 ~1 ns       1x
Main memory (RAM) reference        ~100 ns     100x
Read 1 MB sequentially from RAM    ~10 µs
SSD random read                    ~100 µs     (10^5 ns)
Read 1 MB sequentially from SSD    ~1 ms
Network round trip within a datacenter ~0.5 ms
Disk (HDD) seek                    ~10 ms
Network round trip across continents   ~150 ms
```

The takeaway: memory is ~100× faster than SSD, SSD is ~100× faster than a disk seek, and a cross-continent round trip (150ms) dwarfs everything — which is *why* caching and CDNs exist.

### From users to QPS

The core conversion, step by step:

```mermaid
graph LR
  DAU[Daily Active Users] -->|x requests/user/day| REQ[Requests per day]
  REQ -->|/ 86400 sec| AVG[Average QPS]
  AVG -->|x peak factor 2-10| PEAK[Peak QPS]
```

Worked example — a photo-sharing app:
- **10 million** daily active users (DAU)
- Each user makes **20** requests/day → **200 million** requests/day
- Average QPS = 200M / 86,400 ≈ **2,300 QPS**
- Traffic isn't flat; peak is often 2–10× average. Use **5×** → **~11,500 QPS peak**

That single number tells you a single server (good for a few thousand QPS) is borderline, so you'll need a load balancer and several app servers. Design follows.

### Storage estimation

How much data accumulates? Multiply write rate by object size by time.

Worked example — same app, users upload photos:
- 10% of 200M daily requests are uploads → **20 million** uploads/day
- Average photo (compressed) = **500 KB**
- Per day: 20M × 500 KB = **10 TB/day**
- Per year: 10 TB × 365 ≈ **3.65 PB/year**

That's far beyond one disk — it mandates object storage (S3-style) and a CDN, not a database blob column. Again, the number drove the design.

### Bandwidth estimation

Bandwidth = request rate × payload size.
- Reads: 180M image views/day × 500 KB ÷ 86,400 ≈ **1 GB/s** egress.
- That much egress is expensive and points straight to a CDN to offload it from your origin.

### A common misconception

People think estimation has to be accurate to be useful. It doesn't. If you assume 500 KB per photo and the real number is 800 KB, your storage estimate is off by 1.6× — but it's still "petabytes per year, not gigabytes," and the design conclusion (object storage + CDN) is unchanged. Round aggressively and move on. The decision you're informing rarely depends on the second significant figure.

## Build It

You'll write a small estimator that takes a few assumptions and prints capacity numbers. Create `estimator.py`.

### Step 1 — Define the inputs

```python
# Run: python estimator.py
# A back-of-the-envelope capacity estimator.

SECONDS_PER_DAY = 86_400
DAYS_PER_YEAR = 365

# --- Assumptions (edit these for your system) ---
daily_active_users = 10_000_000      # DAU
requests_per_user_per_day = 20       # how chatty each user is
peak_factor = 5                      # peak QPS / average QPS
write_fraction = 0.10                # 10% of requests are writes
avg_object_size_kb = 500             # size of one stored object
avg_response_size_kb = 500           # size of one read response
```

### Step 2 — Compute QPS

```python
requests_per_day = daily_active_users * requests_per_user_per_day
avg_qps = requests_per_day / SECONDS_PER_DAY
peak_qps = avg_qps * peak_factor
writes_per_day = requests_per_day * write_fraction
write_qps = writes_per_day / SECONDS_PER_DAY
```

### Step 3 — Compute storage growth

```python
daily_storage_gb = (writes_per_day * avg_object_size_kb) / (1024 * 1024)  # KB -> GB
yearly_storage_tb = (daily_storage_gb * DAYS_PER_YEAR) / 1024             # GB -> TB
```

### Step 4 — Compute read bandwidth

```python
reads_per_day = requests_per_day * (1 - write_fraction)
read_bytes_per_sec = (reads_per_day * avg_response_size_kb * 1024) / SECONDS_PER_DAY
read_gbps = read_bytes_per_sec / (1024 * 1024 * 1024)
```

### Step 5 — Print a report

```python
def hum_qps(x): return f"{x:,.0f} QPS"

print("=== Capacity Estimate ===")
print(f"DAU:                 {daily_active_users:,}")
print(f"Requests/day:        {requests_per_day:,.0f}")
print(f"Average load:        {hum_qps(avg_qps)}")
print(f"Peak load (x{peak_factor}):     {hum_qps(peak_qps)}")
print(f"Write load:          {hum_qps(write_qps)}")
print(f"Storage/day:         {daily_storage_gb:,.1f} GB")
print(f"Storage/year:        {yearly_storage_tb:,.1f} TB")
print(f"Read bandwidth:      {read_gbps:,.2f} GB/s")
print()
print("Design implications:")
print(f"  - {'Single server OK' if peak_qps < 5000 else 'Need load balancer + multiple app servers'}")
print(f"  - {'DB blob storage OK' if yearly_storage_tb < 1 else 'Need object storage (S3) + CDN'}")
print(f"  - {'Origin can serve reads' if read_gbps < 0.1 else 'Need a CDN to offload read bandwidth'}")
```

### Step 6 — Run it

```bash
python estimator.py
```

Compare the output to the expected results in `outputs/expected.md`. Then change the assumptions (try 100M DAU, or a 5 MB video instead of a 500 KB photo) and watch which design implications flip.

## Exercises

1. **Run the baseline.** Run `estimator.py` and confirm it matches the expected output. Note which design implications fire.

2. **Scale to video.** Change `avg_object_size_kb` to 5,000 (a 5 MB video clip). How does yearly storage change, and which implication flips?

3. **A quiet internal tool.** Set DAU to 5,000 and requests/user to 10. What's peak QPS now? Does it still need a load balancer? This shows why over-engineering is wrong.

4. **Add a five-year projection.** Extend the script to print storage after 1, 3, and 5 years assuming 50% annual user growth.

5. **Mental math drill.** Without the script, estimate peak QPS for 50M DAU at 30 requests/user/day with a 4× peak factor. Then verify with the code.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| QPS | "Requests per second" | The request rate; peak QPS, not average, drives capacity planning |
| DAU | "Daily users" | Daily Active Users — the base number most estimates start from |
| Peak factor | "Burstiness" | The ratio of peak QPS to average QPS; traffic is never flat, typically 2–10× |
| Back-of-the-envelope | "Rough math" | Order-of-magnitude estimation from a few assumptions, accepting ~2× error |
| Egress bandwidth | "Outbound data" | Data sent from your servers to clients; expensive at scale, offloaded by CDNs |
| Order of magnitude | "Ballpark" | The power-of-ten size of a number (hundreds vs millions); what design decisions actually hinge on |

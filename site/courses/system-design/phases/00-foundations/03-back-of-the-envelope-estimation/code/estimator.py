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

# --- QPS ---
requests_per_day = daily_active_users * requests_per_user_per_day
avg_qps = requests_per_day / SECONDS_PER_DAY
peak_qps = avg_qps * peak_factor
writes_per_day = requests_per_day * write_fraction
write_qps = writes_per_day / SECONDS_PER_DAY

# --- Storage ---
daily_storage_gb = (writes_per_day * avg_object_size_kb) / (1024 * 1024)  # KB -> GB
yearly_storage_tb = (daily_storage_gb * DAYS_PER_YEAR) / 1024             # GB -> TB

# --- Read bandwidth ---
reads_per_day = requests_per_day * (1 - write_fraction)
read_bytes_per_sec = (reads_per_day * avg_response_size_kb * 1024) / SECONDS_PER_DAY
read_gbps = read_bytes_per_sec / (1024 * 1024 * 1024)


def hum_qps(x):
    return f"{x:,.0f} QPS"


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

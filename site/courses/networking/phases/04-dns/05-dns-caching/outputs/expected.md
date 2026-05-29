# Expected Output

Running `python3 dns_cache.py --fast` (uses 2s TTL instead of 5s so the demo completes quickly):

```
────────────────────────────────────────────────────────────
  DNS Cache Demo
────────────────────────────────────────────────────────────

[Scenario 1] First lookup triggers upstream; second serves from cache

  [CACHE MISS] example.com                     (not in cache)
  [UPSTREAM]   example.com                     → ['93.184.216.34']  TTL=300s
  [CACHE PUT]  example.com                     TTL=300s  ['93.184.216.34']
  Resolved example.com → ['93.184.216.34']

  [CACHE HIT]  example.com                     remaining TTL=299.9s  ['93.184.216.34']
  Resolved example.com → ['93.184.216.34']  (from cache, no upstream call)


[Scenario 2] TTL countdown — record expires after 2s

  [CACHE PUT]  api.example.com                 TTL=2s  ['10.0.0.5']
  [CACHE HIT]  api.example.com                 remaining TTL=1.9s  ['10.0.0.5']
  Immediately after put: remaining TTL = 1.9s

  Waiting 2.2s for TTL to expire …
  [CACHE STALE]api.example.com                 TTL expired, evicting
  Record evicted as expected — next lookup will go upstream
  [CACHE MISS] api.example.com                 (not in cache)
  [UPSTREAM]   api.example.com                 → ['10.0.0.5']  TTL=60s
  [CACHE PUT]  api.example.com                 TTL=60s  ['10.0.0.5']
  Upstream re-resolved api.example.com → ['10.0.0.5']

[Scenario 3] NXDOMAIN negative caching

  [CACHE MISS] nosuchdomain.example.com        (not in cache)
  [UPSTREAM]   nosuchdomain.example.com        → NXDOMAIN  neg-TTL=30s
  [CACHE PUT]  nosuchdomain.example.com        TTL=30s  NXDOMAIN
  First lookup: NXDOMAIN: nosuchdomain.example.com

  [CACHE HIT]  nosuchdomain.example.com        remaining TTL=29.9s  NXDOMAIN
  Second lookup: NXDOMAIN (cached): nosuchdomain.example.com  (served from negative cache, no upstream)

[Scenario 4] Resolving multiple names, only new ones hit upstream

  [CACHE MISS] google.com                      (not in cache)
  [UPSTREAM]   google.com                      → ['142.250.80.46']  TTL=300s
  [CACHE PUT]  google.com                      TTL=300s  ['142.250.80.46']
  google.com                          → ['142.250.80.46']
  [CACHE MISS] github.com                      (not in cache)
  [UPSTREAM]   github.com                      → ['140.82.121.4']  TTL=60s
  [CACHE PUT]  github.com                      TTL=60s  ['140.82.121.4']
  github.com                          → ['140.82.121.4']
  [CACHE HIT]  google.com                      remaining TTL=299.8s  ['142.250.80.46']
  google.com                          → ['142.250.80.46']
  [CACHE HIT]  github.com                      remaining TTL=59.8s  ['140.82.121.4']
  github.com                          → ['140.82.121.4']

────────────────────────────────────────────────────────────
  Cache Statistics
────────────────────────────────────────────────────────────
  Current entries: 5
  Cache hits:      5
  Cache misses:    5
  Stale evictions: 1
  Hit rate:        45%
```

Key things to observe:
- Scenario 1: second `resolve()` call shows `[CACHE HIT]` with a slightly lower TTL than the first
- Scenario 2: after the TTL expires the record is evicted and the next call hits upstream again
- Scenario 3: both the positive miss and the negative (NXDOMAIN) entry are cached separately

## Common issues

- **Issue**: Script exits before the TTL expires in Scenario 2 → **Fix**: Use `--fast` flag (2s TTL) for a quicker demonstration.
- **Issue**: Hit rate is lower than expected → **Fix**: Each `[CACHE STALE]` event counts as a miss (the stale counter).  The demo is designed to show one stale eviction in Scenario 2.
- **Issue**: `NameError: NXDOMAIN` raised on a name you expected to resolve → **Fix**: The domain may not be in the `ZONE` dictionary in the script.  The script uses a hardcoded zone — add your domain there to test it.

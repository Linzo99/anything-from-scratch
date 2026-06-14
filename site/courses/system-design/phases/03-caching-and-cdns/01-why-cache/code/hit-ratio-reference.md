<!-- Reference: the math and layers of caching. -->

# Caching Quick Reference

## Hit ratio → origin load (per 1,000,000 reads)
| Hit ratio | Reads reaching origin | vs no cache |
|-----------|----------------------:|-------------|
| 0%   | 1,000,000 | 1x |
| 50%  |   500,000 | 2x fewer |
| 90%  |   100,000 | 10x fewer |
| 95%  |    50,000 | 20x fewer |
| 99%  |    10,000 | 100x fewer |
| 99.9%|     1,000 | 1000x fewer |

> origin_reads = total_reads × (1 − hit_ratio)

## Average latency
> avg_latency = hit_ratio × hit_cost + (1 − hit_ratio) × miss_cost

Example: hit=1ms, miss=20ms
- 90% → 0.9(1) + 0.1(20) = 2.9 ms
- 99% → 0.99(1) + 0.01(20) = 1.19 ms

## Latency by layer (rough)
| Source | Latency |
|--------|---------|
| In-process cache (RAM) | ~0.1 µs |
| Redis (network) | ~0.5 ms |
| Database query | ~5–50 ms |

## Where caches live (first hit wins, shields below)
Browser → CDN edge → reverse proxy → app/in-process → distributed (Redis) → DB buffer pool

## The cost
- A cache is a SECOND COPY → can disagree with origin → staleness
- "Two hard things: cache invalidation and naming things."
- A cache that dies can stampede the DB (thundering herd — see lesson 04)

## When caching helps
- ✅ Skewed access (a hot set): trending list, session profile
- ❌ Unique-every-time access (random UUID lookups): nothing to reuse

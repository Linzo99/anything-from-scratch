# Expected Output

Running `python url_shortener.py` should produce:

```
Base62 encoding of IDs:
                0 -> '0'  (decode -> 0)
               61 -> 'Z'  (decode -> 61)
               62 -> '10'  (decode -> 62)
              125 -> '21'  (decode -> 125)
           999999 -> '4c91'  (decode -> 999999)
    3521614606207 -> 'ZZZZZZZ'  (decode -> 3521614606207)

shorten https://example.com/a -> sho.rt/g8

shorten https://example.com/b -> sho.rt/g9

shorten https://python.org -> sho.rt/ga

Resolving (first time = DB miss, then cached):
  g8 -> https://example.com/a   [1st: DB]
  g9 -> https://example.com/b   [1st: DB]
  ga -> https://python.org   [1st: DB]

After read-heavy traffic:
  DB hits:    3
  cache hits: 303
  cache hit ratio: 99.0%  <- DB shielded from reads
```

What to notice:
- **Base62 round-trips**: every `encode` then `decode` returns the original number.
  Note `62^7 - 1 = 3,521,614,606,207` encodes to `ZZZZZZZ` — 7 chars hold ~3.5
  trillion codes.
- **Counter → code**: the first ID (1000) encodes to `g8`, then `g9`, `ga` — unique
  codes with no collision check needed, because the IDs are unique.
- **Cache hit ratio ~99%**: each link is fetched from the DB exactly once (3 DB
  hits) then served from cache for all subsequent reads (303 cache hits). Under the
  100:1 read-heavy load this system faces, the cache shields the database almost
  entirely — which is exactly why caching is the deep-dive bottleneck for a URL
  shortener.

Common issues:
- **Codes start at '0' not 'g8':** the counter starts at 1000 (encode(1000)='g8').
  Different start = different first code.
- **Low cache hit ratio:** confirm `resolve` populates the cache on a miss
  (cache-aside) so repeat reads hit the cache.

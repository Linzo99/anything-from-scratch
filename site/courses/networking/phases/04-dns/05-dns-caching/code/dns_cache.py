# Run: python3 dns_cache.py
"""
dns_cache.py — Simulate a DNS cache with TTL expiry.

Implements get(name) and put(name, records, ttl).
Demonstrates:
  - Serving from cache on second lookup (with remaining TTL)
  - Stale record detection when TTL expires
  - Cache eviction / miss triggers a new lookup
  - Negative caching (caching NXDOMAIN for a TTL)

Usage:
    python3 dns_cache.py
    python3 dns_cache.py --fast    # use short TTLs so demo completes quickly
"""

import time
import sys
from typing import Any


# ── DNS cache implementation ──────────────────────────────────────────────────

class DNSCacheEntry:
    """One cached DNS record set."""
    def __init__(self, name: str, records: list, ttl: int, negative: bool = False):
        self.name      = name
        self.records   = records      # list of IP strings (or other record values)
        self.ttl       = ttl          # original TTL in seconds
        self.stored_at = time.monotonic()
        self.negative  = negative     # True = NXDOMAIN cached

    def remaining_ttl(self) -> float:
        """Seconds of TTL remaining (0 if expired)."""
        elapsed = time.monotonic() - self.stored_at
        return max(0.0, self.ttl - elapsed)

    def is_expired(self) -> bool:
        return self.remaining_ttl() <= 0

    def __repr__(self) -> str:
        kind = "NXDOMAIN" if self.negative else f"{self.records}"
        return (f"CacheEntry({self.name!r}, {kind}, "
                f"ttl={self.ttl}s, remaining={self.remaining_ttl():.1f}s)")


class DNSCache:
    """
    Simple TTL-based DNS cache.

    In a real resolver this would also handle:
    - Different record types per name (A vs AAAA vs MX)
    - Thread safety
    - Maximum cache size with LRU eviction
    """

    def __init__(self):
        self._cache: dict[str, DNSCacheEntry] = {}
        self.hits   = 0
        self.misses = 0
        self.stales = 0

    def put(self, name: str, records: list, ttl: int, negative: bool = False) -> None:
        """Store records for `name` with the given TTL (seconds)."""
        entry = DNSCacheEntry(name, records, ttl, negative=negative)
        self._cache[name] = entry
        kind = "NXDOMAIN" if negative else f"{records}"
        print(f"  [CACHE PUT]  {name:<30} TTL={ttl}s  {kind}")

    def get(self, name: str) -> "DNSCacheEntry | None":
        """
        Look up `name` in the cache.
        Returns the entry if present and not expired; None if missing or stale.
        """
        entry = self._cache.get(name)
        if entry is None:
            self.misses += 1
            print(f"  [CACHE MISS] {name:<30} (not in cache)")
            return None
        if entry.is_expired():
            self.stales += 1
            del self._cache[name]
            print(f"  [CACHE STALE]{name:<30} TTL expired, evicting")
            return None
        self.hits += 1
        print(f"  [CACHE HIT]  {name:<30} "
              f"remaining TTL={entry.remaining_ttl():.1f}s  "
              f"{'NXDOMAIN' if entry.negative else entry.records}")
        return entry

    def stats(self) -> dict:
        return {
            "entries": len(self._cache),
            "hits":    self.hits,
            "misses":  self.misses,
            "stales":  self.stales,
        }


# ── simulated upstream resolver ───────────────────────────────────────────────

# Pretend zone data (name → (records, ttl))
ZONE = {
    "example.com":   (["93.184.216.34"],       300),
    "api.example.com": (["10.0.0.5"],           60),
    "google.com":    (["142.250.80.46"],        300),
    "github.com":    (["140.82.121.4"],          60),
}


def upstream_lookup(name: str) -> tuple:
    """
    Simulate a lookup against the authoritative server.
    Returns (records, ttl, nxdomain).
    In reality this would send a DNS query.
    """
    time.sleep(0.05)   # simulate 50ms network RTT
    if name in ZONE:
        records, ttl = ZONE[name]
        print(f"  [UPSTREAM]   {name:<30} → {records}  TTL={ttl}s")
        return records, ttl, False
    else:
        # NXDOMAIN — negative caching TTL = 30s (from SOA minimum)
        neg_ttl = 30
        print(f"  [UPSTREAM]   {name:<30} → NXDOMAIN  neg-TTL={neg_ttl}s")
        return [], neg_ttl, True


def resolve(cache: DNSCache, name: str) -> list:
    """
    Resolve a name using the cache; fall back to upstream on miss.
    Returns list of records, or raises NameError for NXDOMAIN.
    """
    entry = cache.get(name)
    if entry is not None:
        if entry.negative:
            raise NameError(f"NXDOMAIN (cached): {name}")
        return entry.records

    # Cache miss or stale → go upstream
    records, ttl, nxdomain = upstream_lookup(name)
    cache.put(name, records, ttl, negative=nxdomain)

    if nxdomain:
        raise NameError(f"NXDOMAIN: {name}")
    return records


# ── demo scenarios ────────────────────────────────────────────────────────────

def demo(fast: bool = False) -> None:
    cache = DNSCache()
    sep = "─" * 60

    print(f"\n{sep}")
    print("  DNS Cache Demo")
    print(sep)

    # ── Scenario 1: cache miss → hit ──────────────────────────────────────
    print("\n[Scenario 1] First lookup triggers upstream; second serves from cache")
    print()

    ips = resolve(cache, "example.com")
    print(f"  Resolved example.com → {ips}")
    print()
    time.sleep(0.1)

    ips = resolve(cache, "example.com")
    print(f"  Resolved example.com → {ips}  (from cache, no upstream call)")
    print()

    # ── Scenario 2: TTL countdown ─────────────────────────────────────────
    short_ttl = 2 if fast else 5
    print(f"\n[Scenario 2] TTL countdown — record expires after {short_ttl}s")
    print()

    cache.put("api.example.com", ["10.0.0.5"], ttl=short_ttl)
    time.sleep(0.1)

    entry = cache.get("api.example.com")
    if entry:
        print(f"  Immediately after put: remaining TTL = {entry.remaining_ttl():.1f}s")

    wait = short_ttl + 0.2
    print(f"\n  Waiting {wait:.1f}s for TTL to expire …")
    time.sleep(wait)

    entry = cache.get("api.example.com")   # should be stale/evicted
    if entry is None:
        print("  Record evicted as expected — next lookup will go upstream")
        ips = resolve(cache, "api.example.com")
        print(f"  Upstream re-resolved api.example.com → {ips}")

    # ── Scenario 3: negative caching ──────────────────────────────────────
    print("\n[Scenario 3] NXDOMAIN negative caching")
    print()

    try:
        resolve(cache, "nosuchdomain.example.com")
    except NameError as exc:
        print(f"  First lookup: {exc}")

    print()

    try:
        resolve(cache, "nosuchdomain.example.com")
    except NameError as exc:
        print(f"  Second lookup: {exc}  (served from negative cache, no upstream)")

    # ── Scenario 4: multiple names ─────────────────────────────────────────
    print("\n[Scenario 4] Resolving multiple names, only new ones hit upstream")
    print()

    for name in ["google.com", "github.com", "google.com", "github.com"]:
        try:
            ips = resolve(cache, name)
            print(f"  {name:<30} → {ips}")
        except NameError as exc:
            print(f"  {name:<30} → NXDOMAIN")

    # ── stats ──────────────────────────────────────────────────────────────
    st = cache.stats()
    print(f"\n{sep}")
    print("  Cache Statistics")
    print(sep)
    print(f"  Current entries: {st['entries']}")
    print(f"  Cache hits:      {st['hits']}")
    print(f"  Cache misses:    {st['misses']}")
    print(f"  Stale evictions: {st['stales']}")
    total = st["hits"] + st["misses"] + st["stales"]
    if total > 0:
        print(f"  Hit rate:        {st['hits']/total:.0%}")


def main() -> None:
    fast = "--fast" in sys.argv
    demo(fast=fast)


if __name__ == "__main__":
    main()

<!-- Reference: CDN cache-control headers and the cache-busting pattern. -->

# Cache-Control Cheat-Sheet

## The headers
| Directive | Meaning |
|-----------|---------|
| `public` | Any cache (browser + CDN) may store it |
| `private` | Only the user's browser may cache; CDN must NOT |
| `no-store` | Never cache anywhere (sensitive / per-user) |
| `max-age=N` | Serve from cache for N seconds before revalidating |
| `immutable` | Content at this URL never changes (skip revalidation) |
| `ETag` / `Last-Modified` | Validators → cheap `304 Not Modified` checks |

## What to set on what
| Resource | Cache-Control |
|----------|---------------|
| Content-hashed asset `app.3f9a2c.js` | `public, max-age=31536000, immutable` |
| `index.html` (points to hashed assets) | `public, max-age=60` (short) |
| Public blog post (occasional updates) | `public, max-age=300` + ETag |
| Logged-in user's profile / balance | `no-store` (or `private`) |

## Cache busting (the key pattern)
- NEVER overwrite a URL's content.
- Fingerprint filenames with a content hash: `app.<hash>.js`.
- New build → new hash → new URL the CDN has never seen → instant update.
- HTML referencing it is short-TTL so it picks up the new asset name quickly.
- This lets you set 1-year immutable on assets AND ship updates instantly.

## How a CDN serves a request
```
User → nearest PoP (anycast)
  HIT  → served from edge (origin never touched)   ← fast
  MISS → PoP fetches from ORIGIN, caches per headers, serves
         next user in region → HIT
```

## Gotchas
- Wrong headers can pin STALE content globally (hard to fix without a purge).
- `public` on personalized data can leak one user's data to another.
- A CDN caches STATIC well; dynamic/personalized usually can't be cached
  (or only micro-cached / personalized via edge functions).

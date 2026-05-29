# Expected Output

Running `bash http_methods.sh` should produce (abbreviated):

```
================================================================
  HTTP Methods Demo — testing against https://httpbin.org
================================================================

────────────────────────────────────────────────────────
  GET — Retrieve a resource (safe, idempotent)
────────────────────────────────────────────────────────
  ...

  >> GET /get — echoes back your request
  → GET /get HTTP/2
  → Host: httpbin.org
  → Accept: application/json
  ← HTTP/2 200
  ← content-type: application/json
  ← content-length: 264
    {
      "args": {},
      "headers": {
        "Accept": "application/json",
        "Host": "httpbin.org"
      },
      "url": "https://httpbin.org/get"
    }

────────────────────────────────────────────────────────
  HEAD — Like GET but no body
────────────────────────────────────────────────────────
  >> HEAD /get — same headers as GET, but no response body
  → HEAD /get HTTP/2
  ← HTTP/2 200
  ← content-type: application/json
  ← content-length: 264
  (no body — HEAD requests never have a body)

────────────────────────────────────────────────────────
  POST — Create a new resource (NOT idempotent)
────────────────────────────────────────────────────────
  >> POST /post — create with JSON body
  → POST /post HTTP/2
  → Content-Type: application/json
  ← HTTP/2 200
    {
      "json": {"name": "Widget", "price": 9.99},
      "url": "https://httpbin.org/post"
    }

────────────────────────────────────────────────────────
  Status Code Examples
────────────────────────────────────────────────────────

     200 — success
     201 — resource created
     204 — success, no body (typical for DELETE)
     400 — client sent malformed data
     404 — resource does not exist
     405 — method not supported on this URL
     500 — server-side failure

────────────────────────────────────────────────────────
  Method Properties Summary
────────────────────────────────────────────────────────

  Method      Safe        Idempotent    Typical Use
  ──────      ────        ──────────    ───────────
  GET         Yes         Yes           Retrieve resource
  HEAD        Yes         Yes           Check metadata only
  OPTIONS     Yes         Yes           Query allowed methods
  POST        No          No            Create new resource
  PUT         No          Yes           Replace resource entirely
  PATCH       No          No            Partial update
  DELETE      No          Yes           Remove resource
```

## Common issues

- **Issue**: `curl: (6) Could not resolve host: httpbin.org` → **Fix**: No internet access.  Replace `BASE_URL` with a local server URL.  Run `python3 http_server.py 8080` from the previous lesson and change `BASE_URL="http://localhost:8080"`.
- **Issue**: `curl: (35) OpenSSL SSL_connect: Connection reset` → **Fix**: httpbin.org may be temporarily down.  Try `BASE_URL="https://httpbun.com"` (an alternative testing service).
- **Issue**: Script outputs `HTTP/1.1` instead of `HTTP/2` → **Fix**: Some networks or proxies don't support HTTP/2.  HTTP/1.1 is equally valid for this lesson's purposes.

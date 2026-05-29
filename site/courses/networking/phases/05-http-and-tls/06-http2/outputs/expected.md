# Expected Output

Running `bash http2_compare.sh` should produce:

```
================================================================
  HTTP/1.1 vs HTTP/2 Comparison
  Test server: https://nghttp2.org
================================================================

────────────────────────────────────────────────────────
  STEP 1 — Protocol negotiation via ALPN
────────────────────────────────────────────────────────
  During the TLS handshake, the client sends ALPN extensions:
    'h2'       = HTTP/2
    'http/1.1' = HTTP/1.1
  The server selects the highest version it supports.

  >> HTTP/1.1 forced (--http1.1):
    * ALPN: offers http/1.1
    < HTTP/1.1 200 OK

  >> HTTP/2 (--http2, default for HTTPS on modern curl):
    * ALPN: offers h2,http/1.1
    * ALPN: server accepted h2
    < HTTP/2 200

────────────────────────────────────────────────────────
  STEP 2 — Header format differences
────────────────────────────────────────────────────────
  HTTP/1.1: plain text, mixed case, line-per-header
  HTTP/2:   binary HPACK, lowercase, pseudo-headers (:method, :path, :status)

  >> HTTP/1.1 response headers:
    HTTP/1.1 200 OK
    Date: Fri, 29 May 2026 12:00:00 GMT
    Content-Type: text/html; charset=UTF-8
    Content-Length: 6789
    Server: nghttpx

  >> HTTP/2 response headers (note lowercase + :status pseudo-header):
    :status: 200
    date: Fri, 29 May 2026 12:00:00 GMT
    content-type: text/html; charset=UTF-8
    content-length: 6789
    server: nghttpx

────────────────────────────────────────────────────────
  STEP 3 — Alt-Svc header (advertises protocol upgrades)
────────────────────────────────────────────────────────
  Alt-Svc tells clients a faster protocol is available.
  'h2=":443"' = HTTP/2 on the same host port 443
  'h3=":443"' = HTTP/3 (QUIC) on port 443

    alt-svc: h3=":443"; ma=3600, h3-29=":443"; ma=3600

────────────────────────────────────────────────────────
  STEP 4 — HTTP/2 multiplexing (multiple requests, one connection)
────────────────────────────────────────────────────────
  Sending 4 URLs in parallel with --http2 vs --http1.1

  >> HTTP/1.1 (sequential, separate connections):
    200  0.312s
    200  0.298s
    200  0.301s
    200  0.289s
    Total: 1203ms  (sum of sequential requests)

  >> HTTP/2 (parallel streams, single TLS connection):
    200  0.314s
    Total: 387ms  (all requests share one connection)

────────────────────────────────────────────────────────
  STEP 5 — Timing breakdown: TTFB and total time
────────────────────────────────────────────────────────
  TTFB = Time To First Byte (includes TCP+TLS handshake + server processing)

  HTTP/1.1:
    namelookup:  0.012s
    connect:      0.089s
    appconnect:   0.198s  (TCP+TLS done)
    pretransfer:  0.199s
    starttransfer:0.287s  (TTFB)
    total:        0.312s
    http_version: 1.1

  HTTP/2:
    namelookup:  0.011s
    connect:      0.087s
    appconnect:   0.193s  (TCP+TLS done)
    pretransfer:  0.194s
    starttransfer:0.279s  (TTFB)
    total:        0.305s
    http_version: 2

────────────────────────────────────────────────────────
  STEP 6 — HTTP/2 binary framing summary
────────────────────────────────────────────────────────
  HTTP/1.1: text protocol, one request per connection (without pipelining)
  HTTP/2:   binary frames, multiple streams on one connection

  Key HTTP/2 frame types:
    HEADERS    — HTTP headers (replaces request/status line)
    DATA       — body chunks
    SETTINGS   — connection configuration
    WINDOW_UPDATE — flow control
    GOAWAY     — close the connection

  Verbose curl HTTP/2 request shows stream ID assignment:
    * ALPN: server accepted h2
    * [STREAM 1] opened for https://nghttp2.org/
    * Using Stream ID: 1

================================================================
  Comparison complete
================================================================
```

The key observations:
- **ALPN negotiation**: HTTP/1.1 offers only `http/1.1`; HTTP/2 offers `h2,http/1.1` and the server accepts `h2`.
- **Header format**: HTTP/1.1 uses `HTTP/1.1 200 OK` status line; HTTP/2 uses lowercase `:status: 200` pseudo-header.
- **Multiplexing speedup**: HTTP/1.1 takes ~1200ms for 4 sequential requests; HTTP/2 completes all 4 in ~390ms via parallel streams on one connection.
- **Timing**: Both protocols show similar TTFB for a single request (the difference comes from multiplexing, not per-request latency).
- **Stream IDs**: HTTP/2 assigns odd stream IDs (1, 3, 5, ...) for client-initiated requests.

## Common issues

- **Issue**: `curl: (1) Unsupported protocol` or HTTP/2 tests fall back to HTTP/1.1 → **Fix**: Your curl was not compiled with HTTP/2 support. Check: `curl --version | grep HTTP2`. Install a newer curl: `sudo apt-get install -y curl` (Ubuntu) or use `brew install curl` (macOS). On macOS the system curl may not include HTTP/2 — use `$(brew --prefix curl)/bin/curl`.
- **Issue**: `nghttp2.org unreachable, using https://www.cloudflare.com instead` → **Fix**: No internet access to nghttp2.org. The script falls back to cloudflare.com automatically. If both are unreachable, you need internet access for this demo.
- **Issue**: Multiplexing shows no speedup (HTTP/2 total ≈ HTTP/1.1 total) → **Fix**: This can happen if the test server is very fast or very close. Try a host with higher latency (e.g. a server on a different continent). The speedup is most pronounced when RTT > 50ms.
- **Issue**: `Warning: your curl was not compiled with HTTP/2 support` → **Fix**: See the first issue above. The script will continue, but all requests will use HTTP/1.1 regardless of the `--http2` flag.
- **Issue**: Step 6 shows no stream ID output → **Fix**: Some curl versions format the verbose output differently. Try running `curl -sv --http2 https://nghttp2.org/ 2>&1 | grep -i stream` manually to see what your curl outputs.

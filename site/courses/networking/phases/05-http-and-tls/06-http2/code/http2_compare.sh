#!/usr/bin/env bash
# Run: bash http2_compare.sh
# Compares HTTP/1.1 vs HTTP/2 using curl against https://nghttp2.org/
# (a public HTTP/2 test server).
#
# Shows:
#   - Protocol negotiated (via ALPN)
#   - Number of round trips (TCP + TLS + HTTP)
#   - Response headers format differences (lowercase pseudo-headers in HTTP/2)
#   - Multiplexing evidence: multiple requests in a single TLS session
#   - Alt-Svc header advertising HTTP/2 (or h3)
#   - Timing comparison
#
# Requires: curl (built with HTTP/2 support: curl --version | grep HTTP2)
# Ubuntu:   sudo apt-get install -y curl  (usually includes HTTP/2)
# macOS:    curl is pre-installed with HTTP/2 support

set -euo pipefail

H2_HOST="https://nghttp2.org"
ALT_HOST="https://www.cloudflare.com"   # fallback if nghttp2.org is unreachable
SEP="────────────────────────────────────────────────────────"

# ── check curl HTTP/2 support ─────────────────────────────────────────────────
check_h2_support() {
    if ! command -v curl &>/dev/null; then
        echo "Error: curl not found."
        exit 1
    fi

    if ! curl --version | grep -q "HTTP2"; then
        echo "Warning: your curl was not compiled with HTTP/2 support."
        echo "  Ubuntu: sudo apt-get install -y curl"
        echo "  macOS:  curl is pre-installed with HTTP/2"
        echo "  Check:  curl --version | grep HTTP2"
        echo
        echo "Continuing, but HTTP/2 tests will fall back to HTTP/1.1."
    fi
}

check_h2_support

# ── choose a reachable test server ────────────────────────────────────────────
HOST="$H2_HOST"
if ! curl -s --max-time 5 "$H2_HOST" &>/dev/null; then
    echo "nghttp2.org unreachable, using $ALT_HOST instead"
    HOST="$ALT_HOST"
fi

echo "================================================================"
echo "  HTTP/1.1 vs HTTP/2 Comparison"
echo "  Test server: $HOST"
echo "================================================================"

# ── Step 1: Protocol negotiation ─────────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 1 — Protocol negotiation via ALPN"
echo "$SEP"
echo "  During the TLS handshake, the client sends ALPN extensions:"
echo "    'h2'       = HTTP/2"
echo "    'http/1.1' = HTTP/1.1"
echo "  The server selects the highest version it supports."
echo
echo "  >> HTTP/1.1 forced (--http1.1):"
curl -sv --http1.1 "$HOST/" 2>&1 | grep -E "Using HTTP|< HTTP|Protocol:|ALPN|alpn" | \
    head -5 | sed 's/^/    /'

echo
echo "  >> HTTP/2 (--http2, default for HTTPS on modern curl):"
curl -sv --http2 "$HOST/" 2>&1 | grep -E "Using HTTP|< HTTP|Protocol:|ALPN|alpn|h2" | \
    head -5 | sed 's/^/    /'

# ── Step 2: Header format differences ────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 2 — Header format differences"
echo "$SEP"
echo "  HTTP/1.1: plain text, mixed case, line-per-header"
echo "  HTTP/2:   binary HPACK, lowercase, pseudo-headers (:method, :path, :status)"
echo
echo "  >> HTTP/1.1 response headers:"
curl -si --http1.1 "$HOST/" 2>&1 | grep "^[A-Za-z:< ]" | head -15 | sed 's/^/    /'
echo
echo "  >> HTTP/2 response headers (note lowercase + :status pseudo-header):"
curl -si --http2 "$HOST/" 2>&1 | grep "^[a-z:<]" | head -15 | sed 's/^/    /'

# ── Step 3: Alt-Svc header ────────────────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 3 — Alt-Svc header (advertises protocol upgrades)"
echo "$SEP"
echo "  Alt-Svc tells clients a faster protocol is available."
echo "  'h2=\":443\"' = HTTP/2 on the same host port 443"
echo "  'h3=\":443\"' = HTTP/3 (QUIC) on port 443"
echo
curl -si --http1.1 "$HOST/" 2>&1 | grep -i "alt-svc" | sed 's/^/    /' || \
    echo "    (no Alt-Svc header on HTTP/1.1 response)"
curl -si --http2 "$HOST/" 2>&1 | grep -i "alt-svc" | sed 's/^/    /' || \
    echo "    (no Alt-Svc header on HTTP/2 response)"

# ── Step 4: Multiplexing evidence ────────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 4 — HTTP/2 multiplexing (multiple requests, one connection)"
echo "$SEP"
echo "  Sending 4 URLs in parallel with --http2 vs --http1.1"
echo

URLS=("$HOST/" "$HOST/" "$HOST/" "$HOST/")

echo "  >> HTTP/1.1 (sequential, separate connections):"
t_start=$(date +%s%3N)
for url in "${URLS[@]}"; do
    curl -s -o /dev/null --http1.1 --write-out "    %{http_code}  %{time_total}s\n" "$url"
done
t_end=$(date +%s%3N)
echo "    Total: $(( t_end - t_start ))ms  (sum of sequential requests)"

echo
echo "  >> HTTP/2 (parallel streams, single TLS connection):"
t_start=$(date +%s%3N)
curl -s -o /dev/null --http2 --write-out "    %{http_code}  %{time_total}s\n" \
    "${URLS[@]}" &
wait
t_end=$(date +%s%3N)
echo "    Total: $(( t_end - t_start ))ms  (all requests share one connection)"

# ── Step 5: Timing comparison ─────────────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 5 — Timing breakdown: TTFB and total time"
echo "$SEP"
echo "  TTFB = Time To First Byte (includes TCP+TLS handshake + server processing)"
echo

timing_format='    namelookup:  %{time_namelookup}s\n    connect:      %{time_connect}s\n    appconnect:   %{time_appconnect}s  (TCP+TLS done)\n    pretransfer:  %{time_pretransfer}s\n    starttransfer:%{time_starttransfer}s  (TTFB)\n    total:        %{time_total}s\n    http_version: %{http_version}\n'

echo "  HTTP/1.1:"
curl -s -o /dev/null --http1.1 --write-out "$timing_format" "$HOST/"
echo
echo "  HTTP/2:"
curl -s -o /dev/null --http2 --write-out "$timing_format" "$HOST/"

# ── Step 6: Frame count evidence ─────────────────────────────────────────────
echo
echo "$SEP"
echo "  STEP 6 — HTTP/2 binary framing summary"
echo "$SEP"
echo "  HTTP/1.1: text protocol, one request per connection (without pipelining)"
echo "  HTTP/2:   binary frames, multiple streams on one connection"
echo
echo "  Key HTTP/2 frame types:"
echo "    HEADERS    — HTTP headers (replaces request/status line)"
echo "    DATA       — body chunks"
echo "    SETTINGS   — connection configuration"
echo "    WINDOW_UPDATE — flow control"
echo "    GOAWAY     — close the connection"
echo
echo "  Verbose curl HTTP/2 request shows stream ID assignment:"
curl -sv --http2 "$HOST/" 2>&1 | grep -E "Stream|ALPN|h2 |\[STREAM" | \
    head -10 | sed 's/^/    /' || true

echo
echo "================================================================"
echo "  Comparison complete"
echo "================================================================"

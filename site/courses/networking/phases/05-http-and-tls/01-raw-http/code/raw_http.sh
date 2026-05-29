#!/usr/bin/env bash
# Run: bash raw_http.sh
# Send a raw HTTP/1.1 GET request using ncat (or nc as fallback).
# Starts python3 -m http.server 8080 as the target server,
# then sends the exact bytes of a GET request and shows what the server returns.
#
# Demonstrates:
#   - The exact bytes sent and received (request-line, headers, blank line)
#   - HTTP/1.1 is human-readable text over TCP
#   - CRLF (\r\n) line endings are required
#
# Requires: ncat (or nc), python3
# Install ncat:  sudo apt-get install -y ncat    (Ubuntu)
#               brew install nmap                (macOS)

set -euo pipefail

PORT=8080
HOST=127.0.0.1

cleanup() {
    [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
    rm -rf "$SERVE_DIR"
}
trap cleanup EXIT

# ── create a minimal site to serve ───────────────────────────────────────────
SERVE_DIR=$(mktemp -d)
cat > "$SERVE_DIR/index.html" <<'HTML'
<!DOCTYPE html>
<html>
<head><title>Raw HTTP Demo</title></head>
<body>
<h1>Hello from raw HTTP!</h1>
<p>This page was served by python3 -m http.server</p>
</body>
</html>
HTML
echo '{"status":"ok","lesson":"raw-http"}' > "$SERVE_DIR/api.json"

# ── start the server ──────────────────────────────────────────────────────────
python3 -m http.server "$PORT" --directory "$SERVE_DIR" \
    --bind "$HOST" &>/dev/null &
SERVER_PID=$!
sleep 0.4   # wait for server to bind

echo "================================================================"
echo "  Raw HTTP/1.1 Demo — server on $HOST:$PORT"
echo "================================================================"

SEP="────────────────────────────────────────────────────────"

# ── choose ncat or nc ─────────────────────────────────────────────────────────
if command -v ncat &>/dev/null; then
    NETCAT_CMD="ncat"
elif command -v nc &>/dev/null; then
    NETCAT_CMD="nc"
else
    echo "Warning: neither ncat nor nc found.  Using Python socket instead."
    NETCAT_CMD=""
fi

send_raw_request() {
    local method="$1"
    local path="$2"
    local extra_headers="${3:-}"

    echo
    echo "$SEP"
    echo "  REQUEST: $method $path"
    echo "$SEP"
    echo
    echo "  Bytes sent (\\r\\n shown as ↵):"

    # Build the request with literal CRLF line endings
    REQUEST="${method} ${path} HTTP/1.1\r\nHost: ${HOST}:${PORT}\r\nConnection: close\r\nUser-Agent: raw-http-demo/1.0\r\nAccept: */*\r\n"
    [[ -n "$extra_headers" ]] && REQUEST="${REQUEST}${extra_headers}\r\n"
    REQUEST="${REQUEST}\r\n"

    # Display the request with visible CRLF markers
    printf "%s" "$REQUEST" | sed 's/\r/↵/g' | sed 's/^/    /'

    echo
    echo "  Bytes received:"
    echo

    if [[ -n "$NETCAT_CMD" ]]; then
        # Use ncat/nc — pipe the request bytes and show the full response
        printf "%b" "$REQUEST" | "$NETCAT_CMD" -q 1 "$HOST" "$PORT" 2>/dev/null | \
            awk '
            BEGIN { in_header=1; blank=0 }
            in_header {
                if ($0 == "\r" || $0 == "") {
                    print "    "  # blank line separator
                    in_header=0
                    next
                }
                print "    " $0
                next
            }
            { print "    " $0 }
            ' | head -40
    else
        # Python fallback
        python3 - "$HOST" "$PORT" "$method" "$path" <<'PYEOF'
import socket, sys
host, port, method, path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
req = f"{method} {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
s = socket.socket(); s.settimeout(5); s.connect((host, port))
s.sendall(req.encode()); buf = b""
while True:
    chunk = s.recv(4096)
    if not chunk: break
    buf += chunk
s.close()
for line in buf.decode("utf-8", errors="replace").splitlines()[:40]:
    print("   ", line)
PYEOF
    fi
}

# ── Demo 1: GET / ─────────────────────────────────────────────────────────────
send_raw_request "GET" "/"

# ── Demo 2: GET /api.json ─────────────────────────────────────────────────────
send_raw_request "GET" "/api.json"

# ── Demo 3: GET a non-existent path ───────────────────────────────────────────
send_raw_request "GET" "/notexist.html"

# ── explain what we saw ───────────────────────────────────────────────────────
echo
echo "$SEP"
echo "  Key observations"
echo "$SEP"
echo
echo "  REQUEST LINE:   METHOD SP path SP HTTP/1.1 CRLF"
echo "  HEADERS:        Key: Value CRLF  (each header ends with \\r\\n)"
echo "  BLANK LINE:     \\r\\n  (signals end of headers)"
echo "  BODY:           Content-Length bytes follow (or until connection close)"
echo
echo "  Status codes observed:"
echo "    200 OK         — resource found and returned"
echo "    404 Not Found  — no file at that path"
echo
echo "  Content-Type header tells the client how to interpret the body:"
echo "    text/html        → render as HTML"
echo "    application/json → parse as JSON"
echo "    text/plain       → show as plain text"
echo

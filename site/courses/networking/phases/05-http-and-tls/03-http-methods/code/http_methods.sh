#!/usr/bin/env bash
# Run: bash http_methods.sh
# Demonstrates GET, POST, PUT, DELETE, HEAD, and OPTIONS using curl.
# For each method, shows the request headers sent and the response received.
# Uses httpbin.org (a public HTTP testing service).
#
# Requires: curl
# Optional: python3 (for a local httpbin-style server when offline)

set -euo pipefail

BASE_URL="https://httpbin.org"
SEP="────────────────────────────────────────────────────────"

# ── check curl ────────────────────────────────────────────────────────────────
if ! command -v curl &>/dev/null; then
    echo "Error: curl not found.  Install with: sudo apt-get install -y curl"
    exit 1
fi

section() {
    echo; echo "$SEP"
    echo "  $1"
    echo "$SEP"
    echo "  $2"
    echo
}

run_curl() {
    local desc="$1"; shift
    echo "  >> $desc"
    # -s = silent (no progress bar), -S = show errors, -v = verbose headers
    # We show request + response headers, then the first 30 lines of body
    curl -s -S -v "$@" 2>&1 | \
        awk '
        /^> / { sub(/^> /,"  → "); print }
        /^< / { sub(/^< /,"  ← "); print }
        /^\{/,/^\}/ { print "    " $0 }
        ' | head -60
    echo
}

echo "================================================================"
echo "  HTTP Methods Demo — testing against $BASE_URL"
echo "================================================================"

# ── GET ───────────────────────────────────────────────────────────────────────
section "GET — Retrieve a resource (safe, idempotent)" \
        "Retrieves without modifying.  Can be cached, bookmarked, retried safely."
run_curl "GET /get — echoes back your request" \
    -X GET "$BASE_URL/get" \
    -H "Accept: application/json"

# ── HEAD ─────────────────────────────────────────────────────────────────────
section "HEAD — Like GET but no body (safe, idempotent)" \
        "Used to check Content-Length or Last-Modified before downloading."
run_curl "HEAD /get — same headers as GET, but no response body" \
    -X HEAD "$BASE_URL/get" \
    -H "Accept: application/json"

# ── POST ─────────────────────────────────────────────────────────────────────
section "POST — Create a new resource (NOT idempotent)" \
        "Each call may create a new resource.  Not safe to retry automatically."
run_curl "POST /post — create with JSON body" \
    -X POST "$BASE_URL/post" \
    -H "Content-Type: application/json" \
    -d '{"name":"Widget","price":9.99}'

# ── PUT ───────────────────────────────────────────────────────────────────────
section "PUT — Replace a resource entirely (idempotent)" \
        "Calling PUT twice with the same body gives the same result as calling it once."
run_curl "PUT /put — replace/create resource" \
    -X PUT "$BASE_URL/put" \
    -H "Content-Type: application/json" \
    -d '{"id":42,"name":"Updated Widget","price":14.99}'

# ── DELETE ───────────────────────────────────────────────────────────────────
section "DELETE — Remove a resource (idempotent)" \
        "Deleting an already-deleted resource should return 404, not an error."
run_curl "DELETE /delete — delete a resource" \
    -X DELETE "$BASE_URL/delete" \
    -H "Accept: application/json"

# ── OPTIONS ──────────────────────────────────────────────────────────────────
section "OPTIONS — Query which methods are allowed (safe, idempotent)" \
        "The Allow response header lists the methods the server accepts."
run_curl "OPTIONS /get — what methods does this endpoint accept?" \
    -X OPTIONS "$BASE_URL/get" \
    -i

# ── PATCH ────────────────────────────────────────────────────────────────────
section "PATCH — Partial update (NOT idempotent by default)" \
        "Like PUT but only sends the fields that changed."
run_curl "PATCH /patch — partial update" \
    -X PATCH "$BASE_URL/patch" \
    -H "Content-Type: application/json" \
    -d '{"price":12.50}'

# ── status code demo ─────────────────────────────────────────────────────────
echo "$SEP"
echo "  Status Code Examples"
echo "$SEP"
echo
echo "  >> HTTP 200 OK"
curl -s -o /dev/null -w "     %{http_code} — success\n" "$BASE_URL/status/200"

echo "  >> HTTP 201 Created"
curl -s -o /dev/null -w "     %{http_code} — resource created\n" \
    -X POST "$BASE_URL/status/201"

echo "  >> HTTP 204 No Content"
curl -s -o /dev/null -w "     %{http_code} — success, no body (typical for DELETE)\n" \
    -X DELETE "$BASE_URL/status/204"

echo "  >> HTTP 400 Bad Request"
curl -s -o /dev/null -w "     %{http_code} — client sent malformed data\n" \
    "$BASE_URL/status/400"

echo "  >> HTTP 404 Not Found"
curl -s -o /dev/null -w "     %{http_code} — resource does not exist\n" \
    "$BASE_URL/status/404"

echo "  >> HTTP 405 Method Not Allowed"
curl -s -o /dev/null -w "     %{http_code} — method not supported on this URL\n" \
    "$BASE_URL/status/405"

echo "  >> HTTP 500 Internal Server Error"
curl -s -o /dev/null -w "     %{http_code} — server-side failure\n" \
    "$BASE_URL/status/500"

echo
echo "$SEP"
echo "  Method Properties Summary"
echo "$SEP"
echo
printf "  %-10s  %-10s  %-12s  %s\n" "Method" "Safe" "Idempotent" "Typical Use"
printf "  %-10s  %-10s  %-12s  %s\n" "──────" "────" "──────────" "───────────"
printf "  %-10s  %-10s  %-12s  %s\n" "GET"     "Yes"  "Yes"  "Retrieve resource"
printf "  %-10s  %-10s  %-12s  %s\n" "HEAD"    "Yes"  "Yes"  "Check metadata only"
printf "  %-10s  %-10s  %-12s  %s\n" "OPTIONS" "Yes"  "Yes"  "Query allowed methods"
printf "  %-10s  %-10s  %-12s  %s\n" "POST"    "No"   "No"   "Create new resource"
printf "  %-10s  %-10s  %-12s  %s\n" "PUT"     "No"   "Yes"  "Replace resource entirely"
printf "  %-10s  %-10s  %-12s  %s\n" "PATCH"   "No"   "No"   "Partial update"
printf "  %-10s  %-10s  %-12s  %s\n" "DELETE"  "No"   "Yes"  "Remove resource"
echo

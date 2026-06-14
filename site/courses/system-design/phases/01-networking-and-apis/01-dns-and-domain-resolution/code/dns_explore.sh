#!/usr/bin/env bash
# Run: bash dns_explore.sh [domain]
# Explore DNS resolution layer by layer with dig.

set -euo pipefail
DOMAIN="${1:-example.com}"

echo "=== 1. Basic A record + TTL for $DOMAIN ==="
dig "$DOMAIN" A +noall +answer

echo
echo "=== 2. TTL counts down in the resolver cache (run twice) ==="
dig "$DOMAIN" A +noall +answer
sleep 1
dig "$DOMAIN" A +noall +answer

echo
echo "=== 3. Record types ==="
echo "-- NS (authoritative name servers) --"
dig "$DOMAIN" NS +short
echo "-- MX (mail servers) --"
dig "$DOMAIN" MX +short
echo "-- AAAA (IPv6) --"
dig "$DOMAIN" AAAA +short

echo
echo "=== 4. Query a specific public resolver (Google 8.8.8.8) ==="
dig @8.8.8.8 "$DOMAIN" +short

echo
echo "=== 5. Full hierarchy trace (root -> TLD -> authoritative) ==="
echo "(this can be long; comment out if you only want the basics)"
dig +trace "$DOMAIN" | grep -E "NS|A\s" | head -20

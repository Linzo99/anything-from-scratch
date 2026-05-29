#!/usr/bin/env bash
# Run: bash dns_records.sh
# Query each major DNS record type for several real domains using dig.
# Labels each query type and explains the response.
#
# Record types covered: A, AAAA, MX, TXT, CNAME, NS, SOA
# Domains used: example.com, google.com, github.com, gmail.com, cloudflare.com
#
# Requires: dig (dnsutils on Ubuntu, pre-installed on macOS)

set -euo pipefail

SEP="─────────────────────────────────────────────────────────"

check_dig() {
    if ! command -v dig &>/dev/null; then
        echo "Error: 'dig' not found."
        echo "  Ubuntu/Debian: sudo apt-get install -y dnsutils"
        echo "  macOS:         dig is pre-installed"
        exit 1
    fi
}

section() { echo; echo "$SEP"; echo "  $1"; echo "$SEP"; }
run_dig() {
    local desc="$1"; shift
    echo; echo "  >> $desc"
    dig "$@" +noall +answer +comments 2>/dev/null | \
        grep -v "^$" | sed 's/^/     /'
}

check_dig

echo "================================================================"
echo "  DNS Record Types — dig queries for real domains"
echo "================================================================"

# ── A Record ─────────────────────────────────────────────────────────────────
section "A Record — Maps hostname to IPv4 address"
echo "  Purpose: The most common record type. Tells clients which IPv4"
echo "  address to connect to. Multiple A records = round-robin pool."
run_dig "example.com A (single address)"       example.com A +short
run_dig "google.com A (multiple IPs, round-robin)" google.com A +short

# ── AAAA Record ──────────────────────────────────────────────────────────────
section "AAAA Record — Maps hostname to IPv6 address"
echo "  Purpose: Same as A but for IPv6 (128-bit address)."
echo "  'Quad A' = four A's in AAAA."
run_dig "google.com AAAA" google.com AAAA +short
run_dig "cloudflare.com AAAA" cloudflare.com AAAA +short
run_dig "example.com AAAA (may be empty)" example.com AAAA +short || \
    echo "     (no AAAA record)"

# ── CNAME Record ─────────────────────────────────────────────────────────────
section "CNAME Record — Alias one name to another (canonical name)"
echo "  Purpose: Make one hostname an alias for another."
echo "  Rule: A CNAME cannot coexist with other records at the same name."
echo "  Rule: The apex domain (example.com) cannot be a CNAME."
run_dig "www.github.com CNAME (often aliased)" www.github.com CNAME +short
run_dig "www.github.com A (follow CNAME chain)" www.github.com A +short

# ── MX Record ────────────────────────────────────────────────────────────────
section "MX Record — Mail exchanger (email delivery routing)"
echo "  Purpose: Tells sending mail servers where to deliver email."
echo "  Format:  priority  hostname  (lower priority = higher preference)"
echo "  Note:    MX records point to hostnames, never IP addresses directly."
run_dig "gmail.com MX (multiple priorities)" gmail.com MX +short
run_dig "github.com MX" github.com MX +short

# Resolve the top-priority MX to an IP to show the chain
TOP_MX=$(dig gmail.com MX +short 2>/dev/null | sort -n | head -1 | awk '{print $2}')
if [[ -n "$TOP_MX" ]]; then
    run_dig "Top-priority MX '$TOP_MX' resolves to:" "$TOP_MX" A +short
fi

# ── TXT Record ───────────────────────────────────────────────────────────────
section "TXT Record — Arbitrary text (SPF, DKIM, DMARC, verification)"
echo "  Purpose: Stores text strings for:"
echo "    SPF   — which servers may send email claiming to be from this domain"
echo "    DKIM  — public key for verifying email signatures"
echo "    DMARC — policy for handling SPF/DKIM failures"
echo "    Verification — domain ownership proofs (Google, GitHub, etc.)"
run_dig "github.com TXT (SPF + verification tokens)" github.com TXT +short
run_dig "_dmarc.gmail.com TXT (DMARC policy)" _dmarc.gmail.com TXT +short
echo
echo "  >> How to read the SPF record:"
dig github.com TXT +short 2>/dev/null | grep -i spf | head -1 | \
    sed 's/^/     /' || echo "     (no SPF found)"

# ── NS Record ────────────────────────────────────────────────────────────────
section "NS Record — Authoritative nameservers for a zone"
echo "  Purpose: Identifies which nameservers hold the zone file."
echo "  Set by:  your domain registrar, delegated into the parent TLD zone."
echo "  Rule:    Every domain must have ≥2 NS records (for redundancy)."
run_dig "example.com NS" example.com NS +short
run_dig "google.com NS" google.com NS +short

# Query one of the authoritative NSes directly to show the 'aa' flag
FIRST_NS=$(dig google.com NS +short 2>/dev/null | sort | head -1)
if [[ -n "$FIRST_NS" ]]; then
    echo
    echo "  >> Querying $FIRST_NS directly (should show 'aa' flag):"
    dig @"$FIRST_NS" google.com A +noall +comments 2>/dev/null | \
        grep "flags:" | sed 's/^/     /'
fi

# ── SOA Record ───────────────────────────────────────────────────────────────
section "SOA Record — Start of Authority (zone metadata)"
echo "  Purpose: Zone administrative info + parameters for secondary servers."
echo "  Fields:  primary-ns  admin-email  serial  refresh  retry  expire  min-ttl"
echo "  min-ttl is also the negative caching TTL (how long NXDOMAIN is cached)."
run_dig "example.com SOA" example.com SOA +short
run_dig "google.com SOA" google.com SOA +short

# ── summary ───────────────────────────────────────────────────────────────────
echo
echo "$SEP"
echo "  Summary"
echo "$SEP"
echo "  Record  Holds               Primary Use"
echo "  ──────────────────────────────────────────────────────────"
echo "  A       IPv4 address        Map hostname → IP"
echo "  AAAA    IPv6 address        Map hostname → IPv6"
echo "  CNAME   Domain name         Alias (cannot be at apex)"
echo "  MX      Priority + name     Email delivery routing"
echo "  TXT     Arbitrary text      SPF / DKIM / DMARC / verification"
echo "  NS      Domain name         Authoritative nameservers for zone"
echo "  SOA     Zone metadata       Serial, refresh, negative TTL"
echo

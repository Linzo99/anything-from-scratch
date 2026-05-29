#!/usr/bin/env bash
# Run: bash dns_trace.sh [domain]
# Trace the full recursive DNS resolution chain for a domain using dig +trace,
# then compare it to a direct query against Google's public resolver (8.8.8.8).
#
# Labels each step: root → TLD → authoritative.
# Requires: dig (part of dnsutils / bind-utils on Linux, pre-installed on macOS)
#
# Usage:
#   bash dns_trace.sh              # defaults to github.com
#   bash dns_trace.sh example.com

set -euo pipefail

DOMAIN="${1:-github.com}"
SEPARATOR="─────────────────────────────────────────────────────────────────"

# ── check prerequisites ───────────────────────────────────────────────────────
if ! command -v dig &>/dev/null; then
    echo "Error: 'dig' not found."
    echo "  Ubuntu/Debian: sudo apt-get install -y dnsutils"
    echo "  macOS:         dig is pre-installed"
    exit 1
fi

# ── helper: extract server that answered each delegation ─────────────────────
label_step() {
    local server="$1"
    case "$server" in
        *root-servers.net*) echo "ROOT NAMESERVER";;
        *gtld-servers.net*) echo "TLD NAMESERVER (.com/.net)";;
        *iana-servers.net*) echo "AUTHORITATIVE NAMESERVER (iana)";;
        a.root-servers.net|b.root-servers.net|c.root-servers.net|\
        d.root-servers.net|e.root-servers.net|f.root-servers.net|\
        g.root-servers.net|h.root-servers.net|i.root-servers.net|\
        j.root-servers.net|k.root-servers.net|l.root-servers.net|\
        m.root-servers.net) echo "ROOT NAMESERVER";;
        *) echo "AUTHORITATIVE NAMESERVER";;
    esac
}

echo ""
echo "=============================="
echo " DNS Resolution Trace for: $DOMAIN"
echo "=============================="
echo ""

# ── Step 1: full recursive trace ─────────────────────────────────────────────
echo "$SEPARATOR"
echo "STEP 1 — Full iterative trace (dig +trace)"
echo "$SEPARATOR"
echo "  Each block shows one delegation step, ending with the server that answered."
echo "  The resolver walks: local cache → root → TLD → authoritative nameserver"
echo ""

# Run dig +trace and parse the output to label each server block
dig +trace +additional "$DOMAIN" A 2>/dev/null | \
    awk '
    /^;; Received/ {
        # "Received N bytes from <server>#<port>(<server2>) in <ms> ms"
        match($0, /from ([^#]+)#[0-9]+/, arr)
        if (arr[1] != "") {
            server = arr[1]
            gsub(/^[ \t]+|[ \t]+$/, "", server)
            if (server ~ /root-servers/) step="[ROOT → returns TLD nameservers]"
            else if (server ~ /gtld-servers/) step="[TLD → returns authoritative NS]"
            else step="[AUTHORITATIVE → returns final answer]"
            printf "  *** %s  %s\n\n", server, step
        }
    }
    /^[^;]/ { print "    " $0 }
    /^;/ { print "  " $0 }
    '

# ── Step 2: direct query to Google's resolver ────────────────────────────────
echo ""
echo "$SEPARATOR"
echo "STEP 2 — Direct query to 8.8.8.8 (Google Public DNS)"
echo "$SEPARATOR"
echo "  This bypasses your local cache and asks Google's recursive resolver."
echo ""
dig @8.8.8.8 "$DOMAIN" A +noall +answer +comments 2>/dev/null | \
    awk '
    /^;; ->>HEADER/ { print "  " $0; next }
    /^[^;]/ {
        printf "  %-45s %s %s %s %s\n", $1, $2, $3, $4, $5
    }
    '

# ── Step 3: authoritative nameservers ────────────────────────────────────────
echo ""
echo "$SEPARATOR"
echo "STEP 3 — Who are the authoritative nameservers for $DOMAIN?"
echo "$SEPARATOR"
echo ""
dig @8.8.8.8 "$DOMAIN" NS +short 2>/dev/null | sort | \
    while read ns; do
        echo "  NS: $ns"
    done

# ── Step 4: query the authoritative NS directly ───────────────────────────────
FIRST_NS=$(dig @8.8.8.8 "$DOMAIN" NS +short 2>/dev/null | sort | head -1)
if [[ -n "$FIRST_NS" ]]; then
    echo ""
    echo "$SEPARATOR"
    echo "STEP 4 — Query authoritative NS ($FIRST_NS) directly"
    echo "$SEPARATOR"
    echo "  Expect 'aa' (authoritative answer) flag in the response."
    echo ""
    dig @"$FIRST_NS" "$DOMAIN" A +noall +answer +comments 2>/dev/null | \
        awk '/^;; flags/ { print "  " $0 }
             /^[^;]/ { printf "  %-45s %s %s %s %s\n", $1, $2, $3, $4, $5 }'
fi

echo ""
echo "=============================="
echo " Trace complete for $DOMAIN"
echo "=============================="

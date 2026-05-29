# Run: bash verify_lab.sh
#!/usr/bin/env bash
# verify_lab.sh — Check that all four essential networking tools are installed.
# Prints PASS or FAIL for each tool and exits 0 only if all four pass.

set -euo pipefail

PASS=0
FAIL=0

check_tool() {
    local name="$1"
    local cmd="$2"

    if command -v "$cmd" &>/dev/null; then
        local version
        version=$("$cmd" --version 2>&1 | head -1)
        printf "%-12s  PASS  (%s)\n" "$name" "$version"
        PASS=$((PASS + 1))
    else
        printf "%-12s  FAIL  (not found — install with: sudo apt-get install -y %s)\n" \
            "$name" "$cmd"
        FAIL=$((FAIL + 1))
    fi
}

echo "=============================="
echo " Networking Lab Tool Checker  "
echo "=============================="
echo ""

# 1. iproute2 — the ip command (L2/L3 management)
if command -v ip &>/dev/null; then
    version=$(ip --version 2>&1 | head -1)
    printf "%-12s  PASS  (%s)\n" "iproute2" "$version"
    PASS=$((PASS + 1))
else
    printf "%-12s  FAIL  (not found — install with: sudo apt-get install -y iproute2)\n" "iproute2"
    FAIL=$((FAIL + 1))
fi

# 2. tcpdump — packet capture (L2–L7)
check_tool "tcpdump" "tcpdump"

# 3. nmap — network scanner (L3–L7)
check_tool "nmap" "nmap"

# 4. ncat — TCP/UDP utility (L3–L4)
#    Try ncat first, then nc as fallback
if command -v ncat &>/dev/null; then
    version=$(ncat --version 2>&1 | head -1)
    printf "%-12s  PASS  (%s)\n" "ncat" "$version"
    PASS=$((PASS + 1))
elif command -v nc &>/dev/null; then
    version=$(nc -h 2>&1 | head -1)
    printf "%-12s  PASS  (nc found: %s)\n" "ncat/nc" "$version"
    PASS=$((PASS + 1))
else
    printf "%-12s  FAIL  (not found — install with: sudo apt-get install -y ncat)\n" "ncat"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "------------------------------"
echo " Results: ${PASS} PASS / ${FAIL} FAIL"
echo "------------------------------"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Fix FAIL items above, then re-run this script."
    exit 1
else
    echo ""
    echo "All tools present. Your lab is ready."
    exit 0
fi

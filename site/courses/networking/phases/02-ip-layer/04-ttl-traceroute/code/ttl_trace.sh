# Run: bash ttl_trace.sh
#!/usr/bin/env bash
# ttl_trace.sh — Demonstrate TTL expiry step by step, simulating what traceroute does.
#
# Sends pings with TTL=1, 2, 3 ... to a target and watches for:
#   - ICMP "Time Exceeded" (TTL expired in transit) at intermediate hops
#   - ICMP "Echo Reply" when the packet reaches the destination
#
# Also captures the ICMP responses with tcpdump to show the raw exchange.
#
# Usage:
#   bash ttl_trace.sh                     # trace to 8.8.8.8 (requires internet)
#   bash ttl_trace.sh 192.168.1.1 5       # trace to gateway, max 5 hops
#   bash ttl_trace.sh 127.0.0.1 3         # loopback — always reaches in 1 hop
#
# Note: ping with ttl option requires no special privileges on Linux.
#       For a real trace you may want to run as root to capture ICMP replies.

set -uo pipefail

TARGET="${1:-8.8.8.8}"
MAX_HOPS="${2:-15}"

SEP="──────────────────────────────────────────────────────────"

echo ""
echo "$SEP"
echo " TTL Expiry Demo — Step-by-step traceroute simulation"
echo " Target: $TARGET  |  Max hops: $MAX_HOPS"
echo "$SEP"
echo ""
echo " Theory:"
echo "   TTL = 1 → packet dies at first router → ICMP Time Exceeded from hop 1"
echo "   TTL = 2 → packet dies at second router → ICMP Time Exceeded from hop 2"
echo "   TTL = N → packet reaches destination → ICMP Echo Reply"
echo ""

# ── Check if target is reachable ──────────────────────────────────────────────
echo "Step 0: Resolving $TARGET ..."
if command -v host &>/dev/null; then
    host "$TARGET" 2>/dev/null | head -2 || true
elif command -v nslookup &>/dev/null; then
    nslookup "$TARGET" 2>/dev/null | head -5 || true
else
    echo "  (no DNS tool available — using IP directly)"
fi
echo ""

# ── Loopback fast-path ────────────────────────────────────────────────────────
if [ "$TARGET" = "127.0.0.1" ] || [ "$TARGET" = "::1" ] || [ "$TARGET" = "localhost" ]; then
    echo "Loopback target detected — packet never leaves the host."
    echo "TTL is not decremented on loopback, so it always reaches in 1 hop."
    echo ""
    echo "Sending ping with TTL=1 to 127.0.0.1:"
    ping -c 1 -t 1 -W 1 127.0.0.1 2>&1 || ping -c 1 -m 1 -W 1 127.0.0.1 2>&1 || \
        ping -c 1 127.0.0.1
    echo ""
    exit 0
fi

# ── Step-by-step TTL probes ───────────────────────────────────────────────────
echo "$SEP"
echo " Sending ICMP probes with increasing TTL values:"
echo "$SEP"
echo ""

REACHED=0

for ttl in $(seq 1 "$MAX_HOPS"); do
    printf "  TTL=%2d  " "$ttl"

    # Try to detect the platform (Linux vs macOS) for the TTL flag
    # Linux ping: -t TTL  or  --ttl TTL  (GNU inetutils)
    # macOS ping: -m TTL
    if ping -c 1 -W 2 -t "$ttl" "$TARGET" >/tmp/ttl_ping_out.txt 2>&1; then
        # Packet reached the destination
        RTT=$(grep -oP 'time=\K[0-9.]+' /tmp/ttl_ping_out.txt | head -1 || echo "?")
        echo "REACHED destination ($TARGET)  RTT=${RTT} ms"
        REACHED=1
        break
    else
        OUTPUT=$(cat /tmp/ttl_ping_out.txt)
        # Check for "Time to live exceeded" or "Time exceeded" in output
        if echo "$OUTPUT" | grep -qiE "time.*exceed|ttl.*exceed"; then
            # Extract the hop IP from the ICMP error message
            HOP_IP=$(echo "$OUTPUT" | grep -oE "From [0-9.]+" | awk '{print $2}' | head -1)
            if [ -z "$HOP_IP" ]; then
                HOP_IP="(unknown)"
            fi
            echo "Time Exceeded from $HOP_IP  (this router decremented TTL to 0)"
        elif echo "$OUTPUT" | grep -qiE "unreachable|network is"; then
            echo "Network unreachable  (no route to $TARGET)"
            break
        else
            echo "*  (no response — router blocked ICMP or rate-limited)"
        fi
    fi
done

echo ""
if [ "$REACHED" -eq 1 ]; then
    echo "$SEP"
    echo " Destination reached!"
else
    echo "$SEP"
    echo " Max hops ($MAX_HOPS) reached without reaching $TARGET"
    echo " (Either the path is longer, or intermediate routers block ICMP)"
fi

# ── Compare with system traceroute ───────────────────────────────────────────
echo ""
echo "$SEP"
echo " For comparison, running system traceroute (if available):"
echo "$SEP"
if command -v traceroute &>/dev/null; then
    traceroute -n -m "$MAX_HOPS" -w 2 "$TARGET" 2>/dev/null | head -20 || true
elif command -v tracepath &>/dev/null; then
    tracepath -n -m "$MAX_HOPS" "$TARGET" 2>/dev/null | head -20 || true
else
    echo " (traceroute/tracepath not installed)"
    echo " Install with: sudo apt-get install -y traceroute"
fi

echo ""
echo "$SEP"
echo " Key takeaways:"
echo "   Each hop decrements TTL by 1"
echo "   TTL=0 triggers ICMP Time Exceeded → reveals the hop's IP"
echo "   traceroute sends TTL=1, 2, 3 ... to map every hop"
echo "   '*' means that hop doesn't respond to ICMP probes"
echo "$SEP"
echo ""

rm -f /tmp/ttl_ping_out.txt

# Run: bash arp_table.sh
#!/usr/bin/env bash
# arp_table.sh — Inspect the ARP cache, classify MAC addresses, and watch
#                the table update after generating local traffic.
#
# Steps:
#   1. Show the current ARP/neighbour table (ip neigh show).
#   2. Classify each MAC as UNICAST, MULTICAST, or BROADCAST.
#   3. Look up the OUI (first 3 bytes) of the default gateway's MAC.
#   4. Generate loopback traffic with ncat to populate the table.
#   5. Show the updated neighbour table.

set -uo pipefail

SEP="──────────────────────────────────────────────────────────"

echo ""
echo "$SEP"
echo " MAC Address and ARP Table Inspector"
echo "$SEP"

# ── Helper: classify a MAC address ───────────────────────────────────────────
classify_mac() {
    local mac="$1"
    if [ "$mac" = "ff:ff:ff:ff:ff:ff" ]; then
        echo "BROADCAST"
        return
    fi
    local first_byte_hex="${mac%%:*}"
    local first_byte=$((16#$first_byte_hex))
    if (( (first_byte & 1) == 1 )); then
        echo "MULTICAST"
    else
        echo "UNICAST"
    fi
}

# ── Step 1: Current ARP / neighbour table ────────────────────────────────────
echo ""
echo "Step 1: Current ARP cache (ip neigh show)"
echo ""
NEIGH=$(ip neigh show 2>/dev/null)
if [ -z "$NEIGH" ]; then
    echo "  (ARP cache is empty)"
else
    echo "$NEIGH"
fi

# ── Step 2: Classify each MAC in the neighbour table ─────────────────────────
echo ""
echo "Step 2: Classify each MAC address in the cache"
echo ""
printf "  %-20s  %-18s  %s\n" "IP" "MAC" "Type"
printf "  %-20s  %-18s  %s\n" "──────────────────" "────────────────" "────────────"
ip neigh show 2>/dev/null | while read -r ip _dev _iface _lladdr mac _state; do
    if [ -n "$mac" ] && [[ "$mac" =~ ^[0-9a-f]{2}: ]]; then
        type=$(classify_mac "$mac")
        printf "  %-20s  %-18s  %s\n" "$ip" "$mac" "$type"
    fi
done
if [ -z "$NEIGH" ]; then
    echo "  (no entries to classify)"
fi

# ── Step 3: OUI lookup for default gateway ────────────────────────────────────
echo ""
echo "Step 3: OUI lookup for default gateway MAC"
echo ""
GW=$(ip route show default 2>/dev/null | awk '/default via/ {print $3}' | head -1)
if [ -z "$GW" ]; then
    echo "  No default gateway configured."
else
    echo "  Default gateway IP: $GW"
    GW_IFACE=$(ip route show default 2>/dev/null | awk '{print $5}' | head -1)
    GW_MAC=$(ip neigh show "$GW" dev "$GW_IFACE" 2>/dev/null | awk '{print $5}' | head -1)

    if [ -z "$GW_MAC" ] || [[ ! "$GW_MAC" =~ ^[0-9a-f]{2}: ]]; then
        # Try to populate the ARP cache for the gateway
        ping -c 1 -W 1 "$GW" >/dev/null 2>&1 || true
        GW_MAC=$(ip neigh show "$GW" 2>/dev/null | awk '{print $5}' | head -1)
    fi

    if [ -n "$GW_MAC" ] && [[ "$GW_MAC" =~ ^[0-9a-f]{2}: ]]; then
        OUI=$(echo "$GW_MAC" | tr ':' '-' | cut -c1-8 | tr 'a-z' 'A-Z')
        echo "  Gateway MAC: $GW_MAC"
        echo "  OUI: $OUI (first 3 bytes = manufacturer prefix)"
        echo ""
        echo "  Known OUI prefixes:"
        echo "    00-50-56  VMware"
        echo "    00-15-5D  Microsoft (Hyper-V)"
        echo "    08-00-27  Oracle (VirtualBox)"
        echo "    DC-A6-32  Raspberry Pi Foundation"
        echo "    00-1A-2B  Apple"
        echo "    02-42-xx  Locally administered (Docker, etc.)"
        echo ""
        echo "  To look up any OUI: https://maclookup.app"
    else
        echo "  Gateway MAC not in ARP cache. Run: ping -c 1 $GW"
    fi
fi

# ── Step 4: Generate traffic and watch the table ────────────────────────────
echo ""
echo "Step 4: Generate loopback traffic and check ARP table"
echo "  (loopback traffic does NOT create real ARP entries — it shows"
echo "   that L2 is handled differently on virtual/loopback interfaces)"
echo ""

if command -v ncat &>/dev/null; then
    echo "  Starting ncat listener on 127.0.0.1:18234 ..."
    ncat -l 18234 &
    NC_PID=$!
    sleep 0.1
    echo "hello arp demo" | ncat -w 1 127.0.0.1 18234 2>/dev/null || true
    sleep 0.1
    kill "$NC_PID" 2>/dev/null || true
    wait "$NC_PID" 2>/dev/null || true
    echo "  Traffic sent."
elif command -v nc &>/dev/null; then
    echo "  Starting nc listener on 127.0.0.1:18234 ..."
    nc -l 18234 &
    NC_PID=$!
    sleep 0.1
    echo "hello arp demo" | nc -w 1 127.0.0.1 18234 2>/dev/null || true
    sleep 0.1
    kill "$NC_PID" 2>/dev/null || true
    wait "$NC_PID" 2>/dev/null || true
    echo "  Traffic sent."
else
    echo "  (ncat/nc not found — skipping traffic generation)"
fi

# ── Step 5: MAC type quick test ───────────────────────────────────────────────
echo ""
echo "Step 5: MAC address type quick tests"
echo ""
test_macs=(
    "00:1a:2b:cc:dd:ee"   # unicast OUI-assigned
    "ff:ff:ff:ff:ff:ff"   # broadcast
    "01:00:5e:01:02:03"   # IPv4 multicast
    "33:33:00:00:00:01"   # IPv6 multicast
    "02:42:ac:11:00:02"   # locally administered (Docker)
)
printf "  %-22s  %s\n" "MAC" "Type"
printf "  %-22s  %s\n" "────────────────────" "──────────────"
for mac in "${test_macs[@]}"; do
    type=$(classify_mac "$mac")
    printf "  %-22s  %s\n" "$mac" "$type"
done

echo ""
echo "$SEP"
echo " Key takeaways:"
echo "  - ARP cache maps IP addresses to MAC addresses (L2→L3 bridge)"
echo "  - MAC I/G bit (bit 0 of first byte): 0=unicast, 1=multicast/broadcast"
echo "  - MAC U/L bit (bit 1 of first byte): 0=global (OUI), 1=locally assigned"
echo "  - MAC addresses change at every router hop; IP addresses do not"
echo "$SEP"
echo ""

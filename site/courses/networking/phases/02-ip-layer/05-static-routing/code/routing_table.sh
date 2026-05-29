# Run: sudo bash routing_table.sh
#!/usr/bin/env bash
# routing_table.sh — Demonstrate static routing using Linux network namespaces.
#
# Creates a minimal two-subnet topology:
#
#   hostA (10.0.1.2/24)  ←→  router (10.0.1.1/24 | 10.0.2.1/24)  ←→  hostB (10.0.2.2/24)
#
# Steps:
#   1. Show the host's current routing table (ip route show).
#   2. Create two network namespaces (hostA, router, hostB) with veth pairs.
#   3. Configure IP addresses and static routes.
#   4. Enable IP forwarding in the router namespace.
#   5. Test connectivity: hostA → router, hostB → router, hostA → hostB.
#   6. Show route lookup: ip route get <dst>.
#   7. Demonstrate what breaks when IP forwarding is disabled.
#   8. Clean up all namespaces and interfaces.
#
# Requires root (or sudo) for ip netns and ip link operations.

set -euo pipefail

SEP="════════════════════════════════════════════════════════"

NS_A="lab-hostA"
NS_R="lab-router"
NS_B="lab-hostB"

VETH_A="veth-la"    # hostA side
VETH_R1="veth-lr1"  # router side (A link)
VETH_B="veth-lb"    # hostB side
VETH_R2="veth-lr2"  # router side (B link)

IP_A="10.0.1.2"
IP_R1="10.0.1.1"
IP_R2="10.0.2.1"
IP_B="10.0.2.2"
PREFIX=24

PASS=0
FAIL=0

result() {
    local label="$1"
    local code="$2"
    if [ "$code" -eq 0 ]; then
        printf "  %-52s  PASS\n" "$label"
        PASS=$((PASS + 1))
    else
        printf "  %-52s  FAIL\n" "$label"
        FAIL=$((FAIL + 1))
    fi
}

cleanup() {
    for ns in "$NS_A" "$NS_R" "$NS_B"; do
        ip netns del "$ns" 2>/dev/null || true
    done
    ip link del "$VETH_A"  2>/dev/null || true
    ip link del "$VETH_B"  2>/dev/null || true
}

# Always clean up on exit
trap cleanup EXIT

# ── Step 1: Host routing table ────────────────────────────────────────────────
echo ""
echo "$SEP"
echo " Step 1: Current host routing table"
echo "$SEP"
ip route show
echo ""
echo " Explanation:"
echo "   'default via X.X.X.X dev ethN' = packets with no specific route go here"
echo "   'X.X.X.X/N dev ethN proto kernel' = directly connected subnet"

# ── Step 2: Create namespaces and veth pairs ──────────────────────────────────
echo ""
echo "$SEP"
echo " Step 2: Building topology in network namespaces"
echo "$SEP"
echo " Topology:"
echo "   ${IP_A}/24  [hostA] ---veth--- [router] ${IP_R1}/24 | ${IP_R2}/24 ---veth--- [hostB] ${IP_B}/24"
echo ""

# Clean up first in case of a previous failed run
cleanup 2>/dev/null || true

ip netns add "$NS_A"
ip netns add "$NS_R"
ip netns add "$NS_B"
echo " Created namespaces: $NS_A, $NS_R, $NS_B"

ip link add "$VETH_A" type veth peer name "$VETH_R1"
ip link set "$VETH_A"  netns "$NS_A"
ip link set "$VETH_R1" netns "$NS_R"

ip link add "$VETH_B" type veth peer name "$VETH_R2"
ip link set "$VETH_B"  netns "$NS_B"
ip link set "$VETH_R2" netns "$NS_R"
echo " Created veth pairs and moved into namespaces"

# ── Step 3: Configure addresses and routes ────────────────────────────────────
echo ""
echo "$SEP"
echo " Step 3: Configuring IP addresses and static routes"
echo "$SEP"

# hostA
ip netns exec "$NS_A" ip link set lo up
ip netns exec "$NS_A" ip link set "$VETH_A" up
ip netns exec "$NS_A" ip addr add "${IP_A}/${PREFIX}" dev "$VETH_A"
ip netns exec "$NS_A" ip route add default via "$IP_R1"
echo " hostA: $IP_A/$PREFIX, default via $IP_R1"

# router
ip netns exec "$NS_R" ip link set lo up
ip netns exec "$NS_R" ip link set "$VETH_R1" up
ip netns exec "$NS_R" ip link set "$VETH_R2" up
ip netns exec "$NS_R" ip addr add "${IP_R1}/${PREFIX}" dev "$VETH_R1"
ip netns exec "$NS_R" ip addr add "${IP_R2}/${PREFIX}" dev "$VETH_R2"
ip netns exec "$NS_R" sysctl -qw net.ipv4.ip_forward=1
echo " router: $IP_R1/$PREFIX (A side), $IP_R2/$PREFIX (B side), forwarding=ON"

# hostB
ip netns exec "$NS_B" ip link set lo up
ip netns exec "$NS_B" ip link set "$VETH_B" up
ip netns exec "$NS_B" ip addr add "${IP_B}/${PREFIX}" dev "$VETH_B"
ip netns exec "$NS_B" ip route add default via "$IP_R2"
echo " hostB: $IP_B/$PREFIX, default via $IP_R2"

# ── Step 4: Show routing tables ───────────────────────────────────────────────
echo ""
echo "$SEP"
echo " Step 4: Routing tables in each namespace"
echo "$SEP"
echo " hostA routing table:"
ip netns exec "$NS_A" ip route show | sed 's/^/   /'
echo " router routing table:"
ip netns exec "$NS_R" ip route show | sed 's/^/   /'
echo " hostB routing table:"
ip netns exec "$NS_B" ip route show | sed 's/^/   /'

# ── Step 5: Connectivity tests ────────────────────────────────────────────────
echo ""
echo "$SEP"
echo " Step 5: Connectivity tests"
echo "$SEP"

ip netns exec "$NS_A" ping -c 1 -W 2 "$IP_R1" >/dev/null 2>&1
result "hostA → router ($IP_R1)" "$?"

ip netns exec "$NS_B" ping -c 1 -W 2 "$IP_R2" >/dev/null 2>&1
result "hostB → router ($IP_R2)" "$?"

ip netns exec "$NS_A" ping -c 1 -W 2 "$IP_B"  >/dev/null 2>&1
result "hostA → hostB ($IP_B) via router" "$?"

ip netns exec "$NS_B" ping -c 1 -W 2 "$IP_A"  >/dev/null 2>&1
result "hostB → hostA ($IP_A) via router" "$?"

# ── Step 6: Route lookup ──────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo " Step 6: Route lookup (ip route get)"
echo "$SEP"
echo " hostA route to $IP_B:"
ip netns exec "$NS_A" ip route get "$IP_B" | sed 's/^/   /'
echo ""
echo " hostB route to $IP_A:"
ip netns exec "$NS_B" ip route get "$IP_A" | sed 's/^/   /'

# ── Step 7: What breaks without IP forwarding ────────────────────────────────
echo ""
echo "$SEP"
echo " Step 7: Demonstrate IP forwarding requirement"
echo "$SEP"
echo " Disabling IP forwarding in router namespace ..."
ip netns exec "$NS_R" sysctl -qw net.ipv4.ip_forward=0
echo " hostA → hostB now (should FAIL):"
ip netns exec "$NS_A" ping -c 1 -W 2 "$IP_B" >/dev/null 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "   FAILED — as expected (forwarding=0 drops cross-subnet packets)"
else
    echo "   Unexpectedly succeeded"
fi

echo ""
echo " Re-enabling IP forwarding ..."
ip netns exec "$NS_R" sysctl -qw net.ipv4.ip_forward=1
ip netns exec "$NS_A" ping -c 1 -W 2 "$IP_B" >/dev/null 2>&1
result "hostA → hostB after re-enabling forwarding" "$?"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "$SEP"
printf " Results: %d PASS / %d FAIL\n" "$PASS" "$FAIL"
echo "$SEP"
if [ "$FAIL" -eq 0 ]; then
    echo " All tests passed. Static routing is working correctly."
else
    echo " Some tests failed. Check the namespace configuration above."
fi
echo ""
echo " Cleaning up namespaces ..."
# cleanup called via trap

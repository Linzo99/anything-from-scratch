# Run: sudo bash lab_interface.sh
#!/usr/bin/env bash
# lab_interface.sh — Create a dummy0 interface, configure it, test it, then clean up.
#
# Steps:
#   1. Load the dummy kernel module.
#   2. Create dummy0 interface.
#   3. Assign 10.99.0.1/24.
#   4. Bring the interface UP.
#   5. Ping the address (verifies the interface is functional).
#   6. Show the auto-added route.
#   7. Tear down (bring DOWN and delete the interface).
#
# Requires root because ip link requires CAP_NET_ADMIN.

set -uo pipefail

IFACE="dummy0"
ADDR="10.99.0.1"
PREFIX=24
PASS=0
FAIL=0

result() {
    local label="$1"
    local ok="$2"   # 0 = success, non-zero = failure
    if [ "$ok" -eq 0 ]; then
        printf "  %-40s  PASS\n" "$label"
        PASS=$((PASS + 1))
    else
        printf "  %-40s  FAIL\n" "$label"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "======================================"
echo " Lab Interface Test (dummy0)"
echo "======================================"

# ── Step 1: Load dummy kernel module ─────────────────────────────────────────
echo ""
echo "Step 1: Load dummy kernel module"
modprobe dummy 2>/dev/null
result "modprobe dummy" "$?"

# ── Step 2: Create dummy0 ─────────────────────────────────────────────────────
echo ""
echo "Step 2: Create $IFACE interface"
# Clean up any existing interface from a previous run
ip link del "$IFACE" 2>/dev/null || true

ip link add dev "$IFACE" type dummy 2>/dev/null
RC=$?
result "ip link add $IFACE type dummy" "$RC"
if [ "$RC" -ne 0 ]; then
    echo "  ERROR: Could not create $IFACE. Are you running as root?"
    exit 1
fi

echo "  Interface state after creation:"
ip link show "$IFACE" | sed 's/^/    /'

# ── Step 3: Assign IP address ─────────────────────────────────────────────────
echo ""
echo "Step 3: Assign ${ADDR}/${PREFIX}"
ip addr add "${ADDR}/${PREFIX}" dev "$IFACE" 2>/dev/null
result "ip addr add ${ADDR}/${PREFIX} dev $IFACE" "$?"

# ── Step 4: Bring interface UP ────────────────────────────────────────────────
echo ""
echo "Step 4: Bring $IFACE UP"
ip link set "$IFACE" up 2>/dev/null
result "ip link set $IFACE up" "$?"

echo ""
echo "  Interface state after up:"
ip addr show "$IFACE" | sed 's/^/    /'

# ── Step 5: Ping the address ──────────────────────────────────────────────────
echo ""
echo "Step 5: Ping ${ADDR} (loopback via dummy0)"
ping -c 2 -W 2 "$ADDR" >/dev/null 2>&1
result "ping -c 2 ${ADDR}" "$?"

# ── Step 6: Show the auto-added route ────────────────────────────────────────
echo ""
echo "Step 6: Show auto-added route for ${ADDR%.*}.0/${PREFIX}"
echo "  Kernel automatically adds a connected route when an IP is assigned:"
echo ""
ip route show | grep "$IFACE" | sed 's/^/    /'
echo ""
ROUTE_FOUND=$(ip route show | grep -c "$IFACE" || true)
if [ "$ROUTE_FOUND" -gt 0 ]; then
    result "Route for ${ADDR%.*}.0/${PREFIX} exists" 0
else
    result "Route for ${ADDR%.*}.0/${PREFIX} exists" 1
fi

# ── Step 7: Tear down ────────────────────────────────────────────────────────
echo ""
echo "Step 7: Tear down (bring DOWN, delete interface)"
ip link set "$IFACE" down 2>/dev/null
result "ip link set $IFACE down" "$?"

ip link del "$IFACE" 2>/dev/null
result "ip link del $IFACE" "$?"

echo ""
echo "  Verify interface is gone:"
if ip link show "$IFACE" 2>&1 | grep -q "does not exist"; then
    echo "    $IFACE: does not exist (correct)"
    result "Interface deleted" 0
else
    result "Interface deleted" 1
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "======================================"
printf "  Results: %d PASS / %d FAIL\n" "$PASS" "$FAIL"
echo "======================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
else
    echo "  All steps passed!"
    exit 0
fi

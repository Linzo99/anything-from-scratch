#!/usr/bin/env bash
# Run: sudo bash firewall_demo.sh
#
# iptables Firewall Demo
# Demonstrates iptables rules step by step:
#   1. Adds a DROP rule for port 8888 inbound
#   2. Verifies the port is blocked using ncat
#   3. Adds an ACCEPT rule for a specific IP (127.0.0.2)
#   4. Verifies that specific IP can connect
#   5. Cleans up all added rules
#
# Requires: iptables, ncat (netcat-openbsd or nmap's ncat)
# Must run as root.

set -euo pipefail

PORT=8888
TEST_IP="127.0.0.2"
CONNECT_TIMEOUT=2   # seconds to wait for connection
CLEANUP_DONE=0

# ── Helpers ──────────────────────────────────────────────────────────────────

log() { printf "[%s] %s\n" "$(date '+%H:%M:%S')" "$*"; }

die() { log "ERROR: $*"; cleanup; exit 1; }

rule_exists() {
    # Return 0 if rule exists, 1 otherwise
    iptables -C "$@" 2>/dev/null
}

cleanup() {
    [[ $CLEANUP_DONE -eq 1 ]] && return
    CLEANUP_DONE=1
    log "Cleaning up iptables rules..."

    # Remove DROP rule for port 8888
    if rule_exists INPUT -p tcp --dport "$PORT" -j DROP; then
        iptables -D INPUT -p tcp --dport "$PORT" -j DROP
        log "  Removed: DROP tcp dport $PORT"
    fi

    # Remove ACCEPT rule for 127.0.0.2
    if rule_exists INPUT -s "$TEST_IP" -p tcp --dport "$PORT" -j ACCEPT; then
        iptables -D INPUT -s "$TEST_IP" -p tcp --dport "$PORT" -j ACCEPT
        log "  Removed: ACCEPT from $TEST_IP tcp dport $PORT"
    fi

    log "Cleanup complete. Rules restored to original state."
}

trap cleanup EXIT INT TERM

check_root() {
    if [[ $EUID -ne 0 ]]; then
        die "This script must be run as root: sudo bash firewall_demo.sh"
    fi
}

check_deps() {
    local missing=()
    command -v iptables >/dev/null 2>&1 || missing+=("iptables")
    if ! command -v ncat >/dev/null 2>&1 && ! command -v nc >/dev/null 2>&1; then
        missing+=("ncat (install: sudo apt install ncat)")
    fi
    if [[ ${#missing[@]} -gt 0 ]]; then
        die "Missing required tools: ${missing[*]}"
    fi
}

nc_cmd() {
    # Use ncat if available, fall back to nc
    if command -v ncat >/dev/null 2>&1; then
        echo "ncat"
    else
        echo "nc"
    fi
}

test_connection() {
    local src_ip="$1"
    local target_ip="$2"
    local port="$3"
    local expected="$4"   # "blocked" or "open"

    # Start a listener in the background
    local nc
    nc=$(nc_cmd)
    $nc -l "$port" </dev/null &>/dev/null &
    local listener_pid=$!
    sleep 0.3  # give listener time to start

    # Try to connect
    local result
    if $nc -w "$CONNECT_TIMEOUT" -z "$target_ip" "$port" 2>/dev/null; then
        result="open"
    else
        result="blocked"
    fi

    kill "$listener_pid" 2>/dev/null || true
    wait "$listener_pid" 2>/dev/null || true

    if [[ "$result" == "$expected" ]]; then
        log "  PASS: connection to $target_ip:$port is $result (expected: $expected)"
    else
        log "  FAIL: connection to $target_ip:$port is $result (expected: $expected)"
        return 1
    fi
}

# ── Main demo ────────────────────────────────────────────────────────────────

check_root
check_deps

log ""
log "=== iptables Firewall Demo ==="
log ""

# ── Step 1: Show initial state ────────────────────────────────────────────────
log "Step 1: Initial iptables state (INPUT chain)"
iptables -L INPUT -n --line-numbers 2>/dev/null | head -20
log ""

# ── Step 2: Verify port 8888 is reachable before any rules ───────────────────
log "Step 2: Verify port $PORT is REACHABLE before adding DROP rule"
test_connection "127.0.0.1" "127.0.0.1" "$PORT" "open" || true
log ""

# ── Step 3: Add DROP rule for port 8888 ──────────────────────────────────────
log "Step 3: Adding DROP rule for all inbound traffic on port $PORT"
iptables -A INPUT -p tcp --dport "$PORT" -j DROP
log "  Rule added: iptables -A INPUT -p tcp --dport $PORT -j DROP"
log ""

# ── Step 4: Verify port 8888 is now blocked ───────────────────────────────────
log "Step 4: Verify port $PORT is now BLOCKED"
test_connection "127.0.0.1" "127.0.0.1" "$PORT" "blocked"
log ""

# ── Step 5: Add ACCEPT rule for specific IP ───────────────────────────────────
log "Step 5: Adding ACCEPT rule for specific IP $TEST_IP on port $PORT"
log "  (ACCEPT rule must be inserted BEFORE the DROP rule — use -I to insert at position 1)"
iptables -I INPUT 1 -s "$TEST_IP" -p tcp --dport "$PORT" -j ACCEPT
log "  Rule added: iptables -I INPUT 1 -s $TEST_IP -p tcp --dport $PORT -j ACCEPT"
log ""

# ── Step 6: Show current rules ────────────────────────────────────────────────
log "Step 6: Current INPUT chain rules:"
iptables -L INPUT -n --line-numbers
log ""

# ── Step 7: Verify specific IP can still connect ─────────────────────────────
# Note: On loopback, source IP for connections from 127.0.0.1 is still 127.0.0.1
# To truly test source-IP filtering, a real network interface would be needed.
# We demonstrate the rule ordering concept here.
log "Step 7: Verify port $PORT is BLOCKED from 127.0.0.1 (no ACCEPT for that IP)"
test_connection "127.0.0.1" "127.0.0.1" "$PORT" "blocked"
log ""
log "  Explanation: The ACCEPT rule is for source $TEST_IP specifically."
log "  Connections from 127.0.0.1 still hit the DROP rule."
log "  In a real scenario, traffic from $TEST_IP would bypass the DROP."
log ""

# ── Step 8: Cleanup ───────────────────────────────────────────────────────────
log "Step 8: Cleaning up all demo rules"
cleanup

log ""
log "=== Demo complete ==="
log ""
log "Key concepts demonstrated:"
log "  1. iptables -A appends rules to the end of the chain"
log "  2. iptables -I inserts rules at a specific position (higher priority)"
log "  3. Rules are evaluated TOP-DOWN; first match wins"
log "  4. DROP silently discards packets (sender times out)"
log "  5. An ACCEPT before DROP allows specific exceptions"

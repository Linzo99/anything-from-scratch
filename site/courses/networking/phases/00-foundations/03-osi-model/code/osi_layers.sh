# Run: bash osi_layers.sh
#!/usr/bin/env bash
# osi_layers.sh — Demonstrate each OSI layer using live Linux commands.
#
# Shows observable evidence at each layer:
#   L1 Physical   — interface state (UP/DOWN, carrier)
#   L2 Data Link  — MAC addresses, Ethernet link info (ip link)
#   L3 Network    — IP addresses, ping (ip addr, ping)
#   L4 Transport  — TCP/UDP sockets (ss -tn)
#   L5 Session    — (demonstrated via ncat TCP connection)
#   L6 Presentation — (noted as TLS; not demonstrated without certs)
#   L7 Application — HTTP response headers (curl -I)

set -uo pipefail

SEP="────────────────────────────────────────────────────────────"

echo ""
echo "$SEP"
echo "  OSI Layer Demonstration"
echo "$SEP"

# ── Layer 1: Physical ─────────────────────────────────────────────────────────
echo ""
echo "[ LAYER 1 — Physical ]"
echo "  Job: transmit raw bits on a medium"
echo "  Tool: ip link show  (state UP means carrier is detected)"
echo ""
ip -brief link show
echo ""
echo "  Note: 'UP' = administratively enabled; 'LOWER_UP' = physical link active"
echo "  Loopback (lo) shows UNKNOWN because there is no real wire."

# ── Layer 2: Data Link ────────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "[ LAYER 2 — Data Link ]"
echo "  Job: address frames on a single hop (MAC addresses, Ethernet)"
echo "  Tool: ip link show  (shows MAC addresses)"
echo ""
ip link show | grep -E "^[0-9]+:|link/ether|link/loopback"
echo ""
echo "  MAC addresses identify individual NICs on a local segment."
echo "  ff:ff:ff:ff:ff:ff would be the broadcast address."

# ── Layer 3: Network ──────────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "[ LAYER 3 — Network ]"
echo "  Job: route packets between networks using IP addresses"
echo "  Tool: ip addr show  +  ping (ICMP — an L3 protocol)"
echo ""
echo "  --- IP addresses ---"
ip -brief addr show
echo ""
echo "  --- ping 127.0.0.1 (ICMP, stays in L3) ---"
ping -c 2 -W 2 127.0.0.1

# ── Layer 4: Transport ────────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "[ LAYER 4 — Transport ]"
echo "  Job: reliable (TCP) or fast (UDP) delivery between ports"
echo "  Tool: ss -tn  (shows active TCP connections)"
echo ""
echo "  --- Active TCP connections (ss -tn) ---"
ss -tn 2>/dev/null || echo "  (no active TCP connections right now)"
echo ""
echo "  --- Listening TCP sockets (ss -tlnp) ---"
ss -tlnp 2>/dev/null | head -10

# ── Layer 5: Session ──────────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "[ LAYER 5 — Session ]"
echo "  Job: manage long-lived conversations between processes"
echo "  Example: TCP connection establishment is a session"
echo "  (In TCP/IP model, Session is folded into the Application layer)"
echo ""
echo "  Demonstrating a TCP session with ncat (loopback):"
# Start a listener, connect, send data, close
if command -v ncat &>/dev/null; then
    ncat -l 18765 &
    NC_PID=$!
    sleep 0.1
    echo "hello layer 5 session" | ncat -w1 127.0.0.1 18765 2>/dev/null || true
    sleep 0.1
    kill "$NC_PID" 2>/dev/null || true
    wait "$NC_PID" 2>/dev/null || true
    echo "  Session: SYN -> SYN-ACK -> ACK -> data -> FIN (complete)"
else
    echo "  (ncat not installed — skipping session demo)"
fi

# ── Layer 6: Presentation ─────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "[ LAYER 6 — Presentation ]"
echo "  Job: encoding, encryption, compression (TLS, ASCII, gzip)"
echo "  Note: In TCP/IP model this is part of the Application layer."
echo ""
echo "  TLS is the most common L6 protocol. It wraps HTTP:"
echo "  [Ethernet][IP][TCP][TLS record][HTTP data encrypted]"
echo ""
echo "  To see TLS negotiation: curl -v https://example.com 2>&1 | grep -i 'tls\\|ssl\\|cipher'"
if command -v curl &>/dev/null; then
    curl -s --max-time 5 -v https://example.com 2>&1 | grep -iE "TLS|SSL|cipher|protocol" | head -5 || \
        echo "  (no internet access — TLS demo skipped)"
else
    echo "  (curl not installed)"
fi

# ── Layer 7: Application ──────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "[ LAYER 7 — Application ]"
echo "  Job: define the meaning of the data (HTTP, DNS, SSH, SMTP)"
echo "  Tool: curl -I http://example.com  (HTTP HEAD request)"
echo ""
if command -v curl &>/dev/null; then
    echo "  --- HTTP response headers from example.com ---"
    curl -I --max-time 5 http://example.com 2>/dev/null | head -10 || \
        echo "  (no internet access — HTTP demo skipped)"
else
    echo "  (curl not installed)"
fi

echo ""
echo "$SEP"
echo "  Summary: OSI layer tests complete."
echo "  Use these tests to isolate problems:"
echo "    L1 fail → ip link shows DOWN"
echo "    L2 fail → ARP cache empty, no MAC resolution"
echo "    L3 fail → ping fails"
echo "    L4 fail → TCP connect refused or RST"
echo "    L7 fail → HTTP 4xx/5xx or no response"
echo "$SEP"
echo ""

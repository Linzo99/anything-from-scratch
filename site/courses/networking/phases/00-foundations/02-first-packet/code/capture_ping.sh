# Run: sudo bash capture_ping.sh
#!/usr/bin/env bash
# capture_ping.sh — Capture a ping exchange on the loopback interface.
#
# Steps:
#   1. Start tcpdump on lo in the background, capturing to a temp file.
#   2. Send 4 ICMP echo requests to 127.0.0.1.
#   3. Stop tcpdump.
#   4. Re-read the capture with -xx (full hex dump) to show raw bytes.
#
# Requires root (or CAP_NET_RAW) because tcpdump uses raw sockets.

set -euo pipefail

PCAP=$(mktemp /tmp/ping_capture_XXXXXX.pcap)
echo "Capture file: $PCAP"
echo ""

# ── Step 1: Start tcpdump in the background ───────────────────────────────────
echo ">>> Starting tcpdump on lo (capturing ICMP) ..."
tcpdump -i lo -n -w "$PCAP" 'icmp' &
TCPDUMP_PID=$!
sleep 0.3   # give tcpdump time to open the interface

# ── Step 2: Send 4 pings ──────────────────────────────────────────────────────
echo ""
echo ">>> Sending 4 pings to 127.0.0.1 ..."
ping -c 4 127.0.0.1
echo ""

# ── Step 3: Stop tcpdump ──────────────────────────────────────────────────────
sleep 0.2
kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true
echo ">>> Capture complete."
echo ""

# ── Step 4: Show captured packets with hex dump ───────────────────────────────
echo ">>> Replaying capture with hex dump (-xx) — first 2 packets:"
echo "    Ethernet header (bytes 0-13) → IP header (bytes 14-33) → ICMP (bytes 34-41)"
echo ""
tcpdump -r "$PCAP" -n -xx -c 2

echo ""
echo ">>> Summary (human-readable, -v):"
tcpdump -r "$PCAP" -n -v

echo ""
echo "Capture saved to: $PCAP"
echo "To explore further:  sudo tcpdump -r $PCAP -n -xx"

# Run: bash protocol_map.sh
#!/usr/bin/env bash
# protocol_map.sh — Map live protocols to TCP/IP layers.
#
# Demonstrates the four TCP/IP layers by examining live system state:
#   Link layer     → ip -brief link  (Ethernet, loopback)
#   Internet layer → ip route        (IP routing)
#   Transport layer → ss -tn/-un     (TCP/UDP sockets)
#   Application layer → ss -tlnp    (processes + port numbers)
#
# Also shows where protocols such as ARP, ICMP, TCP, UDP, HTTP fit.

set -uo pipefail

SEP="══════════════════════════════════════════════════════════"

echo ""
echo "$SEP"
echo "  TCP/IP Four-Layer Model — Live Protocol Map"
echo "$SEP"
echo ""
echo "  TCP/IP Layer     OSI Equivalent   Protocols"
echo "  ─────────────────────────────────────────────────────"
echo "  Application      L5 + L6 + L7     HTTP, DNS, SSH, TLS, SMTP"
echo "  Transport        L4               TCP, UDP"
echo "  Internet         L3               IP, ICMP, OSPF, BGP"
echo "  Link             L1 + L2          Ethernet, Wi-Fi, ARP"
echo ""

# ── LINK LAYER (L1 + L2) ─────────────────────────────────────────────────────
echo "$SEP"
echo "  [LINK LAYER] — Ethernet interfaces, MAC addresses"
echo "  (ip -brief link show)"
echo ""
ip -brief link show
echo ""
echo "  Each interface above is a Link-layer entity."
echo "  Ethernet frames carry MAC addresses at this layer."
echo "  ARP resolves IP→MAC and operates here too:"
echo ""
echo "  ARP cache (ip neigh show):"
ip neigh show 2>/dev/null | head -10 || echo "  (ARP cache empty)"

# ── INTERNET LAYER (L3) ───────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "  [INTERNET LAYER] — IP routing, ICMP"
echo "  (ip route show)"
echo ""
echo "  Routing table:"
ip route show
echo ""
echo "  Each line is an IP-layer (L3) forwarding decision."
echo "  'default via X.X.X.X' = all unknown destinations go to that gateway."
echo ""
echo "  ICMP lives here — a quick Internet-layer test:"
ping -c 2 -W 2 127.0.0.1 2>/dev/null | grep -E "bytes from|packet loss" || \
    echo "  (ping failed — loopback may be down)"

# ── TRANSPORT LAYER (L4) ──────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "  [TRANSPORT LAYER] — TCP and UDP sockets"
echo "  (ss -tn  and  ss -un)"
echo ""
echo "  Active TCP connections (ss -tn):"
ss -tn 2>/dev/null | head -10 || echo "  (none)"

echo ""
echo "  Active UDP sockets (ss -un):"
ss -un 2>/dev/null | head -10 || echo "  (none)"

echo ""
echo "  Listening TCP sockets with process names (ss -tlnp):"
ss -tlnp 2>/dev/null | head -10 || echo "  (none)"

# ── APPLICATION LAYER (L5–L7) ─────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "  [APPLICATION LAYER] — Protocols that define data meaning"
echo "  (HTTP, DNS, SSH, SMTP, TLS, etc.)"
echo ""
echo "  Well-known ports in use (listening):"
ss -tlnp 2>/dev/null | awk 'NR>1 {print $4}' | \
while read -r addr_port; do
    port="${addr_port##*:}"
    case "$port" in
        22)   echo "  Port $port → SSH (Application layer)" ;;
        53)   echo "  Port $port → DNS (Application layer)" ;;
        80)   echo "  Port $port → HTTP (Application layer)" ;;
        443)  echo "  Port $port → HTTPS/TLS (Application layer)" ;;
        25)   echo "  Port $port → SMTP (Application layer)" ;;
        3306) echo "  Port $port → MySQL (Application layer)" ;;
        5432) echo "  Port $port → PostgreSQL (Application layer)" ;;
        *)    echo "  Port $port → application (unknown name)" ;;
    esac
done 2>/dev/null || echo "  (no listening ports detected)"

# ── WHERE DOES TLS FIT? ───────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "  Special case: TLS"
echo ""
echo "  OSI model calls TLS 'Layer 6 (Presentation)'."
echo "  TCP/IP model puts TLS in the Application layer."
echo ""
echo "  Without TLS: [Ethernet][IP][TCP][HTTP data]"
echo "  With    TLS: [Ethernet][IP][TCP][TLS record][HTTP data encrypted]"
echo ""
echo "  TLS wraps any application protocol: HTTP→HTTPS, SMTP→SMTPS, etc."

echo ""
echo "$SEP"
echo "  Protocol map complete."
echo "$SEP"
echo ""

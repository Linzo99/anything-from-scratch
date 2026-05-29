#!/usr/bin/env bash
# Run: bash arp_monitor.sh
#
# ARP Cache Monitor — detects MAC address changes in the ARP table.
# Polls `ip neigh` every 2 seconds for 30 seconds total.
# Prints a WARNING line when a MAC address for an existing IP changes.
#
# This simulates what an ARP spoofing detector does at the OS level,
# without requiring raw socket access or additional tools.
#
# Requires: iproute2 (ip command), Linux kernel 2.6+
# Note: Run as a normal user (no root needed for `ip neigh show`).

set -euo pipefail

DURATION=30        # seconds to run
POLL_INTERVAL=2    # seconds between polls
ALERT_COUNT=0

declare -A arp_table  # { ip => mac }

log() {
    printf "[%s] %s\n" "$(date '+%H:%M:%S')" "$*"
}

scan_arp() {
    # Parse `ip neigh show` output.
    # Example line: 192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
    while IFS= read -r line; do
        ip=""
        mac=""

        # Extract IP (first field)
        ip=$(echo "$line" | awk '{print $1}')

        # Extract lladdr (MAC)
        if echo "$line" | grep -q "lladdr"; then
            mac=$(echo "$line" | grep -oP 'lladdr \K[0-9a-f:]+')
        fi

        # Skip incomplete or missing entries
        [[ -z "$ip" || -z "$mac" ]] && continue
        # Skip broadcast and loopback-style entries
        [[ "$mac" == "ff:ff:ff:ff:ff:ff" || "$ip" == "127."* ]] && continue

        if [[ -v arp_table[$ip] ]]; then
            old_mac="${arp_table[$ip]}"
            if [[ "$old_mac" != "$mac" ]]; then
                ALERT_COUNT=$(( ALERT_COUNT + 1 ))
                log "WARNING: ARP MAC change detected!"
                log "  IP address : $ip"
                log "  OLD MAC    : $old_mac"
                log "  NEW MAC    : $mac"
                log "  Possible ARP spoofing / MITM attack!"
                arp_table[$ip]="$mac"
            fi
        else
            arp_table[$ip]="$mac"
            log "Learned   $ip  =>  $mac"
        fi
    done < <(ip neigh show 2>/dev/null)
}

# ── Main ──────────────────────────────────────────────────────────────────────

log "ARP Cache Monitor starting (running for ${DURATION}s, polling every ${POLL_INTERVAL}s)"
log "Watching for MAC address changes in the ARP cache..."
log ""

end_time=$(( $(date +%s) + DURATION ))

while (( $(date +%s) < end_time )); do
    scan_arp
    sleep "$POLL_INTERVAL"
done

log ""
log "── Summary ─────────────────────────────────────────────────"
log "  Tracked IPs : ${#arp_table[@]}"
log "  Alerts fired: $ALERT_COUNT"
if (( ALERT_COUNT == 0 )); then
    log "  No ARP anomalies detected during monitoring window."
fi
log ""
log "Final ARP cache snapshot:"
for ip in $(echo "${!arp_table[@]}" | tr ' ' '\n' | sort); do
    log "  $ip  =>  ${arp_table[$ip]}"
done

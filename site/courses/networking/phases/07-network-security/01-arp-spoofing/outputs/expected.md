# Expected Output

Running `bash arp_monitor.sh` should produce:

```
[14:22:01] ARP Cache Monitor starting (running for 30s, polling every 2s)
[14:22:01] Watching for MAC address changes in the ARP cache...

[14:22:01] Learned   192.168.1.1  =>  aa:bb:cc:dd:ee:ff
[14:22:01] Learned   192.168.1.5  =>  11:22:33:44:55:66
[14:22:03] (no changes)
[14:22:05] (no changes)
...
[14:22:31]
[14:22:31] ── Summary ─────────────────────────────────────────────────
[14:22:31]   Tracked IPs : 2
[14:22:31]   Alerts fired: 0
[14:22:31]   No ARP anomalies detected during monitoring window.

[14:22:31] Final ARP cache snapshot:
[14:22:31]   192.168.1.1  =>  aa:bb:cc:dd:ee:ff
[14:22:31]   192.168.1.5  =>  11:22:33:44:55:66
```

If a MAC address change is detected (e.g., via `arp -s` to simulate poisoning), you will see:

```
[14:22:07] WARNING: ARP MAC change detected!
[14:22:07]   IP address : 192.168.1.1
[14:22:07]   OLD MAC    : aa:bb:cc:dd:ee:ff
[14:22:07]   NEW MAC    : de:ad:be:ef:00:01
[14:22:07]   Possible ARP spoofing / MITM attack!
```

## Common issues

- **Issue**: "No tracked IPs" — ARP table is empty — **Fix**: Ping your default gateway first to populate the ARP cache: `ping -c1 $(ip route show default | awk '{print $3}')`. Then run the monitor.
- **Issue**: `ip: command not found` — **Fix**: Install `iproute2`: `sudo apt install iproute2`. On macOS, use `arp -an` instead (the script targets Linux).

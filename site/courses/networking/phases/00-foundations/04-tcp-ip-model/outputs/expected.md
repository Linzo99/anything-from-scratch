# Expected Output

Running `bash protocol_map.sh` should produce:

```
══════════════════════════════════════════════════════════
  TCP/IP Four-Layer Model — Live Protocol Map
══════════════════════════════════════════════════════════

  TCP/IP Layer     OSI Equivalent   Protocols
  ─────────────────────────────────────────────────────
  Application      L5 + L6 + L7     HTTP, DNS, SSH, TLS, SMTP
  Transport        L4               TCP, UDP
  Internet         L3               IP, ICMP, OSPF, BGP
  Link             L1 + L2          Ethernet, Wi-Fi, ARP

══════════════════════════════════════════════════════════
  [LINK LAYER] — Ethernet interfaces, MAC addresses
  (ip -brief link show)

lo               UNKNOWN        00:00:00:00:00:00
eth0             UP             aa:bb:cc:dd:ee:ff

  ARP cache (ip neigh show):
192.168.1.1 dev eth0 lladdr aa:bb:cc:00:11:22 REACHABLE

══════════════════════════════════════════════════════════
  [INTERNET LAYER] — IP routing, ICMP
  (ip route show)

  Routing table:
default via 192.168.1.1 dev eth0 proto dhcp src 192.168.1.10 metric 100
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.10

  64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.044 ms
  2 packets transmitted, 2 received, 0% packet loss

══════════════════════════════════════════════════════════
  [TRANSPORT LAYER] — TCP and UDP sockets
  (ss -tn  and  ss -un)

  Active TCP connections (ss -tn):
State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port
ESTAB   0       0       192.168.1.10:22     192.168.1.5:54321

  Listening TCP sockets with process names (ss -tlnp):
State   Recv-Q  Send-Q  Local Address:Port
LISTEN  0       128     0.0.0.0:22

══════════════════════════════════════════════════════════
  [APPLICATION LAYER] — Protocols that define data meaning

  Well-known ports in use (listening):
  Port 22 → SSH (Application layer)
```

## Common issues

- **Issue**: `ARP cache empty` → **Fix**: This is normal on a freshly booted machine. Ping your gateway (`ping -c 1 $(ip route show default | awk '{print $3}')`) to populate the cache.
- **Issue**: No TCP connections shown at Transport layer → **Fix**: Expected on a quiet machine. Open an SSH session or start `ncat -l 9999` to create an entry.
- **Issue**: No ports shown at Application layer → **Fix**: Run `sudo ss -tlnp` (root required to see process names) or note that some services require `sudo` to display.

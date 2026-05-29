# Expected Output

Running `bash arp_table.sh` should produce:

```
──────────────────────────────────────────────────────────
 MAC Address and ARP Table Inspector
──────────────────────────────────────────────────────────

Step 1: Current ARP cache (ip neigh show)

192.168.1.1 dev eth0 lladdr aa:bb:cc:00:11:22 REACHABLE
192.168.1.5 dev eth0 lladdr dd:ee:ff:44:55:66 STALE

Step 2: Classify each MAC address in the cache

  IP                    MAC                 Type
  ──────────────────    ────────────────    ────────────
  192.168.1.1           aa:bb:cc:00:11:22   UNICAST
  192.168.1.5           dd:ee:ff:44:55:66   UNICAST

Step 3: OUI lookup for default gateway MAC

  Default gateway IP: 192.168.1.1
  Gateway MAC: aa:bb:cc:00:11:22
  OUI: AA-BB-CC (first 3 bytes = manufacturer prefix)

  Known OUI prefixes:
    00-50-56  VMware
    00-15-5D  Microsoft (Hyper-V)
    08-00-27  Oracle (VirtualBox)
    DC-A6-32  Raspberry Pi Foundation
    00-1A-2B  Apple
    02-42-xx  Locally administered (Docker, etc.)

  To look up any OUI: https://maclookup.app

Step 4: Generate loopback traffic and check ARP table
  (loopback traffic does NOT create real ARP entries...)
  Starting ncat listener on 127.0.0.1:18234 ...
  Traffic sent.

Step 5: MAC address type quick tests

  MAC                    Type
  ────────────────────   ──────────────
  00:1a:2b:cc:dd:ee      UNICAST
  ff:ff:ff:ff:ff:ff      BROADCAST
  01:00:5e:01:02:03      MULTICAST
  33:33:00:00:00:01      MULTICAST
  02:42:ac:11:00:02      UNICAST

──────────────────────────────────────────────────────────
 Key takeaways:
  - ARP cache maps IP addresses to MAC addresses (L2→L3 bridge)
  - MAC I/G bit (bit 0 of first byte): 0=unicast, 1=multicast/broadcast
  ...
```

Note: `02:42:ac:11:00:02` (Docker MAC) is shown as UNICAST because bit 0 of `0x02` = `00000010` is 0 (I/G = unicast). The `1` in bit 1 is the U/L bit (locally administered), not the I/G bit.

## Common issues

- **Issue**: `Step 1: (ARP cache is empty)` → **Fix**: Normal on a freshly booted machine or a machine with no recent network activity. Ping your gateway with `ping -c 1 $(ip route show default | awk '{print $3}')` to populate it.
- **Issue**: Step 3 shows `Gateway MAC not in ARP cache` → **Fix**: The script tries to auto-populate the cache. If it still fails, your gateway may not respond to ARP (unusual). Try `arping -c 1 <gateway-ip>` if arping is installed.
- **Issue**: `classify_mac` shows wrong type for Docker MACs → **Fix**: Docker MACs (`02:42:...`) use the U/L bit (bit 1) not the I/G bit (bit 0), so they are correctly UNICAST. The U/L bit means "locally administered", not multicast.

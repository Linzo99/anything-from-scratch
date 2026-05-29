# Expected Output

Running `sudo bash capture_ping.sh` should produce:

```
Capture file: /tmp/ping_capture_ABC123.pcap

>>> Starting tcpdump on lo (capturing ICMP) ...

>>> Sending 4 pings to 127.0.0.1 ...
PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.052 ms
64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.044 ms
64 bytes from 127.0.0.1: icmp_seq=3 ttl=64 time=0.039 ms
64 bytes from 127.0.0.1: icmp_seq=4 ttl=64 time=0.041 ms

--- 127.0.0.1 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3076ms
rtt min/avg/max/mdev = 0.039/0.044/0.052/0.005 ms

>>> Capture complete.

>>> Replaying capture with hex dump (-xx) — first 2 packets:
    Ethernet header (bytes 0-13) → IP header (bytes 14-33) → ICMP (bytes 34-41)

reading from file /tmp/ping_capture_ABC123.pcap, link-type EN10MB (Ethernet)
14:23:01.123456 IP 127.0.0.1 > 127.0.0.1: ICMP echo request, id 3, seq 1, length 64
        0x0000:  0000 0000 0000 0000 0000 0000 0800 4500   ..............E.
        0x0010:  0054 1234 4000 4001 f7c6 7f00 0001 7f00   .T.4@.@.........
        0x0020:  0001 0800 f6d3 0003 0001 dc44 7267 0000   ...........Drg..
        0x0030:  0000 ad08 0b00 0000 0000 1011 1213 1415   ................
        0x0040:  1617 1819 1a1b 1c1d 1e1f 2021 2223 2425   ...........!"#$%
        0x0050:  2627 2829 2a2b 2c2d 2e2f 3031 3233 3435   &'()*+,-./012345
        0x0060:  3637                                       67
14:23:01.123478 IP 127.0.0.1 > 127.0.0.1: ICMP echo reply, id 3, seq 1, length 64
        0x0000:  0000 0000 0000 0000 0000 0000 0800 4500   ..............E.
        ...
```

Key fields to identify in the hex dump:
- Bytes `0x0000–0x000D`: Ethernet header — dst MAC `00:00:00:00:00:00`, src MAC `00:00:00:00:00:00`, EtherType `0800` (IPv4)
- Byte `0x000E`: `45` = IPv4 version 4, IHL 5 (20-byte header)
- Bytes `0x0016`: `40` = TTL 64
- Byte `0x0017`: `01` = Protocol ICMP
- Bytes `0x001A–0x001D`: Source IP `7f000001` = 127.0.0.1
- Byte `0x0022`: `08` = ICMP Type 8 (echo request); in the reply packet this is `00`

## Common issues

- **Issue**: `tcpdump: Operation not permitted` → **Fix**: Run with `sudo` — raw socket capture requires root or `CAP_NET_RAW`.
- **Issue**: `0 packets captured` → **Fix**: Increase the `sleep 0.3` delay after starting tcpdump; on slow systems tcpdump may not have opened the interface before ping runs.
- **Issue**: `ping: connect: Network is unreachable` → **Fix**: The loopback interface is down. Run `sudo ip link set lo up` to restore it.

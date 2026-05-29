# Expected Output

Running `python3 parse_frame.py` (built-in ARP broadcast example) should produce:

```
Parsing built-in ARP request example

  (pass your own hex string as an argument to parse a different frame)

==============================================================
  Ethernet II Frame Parser
==============================================================
  Frame size: 42 bytes  (header=14 B, payload=28 B)

  Offset      Field                 Value                   Description
  ──────────────────────────────────────────────────────────
  0–5         Destination MAC       ff:ff:ff:ff:ff:ff       [BROADCAST]
  6–11        Source MAC            aa:bb:cc:dd:ee:ff       [UNICAST]
  12–13       EtherType             0x0806                  ARP
  14+         Payload               28 bytes                see decoded payload below

  Raw hex dump:
    0x0000:  ff ff ff ff ff ff aa bb cc dd ee ff 08 06 00 01  ................
    0x0010:  08 00 06 04 00 01 aa bb cc dd ee ff c0 a8 01 32  ...............2
    0x0020:  00 00 00 00 00 00 c0 a8 01 01                    ..........

  Decoded payload (EtherType = 0x0806):
  ARP Packet:
    hw_type              0x0001 (Ethernet)
    proto_type           0x0800 (IPv4)
    hw_len               6
    proto_len            4
    operation            1 (REQUEST)
    sender_mac           aa:bb:cc:dd:ee:ff
    sender_ip            192.168.1.50
    target_mac           00:00:00:00:00:00
    target_ip            192.168.1.1

==============================================================
```

To parse an IPv4 frame from a tcpdump hex dump:
```
python3 parse_frame.py "0000000000000000000000000800450000540000400040011234 7f0000017f000001..."
```

## Common issues

- **Issue**: `ERROR: Frame too short` → **Fix**: The hex string is less than 14 bytes. An Ethernet header is always exactly 14 bytes (6+6+2).
- **Issue**: `ERROR: Invalid hex string` → **Fix**: The hex string contains non-hex characters. Spaces and colons are stripped automatically, but other characters (like `0x` prefixes) are not. Remove them manually.
- **Issue**: Payload shows `(payload decoding not implemented)` → **Fix**: The script decodes ARP (0x0806) and IPv4 (0x0800) payloads. For other EtherTypes it shows the raw hex — extend `parse_ethernet_frame()` to add more decoders.

# Expected Output

Running `python3 parse_ip_header.py` (built-in TCP example) should produce:

```
Parsing built-in example:
  Src=10.0.0.1  Dst=93.184.216.34  Protocol=TCP  TTL=128  DF=1

================================================================
  IPv4 Header Parser
================================================================
  Raw bytes (first 20): 450000 3c1234 4000 80 06 0000 0a000001 5db8d822

  Offset  Size       Field                           Value             Description
  ────────────────────────────────────────────────────────────────────────────────
  0       4 bits     Version                         4                 IPv4
  0       4 bits     IHL (Internet Header Length)    5                 5 × 4 = 20 bytes (standard, no options)
  1       6 bits     DSCP                            0x00 (0)          CS0/BE (Best Effort)
  1       2 bits     ECN                             0                 00=non-ECT, 01/10=ECT capable, 11=congestion
  2–3     2 bytes    Total Length                    60                IP header (20 B) + payload (40 B)
  4–5     2 bytes    Identification                  0x1234 (4660)     Fragment group ID — all fragments of same datagram share this value
  6       1 bit      Reserved flag                   0                 Must be 0
  6       1 bit      DF (Don't Fragment)             1                 1 = drop packet if too big instead of fragmenting
  6       1 bit      MF (More Fragments)             0                 1 = more fragments follow; 0 = this is the last fragment
  6–7     13 bits    Fragment Offset                 0                 0 × 8 = 0 bytes from start of original datagram
  8       1 byte     TTL (Time to Live)              128               Hops remaining; 64/128 are common starting values
  9       1 byte     Protocol                        6                 TCP   (Transmission Control Protocol)
  10–11   2 bytes    Header Checksum                 0x0000            INVALID — header may be corrupted
  12–15   4 bytes    Source IP                       10.0.0.1          Sender's IP address
  16–19   4 bytes    Destination IP                  93.184.216.34     Intended recipient's IP address

  Flags+FragOffset word (bytes 6–7): 0x4000  = 0100000000000000
    Bit 15 (reserved):  0
    Bit 14 (DF):        1
    Bit 13 (MF):        0
    Bits 12–0 (offset): 0

  Options: none (IHL = 5, standard 20-byte header)

  Payload starts at byte 20 (length = 40 bytes)
================================================================
```

Note: The checksum shows `INVALID` in the built-in example because it was set to `0x0000` for simplicity. A real captured packet will show `VALID`. To parse a real packet hex from tcpdump, copy the bytes after the 14-byte Ethernet header and run:

```
python3 parse_ip_header.py "45000054..."
```

## Common issues

- **Issue**: `Checksum: INVALID` → **Fix**: This is expected for the built-in static example (checksum field is 0). Real packets from tcpdump captures will have valid checksums. Note that some NICs offload checksum computation, so captures on the sender may show `0x0000` even for real traffic.
- **Issue**: `ERROR: Need at least 20 bytes` → **Fix**: The hex string must be at least 40 hex characters (20 bytes). If you copied from a tcpdump hex dump, make sure you removed the Ethernet header (first 14 bytes = 28 hex chars).
- **Issue**: `IHL = 6` or higher → **Fix**: This indicates IP options are present. The script shows them as raw hex under "Options". The payload starts at byte `IHL × 4`, not byte 20.

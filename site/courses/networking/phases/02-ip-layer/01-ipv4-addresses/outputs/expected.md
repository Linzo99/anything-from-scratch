# Expected Output

Running `python3 ip_binary.py 192.168.1.77/24` should produce:

```
======================================================
  IPv4 Address Analysis: 192.168.1.77/24
======================================================

  Representations:
    Dotted-decimal : 192.168.1.77
    Binary (dotted): 11000000.10101000.00000001.01001101
    Hexadecimal    : 0xC0A8014D
    Integer        : 3,232,235,853

  Octet breakdown:
    Octet 1: 192  →  11000000  (positional: 128+64+32+16+8+4+2+1)
    Octet 2: 168  →  10101000  (positional: 128+64+32+16+8+4+2+1)
    Octet 3:   1  →  00000001  (positional: 128+64+32+16+8+4+2+1)
    Octet 4:  77  →  01001101  (positional: 128+64+32+16+8+4+2+1)

  Classification:
    Class   : C  (192–223, /24 default)
    Special : Private (RFC 1918) — not routed on public internet

  Subnet information (/24):
    Mask (dotted)  : 255.255.255.0
    Mask (binary)  : 11111111.11111111.11111111.00000000
    Network addr   : 192.168.1.0
    Broadcast addr : 192.168.1.255
    First host     : 192.168.1.1
    Last host      : 192.168.1.254
    Usable hosts   : 254

  Network address derivation (bitwise AND):
    Address  : 11000000.10101000.00000001.01001101
    Mask     : 11111111.11111111.11111111.00000000
    AND      : 11000000.10101000.00000001.00000000  →  192.168.1.0
    (mask bits that are 1 preserve the address bits;
     mask bits that are 0 zero out the host bits)
======================================================
```

Other useful examples:
```
python3 ip_binary.py 10.0.0.1 /8        # Class A private range
python3 ip_binary.py 8.8.8.8            # Public DNS — no special range
python3 ip_binary.py 127.0.0.1          # Loopback
python3 ip_binary.py 172.16.50.1/20     # RFC 1918 Class B private
python3 ip_binary.py 255.255.255.255    # Limited broadcast
```

## Common issues

- **Issue**: `ValueError: Expected 4 octets` → **Fix**: Pass a full dotted-decimal IPv4 address. IPv6 addresses and hostnames are not supported.
- **Issue**: `Error: prefix must be 0–32` → **Fix**: Subnet prefix lengths are 0–32. `/33` and above are invalid for IPv4.
- **Issue**: `Usable hosts: 0` for `/32` → **Fix**: A `/32` has exactly 1 address — the host itself. It is not assignable as a subnet with separate network and broadcast addresses. Use `/31` (RFC 3021 point-to-point links) or larger for subnets.

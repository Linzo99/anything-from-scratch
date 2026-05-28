# Decode IPv4 Addresses

> Every website you visit, every file you download, every ping — they all start with a 32-bit number that almost nobody reads in binary. You're about to.

**Type:** Learn
**Languages:** Python
**Prerequisites:** Phase 1, Lesson 01 — How Data Moves Across a Network
**Time:** ~35 minutes

## Learning Objectives
- Convert a dotted-decimal IPv4 address to its 32-bit binary representation
- Identify the historical class (A, B, C, D, E) of any address from its first octet
- Separate the network portion from the host portion given a prefix length
- Explain why address classes became obsolete and what replaced them
- Write a Python script that performs all of the above automatically

## The Problem

You type `curl https://example.com` and packets fly across the planet. Somewhere in that journey every router looks at a destination address and decides: "Is this for my network, or do I forward it?" That decision is made by comparing bit patterns — not domain names, not hostnames, but raw binary numbers.

If you treat IP addresses as opaque labels ("192.168.1.1 is my router, done"), you will never understand why `192.168.0.255` cannot be assigned to a host, why two machines on different subnets cannot talk without a router even if they are plugged into the same switch, or why your VPN assigns you a `10.x.x.x` address instead of a real internet address.

This lesson tears the address apart, octet by octet and bit by bit, so those later concepts click immediately.

## The Concept

### An IPv4 address is just a 32-bit integer

A 32-bit integer can hold values from 0 to 4,294,967,295. That is exactly how many unique IPv4 addresses exist — about 4.3 billion. We write them in **dotted-decimal** notation purely for human readability:

```
192      .   168      .     1     .     1
11000000 . 10101000 . 00000001 . 00000001
```

Each group of 8 bits is called an **octet** (not a "byte" in this context — octet emphasises the exact size). Each octet ranges from 0 to 255.

Converting decimal to binary: divide by 2 repeatedly and read remainders from bottom to top. Or memorise the positional values:

```
Bit position:  7    6    5    4    3    2    1    0
Value:        128   64   32   16    8    4    2    1

Example: 192 = 128 + 64 = 11000000
Example: 168 = 128 + 32 + 8 = 10101000
Example:  10 = 8 + 2       = 00001010
```

### Address Classes (historical, but every textbook mentions them)

Before CIDR (1993), the entire address space was divided into fixed classes based solely on the first few bits of the first octet:

```
First octet    First bits    Class    Default prefix    Network/Host split
0   – 127      0xxxxxxx      A        /8               8 net  + 24 host bits
128 – 191      10xxxxxx      B        /16              16 net + 16 host bits
192 – 223      110xxxxx      C        /24              24 net +  8 host bits
224 – 239      1110xxxx      D        Multicast        (no host bits)
240 – 255      1111xxxx      E        Reserved         (experimental)
```

A single Class A network (say `10.0.0.0/8`) has 2^24 − 2 = 16,777,214 usable host addresses. A single company cannot use all of those efficiently. Address classes caused enormous waste: if you needed 300 hosts you had to get a full Class B (/16, ~65,000 addresses), wasting 99.5% of the allocation.

### CIDR replaced classes

**Classless Inter-Domain Routing (CIDR)** lets you express *any* prefix length with a `/N` suffix. The network portion is the first N bits; the host portion is the remaining 32 − N bits.

```
Address:   192.168.1.0/26

Binary:    11000000.10101000.00000001.00xxxxxx
                                      ^^
Network:   11000000.10101000.00000001.00  (26 bits fixed)
Host:                                  xxxxxx  (6 bits variable)

Usable hosts: 2^6 - 2 = 62
```

We subtract 2 because:
- The all-zeros host part is the **network address** (identifies the subnet itself).
- The all-ones host part is the **broadcast address** (sends to every host on the subnet).

### The subnet mask

A subnet mask is the same information as a prefix length, written as a 32-bit number where the first N bits are 1 and the rest are 0:

```
/24  →  11111111.11111111.11111111.00000000  →  255.255.255.0
/26  →  11111111.11111111.11111111.11000000  →  255.255.255.192
/16  →  11111111.11111111.00000000.00000000  →  255.255.0.0
```

To extract the network address, bitwise-AND the IP address with the subnet mask:

```
IP:     192.168.1.77  =  11000000.10101000.00000001.01001101
Mask:   255.255.255.0  =  11111111.11111111.11111111.00000000
AND:                      11000000.10101000.00000001.00000000
                       =  192.168.1.0   ← network address
```

### Special address ranges (memorise these)

```
10.0.0.0/8            Private (RFC 1918) — not routed on the public internet
172.16.0.0/12         Private (RFC 1918)
192.168.0.0/16        Private (RFC 1918)
127.0.0.0/8           Loopback — stays on the local machine
169.254.0.0/16        Link-local / APIPA — autoconfigured when DHCP fails
0.0.0.0/0             Default route — matches everything
255.255.255.255/32    Limited broadcast
```

## Build It

Create a file called `ipv4_decode.py`. We will build it function by function.

```python
#!/usr/bin/env python3
"""
ipv4_decode.py — decode and annotate an IPv4 address.

Usage:
    python3 ipv4_decode.py 192.168.1.77
    python3 ipv4_decode.py 10.0.0.1 /8
"""

import sys


def ip_to_int(address: str) -> int:
    """Convert a dotted-decimal address string to a 32-bit integer.

    We split on dots, convert each part to an integer, then pack them
    into a single 32-bit value by shifting each octet into position.

    Example: "192.168.1.1"
        192 << 24  =  0xC0000000
        168 << 16  =  0x00A80000
          1 <<  8  =  0x00000100
          1 <<  0  =  0x00000001
    Total          =  0xC0A80101  =  3232235777
    """
    parts = address.split(".")
    if len(parts) != 4:
        raise ValueError(f"Expected 4 octets, got {len(parts)}: {address!r}")
    result = 0
    for part in parts:
        value = int(part)
        if not 0 <= value <= 255:
            raise ValueError(f"Octet out of range 0-255: {value}")
        result = (result << 8) | value  # shift existing bits left, OR in new octet
    return result


def int_to_ip(n: int) -> str:
    """Convert a 32-bit integer back to dotted-decimal notation.

    We extract each octet with a bitmask and right-shift.
    """
    if not 0 <= n <= 0xFFFFFFFF:
        raise ValueError(f"Value {n} out of 32-bit range")
    return ".".join([
        str((n >> 24) & 0xFF),  # most-significant octet
        str((n >> 16) & 0xFF),
        str((n >>  8) & 0xFF),
        str( n        & 0xFF),  # least-significant octet
    ])


def ip_to_binary(address: str) -> str:
    """Return the dotted-binary string, e.g. '11000000.10101000.00000001.00000001'."""
    n = ip_to_int(address)
    # Format as 32-bit binary, zero-padded, then insert dots every 8 characters
    bits = format(n, "032b")
    return ".".join(bits[i:i+8] for i in range(0, 32, 8))


def classify(address: str) -> str:
    """Return the historical address class based on the leading bits of the first octet."""
    first_octet = int(address.split(".")[0])
    if first_octet < 128:       # 0xxxxxxx
        return "A"
    elif first_octet < 192:     # 10xxxxxx
        return "B"
    elif first_octet < 224:     # 110xxxxx
        return "C"
    elif first_octet < 240:     # 1110xxxx
        return "D (Multicast)"
    else:                       # 1111xxxx
        return "E (Reserved)"


def prefix_to_mask(prefix: int) -> int:
    """Convert a prefix length (0-32) to a 32-bit subnet mask integer.

    A /24 mask has the top 24 bits set: 0xFFFFFF00.
    We build this with a left-shift and subtraction trick:
        (1 << 32) - (1 << (32 - prefix))
    For /24: 0x100000000 - 0x100 = 0xFFFFFF00
    """
    if not 0 <= prefix <= 32:
        raise ValueError(f"Prefix must be 0-32, got {prefix}")
    if prefix == 0:
        return 0
    if prefix == 32:
        return 0xFFFFFFFF
    return ((1 << 32) - (1 << (32 - prefix))) & 0xFFFFFFFF


def network_info(address: str, prefix: int) -> dict:
    """Compute network address, broadcast, host range, and usable count."""
    ip_int = ip_to_int(address)
    mask_int = prefix_to_mask(prefix)

    network_int = ip_int & mask_int                 # zero out host bits
    broadcast_int = network_int | (~mask_int & 0xFFFFFFFF)  # set all host bits
    host_min = network_int + 1
    host_max = broadcast_int - 1
    usable = max(0, (broadcast_int - network_int) - 1)

    return {
        "network":   int_to_ip(network_int),
        "broadcast": int_to_ip(broadcast_int),
        "host_min":  int_to_ip(host_min),
        "host_max":  int_to_ip(host_max),
        "usable":    usable,
        "mask":      int_to_ip(mask_int),
    }


def is_special(address: str) -> str | None:
    """Return a description if the address falls in a well-known special range."""
    n = ip_to_int(address)
    # Each entry: (network_int, mask_int, description)
    special_ranges = [
        ("10.0.0.0",      8,  "Private (RFC 1918)"),
        ("172.16.0.0",   12,  "Private (RFC 1918)"),
        ("192.168.0.0",  16,  "Private (RFC 1918)"),
        ("127.0.0.0",     8,  "Loopback"),
        ("169.254.0.0",  16,  "Link-local / APIPA"),
        ("224.0.0.0",     4,  "Multicast (D)"),
        ("240.0.0.0",     4,  "Reserved (E)"),
        ("0.0.0.0",       8,  "This network (source only)"),
        ("255.255.255.255", 32, "Limited broadcast"),
    ]
    for base_str, prefix, description in special_ranges:
        mask = prefix_to_mask(prefix)
        base = ip_to_int(base_str)
        if (n & mask) == (base & mask):
            return description
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ipv4_decode.py <address> [/<prefix>]")
        sys.exit(1)

    # Parse address and optional prefix
    raw = sys.argv[1]
    if "/" in raw:
        address, prefix_str = raw.split("/", 1)
        prefix = int(prefix_str)
    elif len(sys.argv) >= 3 and sys.argv[2].startswith("/"):
        address = raw
        prefix = int(sys.argv[2][1:])
    else:
        address = raw
        prefix = None  # will infer from class

    # Validate address
    ip_to_int(address)  # raises on malformed input

    cls = classify(address)
    special = is_special(address)

    print(f"\n{'='*50}")
    print(f"  Address:  {address}")
    print(f"  Binary:   {ip_to_binary(address)}")
    print(f"  Class:    {cls}")
    if special:
        print(f"  Special:  {special}")

    # Infer default prefix from class if not given
    if prefix is None:
        inferred = {"A": 8, "B": 16, "C": 24}.get(cls[0], 24)
        print(f"  (No prefix given — using classful default /{inferred})")
        prefix = inferred

    info = network_info(address, prefix)
    print(f"\n  Prefix:      /{prefix}")
    print(f"  Mask:        {info['mask']}")
    print(f"  Network:     {info['network']}")
    print(f"  Broadcast:   {info['broadcast']}")
    print(f"  Host range:  {info['host_min']} – {info['host_max']}")
    print(f"  Usable:      {info['usable']:,} addresses")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
```

Run it:

```bash
python3 ipv4_decode.py 192.168.1.77 /24
python3 ipv4_decode.py 10.0.0.1 /8
python3 ipv4_decode.py 172.31.200.5 /20
python3 ipv4_decode.py 8.8.8.8 /32
```

Expected output for `192.168.1.77 /24`:

```
==================================================
  Address:  192.168.1.77
  Binary:   11000000.10101000.00000001.01001101
  Class:    C
  Special:  Private (RFC 1918)

  Prefix:      /24
  Mask:        255.255.255.0
  Network:     192.168.1.0
  Broadcast:   192.168.1.255
  Host range:  192.168.1.1 – 192.168.1.254
  Usable:      254 addresses
==================================================
```

### Understanding the bitwise AND operation

The most important operation in all of IP networking is the bitwise AND between an address and a mask. Let's trace it manually for our example:

```
Address:  192.168.1.77
Mask:     255.255.255.0

Octet by octet:
  192 & 255 = 192    (11000000 & 11111111 = 11000000)
  168 & 255 = 168    (10101000 & 11111111 = 10101000)
    1 & 255 =   1    (00000001 & 11111111 = 00000001)
   77 &   0 =   0    (01001101 & 00000000 = 00000000)

Result: 192.168.1.0  ← this is the network address
```

The mask acts as a filter: bits where the mask is 1 are preserved (network bits); bits where the mask is 0 are zeroed (host bits cleared to give the network address).

## Exercises

1. **Verify by hand.** Take `172.20.45.130 /20`. Without running the script, calculate the network address, broadcast address, and number of usable hosts. Then run the script to check.

2. **All prefix lengths.** Modify the script to print a table showing the mask, number of hosts, and network address for every prefix length from /16 to /32 applied to `10.0.0.0`.

3. **Reverse lookup.** Write a function `is_same_network(ip1, ip2, prefix)` that returns `True` if both addresses are in the same network. Test with `192.168.1.5`, `192.168.1.200`, prefix `/24` (same) and `192.168.1.5`, `192.168.2.5`, prefix `/24` (different).

4. **Edge cases.** What does the script do with `0.0.0.0`, `255.255.255.255`, and `127.0.0.1`? Does the special-range detection work? Fix any issues you find.

5. **CIDR notation parser.** Write a function that accepts a CIDR string like `"10.0.0.0/8"` and returns a Python dictionary with all the fields the `network_info` function returns, plus the binary representation.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Octet | "Byte of an IP address" | Exactly 8 bits; same size as a byte but the name stresses the exact bit count |
| Dotted-decimal | "The normal IP format" | A human-readable representation of a 32-bit integer split into four 8-bit groups separated by dots |
| Prefix length | "The slash number" | The number of leading bits that identify the network; the remaining bits identify the host |
| Subnet mask | "The 255.255.255.0 thing" | The same information as a prefix length but written as a 32-bit number (1s in network positions, 0s in host positions) |
| Network address | "The base address" | The IP address with all host bits set to zero; identifies the subnet itself, not assignable to a host |
| Broadcast address | "The .255 address" | The IP address with all host bits set to one; a packet sent here is delivered to every host on the subnet |
| CIDR | "Classless" | Classless Inter-Domain Routing — the modern system where prefix length can be any value 0–32, replacing fixed class boundaries |
| Address class | "Class A/B/C" | A historical fixed-width scheme for splitting the address space; obsolete since 1993 but still mentioned everywhere |

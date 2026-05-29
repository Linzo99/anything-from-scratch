# Run: python3 ip_binary.py 192.168.1.77
#!/usr/bin/env python3
"""
ip_binary.py — Convert any IPv4 address to dotted-decimal, binary, and hex.

Shows all three representations side by side, plus:
  - Historical address class (A/B/C/D/E)
  - Special range detection (RFC 1918, loopback, link-local, etc.)
  - Subnet info when a prefix length is supplied (e.g. 192.168.1.0/24)
  - Bitwise AND of address with mask to derive network address

No third-party libraries. Python 3.8+ stdlib only.

Usage:
    python3 ip_binary.py 192.168.1.77
    python3 ip_binary.py 192.168.1.77/24
    python3 ip_binary.py 10.0.0.1 /8
    python3 ip_binary.py 8.8.8.8
"""

import sys


# ── Conversion helpers ────────────────────────────────────────────────────────

def ip_to_int(addr: str) -> int:
    """Convert 'A.B.C.D' → 32-bit integer."""
    parts = addr.strip().split(".")
    if len(parts) != 4:
        raise ValueError(f"Expected 4 octets, got {len(parts)}: {addr!r}")
    result = 0
    for part in parts:
        v = int(part)
        if not 0 <= v <= 255:
            raise ValueError(f"Octet out of range (0–255): {v}")
        result = (result << 8) | v
    return result


def int_to_ip(n: int) -> str:
    """Convert 32-bit integer → 'A.B.C.D'."""
    return ".".join([
        str((n >> 24) & 0xFF),
        str((n >> 16) & 0xFF),
        str((n >>  8) & 0xFF),
        str( n        & 0xFF),
    ])


def ip_to_binary_dotted(addr: str) -> str:
    """Return dotted-binary like '11000000.10101000.00000001.01001101'."""
    n = ip_to_int(addr)
    bits = format(n, "032b")
    return ".".join(bits[i:i+8] for i in range(0, 32, 8))


def ip_to_hex(addr: str) -> str:
    """Return '0xC0A8014D' style hex for the address."""
    return f"0x{ip_to_int(addr):08X}"


def prefix_to_mask(prefix: int) -> int:
    """Convert prefix length 0–32 → 32-bit mask integer."""
    if prefix == 0:
        return 0
    if prefix == 32:
        return 0xFFFFFFFF
    return ((1 << 32) - (1 << (32 - prefix))) & 0xFFFFFFFF


# ── Classification ────────────────────────────────────────────────────────────

def address_class(addr: str) -> str:
    """Return historical class (A/B/C/D/E) based on first octet."""
    first = int(addr.split(".")[0])
    if first < 128:   return "A  (0–127,  /8 default)"
    if first < 192:   return "B  (128–191, /16 default)"
    if first < 224:   return "C  (192–223, /24 default)"
    if first < 240:   return "D  (224–239, multicast)"
    return              "E  (240–255, reserved/experimental)"


SPECIAL_RANGES = [
    ("10.0.0.0",     8,  "Private (RFC 1918) — not routed on public internet"),
    ("172.16.0.0",  12,  "Private (RFC 1918) — not routed on public internet"),
    ("192.168.0.0", 16,  "Private (RFC 1918) — not routed on public internet"),
    ("127.0.0.0",    8,  "Loopback — stays on the local machine"),
    ("169.254.0.0", 16,  "Link-local / APIPA — autoconfigured when DHCP fails"),
    ("224.0.0.0",    4,  "Multicast (Class D)"),
    ("240.0.0.0",    4,  "Reserved (Class E / experimental)"),
    ("0.0.0.0",      8,  "This network (source-only)"),
    ("255.255.255.255", 32, "Limited broadcast"),
]


def special_range(addr: str) -> str:
    """Return a description if addr falls in a well-known special range."""
    n = ip_to_int(addr)
    for base_str, prefix, desc in SPECIAL_RANGES:
        mask = prefix_to_mask(prefix)
        base = ip_to_int(base_str)
        if (n & mask) == (base & mask):
            return desc
    return ""


# ── Subnet info ───────────────────────────────────────────────────────────────

def subnet_info(addr: str, prefix: int) -> dict:
    """Compute network, broadcast, host range, usable count."""
    ip_int   = ip_to_int(addr)
    mask_int = prefix_to_mask(prefix)
    net_int  = ip_int & mask_int
    bcast    = net_int | (~mask_int & 0xFFFFFFFF)
    usable   = max(0, (bcast - net_int) - 1)
    return {
        "mask":       int_to_ip(mask_int),
        "mask_bin":   ip_to_binary_dotted(int_to_ip(mask_int)),
        "network":    int_to_ip(net_int),
        "broadcast":  int_to_ip(bcast),
        "host_first": int_to_ip(net_int + 1) if usable > 0 else "N/A",
        "host_last":  int_to_ip(bcast - 1)   if usable > 0 else "N/A",
        "usable":     usable,
        "and_demo": {
            "addr_bin": ip_to_binary_dotted(addr),
            "mask_bin": ip_to_binary_dotted(int_to_ip(mask_int)),
            "net_bin":  ip_to_binary_dotted(int_to_ip(net_int)),
        },
    }


# ── Display ───────────────────────────────────────────────────────────────────

def display(addr: str, prefix: int | None) -> None:
    W = 54  # divider width
    print()
    print("=" * W)
    print(f"  IPv4 Address Analysis: {addr}"
          + (f"/{prefix}" if prefix is not None else ""))
    print("=" * W)

    # Representations
    dotted  = addr
    binary  = ip_to_binary_dotted(addr)
    hexval  = ip_to_hex(addr)
    integer = ip_to_int(addr)

    print(f"\n  Representations:")
    print(f"    Dotted-decimal : {dotted}")
    print(f"    Binary (dotted): {binary}")
    print(f"    Hexadecimal    : {hexval}")
    print(f"    Integer        : {integer:,}")

    # Octet breakdown
    print(f"\n  Octet breakdown:")
    parts = dotted.split(".")
    for i, p in enumerate(parts):
        v = int(p)
        print(f"    Octet {i+1}: {p:>3}  →  {format(v, '08b')}  "
              f"(positional: 128+64+32+16+8+4+2+1)")

    # Classification
    print(f"\n  Classification:")
    print(f"    Class   : {address_class(addr)}")
    sp = special_range(addr)
    if sp:
        print(f"    Special : {sp}")
    else:
        print(f"    Special : (none — publicly routable)")

    # Subnet info
    if prefix is not None:
        print(f"\n  Subnet information (/{prefix}):")
        info = subnet_info(addr, prefix)
        print(f"    Mask (dotted)  : {info['mask']}")
        print(f"    Mask (binary)  : {info['mask_bin']}")
        print(f"    Network addr   : {info['network']}")
        print(f"    Broadcast addr : {info['broadcast']}")
        print(f"    First host     : {info['host_first']}")
        print(f"    Last host      : {info['host_last']}")
        print(f"    Usable hosts   : {info['usable']:,}")

        d = info["and_demo"]
        print(f"\n  Network address derivation (bitwise AND):")
        print(f"    Address  : {d['addr_bin']}")
        print(f"    Mask     : {d['mask_bin']}")
        print(f"    AND      : {d['net_bin']}  →  {info['network']}")
        print(f"    (mask bits that are 1 preserve the address bits;")
        print(f"     mask bits that are 0 zero out the host bits)")
    else:
        first = int(addr.split(".")[0])
        inferred = {"A": 8, "B": 16, "C": 24}.get(address_class(addr)[0], 24)
        print(f"\n  (No prefix given — use /<N> for subnet details)")
        print(f"    Classful default would be /{inferred}")

    print("=" * W)
    print()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 ip_binary.py <address>[/<prefix>]")
        print("Examples:")
        print("  python3 ip_binary.py 192.168.1.77")
        print("  python3 ip_binary.py 192.168.1.77/24")
        print("  python3 ip_binary.py 10.0.0.1 /8")
        sys.exit(0)

    raw = sys.argv[1]
    prefix: int | None = None

    if "/" in raw:
        addr_part, prefix_str = raw.split("/", 1)
        prefix = int(prefix_str)
    elif len(sys.argv) >= 3 and sys.argv[2].startswith("/"):
        addr_part = raw
        prefix = int(sys.argv[2][1:])
    else:
        addr_part = raw

    # Validate
    try:
        ip_to_int(addr_part)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if prefix is not None and not 0 <= prefix <= 32:
        print(f"Error: prefix must be 0–32, got {prefix}")
        sys.exit(1)

    display(addr_part, prefix)


if __name__ == "__main__":
    main()

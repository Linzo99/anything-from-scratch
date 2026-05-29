# Run: python3 subnet_calc.py 192.168.1.0/24
#!/usr/bin/env python3
"""
subnet_calc.py — CIDR subnet calculator.

Given an IP/prefix, prints:
  - Network address
  - Broadcast address
  - First usable host
  - Last usable host
  - Total addresses and usable hosts
  - Subnet mask in dotted-decimal and binary
  - Optionally splits the block into N equal subnets (--split N)

No third-party libraries. Python 3.8+ stdlib only.

Usage:
    python3 subnet_calc.py 192.168.1.0/24
    python3 subnet_calc.py 192.168.1.0/24 --split 4
    python3 subnet_calc.py 10.0.0.0/8 --split 256
    python3 subnet_calc.py 172.16.0.0/16 --split 8
"""

import argparse
import math
import sys


# ── helpers ───────────────────────────────────────────────────────────────────

def ip_to_int(addr: str) -> int:
    """Convert 'A.B.C.D' → 32-bit integer."""
    parts = addr.strip().split(".")
    if len(parts) != 4:
        raise ValueError(f"Expected 4 octets, got {len(parts)}: {addr!r}")
    result = 0
    for p in parts:
        v = int(p)
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


def prefix_to_mask(prefix: int) -> int:
    """Convert /prefix (0–32) → 32-bit mask integer."""
    if prefix == 0:
        return 0
    if prefix == 32:
        return 0xFFFFFFFF
    return ((1 << 32) - (1 << (32 - prefix))) & 0xFFFFFFFF


def mask_to_binary(mask_int: int) -> str:
    """Return dotted-binary representation of a mask."""
    bits = format(mask_int, "032b")
    return ".".join(bits[i:i+8] for i in range(0, 32, 8))


def parse_cidr(cidr: str) -> tuple:
    """Parse 'A.B.C.D/N' → (addr_str, prefix_int)."""
    if "/" not in cidr:
        raise ValueError(f"Expected CIDR notation (e.g. 10.0.0.0/24), got: {cidr!r}")
    addr, prefix_str = cidr.split("/", 1)
    prefix = int(prefix_str)
    if not 0 <= prefix <= 32:
        raise ValueError(f"Prefix must be 0–32, got {prefix}")
    ip_to_int(addr)  # validate
    return addr, prefix


# ── Subnet class ──────────────────────────────────────────────────────────────

class Subnet:
    """Represents a single subnet with all computed properties."""

    def __init__(self, addr: str, prefix: int):
        self.prefix    = prefix
        self.mask_int  = prefix_to_mask(prefix)
        ip_int         = ip_to_int(addr)

        self.net_int   = ip_int & self.mask_int
        self.bcast_int = self.net_int | (~self.mask_int & 0xFFFFFFFF)
        self.total     = 1 << (32 - prefix)
        self.usable    = max(0, self.total - 2)

    @property
    def network(self) -> str:   return int_to_ip(self.net_int)
    @property
    def broadcast(self) -> str: return int_to_ip(self.bcast_int)
    @property
    def host_first(self) -> str:
        return int_to_ip(self.net_int + 1) if self.usable > 0 else "N/A"
    @property
    def host_last(self) -> str:
        return int_to_ip(self.bcast_int - 1) if self.usable > 0 else "N/A"
    @property
    def mask(self) -> str: return int_to_ip(self.mask_int)
    @property
    def mask_bin(self) -> str: return mask_to_binary(self.mask_int)
    @property
    def cidr(self) -> str: return f"{self.network}/{self.prefix}"

    def print_info(self) -> None:
        W = 54
        print("=" * W)
        print(f"  Subnet: {self.cidr}")
        print("=" * W)
        print(f"  Network address  : {self.network}")
        print(f"  Broadcast address: {self.broadcast}")
        print(f"  First host       : {self.host_first}")
        print(f"  Last host        : {self.host_last}")
        print(f"  Total addresses  : {self.total:,}  (2^{32-self.prefix})")
        print(f"  Usable hosts     : {self.usable:,}  (total - network - broadcast)")
        print(f"  Subnet mask      : {self.mask}")
        print(f"  Mask (binary)    : {self.mask_bin}")
        print("=" * W)


# ── split logic ───────────────────────────────────────────────────────────────

def split_subnet(base_cidr: str, num_subnets: int) -> list:
    """
    Divide base_cidr into num_subnets equal subnets.

    Algorithm:
      1. bits_to_borrow = ceil(log2(num_subnets))
      2. new_prefix = base_prefix + bits_to_borrow
      3. subnet_size = 2^(32 - new_prefix)
      4. Walk through the address space in steps of subnet_size
    """
    base_addr, base_prefix = parse_cidr(base_cidr)
    base = Subnet(base_addr, base_prefix)

    if num_subnets < 1:
        raise ValueError("Need at least 1 subnet")

    bits_borrowed = math.ceil(math.log2(max(num_subnets, 2)))
    actual_count  = 1 << bits_borrowed
    new_prefix    = base_prefix + bits_borrowed

    if new_prefix > 32:
        raise ValueError(
            f"Cannot create {num_subnets} subnets from /{base_prefix}: "
            f"would require /{new_prefix} (exceeds /32)"
        )

    subnet_size = 1 << (32 - new_prefix)
    subnets = []
    n = base.net_int
    for _ in range(actual_count):
        subnets.append(Subnet(int_to_ip(n), new_prefix))
        n += subnet_size
    return subnets, bits_borrowed, actual_count, new_prefix


def print_split(base_cidr: str, num_subnets: int) -> None:
    subnets, bits_borrowed, actual, new_prefix = split_subnet(base_cidr, num_subnets)
    _, base_prefix = parse_cidr(base_cidr)

    print(f"\nSplitting {base_cidr} into {num_subnets} subnet(s):")
    print(f"  Bits borrowed   : {bits_borrowed}")
    print(f"  New prefix      : /{new_prefix}")
    print(f"  Subnets created : {actual}"
          + (f"  (rounded up from {num_subnets})" if actual != num_subnets else "  (exact)"))
    print(f"  Hosts/subnet    : {subnets[0].usable:,}")
    print()

    # Column widths
    cw = 18
    header = (f"  {'#':<4} {'Network':<{cw}} {'Broadcast':<{cw}}"
              f" {'First Host':<{cw}} {'Last Host':<{cw}} Usable")
    print(header)
    print("  " + "─" * (4 + cw * 4 + 10))
    for i, sn in enumerate(subnets, 1):
        print(f"  {i:<4} {sn.network:<{cw}} {sn.broadcast:<{cw}}"
              f" {sn.host_first:<{cw}} {sn.host_last:<{cw}} {sn.usable:,}")
    print()

    # Trace the split calculation
    print(f"  How the split works:")
    print(f"    base_prefix  = {base_prefix}")
    print(f"    num_subnets  = {num_subnets}")
    print(f"    bits_borrowed = ceil(log2({num_subnets})) = {bits_borrowed}")
    print(f"    new_prefix   = {base_prefix} + {bits_borrowed} = {new_prefix}")
    print(f"    subnet_size  = 2^(32-{new_prefix}) = {1 << (32 - new_prefix)}")
    print(f"    subnets start at network + 0, +{1 << (32-new_prefix)}, "
          f"+{2 * (1 << (32-new_prefix))}, ...")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CIDR subnet calculator"
    )
    parser.add_argument("cidr", help="Network in CIDR notation, e.g. 192.168.1.0/24")
    parser.add_argument("--split", type=int, metavar="N",
                        help="Split into N equal subnets")
    args = parser.parse_args()

    try:
        if args.split:
            print_split(args.cidr, args.split)
        else:
            addr, prefix = parse_cidr(args.cidr)
            sn = Subnet(addr, prefix)
            print()
            sn.print_info()
            print()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

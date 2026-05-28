# Subnet a Network by Hand

> You have been given `10.0.0.0/24`. Your manager wants four equal subnets. Which addresses go in which subnet, and how many hosts fit in each one?

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 2, Lesson 01 — Decode IPv4 Addresses
**Time:** ~45 minutes

## Learning Objectives
- Compute network address, broadcast address, and host range for any CIDR block
- Determine the correct prefix length to create N equal subnets from a given block
- Enumerate all subnets produced by dividing a block
- Explain why the network and broadcast addresses cannot be assigned to hosts
- Write a Python subnet calculator that validates input and prints a full breakdown

## The Problem

You are setting up a small office network. ISP gives you `192.168.10.0/24` — 254 usable addresses. You need to split that space into separate segments for different departments so that traffic from Sales cannot directly reach the servers, and vice versa. The firewall will enforce rules between segments.

To split the space correctly you need to answer: if I take a /24 and cut it into four pieces, what are the exact address ranges? What mask do I put on each host? What is the broadcast address of each piece?

Get this wrong and you will end up with hosts in the wrong segment, or two segments that overlap, or addresses that seem valid but are silently dropped because a router classifies them as network or broadcast addresses.

Subnetting is also the foundation of everything that follows: static routing (Lesson 05) needs you to know which network addresses exist; NAT (Lesson 06) operates on entire subnets; firewall rules use CIDR notation. You cannot skip this.

## The Concept

### What "subnetting" means

Subnetting means taking a block of IP addresses (a network) and dividing it into smaller blocks (subnets). Each subnet is still a contiguous range of addresses, but with a longer prefix.

When you lengthen the prefix by 1 bit, you double the number of subnets and halve the size of each one:

```
Original:   10.0.0.0/24   →  1 network,  256 addresses, 254 usable
Split /25:  10.0.0.0/25   →  2 subnets,  128 addresses, 126 usable each
Split /26:  10.0.0.0/26   →  4 subnets,   64 addresses,  62 usable each
Split /27:  10.0.0.0/27   →  8 subnets,   32 addresses,  30 usable each
```

### Why subnets must be aligned

A subnet must start at an address that is a multiple of its size. This is **alignment**. For a /26 (64 addresses), valid starting addresses in a /24 are 0, 64, 128, 192. You cannot have a /26 starting at 10.

Why? Because the subnet mask zeroes out the host bits. If you put a host at `10.0.0.65` with a /26 mask, the AND with the mask gives `10.0.0.64` as the network. If you put a host at `10.0.0.73` with a /26 mask, the AND gives `10.0.0.64`. Both end up in the same subnet. The subnets are *defined* by the network address, not by what you label them.

```
/26 subnets within 10.0.0.0/24:
                              
  10.0.0.0   /26  [  0 –  63]  network=  0, broadcast= 63, hosts=  1– 62
  10.0.0.64  /26  [ 64 – 127]  network= 64, broadcast=127, hosts= 65–126
  10.0.0.128 /26  [128 – 191]  network=128, broadcast=191, hosts=129–190
  10.0.0.192 /26  [192 – 255]  network=192, broadcast=255, hosts=193–254
```

### Calculating number of subnets needed → prefix length

To create at least N subnets from a block with prefix P, you need to borrow enough bits:

```
Bits to borrow = ceil(log2(N))

Example: 4 subnets → log2(4) = 2 → borrow 2 bits → new prefix = P + 2
Example: 5 subnets → log2(5) ≈ 2.32 → ceil = 3 → borrow 3 bits → new prefix = P + 3
Example: 8 subnets → log2(8) = 3 → borrow 3 bits → new prefix = P + 3
```

Each borrowed bit doubles the number of subnets. You always round up to the next power of two, which means you often end up with more subnets than requested (but never fewer).

### The "magic number" shortcut for hand calculation

The **magic number** is the size of each subnet. For prefix /N:

```
magic number = 2^(32 - N)   for the last "interesting" octet
```

For a /26 the magic number is 2^(32-26) = 64. Subnets increment by 64 in the last octet: .0, .64, .128, .192.

For a /20, the interesting octet is the third:
```
magic = 2^(32-20) = 4096 addresses total
In the third octet: increment by 2^(20-16) = 16
Subnets: x.x.0.0, x.x.16.0, x.x.32.0, ...
```

### Broadcast address trick

Given a network address and prefix, the broadcast address is the network address with all host bits set to 1. In practice, add (subnet_size − 1) to the network address integer:

```
10.0.0.64 /26
Subnet size = 64
Broadcast = 10.0.0.64 + 64 - 1 = 10.0.0.127
```

## Build It

Create `subnet_calc.py`:

```python
#!/usr/bin/env python3
"""
subnet_calc.py — CIDR subnet calculator.

Usage:
    python3 subnet_calc.py 192.168.10.0/24         # show single subnet info
    python3 subnet_calc.py 192.168.10.0/24 --split 4   # divide into 4 subnets
    python3 subnet_calc.py 10.0.0.0/8 --split 256  # 256 /16 subnets
"""

import sys
import math
import argparse


# ── helpers ──────────────────────────────────────────────────────────────────

def ip_to_int(addr: str) -> int:
    parts = addr.split(".")
    assert len(parts) == 4, f"Bad address: {addr!r}"
    result = 0
    for p in parts:
        v = int(p)
        assert 0 <= v <= 255, f"Octet out of range: {v}"
        result = (result << 8) | v
    return result


def int_to_ip(n: int) -> str:
    assert 0 <= n <= 0xFFFFFFFF
    return ".".join([
        str((n >> 24) & 0xFF),
        str((n >> 16) & 0xFF),
        str((n >>  8) & 0xFF),
        str( n        & 0xFF),
    ])


def prefix_to_mask(prefix: int) -> int:
    """Return the integer value of a /prefix subnet mask."""
    if prefix == 0:
        return 0
    if prefix == 32:
        return 0xFFFFFFFF
    return ((1 << 32) - (1 << (32 - prefix))) & 0xFFFFFFFF


def parse_cidr(cidr: str) -> tuple[str, int]:
    """Parse '192.168.1.0/24' into ('192.168.1.0', 24)."""
    if "/" not in cidr:
        raise ValueError(f"Expected CIDR notation (e.g. 10.0.0.0/8), got: {cidr!r}")
    addr, prefix_str = cidr.split("/", 1)
    prefix = int(prefix_str)
    if not 0 <= prefix <= 32:
        raise ValueError(f"Prefix must be 0-32, got {prefix}")
    return addr, prefix


# ── core calculation ──────────────────────────────────────────────────────────

class Subnet:
    """Represents a single subnet with all computed properties."""

    def __init__(self, address: str, prefix: int):
        self.prefix = prefix
        self.mask_int = prefix_to_mask(prefix)
        ip_int = ip_to_int(address)

        # Network address: zero out host bits
        self.network_int = ip_int & self.mask_int

        # Broadcast: set all host bits to 1
        # ~mask_int inverts all bits; & 0xFFFFFFFF keeps it 32-bit
        self.broadcast_int = self.network_int | (~self.mask_int & 0xFFFFFFFF)

        self.host_min_int = self.network_int + 1
        self.host_max_int = self.broadcast_int - 1
        self.total = 1 << (32 - prefix)          # 2^(32-prefix) total addresses
        self.usable = max(0, self.total - 2)      # subtract network + broadcast

    @property
    def network(self) -> str:
        return int_to_ip(self.network_int)

    @property
    def broadcast(self) -> str:
        return int_to_ip(self.broadcast_int)

    @property
    def host_min(self) -> str:
        return int_to_ip(self.host_min_int) if self.usable > 0 else "N/A"

    @property
    def host_max(self) -> str:
        return int_to_ip(self.host_max_int) if self.usable > 0 else "N/A"

    @property
    def mask(self) -> str:
        return int_to_ip(self.mask_int)

    @property
    def cidr(self) -> str:
        return f"{self.network}/{self.prefix}"

    def print_info(self, label: str = ""):
        header = f"  {label}" if label else ""
        if header:
            print(header)
        print(f"    CIDR:       {self.cidr}")
        print(f"    Mask:       {self.mask}")
        print(f"    Network:    {self.network}")
        print(f"    Broadcast:  {self.broadcast}")
        if self.usable > 0:
            print(f"    Hosts:      {self.host_min} – {self.host_max}")
            print(f"    Usable:     {self.usable:,}")
        else:
            print(f"    Usable:     0  (prefix too long for host assignment)")


def split_subnet(base_cidr: str, num_subnets: int) -> list[Subnet]:
    """
    Divide base_cidr into num_subnets equal subnets.

    Steps:
      1. Calculate how many bits to borrow: ceil(log2(num_subnets))
      2. New prefix = base_prefix + borrowed_bits
      3. New subnet size = 2^(32 - new_prefix)
      4. Generate subnets by incrementing network address by subnet_size each time
    """
    base_addr, base_prefix = parse_cidr(base_cidr)
    base = Subnet(base_addr, base_prefix)

    if num_subnets < 1:
        raise ValueError("Need at least 1 subnet")

    # Bits to borrow — round up to next power of two
    bits_to_borrow = math.ceil(math.log2(max(num_subnets, 2)))
    actual_subnets = 1 << bits_to_borrow   # actual count (power of 2 >= requested)
    new_prefix = base_prefix + bits_to_borrow

    if new_prefix > 30:
        # /31 has 2 addresses (no usable hosts per traditional rules), /32 has 1
        print(f"Warning: new prefix /{new_prefix} leaves very few host addresses.")
    if new_prefix > 32:
        raise ValueError(
            f"Cannot create {num_subnets} subnets from /{base_prefix}: "
            f"would need /{new_prefix}, exceeding 32."
        )

    subnet_size = 1 << (32 - new_prefix)  # addresses per subnet
    subnets = []
    network_int = base.network_int
    for _ in range(actual_subnets):
        # Create subnet from the current network integer
        subnets.append(Subnet(int_to_ip(network_int), new_prefix))
        network_int += subnet_size  # advance to next subnet

    return subnets


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CIDR subnet calculator")
    parser.add_argument("cidr", help="Network in CIDR notation, e.g. 192.168.0.0/24")
    parser.add_argument(
        "--split", type=int, metavar="N",
        help="Divide the network into N equal subnets"
    )
    args = parser.parse_args()

    if args.split:
        # Split mode
        num = args.split
        print(f"\nSplitting {args.cidr} into {num} subnet(s):")
        try:
            subnets = split_subnet(args.cidr, num)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        bits_borrowed = math.ceil(math.log2(max(num, 2)))
        _, base_prefix = parse_cidr(args.cidr)
        new_prefix = base_prefix + bits_borrowed
        actual = len(subnets)

        print(f"  Bits borrowed:    {bits_borrowed}")
        print(f"  New prefix:       /{new_prefix}")
        print(f"  Subnets created:  {actual} "
              f"({'exact' if actual == num else f'rounded up from {num}'})")
        print(f"  Hosts per subnet: {subnets[0].usable:,}")
        print()

        # Print a summary table
        col_w = 18
        print(
            f"  {'#':<4} {'Network':<{col_w}} {'Broadcast':<{col_w}} "
            f"{'First Host':<{col_w}} {'Last Host':<{col_w}} Usable"
        )
        print("  " + "-" * (4 + col_w * 4 + 8))
        for i, sn in enumerate(subnets, 1):
            print(
                f"  {i:<4} {sn.network:<{col_w}} {sn.broadcast:<{col_w}} "
                f"{sn.host_min:<{col_w}} {sn.host_max:<{col_w}} {sn.usable:,}"
            )
        print()

    else:
        # Single subnet info
        try:
            addr, prefix = parse_cidr(args.cidr)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        sn = Subnet(addr, prefix)
        print(f"\nSubnet information for {args.cidr}:")
        sn.print_info()
        print()


if __name__ == "__main__":
    main()
```

Try it out:

```bash
# Single subnet breakdown
python3 subnet_calc.py 192.168.10.0/24

# Split a /24 into 4 equal subnets
python3 subnet_calc.py 192.168.10.0/24 --split 4

# Split a /16 into 8 subnets
python3 subnet_calc.py 172.16.0.0/16 --split 8

# Split a /8 into 256 subnets (each becomes a /16)
python3 subnet_calc.py 10.0.0.0/8 --split 256
```

Sample output for `192.168.10.0/24 --split 4`:

```
Splitting 192.168.10.0/24 into 4 subnet(s):
  Bits borrowed:    2
  New prefix:       /26
  Subnets created:  4 (exact)
  Hosts per subnet: 62

  #    Network            Broadcast          First Host         Last Host          Usable
  -----------------------------------------------------------------------------------------
  1    192.168.10.0       192.168.10.63      192.168.10.1       192.168.10.62      62
  2    192.168.10.64      192.168.10.127     192.168.10.65      192.168.10.126     62
  3    192.168.10.128     192.168.10.191     192.168.10.129     192.168.10.190     62
  4    192.168.10.192     192.168.10.255     192.168.10.193     192.168.10.254     62
```

### Tracing the split logic

Here is what happens when we split `192.168.10.0/24` into 4:

```
base_prefix = 24
num_subnets = 4
bits_to_borrow = ceil(log2(4)) = 2
new_prefix = 24 + 2 = 26
subnet_size = 2^(32-26) = 2^6 = 64

Start: 192.168.10.0  (integer = 3232237568)
  subnet 1: 192.168.10.0   to 192.168.10.63
  subnet 2: 192.168.10.64  to 192.168.10.127
  subnet 3: 192.168.10.128 to 192.168.10.191
  subnet 4: 192.168.10.192 to 192.168.10.255
  
Each step adds 64 to the integer:
3232237568 + 64 = 3232237632 → 192.168.10.64
3232237632 + 64 = 3232237696 → 192.168.10.128
...
```

## Exercises

1. **Manual verification.** Given `172.20.0.0/16`, split it into 16 subnets. How many bits must you borrow? What is the new prefix? What is the size of each subnet? Verify with the script.

2. **Odd count.** Run `python3 subnet_calc.py 10.0.0.0/24 --split 5`. How many subnets are actually created? Why? What is the new prefix?

3. **Supernetting (reverse).** If you have four consecutive /26 subnets starting at `10.1.0.0/26`, what single CIDR block summarises all four? Write a function `supernet(cidr_list)` that takes a list of same-prefix CIDR strings and returns the containing supernet.

4. **VLSM.** Variable Length Subnet Masking lets you carve different-sized subnets from one block. Given `192.168.1.0/24`, manually allocate: one /25 (100 hosts), two /27 (25 hosts each), one /28 (10 hosts). Draw the address map and verify no ranges overlap.

5. **Containment check.** Write a function `is_subnet_of(inner_cidr, outer_cidr)` that returns `True` if inner is fully contained within outer. Test with `10.0.1.0/24` inside `10.0.0.0/16` (True) and `10.1.0.0/24` inside `10.0.0.0/16` (False).

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Subnetting | "Splitting a network" | Increasing the prefix length to create multiple smaller networks from one larger one |
| CIDR block | "A subnet" | A contiguous range of IP addresses defined by a base address and prefix length |
| Subnet size | "How many addresses" | 2^(32 − prefix): includes network and broadcast addresses, not all are assignable |
| Bits borrowed | "How much we split" | The number of host bits converted to network bits to create subnets |
| Alignment | "Starting on a boundary" | The requirement that a subnet's network address is a multiple of its size |
| Supernetting | "Route aggregation" | The reverse of subnetting: combining multiple contiguous subnets into a single larger CIDR block |
| Magic number | "The increment" | The size of each subnet, used as the increment between consecutive subnet network addresses |

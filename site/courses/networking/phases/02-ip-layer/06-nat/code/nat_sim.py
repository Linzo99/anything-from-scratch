# Run: python3 nat_sim.py
#!/usr/bin/env python3
"""
nat_sim.py — Simulate a NAT/PAT (NAPT) translation table.

Demonstrates:
  - How multiple private (IP, port) pairs share a single public IP
  - The NAT table structure: private endpoint ↔ public endpoint
  - Translating outbound packets: private src → public src
  - Translating inbound replies: public dst → private dst
  - Port allocation and reuse
  - Why incoming connections without an existing NAT entry are dropped

No third-party libraries. Python 3.8+ stdlib only.

Usage:
    python3 nat_sim.py              # run built-in scenario
    python3 nat_sim.py --demo       # extended demo with collision handling
"""

import argparse
import time
from dataclasses import dataclass, field
from typing import Optional


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Endpoint:
    """An IP:port pair."""
    ip:   str
    port: int

    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"

    def __hash__(self) -> int:
        return hash((self.ip, self.port))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Endpoint):
            return NotImplemented
        return self.ip == other.ip and self.port == other.port


@dataclass
class NATEntry:
    """One entry in the NAT translation table."""
    private_src:   Endpoint    # original source (private host)
    public_src:    Endpoint    # translated source (public gateway IP + assigned port)
    dst:           Endpoint    # destination (same in both directions)
    protocol:      str         # "TCP" or "UDP"
    created_at:    float = field(default_factory=time.monotonic)
    last_seen:     float = field(default_factory=time.monotonic)
    packets_out:   int = 0
    packets_in:    int = 0

    def touch(self) -> None:
        self.last_seen = time.monotonic()

    def age(self) -> float:
        return time.monotonic() - self.created_at

    def __str__(self) -> str:
        return (f"  {str(self.private_src):<22} ↔  {str(self.public_src):<22}"
                f"  →  {str(self.dst):<22}  [{self.protocol}]"
                f"  pkts out={self.packets_out} in={self.packets_in}")


# ── NAT gateway simulator ─────────────────────────────────────────────────────

class NATGateway:
    """
    Simulates a NAPT (Network Address and Port Translation) gateway.

    The gateway has one public IP. Private hosts behind it share this IP.
    For each new outbound connection (private_src → dst), the gateway:
      1. Assigns an unused public port from its pool.
      2. Creates a NAT entry: private_src ↔ public_src (public_ip:assigned_port)
      3. Rewrites the source of outbound packets.
      4. Rewrites the destination of inbound reply packets.
    """

    PUBLIC_IP  = "203.0.113.5"    # RFC 5737 documentation address (fake "public" IP)
    PORT_START = 40000
    PORT_END   = 65000

    def __init__(self):
        self._next_port = self.PORT_START
        # Primary index: (private_src, dst) → NATEntry
        self._by_private: dict[tuple, NATEntry] = {}
        # Reverse index: (public_src, dst) → NATEntry
        self._by_public:  dict[tuple, NATEntry] = {}

    def _allocate_port(self) -> int:
        """Return the next available public port."""
        port = self._next_port
        if port > self.PORT_END:
            raise RuntimeError("NAT port pool exhausted (all ports 40000–65000 in use)")
        self._next_port += 1
        return port

    def send(self, private_ip: str, private_port: int,
             dst_ip: str, dst_port: int,
             protocol: str = "TCP") -> tuple:
        """
        Process an outbound packet from a private host.

        Returns (translated_src_ip, translated_src_port, dst_ip, dst_port)
        — the source address the destination server will see.
        """
        priv = Endpoint(private_ip, private_port)
        dst  = Endpoint(dst_ip, dst_port)
        key  = (priv, dst)

        if key not in self._by_private:
            # New connection — allocate a public port
            pub_port = self._allocate_port()
            pub_src  = Endpoint(self.PUBLIC_IP, pub_port)
            entry    = NATEntry(
                private_src=priv,
                public_src=pub_src,
                dst=dst,
                protocol=protocol,
            )
            self._by_private[key]           = entry
            self._by_public[(pub_src, dst)] = entry
            print(f"  [NAT] NEW entry:   {priv} → MASQUERADE → {pub_src}  (dest={dst})")
        else:
            entry = self._by_private[key]

        entry.touch()
        entry.packets_out += 1
        return (entry.public_src.ip, entry.public_src.port, dst_ip, dst_port)

    def receive(self, public_dst_ip: str, public_dst_port: int,
                src_ip: str, src_port: int) -> Optional[tuple]:
        """
        Process an inbound (reply) packet arriving at the gateway's public IP.

        Returns (original_private_ip, original_private_port) if an entry matches,
        or None if no matching entry (packet is dropped).
        """
        pub_dst = Endpoint(public_dst_ip, public_dst_port)
        src     = Endpoint(src_ip, src_port)
        key     = (pub_dst, src)

        if key not in self._by_public:
            print(f"  [NAT] DROPPED inbound packet from {src} to {pub_dst} "
                  f"— no matching NAT entry")
            return None

        entry = self._by_public[key]
        entry.touch()
        entry.packets_in += 1
        return (entry.private_src.ip, entry.private_src.port)

    def show_table(self) -> None:
        """Print the current NAT translation table."""
        print(f"\n  NAT Translation Table ({len(self._by_private)} entries):")
        if not self._by_private:
            print("    (empty)")
            return
        print(f"  {'Private source':<22}    {'Public source':<22}    "
              f"{'Destination':<22}  Protocol  Out  In")
        print("  " + "─" * 90)
        for entry in self._by_private.values():
            print(f"  {str(entry.private_src):<22} ↔  {str(entry.public_src):<22}"
                  f"  →  {str(entry.dst):<22}  {entry.protocol:<8} "
                  f" {entry.packets_out:>3}  {entry.packets_in:>3}")

    def show_rewrite_demo(self, priv_ip: str, priv_port: int,
                           dst_ip: str, dst_port: int) -> None:
        """Show the before/after packet rewrite for a given flow."""
        key = (Endpoint(priv_ip, priv_port), Endpoint(dst_ip, dst_port))
        if key not in self._by_private:
            print(f"  (No NAT entry for {priv_ip}:{priv_port} → {dst_ip}:{dst_port})")
            return
        entry = self._by_private[key]
        print()
        print("  Packet rewrite example:")
        print(f"    Outbound (private → public):")
        print(f"      Before: src={entry.private_src}  dst={entry.dst}")
        print(f"      After:  src={entry.public_src}   dst={entry.dst}")
        print(f"    Inbound (public → private):")
        print(f"      Before: dst={entry.public_src}   src={entry.dst}")
        print(f"      After:  dst={entry.private_src}  src={entry.dst}")
        print(f"    NAT also recomputes TCP/UDP checksums (IP and port changed)")


# ── Scenarios ─────────────────────────────────────────────────────────────────

def run_basic_scenario(gw: NATGateway) -> None:
    DIV = "═" * 62
    print(f"\n{DIV}")
    print("  Basic NAT/PAT Scenario")
    print(f"{DIV}")
    print(f"  Public IP: {NATGateway.PUBLIC_IP}")
    print(f"  Private hosts: 192.168.1.10, 192.168.1.11, 192.168.1.12\n")

    # Three hosts connecting to example.com:80
    connections = [
        ("192.168.1.10", 54321, "93.184.216.34", 80,  "TCP"),
        ("192.168.1.11", 54321, "93.184.216.34", 80,  "TCP"),  # same private port!
        ("192.168.1.12", 33445, "8.8.8.8",       53,  "UDP"),
        ("192.168.1.10", 54322, "93.184.216.34", 443, "TCP"),  # same host, diff port
    ]

    print("  Outbound packets:\n")
    for priv_ip, priv_port, dst_ip, dst_port, proto in connections:
        pub_ip, pub_port, d_ip, d_port = gw.send(priv_ip, priv_port,
                                                   dst_ip, dst_port, proto)
        print(f"    {priv_ip}:{priv_port} → {dst_ip}:{dst_port}"
              f"   becomes   {pub_ip}:{pub_port} → {d_ip}:{d_port}")
    gw.show_table()

    # Show address rewrite for first connection
    gw.show_rewrite_demo("192.168.1.10", 54321, "93.184.216.34", 80)

    # Inbound reply
    print(f"\n  Inbound reply packets:\n")
    first_entry = list(gw._by_private.values())[0]
    pub_ip  = first_entry.public_src.ip
    pub_port = first_entry.public_src.port
    dst_ip  = first_entry.dst.ip
    dst_port = first_entry.dst.port

    result = gw.receive(pub_ip, pub_port, dst_ip, dst_port)
    if result:
        priv_ip, priv_port = result
        print(f"    Reply {dst_ip}:{dst_port} → {pub_ip}:{pub_port}")
        print(f"    NAT rewrites dst → {priv_ip}:{priv_port}  (delivered to correct host)")

    # Unsolicited inbound (should be dropped)
    print()
    print("  Unsolicited inbound attempt (public → private, no NAT entry):\n")
    gw.receive(NATGateway.PUBLIC_IP, 12345, "10.20.30.40", 54000)

    print()
    print("  Observation: both 192.168.1.10 and 192.168.1.11 used private port 54321")
    print("  NAT assigned them DIFFERENT public ports (key point of PAT/NAPT).")
    print("  The destination server at 93.184.216.34 only sees the public IP.")


def run_extended_demo(gw: NATGateway) -> None:
    DIV = "═" * 62
    print(f"\n{DIV}")
    print("  Extended Demo: port reuse across hosts")
    print(f"{DIV}\n")
    n = 5
    print(f"  Simulating {n} private hosts all connecting from port 12345:\n")
    for i in range(1, n + 1):
        priv = f"10.0.0.{i}"
        gw.send(priv, 12345, "1.2.3.4", 80, "TCP")
    gw.show_table()
    print(f"\n  Each private host got a unique public port despite using the same")
    print(f"  private source port. This is the core NAPT mechanism.")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="NAT/PAT translation table simulation"
    )
    parser.add_argument("--demo", action="store_true",
                        help="Also run the extended port-reuse demo")
    args = parser.parse_args()

    gw = NATGateway()
    run_basic_scenario(gw)
    if args.demo:
        gw2 = NATGateway()
        run_extended_demo(gw2)

    print()


if __name__ == "__main__":
    main()

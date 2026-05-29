# Run: python3 mac_switch.py
#!/usr/bin/env python3
"""
mac_switch.py — Simulate a Layer-2 Ethernet switch with MAC address learning.

Implements:
  - MAC learning: records src_mac → incoming_port on every frame
  - Forwarding: sends to known unicast destination port directly
  - Flooding: sends to all ports except incoming for unknown/broadcast/multicast
  - Entry expiry: entries older than max_age_seconds are evicted
  - Simulation scenarios: demonstrates the learning behaviour step by step

No third-party libraries. Python 3.8+ stdlib only.

Usage:
    python3 mac_switch.py          # run all built-in scenarios
    python3 mac_switch.py --flood  # also run the MAC flooding attack demo
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from typing import Optional


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class EthernetFrame:
    """A simulated Ethernet frame (src MAC, dst MAC, payload, port)."""
    src_mac:      str
    dst_mac:      str
    payload:      str
    incoming_port: int = 0

    def __str__(self) -> str:
        return (f"[{self.src_mac} → {self.dst_mac}]"
                f" payload={self.payload!r} port={self.incoming_port}")


@dataclass
class CAMEntry:
    """One forwarding-table entry: MAC → port with a creation timestamp."""
    port:       int
    learned_at: float = field(default_factory=time.monotonic)

    def is_expired(self, max_age: float = 300.0) -> bool:
        return (time.monotonic() - self.learned_at) > max_age


# ── Switch ────────────────────────────────────────────────────────────────────

class Switch:
    """
    A Layer-2 Ethernet switch simulation.

    The forwarding table (CAM table) maps MAC addresses to port numbers.
    Learning: every incoming frame's source MAC is recorded.
    Forwarding: unicast to known MAC → single port; unknown/broadcast → flood.
    """

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, num_ports: int, name: str = "SW1",
                 max_age: float = 300.0, verbose: bool = True):
        self.name      = name
        self.num_ports = num_ports
        self.max_age   = max_age
        self.verbose   = verbose
        self.cam:  dict[str, CAMEntry] = {}
        self.stats = {"received": 0, "forwarded": 0, "flooded": 0}

    # ── private helpers ───────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [{self.name}] {msg}")

    def _flood_ports(self, exclude: int) -> list[int]:
        return [p for p in range(1, self.num_ports + 1) if p != exclude]

    # ── learning ──────────────────────────────────────────────────────────────

    def _learn(self, src: str, port: int) -> None:
        """Record src_mac → port. Log if the MAC moved to a new port."""
        if src in self.cam:
            old = self.cam[src].port
            if old != port:
                self._log(f"MAC {src} MOVED from port {old} → port {port}")
        else:
            self._log(f"LEARN  {src} → port {port}")
        self.cam[src] = CAMEntry(port=port)

    # ── forwarding decision ───────────────────────────────────────────────────

    def process(self, frame: EthernetFrame) -> dict[int, EthernetFrame]:
        """
        Process one incoming frame. Returns {port: frame} for each output port.

        Algorithm:
          1. Learn src_mac → incoming_port.
          2. If dst is broadcast or multicast: flood.
          3. If dst is in CAM and not expired: forward to that port.
          4. Otherwise: flood (unknown unicast).
        """
        self.stats["received"] += 1
        self._log(f"IN     {frame}")
        self._learn(frame.src_mac, frame.incoming_port)

        dst = frame.dst_mac
        ing = frame.incoming_port

        # Determine output ports
        if dst == self.BROADCAST:
            ports = self._flood_ports(ing)
            self._log(f"FLOOD  broadcast → ports {ports}")
            self.stats["flooded"] += 1

        elif self._is_multicast(dst):
            ports = self._flood_ports(ing)
            self._log(f"FLOOD  multicast {dst} → ports {ports}")
            self.stats["flooded"] += 1

        elif dst in self.cam:
            entry = self.cam[dst]
            if entry.is_expired(self.max_age):
                del self.cam[dst]
                ports = self._flood_ports(ing)
                self._log(f"FLOOD  {dst}: CAM entry expired → ports {ports}")
                self.stats["flooded"] += 1
            else:
                ports = [entry.port]
                self._log(f"FWD    {dst} → port {entry.port}")
                self.stats["forwarded"] += 1

        else:
            ports = self._flood_ports(ing)
            self._log(f"FLOOD  {dst}: unknown unicast → ports {ports}")
            self.stats["flooded"] += 1

        return {p: frame for p in ports}

    @staticmethod
    def _is_multicast(mac: str) -> bool:
        first_byte = int(mac.split(":")[0], 16)
        return bool(first_byte & 0x01) and mac != Switch.BROADCAST

    def show_cam(self) -> None:
        """Print the current CAM table."""
        print(f"\n  [{self.name}] CAM Table ({len(self.cam)} entries):")
        if not self.cam:
            print("    (empty)")
            return
        print(f"    {'MAC':<20}  {'Port':<6}  {'Age(s)'}")
        print(f"    {'─'*20}  {'─'*6}  {'─'*10}")
        now = time.monotonic()
        for mac, entry in sorted(self.cam.items()):
            age = now - entry.learned_at
            print(f"    {mac:<20}  {entry.port:<6}  {age:.2f}")

    def show_stats(self) -> None:
        print(f"\n  [{self.name}] Stats: received={self.stats['received']}  "
              f"forwarded={self.stats['forwarded']}  "
              f"flooded={self.stats['flooded']}")


# ── Host ──────────────────────────────────────────────────────────────────────

class Host:
    """An end host connected to a switch port."""

    def __init__(self, name: str, mac: str, port: int):
        self.name = name
        self.mac  = mac
        self.port = port
        self.inbox: list[EthernetFrame] = []

    def send(self, dst_mac: str, payload: str) -> EthernetFrame:
        return EthernetFrame(src_mac=self.mac, dst_mac=dst_mac,
                             payload=payload, incoming_port=self.port)

    def deliver(self, frame: EthernetFrame) -> None:
        if frame.dst_mac in (self.mac, Switch.BROADCAST):
            self.inbox.append(frame)
            print(f"    {self.name:<6} (port {self.port}) ← '{frame.payload}'"
                  f"  from {frame.src_mac}")
        else:
            # The switch should never send this frame here — log as a bug
            print(f"    {self.name:<6} (port {self.port}) UNEXPECTED frame for"
                  f" {frame.dst_mac}")


# ── Network helper ────────────────────────────────────────────────────────────

def send_frame(sw: Switch, hosts_by_port: dict[int, Host],
               frame: EthernetFrame) -> None:
    """Process a frame through the switch and deliver to recipient hosts."""
    out = sw.process(frame)
    for port, f in out.items():
        if port in hosts_by_port:
            hosts_by_port[port].deliver(f)


# ── Simulation scenarios ──────────────────────────────────────────────────────

def run_scenarios(run_flood: bool = False) -> None:
    sw = Switch(num_ports=4, name="SW1")
    alice = Host("Alice", "aa:aa:aa:aa:aa:aa", port=1)
    bob   = Host("Bob",   "bb:bb:bb:bb:bb:bb", port=2)
    carol = Host("Carol", "cc:cc:cc:cc:cc:cc", port=3)
    dave  = Host("Dave",  "dd:dd:dd:dd:dd:dd", port=4)
    hosts_by_port: dict[int, Host] = {h.port: h for h in [alice, bob, carol, dave]}

    DIV = "=" * 62

    # ── Scenario 1: unknown destination → flood ───────────────────────────────
    print(f"\n{DIV}")
    print("SCENARIO 1: Alice → Bob  (CAM table empty — expect FLOOD)")
    print(f"{DIV}")
    send_frame(sw, hosts_by_port, alice.send(bob.mac, "Hello Bob!"))
    sw.show_cam()
    # Bob, Carol, Dave all receive the frame (flood)

    # ── Scenario 2: known destination → direct forward ────────────────────────
    print(f"\n{DIV}")
    print("SCENARIO 2: Bob → Alice  (Alice's port is now known — expect FORWARD)")
    print(f"{DIV}")
    send_frame(sw, hosts_by_port, bob.send(alice.mac, "Hello Alice!"))
    sw.show_cam()
    # Only Alice receives the frame

    # ── Scenario 3: unknown unicast flood ────────────────────────────────────
    print(f"\n{DIV}")
    print("SCENARIO 3: Carol → Dave  (Dave unknown — expect FLOOD to ports 1,2,4)")
    print(f"{DIV}")
    send_frame(sw, hosts_by_port, carol.send(dave.mac, "Hi Dave!"))
    sw.show_cam()

    # ── Scenario 4: broadcast ────────────────────────────────────────────────
    print(f"\n{DIV}")
    print("SCENARIO 4: Alice broadcasts ARP  (expect FLOOD to all other ports)")
    print(f"{DIV}")
    send_frame(sw, hosts_by_port, alice.send("ff:ff:ff:ff:ff:ff", "ARP: Who has 10.0.0.2?"))

    # ── Scenario 5: fully learned table → direct forward ─────────────────────
    print(f"\n{DIV}")
    print("SCENARIO 5: Alice → Bob again  (Bob's port now known — expect FORWARD)")
    print(f"{DIV}")
    send_frame(sw, hosts_by_port, alice.send(bob.mac, "Got your message, Bob"))
    sw.show_cam()

    sw.show_stats()

    # ── MAC flooding attack demo ──────────────────────────────────────────────
    if run_flood:
        import random
        print(f"\n{DIV}")
        print("ATTACK: MAC flooding — send 50 frames with random source MACs")
        print("        This fills the CAM table, forcing the switch into hub mode")
        print(f"{DIV}")
        before = len(sw.cam)
        for i in range(50):
            fake_mac = ":".join(f"{random.randint(0,255):02x}" for _ in range(6))
            sw.cam[fake_mac] = CAMEntry(port=random.randint(1, 4))
        after = len(sw.cam)
        print(f"\n  CAM entries before attack: {before}")
        print(f"  CAM entries after  attack: {after}")
        print("  (Real switches have a fixed CAM size; overflow forces flooding)")

    print(f"\n{DIV}")
    print("Simulation complete.")
    print(f"{DIV}\n")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Layer-2 switch MAC learning simulation"
    )
    parser.add_argument("--flood", action="store_true",
                        help="Also run the MAC flooding attack demonstration")
    args = parser.parse_args()
    run_scenarios(run_flood=args.flood)


if __name__ == "__main__":
    main()

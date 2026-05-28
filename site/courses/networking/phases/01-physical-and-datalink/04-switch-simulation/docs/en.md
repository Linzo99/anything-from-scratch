# Build a Layer-2 Switch Simulation

> A switch is not magic — it is a forwarding table with a learning algorithm. You can implement the entire logic in 60 lines of Python.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 1, Lesson 03 — Understand MAC Addresses
**Time:** ~50 minutes

## Learning Objectives
- Explain how a Layer-2 switch builds and uses its MAC address forwarding table
- Implement MAC address learning from Ethernet frames in Python
- Implement flooding for unknown destinations and broadcast frames
- Simulate a network of four hosts and trace frame delivery
- Identify the difference between a switch and a hub

## The Problem

Before switches, Ethernet networks used hubs. A hub is dumb: it receives a frame on one port and repeats it out every other port. Every host sees every frame, even ones not addressed to them. This creates two problems:

1. **Privacy**: host A can read frames addressed to host B just by putting its NIC in promiscuous mode
2. **Bandwidth**: all hosts compete for the same shared medium. If A and B are talking, C and D cannot transmit at the same time without causing a collision.

A switch solves both problems by keeping a **forwarding table** — a record of which MAC address was last seen on which port. When a frame arrives, the switch looks up the destination MAC in the table and forwards the frame only to the correct port. Hosts that are not the destination never see the frame.

The forwarding table is built by **learning**: when a frame arrives on port 3 with source MAC `aa:bb:cc:11:22:33`, the switch records "MAC `aa:bb:cc:11:22:33` is reachable via port 3." Future frames destined for that MAC are forwarded directly to port 3 only.

When the destination MAC is not in the table (the switch has not learned it yet), the switch **floods**: it sends the frame out every port except the incoming one. This guarantees delivery even on a fresh switch with an empty table.

Understanding this algorithm lets you:
- Debug why traffic that should stay local is flooding everywhere
- Understand why a switch's forwarding table can fill up (MAC flooding attacks)
- Design simulations for testing Layer 2 network behavior

## The Concept

### The Forwarding Table (CAM Table)

The forwarding table is sometimes called a **CAM table** (Content Addressable Memory table) after the specialized hardware used to implement it in real switches. In software, it is just a dictionary:

```python
forwarding_table = {
    "aa:bb:cc:11:22:33": 2,  # MAC address → port number
    "dd:ee:ff:44:55:66": 5,
    "11:22:33:aa:bb:cc": 1,
}
```

Every entry has an expiry timer (typically 5 minutes). If no frame is seen from a MAC address within that time, the entry is removed to free space and prevent stale routing.

### The Learning and Forwarding Algorithm

```
For every incoming frame:
  1. Record: forwarding_table[src_mac] = incoming_port
             (Learn where this source is located)

  2. Decide where to send it:
     a. If dst_mac == ff:ff:ff:ff:ff:ff (broadcast):
        → Flood: send out ALL ports except incoming_port
     b. Else if dst_mac in forwarding_table:
        → Forward: send ONLY to forwarding_table[dst_mac]
     c. Else:
        → Flood: send out ALL ports except incoming_port
           (We don't know where dst_mac is yet)
```

### Switch vs. Hub

```
Hub (Layer 1 device):
  +------+   Frame on port 1   +------+
  | Port |-------------------> | Port |  port 2 (host B)
  |  1   |                     |  2   |
  | (in) | -------------------> | 3   |  port 3 (host C)  ← also gets frame
  |      | -------------------> | 4   |  port 4 (host D)  ← also gets frame
  +------+

Switch (Layer 2 device):
  +------+   Frame on port 1   +------+
  | Port |--check-table------> | Port |  port 2 (host B)  ← only this port
  |  1   |                     |  2   |
  | (in) |   NOT forwarded     | 3   |  port 3 (host C)  ← sees nothing
  |      |   NOT forwarded     | 4   |  port 4 (host D)  ← sees nothing
  +------+
```

### Flooding vs. Forwarding

```
State of forwarding table           Action
----------------------------------  -----------------------------------------
dst_mac known, port known           Forward to that specific port only
dst_mac unknown                     Flood to all ports except incoming
dst_mac is broadcast                Flood to all ports except incoming
dst_mac is multicast (no snooping)  Flood to all ports except incoming
```

### Switch Ports: A Mental Model

Think of a switch as having N ports. Each port connects to one cable, which connects to one host (or another switch). The switch is the meeting point:

```
                  +------------------+
Host A (MAC:aaaa) |      Switch      | Host B (MAC:bbbb)
port 1 -----------|                  |----------- port 2
                  |  Forwarding      |
Host C (MAC:cccc) |  Table:          | Host D (MAC:dddd)
port 3 -----------|  aaaa → port 1  |----------- port 4
                  |  bbbb → port 2  |
                  |  cccc → port 3  |
                  +------------------+
```

When A sends to B, the switch looks up `bbbb` → port 2, and sends the frame only to port 2. Hosts C and D see nothing.

## Build It

### Step 1 — Define the Frame and Switch classes

Create a file called `switch_simulation.py`:

```python
# switch_simulation.py
# A simulation of a Layer-2 Ethernet switch with MAC address learning.

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


# --- Data structures ---

@dataclass
class EthernetFrame:
    """Represents an Ethernet frame with source MAC, destination MAC, and payload."""
    src_mac: str       # e.g. "aa:bb:cc:11:22:33"
    dst_mac: str       # e.g. "dd:ee:ff:44:55:66"
    payload: str       # Simple string for simulation purposes
    incoming_port: int = 0  # Which port this frame arrived on

    def __str__(self) -> str:
        return (
            f"Frame({self.src_mac} → {self.dst_mac}, "
            f"payload={self.payload!r}, port={self.incoming_port})"
        )


@dataclass
class ForwardingTableEntry:
    """One entry in the switch's forwarding table."""
    port: int
    learned_at: float = field(default_factory=time.time)

    def is_expired(self, max_age_seconds: float = 300.0) -> bool:
        """Return True if this entry is older than max_age_seconds."""
        return (time.time() - self.learned_at) > max_age_seconds


# --- The Switch ---

class Switch:
    """
    A Layer-2 Ethernet switch simulation.

    Maintains a forwarding table: MAC address → port number.
    Learns source MACs from incoming frames.
    Forwards based on destination MAC or floods if unknown.
    """

    BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"

    def __init__(self, num_ports: int, name: str = "SW1"):
        """
        Initialize a switch with a given number of ports.
        Port numbers are 1-indexed (ports 1 through num_ports).
        """
        self.name = name
        self.num_ports = num_ports
        # forwarding_table: maps MAC address strings to ForwardingTableEntry
        self.forwarding_table: dict[str, ForwardingTableEntry] = {}
        # Log of forwarding decisions for inspection
        self.event_log: list[str] = []

    def _log(self, message: str) -> None:
        """Record an event and print it."""
        self.event_log.append(message)
        print(f"  [{self.name}] {message}")

    def _learn(self, frame: EthernetFrame) -> None:
        """
        Learn the source MAC address → incoming port mapping.
        This is how the switch builds its forwarding table.
        """
        src = frame.src_mac
        port = frame.incoming_port

        if src in self.forwarding_table:
            old_port = self.forwarding_table[src].port
            if old_port != port:
                # MAC has moved to a different port (host was reconnected)
                self._log(
                    f"MAC {src} moved from port {old_port} to port {port}"
                )
        else:
            self._log(f"Learned: {src} → port {port}")

        # Update or create the entry
        self.forwarding_table[src] = ForwardingTableEntry(port=port)

    def _get_flood_ports(self, exclude_port: int) -> list[int]:
        """Return all port numbers except the specified one."""
        return [p for p in range(1, self.num_ports + 1) if p != exclude_port]

    def process_frame(self, frame: EthernetFrame) -> dict[int, EthernetFrame]:
        """
        Process one incoming frame. Returns a dict of {port: frame}
        representing which ports the frame should be sent out on.

        This is the core switch algorithm.
        """
        self._log(f"Received: {frame}")

        # Step 1: Learn the source MAC address and its port
        self._learn(frame)

        # Step 2: Make forwarding decision
        dst = frame.dst_mac
        incoming = frame.incoming_port

        if dst == self.BROADCAST_MAC:
            # Broadcast: flood to all ports except incoming
            out_ports = self._get_flood_ports(exclude_port=incoming)
            self._log(f"BROADCAST → flooding to ports {out_ports}")

        elif dst.startswith("01:") or dst.startswith("33:"):
            # Multicast: flood (simplified — no IGMP snooping)
            out_ports = self._get_flood_ports(exclude_port=incoming)
            self._log(f"MULTICAST → flooding to ports {out_ports}")

        elif dst in self.forwarding_table:
            # Known unicast: forward to the specific port
            entry = self.forwarding_table[dst]
            if entry.is_expired():
                # Expired entry — must flood to rediscover
                del self.forwarding_table[dst]
                out_ports = self._get_flood_ports(exclude_port=incoming)
                self._log(
                    f"Known unicast {dst}: entry expired → flooding to ports {out_ports}"
                )
            else:
                out_ports = [entry.port]
                self._log(
                    f"Known unicast {dst} → forward to port {entry.port}"
                )
        else:
            # Unknown unicast: flood (we don't know which port to use)
            out_ports = self._get_flood_ports(exclude_port=incoming)
            self._log(f"Unknown unicast {dst} → flooding to ports {out_ports}")

        # Build the output: one copy of the frame per output port
        return {port: frame for port in out_ports}

    def show_table(self) -> None:
        """Print the current forwarding table."""
        print(f"\n  [{self.name}] Forwarding Table:")
        if not self.forwarding_table:
            print("    (empty)")
        else:
            print(f"    {'MAC Address':<20}  {'Port':<6}  {'Age (s)'}")
            print(f"    {'─' * 20}  {'─' * 6}  {'─' * 10}")
            now = time.time()
            for mac, entry in sorted(self.forwarding_table.items()):
                age = now - entry.learned_at
                print(f"    {mac:<20}  {entry.port:<6}  {age:.1f}s")


# --- Host simulation ---

class Host:
    """Represents an end host connected to a switch port."""

    def __init__(self, name: str, mac: str, port: int):
        self.name = name
        self.mac = mac
        self.port = port
        self.received_frames: list[EthernetFrame] = []

    def receive(self, frame: EthernetFrame) -> None:
        """Accept a frame delivered by the switch."""
        if frame.dst_mac in (self.mac, "ff:ff:ff:ff:ff:ff"):
            self.received_frames.append(frame)
            print(
                f"    {self.name} (port {self.port}) RECEIVED: "
                f"'{frame.payload}' from {frame.src_mac}"
            )
        else:
            # In a real switch, this host should never receive this frame.
            # If it does, the switch has a bug.
            print(
                f"    {self.name} (port {self.port}) ERROR: "
                f"got frame for {frame.dst_mac} — should not happen!"
            )

    def send(self, dst_mac: str, payload: str) -> EthernetFrame:
        """Create a frame to send. The switch will process it."""
        return EthernetFrame(
            src_mac=self.mac,
            dst_mac=dst_mac,
            payload=payload,
            incoming_port=self.port,
        )


# --- Network setup ---

def create_network() -> tuple[Switch, dict[str, Host]]:
    """Create a 4-port switch with 4 hosts."""
    sw = Switch(num_ports=4, name="SW1")

    hosts = {
        "Alice":   Host("Alice",   "aa:aa:aa:aa:aa:aa", port=1),
        "Bob":     Host("Bob",     "bb:bb:bb:bb:bb:bb", port=2),
        "Carol":   Host("Carol",   "cc:cc:cc:cc:cc:cc", port=3),
        "Dave":    Host("Dave",    "dd:dd:dd:dd:dd:dd", port=4),
    }
    return sw, hosts


def deliver_frame(
    sw: Switch,
    hosts: dict[str, Host],
    frame: EthernetFrame,
) -> None:
    """
    Process a frame through the switch and deliver it to the
    appropriate host(s).
    """
    forwarded = sw.process_frame(frame)
    # forwarded is {port: frame} — deliver to the host on each port
    port_to_host = {h.port: h for h in hosts.values()}
    for port, out_frame in forwarded.items():
        if port in port_to_host:
            port_to_host[port].receive(out_frame)
```

### Step 2 — Write the simulation scenarios

Add this to the end of `switch_simulation.py`:

```python
# --- Simulation scenarios ---

def run_simulation() -> None:
    sw, hosts = create_network()
    alice = hosts["Alice"]
    bob   = hosts["Bob"]
    carol = hosts["Carol"]
    dave  = hosts["Dave"]

    print("=" * 60)
    print("SCENARIO 1: Alice → Bob (switch table is empty)")
    print("Expected: flooding (Bob, Carol, Dave all receive)")
    print("=" * 60)
    frame1 = alice.send(bob.mac, "Hello Bob!")
    deliver_frame(sw, hosts, frame1)
    sw.show_table()

    print("\n" + "=" * 60)
    print("SCENARIO 2: Bob → Alice (switch now knows Alice is on port 1)")
    print("Expected: direct forward to port 1 only")
    print("=" * 60)
    frame2 = bob.send(alice.mac, "Hello Alice!")
    deliver_frame(sw, hosts, frame2)
    sw.show_table()

    print("\n" + "=" * 60)
    print("SCENARIO 3: Carol → Dave (unknown destination)")
    print("Expected: flooding to ports 1, 2, 4 (not 3)")
    print("=" * 60)
    frame3 = carol.send(dave.mac, "Hi Dave!")
    deliver_frame(sw, hosts, frame3)
    sw.show_table()

    print("\n" + "=" * 60)
    print("SCENARIO 4: Alice broadcasts ARP request")
    print("Expected: flooding to ALL ports (2, 3, 4)")
    print("=" * 60)
    frame4 = alice.send("ff:ff:ff:ff:ff:ff", "ARP: Who has 10.0.0.2?")
    deliver_frame(sw, hosts, frame4)

    print("\n" + "=" * 60)
    print("SCENARIO 5: Alice → Bob (table now knows Bob from scenario 2)")
    print("Expected: direct forward to port 2 only")
    print("=" * 60)
    frame5 = alice.send(bob.mac, "Hey Bob, got your message!")
    deliver_frame(sw, hosts, frame5)
    sw.show_table()

    print("\n" + "=" * 60)
    print("Final forwarding table state:")
    print("=" * 60)
    sw.show_table()


if __name__ == "__main__":
    run_simulation()
```

Run it:
```bash
python3 switch_simulation.py
```

### Step 3 — Observe the learning behavior

Watch how the forwarding table fills up through the scenarios:
- After Scenario 1: `Alice → port 1` is learned
- After Scenario 2: `Bob → port 2` is learned
- After Scenario 3: `Carol → port 3` and `Dave → port 4` are learned
- After Scenario 5: All four MACs are known; no more flooding for unicast

### Step 4 — Simulate a MAC table overflow attack

A MAC flooding attack works by sending thousands of frames with random source MACs, filling the forwarding table and forcing the switch into "dumb hub" mode:

```python
import random

def mac_flooding_attack(sw: Switch, num_fake_frames: int = 50) -> None:
    """
    Simulate a MAC flooding attack: send frames with random source MACs
    to fill the forwarding table. On a real switch, this causes all
    unicast traffic to be flooded (making eavesdropping possible).
    """
    print(f"\n{'=' * 60}")
    print(f"MAC FLOODING ATTACK: sending {num_fake_frames} fake frames")
    print(f"{'=' * 60}")

    for i in range(num_fake_frames):
        # Generate a random source MAC
        fake_mac = ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))
        fake_frame = EthernetFrame(
            src_mac=fake_mac,
            dst_mac="ff:ff:ff:ff:ff:ff",
            payload=f"fake-{i}",
            incoming_port=random.randint(1, 4),
        )
        sw.forwarding_table[fake_mac] = ForwardingTableEntry(port=random.randint(1, 4))

    print(f"Forwarding table now has {len(sw.forwarding_table)} entries")
    print("(Real switches have limited CAM table size — this overflows it)")
```

Add a call to `mac_flooding_attack(sw, 50)` at the end of `run_simulation()` and re-run.

## Exercises

1. **Entry expiry** — Modify the simulation to use a max age of 5 seconds (`ForwardingTableEntry.is_expired(max_age_seconds=5.0)`). Add a `time.sleep(6)` between two scenarios involving the same MAC pair and observe the switch re-flooding because the entry expired.

2. **Multi-switch topology** — Create two switches (SW1 with 3 ports, SW2 with 3 ports) and connect port 3 of SW1 to port 1 of SW2 (this is called a trunk or uplink). Write a `TwoSwitchNetwork` class and route a frame from a host on SW1 to a host on SW2.

3. **STP awareness** — Research Spanning Tree Protocol (STP). What problem does STP solve? What happens if you connect two switches together with two cables without STP? (Answer: broadcast storm — frames loop forever, saturating the network.)

4. **Unknown unicast statistics** — Add a counter to the `Switch` class that tracks: total frames received, total floods, total direct forwards. Run the simulation and print the ratio of floods to direct forwards. How does it change as the table fills?

5. **Port security** — Add a feature where each port can have a maximum number of allowed MAC addresses. If a new MAC appears on a port that already has its maximum, the switch either drops the frame or disables the port (like a real switch's "port security" feature).

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| CAM table | "switch table", "MAC table" | Content Addressable Memory table. The hardware data structure in a real switch that maps MAC addresses to port numbers. Can be looked up by content (MAC address) in a single hardware clock cycle. In software simulations, a dictionary is a reasonable substitute. |
| flooding | "broadcasting on a switch" | The act of sending a frame out every port except the incoming port. Done when the destination MAC is unknown, multicast, or broadcast. Flooding is how switches handle frames before they have learned the destination. |
| MAC learning | "dynamic MAC learning" | The process by which a switch observes the source MAC address of incoming frames and records the association between that MAC and the incoming port. Requires no configuration — switches learn automatically. |
| CAM overflow | "MAC flooding attack" | An attack where a malicious host sends frames with thousands of different source MACs, filling the switch's CAM table. Once full, the switch cannot learn new MACs and floods all unicast traffic — allowing the attacker to see all network traffic like a hub. |
| uplink | "trunk port" | A port connecting one switch to another switch (or to a router). Carries traffic for all VLANs and multiple MAC addresses. Distinguished from access ports, which connect to a single end host. |

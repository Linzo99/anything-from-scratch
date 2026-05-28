# Detect ARP Spoofing

> ARP has no authentication — anyone on your LAN can claim to be anyone else, and Python can catch them doing it.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 2, Lesson 01 — ARP and Layer 2 Addressing
**Time:** ~45 minutes

## Learning Objectives
- Explain how ARP cache poisoning enables a man-in-the-middle attack
- Use Scapy to sniff ARP reply packets on a network interface
- Maintain a MAC-to-IP mapping table and detect when it changes unexpectedly
- Generate an alert with timestamp, old MAC, new MAC, and IP when poisoning is detected
- Test the detector against a simulated ARP spoofing scenario

## The Problem

ARP (Address Resolution Protocol) translates IP addresses to MAC addresses on a local network. When your laptop wants to send a packet to 192.168.1.1 (your router), it broadcasts: "Who has 192.168.1.1?" The router replies: "I do — my MAC is aa:bb:cc:dd:ee:ff." Your laptop caches this mapping and uses it for the next few minutes.

The problem: ARP has no authentication. Any machine on the network can send an ARP reply claiming "I am 192.168.1.1, and my MAC is XX:XX:XX:XX:XX:XX." Machines accept these replies even without asking. An attacker can continuously broadcast fake ARP replies, poisoning every host's ARP cache. Once the cache is poisoned, traffic meant for the router flows to the attacker's machine instead. This is a man-in-the-middle attack.

With a MITM position, the attacker can read, modify, or drop packets. They can capture passwords, inject content into HTTP responses, and intercept credentials. The attack is completely invisible to the victim — connections appear to work normally while being intercepted.

## The Concept

### How ARP Poisoning Works

```
Normal ARP:
  Victim (10.0.0.2)  ──[Who has 10.0.0.1?]──────►  [Broadcast]
  Router (10.0.0.1)  ◄──[10.0.0.1 is at AA:BB]───  Router responds

After ARP Poisoning:
  Attacker (10.0.0.3) ──[10.0.0.1 is at CC:DD]──►  Victim (gratuitous ARP)
  Attacker (10.0.0.3) ──[10.0.0.2 is at CC:DD]──►  Router (gratuitous ARP)

Now:
  Victim sends packets for 10.0.0.1 → actually go to Attacker (CC:DD)
  Router sends packets for 10.0.0.2 → actually go to Attacker (CC:DD)
  Attacker forwards packets both ways → invisible MITM
```

The attack uses **gratuitous ARP** — ARP replies sent without a corresponding request. Hosts accept them and update their caches. It takes only one reply every ~30 seconds to keep the cache poisoned.

### What a Detector Does

A detector watches all ARP replies on the network. For each reply, it checks: "Have I seen this IP before with a different MAC?" If yes, emit an alert. The core logic is simple:

```python
arp_table = {}   # { ip_address: mac_address }

for each ARP reply:
    ip  = reply.psrc    # sender's IP
    mac = reply.hwsrc   # sender's MAC

    if ip in arp_table:
        if arp_table[ip] != mac:
            ALERT: IP changed MAC!  possible spoofing
    
    arp_table[ip] = mac
```

### Scapy: Python Packet Library

Scapy is a Python library that can craft, send, capture, and decode packets at a very low level. Its `sniff()` function captures live packets from an interface with an optional filter and calls a callback for each one.

```python
from scapy.all import sniff, ARP

def handle_packet(pkt):
    if pkt.haslayer(ARP):
        print(pkt[ARP].psrc, pkt[ARP].hwsrc)

sniff(filter="arp", prn=handle_packet, store=False)
```

The `filter` string uses BPF (Berkeley Packet Filter) syntax — the same filter language used by `tcpdump`.

### Limitations of Simple Detection

A MAC change is not always an attack:
- A device might get a new NIC (genuine MAC change)
- DHCP lease renewal might assign the same IP to a different device
- Virtual machines frequently change their MAC addresses

A robust detector compares against known-good MAC addresses (a whitelist) or rates alerts based on how quickly the MAC changes (a single change is suspicious; ten changes per second is almost certainly an attack).

## Build It

Install Scapy:

```bash
pip3 install scapy
```

Save the detector as `arp_detector.py`:

```python
#!/usr/bin/env python3
"""
ARP Spoofing Detector
Monitors ARP replies on an interface and alerts when a MAC-to-IP mapping changes.

Usage: sudo python3 arp_detector.py [interface]
       sudo python3 arp_detector.py eth0
       sudo python3 arp_detector.py   # uses default interface
"""
import sys
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from scapy.all import ARP, Ether, sniff, get_if_list

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("arp-detector")


@dataclass
class ARPEntry:
    """One tracked IP → MAC binding."""
    ip:          str
    mac:         str
    first_seen:  float = field(default_factory=time.time)
    last_seen:   float = field(default_factory=time.time)
    change_count: int  = 0


class ARPDetector:
    """
    Watches ARP traffic and alerts on unexpected MAC changes.
    """

    def __init__(self, interface: Optional[str] = None, whitelist: Optional[dict] = None):
        self.interface = interface
        # whitelist: { "192.168.1.1": "aa:bb:cc:dd:ee:ff", ... }
        self.whitelist: dict = whitelist or {}
        # Observed mappings: { ip_str: ARPEntry }
        self.table:     dict = {}
        self.alert_count = 0

    def _check_packet(self, pkt) -> None:
        """
        Called for every captured packet.
        Only processes ARP opcode 2 (reply) — that is what carries binding info.
        """
        if not pkt.haslayer(ARP):
            return

        arp = pkt[ARP]

        # ARP opcode: 1 = request, 2 = reply
        # We care about replies (and gratuitous ARPs, which have op=1 but psrc==pdst)
        is_reply      = (arp.op == 2)
        is_gratuitous = (arp.op == 1 and arp.psrc == arp.pdst)

        if not (is_reply or is_gratuitous):
            return

        sender_ip  = arp.psrc
        sender_mac = arp.hwsrc.lower()

        # Ignore broadcast MAC and zero MAC (malformed packets)
        if sender_mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"):
            return

        # Check against whitelist
        if sender_ip in self.whitelist:
            expected_mac = self.whitelist[sender_ip].lower()
            if sender_mac != expected_mac:
                self._alert_whitelist_violation(sender_ip, sender_mac, expected_mac)
                return

        existing = self.table.get(sender_ip)

        if existing is None:
            # First time we see this IP
            entry = ARPEntry(ip=sender_ip, mac=sender_mac)
            self.table[sender_ip] = entry
            log.info(f"Learned   {sender_ip:<18} → {sender_mac}")
        elif existing.mac != sender_mac:
            # MAC has changed — potential spoofing
            existing.change_count += 1
            existing.last_seen     = time.time()
            self._alert_mac_change(sender_ip, existing.mac, sender_mac, existing.change_count)
            existing.mac = sender_mac   # update to new MAC
        else:
            # Same MAC seen again — just refresh
            existing.last_seen = time.time()

    def _alert_mac_change(self, ip: str, old_mac: str, new_mac: str, count: int) -> None:
        self.alert_count += 1
        severity = "CRITICAL" if count > 3 else "WARNING"
        log.warning(
            f"[{severity}] ARP MAC change detected! "
            f"IP={ip}  OLD={old_mac}  NEW={new_mac}  "
            f"(change #{count})"
        )
        if count > 3:
            log.warning(
                f"  IP {ip} has changed MAC {count} times — likely ongoing ARP poisoning attack!"
            )

    def _alert_whitelist_violation(self, ip: str, seen_mac: str, expected_mac: str) -> None:
        self.alert_count += 1
        log.error(
            f"[WHITELIST VIOLATION] IP={ip} "
            f"expected MAC={expected_mac} but got MAC={seen_mac} — SPOOFING DETECTED"
        )

    def start(self) -> None:
        iface_str = self.interface or "default interface"
        log.info(f"ARP Detector starting on {iface_str}")
        log.info(f"Whitelist entries: {len(self.whitelist)}")
        log.info("Press Ctrl+C to stop.\n")

        try:
            sniff(
                iface=self.interface,
                filter="arp",
                prn=self._check_packet,
                store=False,
            )
        except KeyboardInterrupt:
            pass
        finally:
            self._print_summary()

    def _print_summary(self) -> None:
        log.info("\n── Summary ──────────────────────────────────────────")
        log.info(f"  Tracked IPs : {len(self.table)}")
        log.info(f"  Alerts fired: {self.alert_count}")
        if self.table:
            log.info("  Final ARP table:")
            for ip, entry in sorted(self.table.items()):
                age = int(time.time() - entry.first_seen)
                log.info(
                    f"    {ip:<18} → {entry.mac}  "
                    f"(first seen {age}s ago, changes={entry.change_count})"
                )


def main():
    interface = sys.argv[1] if len(sys.argv) > 1 else None

    # Optional hardcoded whitelist — edit to match your network
    # whitelist = {
    #     "192.168.1.1":  "aa:bb:cc:dd:ee:ff",  # your router
    #     "192.168.1.100": "11:22:33:44:55:66",  # your NAS
    # }
    whitelist = {}

    if interface and interface not in get_if_list():
        print(f"Error: interface '{interface}' not found.")
        print(f"Available: {', '.join(get_if_list())}")
        sys.exit(1)

    detector = ARPDetector(interface=interface, whitelist=whitelist)
    detector.start()


if __name__ == "__main__":
    main()
```

### Testing the Detector

Run the detector in one terminal (requires root/sudo for raw socket capture):

```bash
sudo python3 arp_detector.py eth0   # replace eth0 with your interface
```

In a second terminal, simulate ARP spoofing using Scapy:

```bash
# Simulate an attacker sending a fake ARP reply
# claiming that 192.168.1.1 has MAC 11:22:33:44:55:66
sudo python3 -c "
from scapy.all import ARP, Ether, sendp
import time

# First, send a legitimate-looking ARP
legitimate = Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(op=2, psrc='192.168.1.1', hwsrc='aa:bb:cc:dd:ee:ff', pdst='0.0.0.0')
sendp(legitimate, verbose=False)
print('Sent legitimate ARP: 192.168.1.1 -> aa:bb:cc:dd:ee:ff')
time.sleep(2)

# Now send the spoofed ARP (different MAC for same IP)
spoofed = Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(op=2, psrc='192.168.1.1', hwsrc='11:22:33:44:55:66', pdst='0.0.0.0')
sendp(spoofed, verbose=False)
print('Sent spoofed ARP:  192.168.1.1 -> 11:22:33:44:55:66')
"
```

You should see the detector print a WARNING alert in the first terminal.

### Adding a Whitelist

Edit the `whitelist` dictionary in `main()` to add your router's real MAC:

```python
whitelist = {
    "192.168.1.1": "your:real:router:mac:here:xx",
}
```

Any ARP reply claiming to be 192.168.1.1 with a different MAC will trigger a WHITELIST VIOLATION error. Find your router's real MAC with:

```bash
arp -n 192.168.1.1   # after pinging the router once
# or
ip neigh show | grep 192.168.1.1
```

## Exercises

1. **Rate-based detection**: Modify the detector to track how many times per minute a given IP changes its MAC. If more than 5 changes in 60 seconds, escalate to CRITICAL and print "Active attack in progress."

2. **Detect spoofing of your own IP**: Add logic to check if an ARP reply claims your own IP address with someone else's MAC. This means someone is trying to impersonate you.

3. **Passive ARP table builder**: Extend the detector to also record ARP requests (opcode 1) and show which IPs are actively querying the network. This reveals what hosts are present even before they send replies.

4. **Log to a file**: Add a `FileHandler` to the logger that writes all alerts to `/var/log/arp-detector.log`. Include the raw packet info (src IP, src MAC, interface).

5. **Compare with `arpwatch`**: Install `arpwatch` (`apt install arpwatch`) and run it alongside your detector. Feed the same spoofed ARP packets. Do both tools fire alerts? What different information does each report?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| ARP spoofing | "ARP poisoning" | Sending fake ARP replies to corrupt a host's ARP cache so it associates the wrong MAC with an IP |
| Gratuitous ARP | "gARP" | An ARP reply sent without a prior request; used legitimately for IP conflict detection but abused in poisoning attacks |
| MITM | "man in the middle" | An attacker positioned between two communicating parties, able to read and modify traffic |
| ARP cache | "ARP table" | A short-lived mapping of IP → MAC stored in every host's OS; populated by ARP replies |
| BPF filter | "pcap filter" | Berkeley Packet Filter syntax used by tcpdump, Wireshark, and Scapy to select which packets to capture |
| Whitelist | "allowlist" | A set of known-good IP→MAC bindings; any deviation triggers an alert |

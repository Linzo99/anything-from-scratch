# Implement a Port Knocker

> SSH is invisible until you knock on three secret ports in the right order — then it opens for 30 seconds.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 7, Lesson 02 — Write iptables Firewall Rules
**Time:** ~50 minutes

## Learning Objectives
- Explain how port knocking hides a service from port scanners
- Write a Python pcap daemon that watches for a knock sequence
- Open a firewall rule for the knocking IP after the correct sequence
- Automatically close the rule after a configurable timeout
- Test the mechanism with a client-side knock script

## The Problem

SSH is the most attacked service on the Internet. Every machine with port 22 open receives brute-force login attempts within minutes. Even with strong passwords and key authentication, the attack traffic wastes bandwidth and clutters logs.

One defence is port knocking: the SSH port is permanently closed in the firewall. To open it, you send a sequence of connection attempts to specific ports (the "knock"). The server's knock daemon sees the sequence and opens port 22 — but only for your IP address, and only for 30 seconds. Then it closes again. A port scanner sees all ports closed; it has no way to know SSH exists.

Port knocking is security through obscurity — it is not a replacement for strong SSH authentication. But it eliminates the brute-force noise and reduces attack surface.

## The Concept

### How Port Knocking Works

```
Client                          Server
  │                               │
  │  SYN ──► port 7000            │  ← closed; SYN silently dropped
  │  SYN ──► port 8000            │  ← closed; SYN silently dropped
  │  SYN ──► port 9000            │  ← closed; SYN silently dropped
  │                               │
  │            Knock daemon sees the sequence [7000, 8000, 9000]
  │            from IP 203.0.113.5 within 10 seconds
  │            → runs: iptables -A INPUT -s 203.0.113.5 -p tcp --dport 22 -j ACCEPT
  │
  │  SYN ──► port 22              │  ← NOW OPEN for this IP
  │  SSH session established ◄────┤
  │                               │
  │  [30 seconds later]           │
  │                               │  → iptables -D INPUT ... (rule removed)
  │  Port 22 is closed again      │
```

### The Daemon Design

The daemon needs to:
1. **Capture packets** on the server's interface — even packets that will be dropped by iptables. The daemon uses `pcap` to see rejected packets before the firewall acts on them.
2. **Track knock sequences** per source IP with timestamps.
3. **Open the firewall** when the full sequence is seen within the window.
4. **Expire rules** automatically after the timeout.

Python's `scapy` gives us pcap capture. `subprocess.run(["iptables", ...])` manages the firewall rules. A background thread handles rule expiry.

### Why pcap, not a Service on Each Port?

You could open a Python server on ports 7000, 8000, and 9000. But:
- These ports would show as `open` in an nmap scan (defeating the purpose)
- Services on those ports would receive the full TCP connection overhead

pcap captures the SYN packet before the kernel processes it. The firewall's DROP rule still fires — the packet is dropped. The daemon just read a copy of the packet at the kernel level. The ports appear `filtered` to any scanner.

## Build It

Install dependencies:

```bash
pip3 install scapy
```

Save the daemon as `knockd.py`:

```python
#!/usr/bin/env python3
"""
Port knocking daemon.
Watches for a TCP SYN knock sequence and opens a firewall rule for the source IP.

Usage: sudo python3 knockd.py

Configuration is at the top of this file.
"""
import subprocess
import threading
import time
import logging
from collections import defaultdict
from typing import Optional

from scapy.all import IP, TCP, sniff

# ── Configuration ─────────────────────────────────────────────────────────────
KNOCK_SEQUENCE  = [7000, 8000, 9000]   # ports to knock, in this order
KNOCK_WINDOW    = 10.0                 # seconds: all knocks must arrive within this window
OPEN_PORT       = 22                   # port to open after correct knock
OPEN_DURATION   = 30.0                 # seconds to keep the port open
INTERFACE       = None                 # None = all interfaces, or "eth0" etc.
LOG_LEVEL       = logging.INFO
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("knockd")


class KnockState:
    """Tracks knock progress for one source IP."""

    def __init__(self):
        self.progress:    int   = 0      # index into KNOCK_SEQUENCE
        self.first_knock: float = 0.0    # timestamp of first knock in current attempt


class KnockDaemon:
    def __init__(self):
        # { src_ip: KnockState }
        self._states: dict = defaultdict(KnockState)
        # { src_ip: expiry_time }
        self._open_rules: dict = {}
        self._lock = threading.Lock()
        self._running = True

    # ── Packet processing ──────────────────────────────────────────────────

    def _process(self, pkt) -> None:
        """Called for every captured packet."""
        if not (pkt.haslayer(IP) and pkt.haslayer(TCP)):
            return

        ip_layer  = pkt[IP]
        tcp_layer = pkt[TCP]

        # Only care about SYN packets (flags=0x02 = SYN, not SYN-ACK)
        if tcp_layer.flags != 0x02:
            return

        src_ip   = ip_layer.src
        dst_port = tcp_layer.dport

        with self._lock:
            self._handle_knock(src_ip, dst_port)

    def _handle_knock(self, src_ip: str, port: int) -> None:
        """
        Advance knock state for src_ip if port matches next expected knock.
        Thread must hold self._lock.
        """
        state    = self._states[src_ip]
        now      = time.time()
        expected = KNOCK_SEQUENCE[state.progress]

        if port == expected:
            if state.progress == 0:
                # First knock — start the window timer
                state.first_knock = now
                log.debug(f"{src_ip}: knock 1/{len(KNOCK_SEQUENCE)} (port {port})")
            else:
                elapsed = now - state.first_knock
                if elapsed > KNOCK_WINDOW:
                    # Window expired — restart
                    log.debug(f"{src_ip}: window expired, resetting (elapsed {elapsed:.1f}s)")
                    state.progress   = 0
                    state.first_knock = now
                    return
                log.debug(
                    f"{src_ip}: knock {state.progress + 1}/{len(KNOCK_SEQUENCE)} (port {port})"
                )

            state.progress += 1

            if state.progress == len(KNOCK_SEQUENCE):
                # Full sequence received
                state.progress = 0
                self._open_firewall(src_ip)
        else:
            # Wrong port — does NOT reset. Partial sequences just stay.
            # (Some implementations reset on wrong port; this one is lenient.)
            pass

    # ── Firewall management ────────────────────────────────────────────────

    def _open_firewall(self, src_ip: str) -> None:
        """
        Add an iptables rule allowing src_ip to reach OPEN_PORT.
        Schedules automatic removal after OPEN_DURATION seconds.
        """
        log.info(
            f"{src_ip}: correct knock sequence — opening port {OPEN_PORT} "
            f"for {OPEN_DURATION:.0f}s"
        )
        cmd = [
            "iptables", "-I", "INPUT", "1",
            "-s", src_ip,
            "-p", "tcp",
            "--dport", str(OPEN_PORT),
            "-j", "ACCEPT",
            "-m", "comment",
            "--comment", f"knockd:{src_ip}",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            log.error(f"iptables error: {e.stderr.decode().strip()}")
            return

        expiry = time.time() + OPEN_DURATION
        with self._lock:
            self._open_rules[src_ip] = expiry

        # Schedule removal
        t = threading.Timer(OPEN_DURATION, self._close_firewall, args=[src_ip])
        t.daemon = True
        t.start()

    def _close_firewall(self, src_ip: str) -> None:
        """Remove the iptables rule for src_ip."""
        cmd = [
            "iptables", "-D", "INPUT",
            "-s", src_ip,
            "-p", "tcp",
            "--dport", str(OPEN_PORT),
            "-j", "ACCEPT",
            "-m", "comment",
            "--comment", f"knockd:{src_ip}",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            log.info(f"{src_ip}: port {OPEN_PORT} closed (timer expired)")
        except subprocess.CalledProcessError as e:
            log.warning(f"Could not remove iptables rule for {src_ip}: {e.stderr.decode().strip()}")

        with self._lock:
            self._open_rules.pop(src_ip, None)

    # ── Main loop ──────────────────────────────────────────────────────────

    def run(self) -> None:
        log.info(f"Port knock daemon starting")
        log.info(f"  Sequence : {KNOCK_SEQUENCE}")
        log.info(f"  Window   : {KNOCK_WINDOW}s")
        log.info(f"  Opens    : port {OPEN_PORT} for {OPEN_DURATION}s")
        log.info(f"  Interface: {INTERFACE or 'all'}")
        log.info("Press Ctrl+C to stop.\n")

        # BPF filter: capture SYN packets on any of the knock ports OR the open port
        # We capture on knock ports to see the sequence.
        ports = KNOCK_SEQUENCE + [OPEN_PORT]
        port_filter = " or ".join(f"port {p}" for p in ports)
        bpf = f"tcp[tcpflags] & tcp-syn != 0 and ({port_filter})"

        try:
            sniff(
                iface=INTERFACE,
                filter=bpf,
                prn=self._process,
                store=False,
            )
        except KeyboardInterrupt:
            pass
        finally:
            log.info("Daemon stopped.")


if __name__ == "__main__":
    daemon = KnockDaemon()
    daemon.run()
```

### Setting Up the Firewall Before Running

Before starting the daemon, block SSH by default (the daemon will open it selectively):

```bash
# Block port 22 for all sources
sudo iptables -A INPUT -p tcp --dport 22 -j DROP

# Verify it's blocked
nc -w2 127.0.0.1 22
# Should time out (no response)
```

Run the daemon:

```bash
sudo python3 knockd.py
```

### Client-Side Knock Script

Save as `knock.sh`:

```bash
#!/usr/bin/env bash
# Usage: bash knock.sh <server_ip>
# Sends the three-port knock sequence to the server.

SERVER=${1:?Usage: knock.sh <server_ip>}
SEQUENCE=(7000 8000 9000)

echo "Knocking on $SERVER: ${SEQUENCE[*]}"

for port in "${SEQUENCE[@]}"; do
  # nmap sends one SYN packet to the port; -Pn skips ping, --host-timeout kills quickly
  # Alternatively use nc with a very short timeout:
  nc -w1 -z "$SERVER" "$port" 2>/dev/null || true
  echo "  Knocked: $port"
  sleep 0.3   # small delay between knocks
done

echo "Knock sequence sent. Attempting SSH..."
sleep 1
ssh "$SERVER"
```

Test it:

```bash
# Terminal 1: Run the daemon
sudo python3 knockd.py

# Terminal 2: Knock and connect
bash knock.sh 127.0.0.1
```

You should see the daemon log the sequence being recognised, the firewall rule being added, SSH connecting successfully, and the rule being removed 30 seconds later.

### Verify the Firewall Rule

While the port is open:

```bash
sudo iptables -L INPUT -n | grep knockd
# Should show: ACCEPT tcp -- 127.0.0.1 ... dport:22 /* knockd:127.0.0.1 */
```

After 30 seconds:

```bash
sudo iptables -L INPUT -n | grep knockd
# Should be empty — rule was removed
```

## Exercises

1. **Add a time-of-day restriction**: Modify the daemon to only process knock sequences during business hours (08:00–18:00 local time). Knocks outside this window are silently ignored.

2. **Support multiple users**: Add a second knock sequence `[9000, 8000, 7000]` that opens a different port (e.g., 8080) or for a different duration. Use a config dictionary mapping sequences to actions.

3. **Log knock attempts to a file**: Write all knock attempts (IP, port, timestamp, whether the knock advanced the sequence) to a JSON lines file. This creates an audit trail.

4. **Implement sequence reset on wrong port**: In the current implementation, wrong-port knocks are ignored. Change it to reset the sequence when a wrong port is seen. What is the security trade-off? (Hint: denial-of-service by flooding knock ports.)

5. **One-time-use sequence**: After a knock sequence is used once, generate a new sequence (e.g., three random ports between 1024 and 65535) and write it to a file that the client must download via SSH. This makes replay attacks impossible.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Port knocking | "knock sequence" | Sending connection attempts to a specific sequence of closed ports to trigger a firewall rule opening |
| pcap | "packet capture" | Library-level access to raw network packets, including packets that will be dropped by the firewall |
| Gratuitous capture | "promiscuous mode" | Capturing all packets on an interface, even those not addressed to this host |
| -I INPUT 1 | "insert rule at top" | Inserts a new iptables rule at position 1 (the top), so it is checked before existing rules |
| Security through obscurity | "STO" | Hiding a service rather than hardening it; not a substitute for strong authentication but reduces noise |
| BPF | "Berkeley Packet Filter" | A kernel-level packet filtering language; Scapy and tcpdump both use BPF syntax for efficient filtering |

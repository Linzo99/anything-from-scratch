# Trace a Packet with TTL

> Traceroute is just a trick: send packets that are designed to die at each hop, collect the error messages, and you have a map of the path.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 2, Lesson 03 — Parse an IPv4 Header
**Time:** ~50 minutes

## Learning Objectives
- Explain how TTL manipulation reveals intermediate routers
- Create raw ICMP echo request packets using Python's `struct` module
- Use raw sockets to send packets with a specified TTL
- Parse ICMP Time Exceeded and Echo Reply responses
- Implement a working minimal traceroute with per-hop RTT measurement

## The Problem

Your application connects to a server and the connection hangs. Is it your machine? Your ISP? A backbone router? The destination server? Without traceroute, you cannot distinguish these cases.

Traceroute is available on every operating system, but most engineers use it as a black box. The fact that it works through TTL manipulation is not obvious — and understanding it reveals a lot about how routers actually work. When you implement it yourself you also see the edge cases: hops that do not respond, firewalls that block ICMP, routers that are multiple hops but show the same IP.

This lesson builds a minimal but functional traceroute from scratch using only Python's standard library and raw sockets.

## The Concept

### The TTL trick

Every IPv4 packet has a TTL field that is decremented by each router. When TTL hits 0, the router:
1. Discards the packet.
2. Sends an **ICMP Time Exceeded** message back to the original source.
3. The ICMP message includes (in its payload) the first 28 bytes of the discarded packet — the IPv4 header + 8 bytes of the original payload.

Traceroute exploits this:

```
Source                    Router 1      Router 2      Destination
  |                           |             |              |
  |--- TTL=1 probe ---------->|             |              |
  |    (discarded at R1)      |             |              |
  |<-- ICMP Time Exceeded ----|             |              |
  |    from R1's address      |             |              |
  |                           |             |              |
  |--- TTL=2 probe ---------->|------------>|              |
  |    (discarded at R2)                    |              |
  |<-- ICMP Time Exceeded ------------------|              |
  |    from R2's address                                   |
  |                                                        |
  |--- TTL=3 probe ---------->------------>--------------->|
  |                                                        | (reached!)
  |<-- ICMP Echo Reply ------------------------------------|
```

By starting at TTL=1 and incrementing by 1 each time, we hear from each router in order. The router's IP address is in the ICMP Time Exceeded's source IP field.

### ICMP packet structure

ICMP is carried in an IPv4 payload (Protocol = 1). An ICMP Echo Request (ping) looks like:

```
 0       7 8      15 16     23 24     31
+---------+---------+---------+---------+
|  Type=8 |  Code=0 |      Checksum     |
+---------+---------+---------+---------+
|     Identifier    |  Sequence Number  |
+-------------------+-------------------+
|                 Data ...              |
+---------------------------------------+
```

- Type 8, Code 0 = Echo Request
- Type 0, Code 0 = Echo Reply
- Type 11, Code 0 = Time Exceeded (TTL expired in transit)

ICMP checksum covers the entire ICMP message (header + data).

### ICMP checksum algorithm

```python
def checksum(data: bytes) -> int:
    """
    One's complement sum of all 16-bit words.
    If the data has an odd number of bytes, pad with a zero byte.
    """
    if len(data) % 2 != 0:
        data += b'\x00'
    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
    # Fold 32-bit sum into 16 bits
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF
```

### Raw sockets

A raw socket (`SOCK_RAW`) bypasses the OS transport layer and lets you send and receive raw IP payloads. For ICMP, you open a raw socket with protocol `IPPROTO_ICMP`. You set socket options to control the TTL.

On Linux/macOS, raw sockets require root (or `CAP_NET_RAW` capability). That is why `ping` and `traceroute` have the setuid bit set.

### The Time Exceeded response

When a router returns an ICMP Time Exceeded, the structure is:

```
IPv4 header (20 bytes) — from router to us
ICMP header (8 bytes)  — Type=11, Code=0, Checksum, unused
IPv4 header (20 bytes) — the ORIGINAL packet's IP header
8 bytes of original payload — first 8 bytes of our probe's ICMP header
```

The original payload contains our Identifier and Sequence Number, which lets us match the response to the probe that triggered it.

## Build It

Create `traceroute.py`. This requires root to run:

```python
#!/usr/bin/env python3
"""
traceroute.py — minimal TTL-based traceroute.

Usage (requires root / sudo):
    sudo python3 traceroute.py 8.8.8.8
    sudo python3 traceroute.py example.com --max-hops 20 --timeout 2 --probes 3
"""

import socket
import struct
import time
import os
import argparse
import sys


# ── ICMP constants ────────────────────────────────────────────────────────────

ICMP_ECHO_REQUEST  = 8
ICMP_ECHO_REPLY    = 0
ICMP_TIME_EXCEEDED = 11


# ── checksum ──────────────────────────────────────────────────────────────────

def checksum(data: bytes) -> int:
    """
    Compute the one's-complement checksum used by ICMP.
    Works by summing all 16-bit words, then folding carries back in.
    """
    if len(data) % 2 != 0:
        data += b'\x00'
    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
    # Fold carries
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


# ── packet construction ───────────────────────────────────────────────────────

def build_icmp_echo(identifier: int, sequence: int, payload_size: int = 32) -> bytes:
    """
    Build an ICMP Echo Request packet.

    Structure:
      B  type       (8 = echo request)
      B  code       (0)
      H  checksum   (computed after zeroing this field)
      H  identifier (unique to this process/session)
      H  sequence   (increments per probe)
      Xs payload    (arbitrary data, we use timestamp for RTT calculation)
    """
    # Embed the send timestamp in the payload for RTT calculation
    timestamp = time.time()
    padding = b'\x42' * max(0, payload_size - 8)  # fill remaining bytes
    payload = struct.pack("!d", timestamp) + padding  # 8-byte double + padding

    # Build header with checksum=0 first
    header = struct.pack("!BBHHH",
        ICMP_ECHO_REQUEST,  # type
        0,                  # code
        0,                  # checksum placeholder
        identifier,
        sequence,
    )

    # Compute checksum over header + payload
    chk = checksum(header + payload)

    # Rebuild header with real checksum
    header = struct.pack("!BBHHH",
        ICMP_ECHO_REQUEST,
        0,
        chk,
        identifier,
        sequence,
    )
    return header + payload


# ── response parsing ──────────────────────────────────────────────────────────

def parse_icmp_response(raw: bytes, identifier: int, sequence: int):
    """
    Parse a raw packet received on an ICMP socket.
    Returns ('reply', src_ip, rtt_ms) or ('exceeded', src_ip, rtt_ms) or None.

    The raw bytes include the IP header, so we skip it:
      - IP header is IHL*4 bytes
      - ICMP header starts right after
    """
    if len(raw) < 20:
        return None

    # Parse IP header to find ICMP start
    ihl = (raw[0] & 0x0F) * 4  # IHL in lower nibble, × 4 for bytes
    if len(raw) < ihl + 8:
        return None

    icmp_start = ihl
    icmp_type = raw[icmp_start]
    icmp_code = raw[icmp_start + 1]

    # Source IP is at bytes 12-15 of the IP header
    src_ip = socket.inet_ntoa(raw[12:16])

    if icmp_type == ICMP_ECHO_REPLY:
        # Check that this reply matches our identifier and sequence
        if len(raw) < icmp_start + 8 + 8:
            return None
        resp_id  = struct.unpack("!H", raw[icmp_start + 4 : icmp_start + 6])[0]
        resp_seq = struct.unpack("!H", raw[icmp_start + 6 : icmp_start + 8])[0]
        if resp_id != identifier or resp_seq != sequence:
            return None
        # Extract timestamp from payload
        ts_bytes = raw[icmp_start + 8 : icmp_start + 16]
        if len(ts_bytes) == 8:
            send_time = struct.unpack("!d", ts_bytes)[0]
            rtt = (time.time() - send_time) * 1000
        else:
            rtt = -1
        return ("reply", src_ip, rtt)

    elif icmp_type == ICMP_TIME_EXCEEDED and icmp_code == 0:
        # ICMP Time Exceeded payload = original IP header + 8 bytes original ICMP
        # Original IP header starts at icmp_start + 8
        orig_ip_start = icmp_start + 8
        if len(raw) < orig_ip_start + 20 + 8:
            return None
        orig_ihl = (raw[orig_ip_start] & 0x0F) * 4
        orig_icmp_start = orig_ip_start + orig_ihl
        if len(raw) < orig_icmp_start + 8:
            return None
        # Original ICMP: type(1) + code(1) + checksum(2) + id(2) + seq(2)
        orig_id  = struct.unpack("!H", raw[orig_icmp_start + 4 : orig_icmp_start + 6])[0]
        orig_seq = struct.unpack("!H", raw[orig_icmp_start + 6 : orig_icmp_start + 8])[0]
        if orig_id != identifier or orig_seq != sequence:
            return None
        return ("exceeded", src_ip, -1)   # no RTT because we don't have the timestamp

    return None


# ── main traceroute loop ──────────────────────────────────────────────────────

def traceroute(destination: str, max_hops: int = 30,
               timeout: float = 3.0, probes: int = 3):
    """
    Send ICMP echo requests with increasing TTL values.
    Print the IP of each responding router (or * for timeouts).
    """
    # Resolve hostname to IP
    try:
        dest_ip = socket.gethostbyname(destination)
    except socket.gaierror as e:
        print(f"Cannot resolve {destination!r}: {e}")
        sys.exit(1)

    print(f"\ntraceroute to {destination} ({dest_ip}), {max_hops} hops max")
    print(f"using ICMP echo, {probes} probes per hop, timeout {timeout}s\n")

    # Use the process ID as the ICMP identifier (fits in 16 bits)
    identifier = os.getpid() & 0xFFFF

    # Create a raw ICMP socket for sending
    try:
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        print("Error: raw sockets require root. Run with: sudo python3 traceroute.py ...")
        sys.exit(1)

    # Create a raw ICMP socket for receiving
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    recv_sock.settimeout(timeout)

    sequence = 0
    reached = False

    for ttl in range(1, max_hops + 1):
        # Set TTL on the send socket for this hop
        send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)

        hop_results = []

        for probe in range(probes):
            sequence += 1
            packet = build_icmp_echo(identifier, sequence)
            send_time = time.time()

            send_sock.sendto(packet, (dest_ip, 0))

            # Wait for a response
            result_ip = None
            result_type = None
            rtt_ms = None

            deadline = send_time + timeout
            while time.time() < deadline:
                remaining = deadline - time.time()
                recv_sock.settimeout(max(0.001, remaining))
                try:
                    raw, addr = recv_sock.recvfrom(1024)
                    recv_time = time.time()
                    parsed = parse_icmp_response(raw, identifier, sequence)
                    if parsed:
                        result_type, result_ip, rtt_ms = parsed
                        if rtt_ms < 0:
                            rtt_ms = (recv_time - send_time) * 1000
                        break
                except socket.timeout:
                    break

            if result_ip:
                hop_results.append((result_ip, rtt_ms, result_type))
                if result_type == "reply":
                    reached = True
            else:
                hop_results.append(None)

        # Print this hop
        # Gather unique IPs that responded
        ips = [r[0] for r in hop_results if r is not None]
        unique_ips = list(dict.fromkeys(ips))  # preserve order, deduplicate

        if not unique_ips:
            # All probes timed out
            print(f"  {ttl:>2}   * * *")
        else:
            # Try to resolve hostname (non-blocking, best-effort)
            resolved = {}
            for ip in unique_ips:
                try:
                    host = socket.gethostbyaddr(ip)[0]
                    resolved[ip] = host
                except socket.herror:
                    resolved[ip] = ip

            # Print RTTs for each probe
            rtt_parts = []
            last_ip = None
            for r in hop_results:
                if r is None:
                    rtt_parts.append("*")
                else:
                    ip, rtt, rtype = r
                    if ip != last_ip:
                        rtt_parts.append(f"{resolved[ip]} ({ip})")
                        last_ip = ip
                    rtt_parts.append(f"{rtt:.2f} ms")

            print(f"  {ttl:>2}   {' '.join(rtt_parts)}")

        if reached:
            break

    send_sock.close()
    recv_sock.close()
    print()


def main():
    parser = argparse.ArgumentParser(description="Minimal ICMP traceroute")
    parser.add_argument("destination", help="Hostname or IP to trace to")
    parser.add_argument("--max-hops", type=int, default=30, metavar="N",
                        help="Maximum number of hops (default: 30)")
    parser.add_argument("--timeout", type=float, default=3.0, metavar="S",
                        help="Timeout per probe in seconds (default: 3.0)")
    parser.add_argument("--probes", type=int, default=3, metavar="N",
                        help="Number of probes per TTL (default: 3)")
    args = parser.parse_args()
    traceroute(args.destination, args.max_hops, args.timeout, args.probes)


if __name__ == "__main__":
    main()
```

Run it:

```bash
sudo python3 traceroute.py 8.8.8.8
sudo python3 traceroute.py example.com --max-hops 15 --probes 1
```

Sample output:

```
traceroute to 8.8.8.8 (8.8.8.8), 30 hops max
using ICMP echo, 3 probes per hop, timeout 3.0s

   1   _gateway (192.168.1.1) 1.45 ms 1.12 ms 0.98 ms
   2   10.10.0.1 (10.10.0.1) 8.34 ms 7.91 ms 8.22 ms
   3   * * *
   4   209.85.168.174 (209.85.168.174) 14.23 ms 13.88 ms 14.01 ms
   5   dns.google (8.8.8.8) 13.99 ms 14.12 ms 14.05 ms
```

The `* * *` on hop 3 means that router did not respond to ICMP (it silently dropped the TTL-expired packet instead of sending a Time Exceeded). This is common — some routers are configured to not respond to ICMP, or they rate-limit ICMP responses.

## Exercises

1. **TTL visualisation.** Modify the script to print a bar chart of RTTs — each hop gets a line of `#` characters proportional to its latency. Large jumps indicate slow or distant links.

2. **UDP traceroute.** Traditional Unix traceroute uses UDP probes to ports 33434+, not ICMP. The destination port is high and closed, so the server returns ICMP Port Unreachable instead of an Echo Reply. Implement a `--mode udp` option.

3. **Parallel probes.** The current code sends probes sequentially. Measure total wall-clock time for 30 hops × 3 probes. Refactor to send all three probes for each hop simultaneously using threads and see how much faster it is.

4. **Route variation.** Run `traceroute 8.8.8.8` ten times in a row. Do the intermediate hops vary? Some routers do ECMP (Equal Cost Multi-Path) routing, sending different packets over different paths. Document what you observe.

5. **Max TTL reached.** What does the output look like when you set `--max-hops 3` for a destination that is 10 hops away? Modify the script to print a clear message when the destination was not reached within the hop limit.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| TTL | "Time to live" | A counter in the IPv4 header, decremented by each router; at 0 the packet is discarded and ICMP Time Exceeded is sent to the source |
| ICMP Time Exceeded | "TTL expired" | An ICMP message (Type 11, Code 0) sent by a router when it discards a packet with TTL=0; contains the original packet's IP header + 8 bytes |
| ICMP Echo Request | "Ping packet" | ICMP Type 8; the probe sent by traceroute and ping |
| ICMP Echo Reply | "Pong" | ICMP Type 0; the response from the destination when it receives an Echo Request |
| Raw socket | "Bypass the kernel stack" | A socket type (SOCK_RAW) that lets you construct and receive raw IP-layer packets; requires root privileges |
| Probe | "Each test packet" | One TTL-limited packet sent to the destination; traceroute sends multiple per hop to measure RTT and detect variability |
| RTT | "Round-trip time" | The elapsed time from sending a probe to receiving the response, in milliseconds |

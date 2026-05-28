# Build a Packet Analyzer CLI

> A pcap file is a mystery novel. Your tool reads it and tells you who talked to whom, about what, and for how long.

**Type:** Capstone
**Languages:** Python
**Prerequisites:** All previous phases
**Time:** ~90 minutes

## Learning Objectives
- Parse a pcap file using Python's `dpkt` or `scapy` library from scratch
- Identify and group packets into conversations by 5-tuple (src IP, dst IP, src port, dst port, protocol)
- Produce a human-readable summary report: protocol distribution, top talkers, per-conversation stats
- Handle Ethernet, IP, TCP, UDP, and ICMP layers correctly
- Accept command-line arguments for filtering by protocol, IP, or minimum packet count

## Architecture Overview

```
Input: pcap file (binary capture format)
           │
           ▼
  ┌─────────────────────┐
  │   PCAPReader        │  Iterates packets, decodes Ethernet/IP/TCP/UDP
  └─────────┬───────────┘
            │
            ▼
  ┌─────────────────────┐
  │  ConversationTracker│  Groups packets into flows by 5-tuple
  └─────────┬───────────┘
            │
            ▼
  ┌─────────────────────┐
  │   Reporter          │  Formats and prints summary tables
  └─────────────────────┘

Output: stdout (tables)
```

The design is a pipeline: read → track → report. Each stage is a class with a clean interface. This makes it easy to add new output formats (JSON, HTML) or new packet decoders later.

### What is a Conversation?

A conversation (also called a flow) is all packets with the same 5-tuple:
- Source IP
- Destination IP
- Source port
- Destination port
- Protocol (TCP / UDP / ICMP)

For TCP, the conversation includes packets in both directions. We normalise the 5-tuple by always putting the lower IP first so that forward and reverse directions map to the same conversation.

### The pcap File Format

A pcap file starts with a global header (magic number, version, link type), then a sequence of packet records. Each record has a timestamp (seconds + microseconds), captured length, original length, and raw bytes.

```
pcap file:
  [24-byte global header]
  [16-byte record header][raw packet bytes]
  [16-byte record header][raw packet bytes]
  ...

Raw packet bytes for Ethernet:
  [6 dst MAC][6 src MAC][2 EtherType]
  [IP header (20+ bytes)]
  [TCP/UDP/ICMP header]
  [payload]
```

Python's `dpkt` library handles all of this transparently.

## Build It

Install dependencies:

```bash
pip3 install dpkt scapy
```

Obtain a test pcap file:

```bash
# Download a sample pcap from Wireshark's sample capture library
curl -L -o sample.pcap \
  "https://wiki.wireshark.org/uploads/__moin_moin_migration/attachments/SampleCaptures/http.cap"

# Or capture your own (requires root):
sudo tcpdump -i eth0 -c 500 -w capture.pcap
```

Save the full analyzer as `packet_analyzer.py`:

```python
#!/usr/bin/env python3
"""
Packet Analyzer CLI
Reads a pcap file and produces a conversation summary by protocol.

Usage:
  python3 packet_analyzer.py <file.pcap> [options]

Options:
  --proto tcp|udp|icmp|all    Filter by protocol (default: all)
  --ip <address>              Only show conversations involving this IP
  --min-packets <n>           Only show conversations with at least n packets
  --top <n>                   Show top N conversations by byte count (default: 20)
  --dns                       Decode DNS payloads and list queried names
"""
import sys
import argparse
import socket
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

try:
    import dpkt
except ImportError:
    print("Install dpkt: pip3 install dpkt")
    sys.exit(1)


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Conversation:
    """All packets between two endpoints on a single protocol/port pair."""
    key:         tuple        # normalised 5-tuple
    proto:       str          # "TCP", "UDP", "ICMP", "OTHER"
    src_ip:      str
    dst_ip:      str
    src_port:    int
    dst_port:    int
    packet_count: int = 0
    byte_count:  int = 0
    first_seen:  float = 0.0
    last_seen:   float = 0.0

    @property
    def duration_s(self) -> float:
        return self.last_seen - self.first_seen

    @property
    def avg_pkt_size(self) -> float:
        return self.byte_count / self.packet_count if self.packet_count else 0


def normalise_key(src_ip, dst_ip, src_port, dst_port, proto):
    """
    Return a canonical 5-tuple where the lower (src_ip, src_port) comes first.
    This ensures A→B and B→A map to the same conversation.
    """
    if (src_ip, src_port) > (dst_ip, dst_port):
        src_ip, dst_ip     = dst_ip, src_ip
        src_port, dst_port = dst_port, src_port
    return (src_ip, dst_ip, src_port, dst_port, proto)


# ── Reader ────────────────────────────────────────────────────────────────────

class PCAPReader:
    """Iterates a pcap file, yielding (timestamp, proto_str, src_ip, dst_ip, src_port, dst_port, length)."""

    def __init__(self, path: str):
        self.path = path

    def packets(self):
        with open(self.path, "rb") as f:
            try:
                pcap = dpkt.pcap.Reader(f)
            except dpkt.dpkt.NeedData:
                print(f"Error: {self.path} is not a valid pcap file.")
                sys.exit(1)

            for ts, raw in pcap:
                try:
                    eth = dpkt.ethernet.Ethernet(raw)
                except Exception:
                    continue

                # We only handle IPv4 packets in this analyzer
                if not isinstance(eth.data, dpkt.ip.IP):
                    continue

                ip = eth.data
                src_ip = socket.inet_ntoa(ip.src)
                dst_ip = socket.inet_ntoa(ip.dst)
                length = len(raw)

                if isinstance(ip.data, dpkt.tcp.TCP):
                    tcp = ip.data
                    yield (ts, "TCP", src_ip, dst_ip, tcp.sport, tcp.dport, length)

                elif isinstance(ip.data, dpkt.udp.UDP):
                    udp = ip.data
                    yield (ts, "UDP", src_ip, dst_ip, udp.sport, udp.dport, length)

                elif isinstance(ip.data, dpkt.icmp.ICMP):
                    # ICMP has type/code, not ports — use 0 as placeholder
                    yield (ts, "ICMP", src_ip, dst_ip, 0, 0, length)

                else:
                    proto_num = ip.p
                    yield (ts, f"PROTO_{proto_num}", src_ip, dst_ip, 0, 0, length)


# ── Tracker ───────────────────────────────────────────────────────────────────

class ConversationTracker:
    """Groups packets into conversations and accumulates statistics."""

    def __init__(self):
        self._convs: dict = {}   # key → Conversation
        self.total_packets = 0
        self.total_bytes   = 0
        self.proto_counts  = defaultdict(int)
        self.proto_bytes   = defaultdict(int)

    def process(self, ts, proto, src_ip, dst_ip, src_port, dst_port, length):
        key  = normalise_key(src_ip, dst_ip, src_port, dst_port, proto)
        conv = self._convs.get(key)

        if conv is None:
            # First packet of this conversation
            k_src_ip, k_dst_ip, k_src_port, k_dst_port, k_proto = key
            conv = Conversation(
                key        = key,
                proto      = proto,
                src_ip     = k_src_ip,
                dst_ip     = k_dst_ip,
                src_port   = k_src_port,
                dst_port   = k_dst_port,
                first_seen = ts,
                last_seen  = ts,
            )
            self._convs[key] = conv

        conv.packet_count += 1
        conv.byte_count   += length
        conv.last_seen     = max(conv.last_seen, ts)

        self.total_packets += 1
        self.total_bytes   += length
        self.proto_counts[proto] += 1
        self.proto_bytes[proto]  += length

    def conversations(self, proto_filter: Optional[str] = None,
                      ip_filter: Optional[str] = None,
                      min_packets: int = 1) -> list:
        """Return sorted list of conversations matching the given filters."""
        result = []
        for conv in self._convs.values():
            if proto_filter and proto_filter.upper() not in conv.proto.upper():
                continue
            if ip_filter and ip_filter not in (conv.src_ip, conv.dst_ip):
                continue
            if conv.packet_count < min_packets:
                continue
            result.append(conv)
        # Sort by byte count descending
        result.sort(key=lambda c: c.byte_count, reverse=True)
        return result


# ── DNS Decoder ───────────────────────────────────────────────────────────────

def extract_dns_names(path: str) -> list:
    """Return a sorted list of unique DNS names queried in the pcap."""
    names = set()
    with open(path, "rb") as f:
        pcap = dpkt.pcap.Reader(f)
        for ts, raw in pcap:
            try:
                eth = dpkt.ethernet.Ethernet(raw)
                if not isinstance(eth.data, dpkt.ip.IP):
                    continue
                ip = eth.data
                if not isinstance(ip.data, dpkt.udp.UDP):
                    continue
                udp = ip.data
                if udp.dport != 53 and udp.sport != 53:
                    continue
                dns = dpkt.dns.DNS(udp.data)
                # Queries (questions section)
                for q in dns.qd:
                    names.add(q.name.rstrip("."))
                # Answers (some resolvers log responses too)
                for a in dns.an:
                    if hasattr(a, "name"):
                        names.add(a.name.rstrip("."))
            except Exception:
                continue
    return sorted(names)


# ── Reporter ──────────────────────────────────────────────────────────────────

def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def print_summary(tracker: ConversationTracker, top: int,
                  proto_filter: Optional[str],
                  ip_filter: Optional[str],
                  min_packets: int) -> None:

    print(f"\n{'═'*70}")
    print(f"  PACKET CAPTURE SUMMARY")
    print(f"{'═'*70}")
    print(f"  Total packets : {tracker.total_packets:,}")
    print(f"  Total bytes   : {human_bytes(tracker.total_bytes)}")

    print(f"\n  Protocol Distribution:")
    print(f"  {'Protocol':<12} {'Packets':>10}  {'Bytes':>12}  {'%':>6}")
    print(f"  {'-'*12} {'-'*10}  {'-'*12}  {'-'*6}")
    for proto, count in sorted(tracker.proto_counts.items(),
                                key=lambda x: x[1], reverse=True):
        pct = 100 * count / tracker.total_packets if tracker.total_packets else 0
        byt = tracker.proto_bytes[proto]
        print(f"  {proto:<12} {count:>10,}  {human_bytes(byt):>12}  {pct:>5.1f}%")

    convs = tracker.conversations(
        proto_filter=proto_filter,
        ip_filter=ip_filter,
        min_packets=min_packets,
    )

    print(f"\n  Top {min(top, len(convs))} Conversations (of {len(convs)} total):")
    print(f"\n  {'#':<4} {'Protocol':<6} {'Source IP:Port':<24} {'Dest IP:Port':<24}"
          f" {'Pkts':>6} {'Bytes':>10} {'Duration':>10}")
    print(f"  {'-'*4} {'-'*6} {'-'*24} {'-'*24} {'-'*6} {'-'*10} {'-'*10}")

    for i, conv in enumerate(convs[:top], start=1):
        if conv.proto in ("ICMP",) or conv.src_port == 0:
            src_ep = conv.src_ip
            dst_ep = conv.dst_ip
        else:
            src_ep = f"{conv.src_ip}:{conv.src_port}"
            dst_ep = f"{conv.dst_ip}:{conv.dst_port}"

        dur = f"{conv.duration_s:.2f}s" if conv.duration_s > 0 else "<1ms"
        print(
            f"  {i:<4} {conv.proto:<6} {src_ep:<24} {dst_ep:<24}"
            f" {conv.packet_count:>6,} {human_bytes(conv.byte_count):>10} {dur:>10}"
        )

    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Packet Analyzer CLI — summarise a pcap file by conversation."
    )
    parser.add_argument("pcap_file",            help="Path to .pcap or .pcapng file")
    parser.add_argument("--proto",  default=None, help="Filter: tcp, udp, icmp")
    parser.add_argument("--ip",     default=None, help="Filter: only conversations with this IP")
    parser.add_argument("--min-packets", type=int, default=1,
                        help="Only show conversations with at least N packets")
    parser.add_argument("--top",    type=int, default=20,
                        help="Show top N conversations by byte count")
    parser.add_argument("--dns",    action="store_true",
                        help="List all DNS names queried in the capture")
    args = parser.parse_args()

    reader  = PCAPReader(args.pcap_file)
    tracker = ConversationTracker()

    print(f"Analysing {args.pcap_file} ...", end=" ", flush=True)
    for pkt in reader.packets():
        tracker.process(*pkt)
    print("done.")

    print_summary(
        tracker,
        top         = args.top,
        proto_filter= args.proto,
        ip_filter   = args.ip,
        min_packets = args.min_packets,
    )

    if args.dns:
        names = extract_dns_names(args.pcap_file)
        print(f"  DNS Names Queried ({len(names)} unique):")
        for name in names:
            print(f"    {name}")
        print()


if __name__ == "__main__":
    main()
```

### Sample Usage

```bash
# Basic summary of all conversations
python3 packet_analyzer.py sample.pcap

# Show only TCP conversations with at least 5 packets
python3 packet_analyzer.py sample.pcap --proto tcp --min-packets 5

# Show conversations involving a specific IP
python3 packet_analyzer.py sample.pcap --ip 192.168.1.100

# Show DNS names and top 10 conversations
python3 packet_analyzer.py sample.pcap --dns --top 10
```

### Sample Output

```
Analysing sample.pcap ... done.

══════════════════════════════════════════════════════════════════════
  PACKET CAPTURE SUMMARY
══════════════════════════════════════════════════════════════════════
  Total packets : 4,289
  Total bytes   : 2.3 MB

  Protocol Distribution:
  Protocol       Packets        Bytes       %
  ------------ ----------  ------------  ------
  TCP               3,812       2.2 MB   88.9%
  UDP                 421      95.4 KB    9.8%
  ICMP                 56       4.8 KB    1.3%

  Top 5 Conversations (of 47 total):

  #    Proto  Source IP:Port          Dest IP:Port             Pkts      Bytes   Duration
  ---- ------ ------------------------ ------------------------ ------ ---------- ----------
  1    TCP    10.0.0.5:54321           93.184.216.34:443         1,200     1.4 MB     12.34s
  2    TCP    10.0.0.5:54400           93.184.216.34:80            320   340.2 KB      5.67s
  3    UDP    10.0.0.5:52000           8.8.8.8:53                  88     8.2 KB      0.92s
  4    TCP    10.0.0.5:54500           172.217.0.1:443             204   180.0 KB      3.10s
  5    ICMP   10.0.0.5                 8.8.8.8                      56     4.8 KB      2.00s
```

## Extension Ideas

1. **IPv6 support**: Add a check for `dpkt.ip6.IP6` in the reader. Extract IPv6 source and destination addresses using `socket.inet_ntop(socket.AF_INET6, ip6.src)`.

2. **TCP flag analysis**: For each TCP conversation, track SYN, SYN-ACK, FIN, and RST flags. Identify incomplete connections (SYN but no SYN-ACK), port-scan evidence (many RSTs from one source), and abruptly terminated sessions (RST without FIN).

3. **HTTP content extraction**: For conversations on port 80, try to decode the TCP stream and extract HTTP request lines (GET /path HTTP/1.1) and Host headers. Print a table of URLs accessed.

4. **Output to JSON**: Add a `--json` flag that writes the full conversation list as a JSON file, suitable for import into Elasticsearch or another analysis platform.

5. **GeoIP enrichment**: Use the `geoip2` Python library with the free MaxMind GeoLite2 database to add country codes to each IP address in the conversation table.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| pcap | "packet capture" | A file format (libpcap format) that stores raw network frames with timestamps |
| 5-tuple | "flow key" | The combination of (src IP, dst IP, src port, dst port, protocol) that uniquely identifies a conversation |
| dpkt | "decode packet" | A Python library for decoding raw packet bytes into structured objects (Ethernet, IP, TCP, etc.) |
| Conversation | "flow" | All packets sharing the same 5-tuple; a bidirectional exchange between two endpoints |
| EtherType | "L3 protocol field" | A field in the Ethernet header identifying the Layer 3 protocol: 0x0800 = IPv4, 0x86DD = IPv6, 0x0806 = ARP |
| Top talkers | "bandwidth hogs" | The source IPs or conversations generating the most traffic in a capture |

# Parse an IPv4 Header

> Every packet on the internet carries a 20-byte header that every router reads and modifies. If you cannot read that header, you cannot understand routing, fragmentation, or why your packets are getting dropped.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 1, Lesson 02 — Capture Traffic with tcpdump; Phase 2, Lesson 01 — Decode IPv4 Addresses
**Time:** ~40 minutes

## Learning Objectives
- Identify all 13 fields in an IPv4 header and state the purpose of each
- Use Python's `struct` module to unpack a binary header from raw bytes
- Calculate the header length from the IHL field
- Decode the flags and fragment offset fields
- Read a packet capture file and parse every IPv4 packet in it

## The Problem

When your ping disappears somewhere between you and `8.8.8.8`, every router along the path looked at the IPv4 header and made a decision: accept, forward, discard. If the Time-To-Live field reached zero, the packet was silently dropped and an ICMP error was sent back. If the Don't Fragment flag was set and the packet was too large, it was dropped without fragmentation.

Without being able to read these headers, debugging is guesswork. You cannot tell if the TTL was consumed before reaching the destination, whether fragmentation is occurring, or whether the source is setting unusual Type-of-Service bits. Packet analysis tools like Wireshark parse these fields, but you should understand what they are doing so you can do it yourself when Wireshark is not available.

## The Concept

### The IPv4 header layout

The header is at minimum 20 bytes (160 bits). Here is every field, drawn to scale (one row = 32 bits = 4 bytes):

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Version|  IHL  |Type of Service|          Total Length         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Identification        |Flags|     Fragment Offset     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  Time to Live |    Protocol   |        Header Checksum        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         Source Address                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Destination Address                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Options (if IHL > 5)                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Field by field:

**Version (4 bits):** Always `0100` (= 4) for IPv4. IPv6 packets have `0110` (= 6) here. This is how your NIC and kernel distinguish them.

**IHL — Internet Header Length (4 bits):** The number of 32-bit *words* in the header. Minimum value is 5 (= 20 bytes). Maximum is 15 (= 60 bytes, when options are present). To get byte count: `IHL × 4`. The payload (TCP/UDP/ICMP data) starts at byte `IHL × 4`.

**Type of Service / DSCP (8 bits):** Originally ToS; now repurposed as DSCP (Differentiated Services Code Point) for QoS. Most packets have this set to 0. Voice/video traffic sets it to prioritise forwarding. You will often see this called the "ToS byte".

**Total Length (16 bits):** The total size of the IP packet including header and payload, in bytes. Maximum is 65,535 bytes. Most packets are much smaller (MTU limits).

**Identification (16 bits):** A value assigned by the sender, used to reassemble fragmented packets. All fragments of the same original datagram share the same Identification value.

**Flags (3 bits):**
```
Bit 0 (MSB): Reserved, must be 0
Bit 1: DF — Don't Fragment. If set, routers MUST drop the packet and send ICMP
         "Fragmentation Needed" if the packet is too big for the outgoing link.
Bit 2: MF — More Fragments. Set on all fragments except the last one.
```

**Fragment Offset (13 bits):** The offset of this fragment's data within the original datagram, measured in units of 8 bytes. The first fragment has offset 0. If a 4000-byte payload is split into 3 fragments, their offsets would be 0, 185, 370 (in 8-byte units).

**Time To Live (8 bits):** Each router that forwards a packet **decrements TTL by 1**. When TTL reaches 0, the packet is discarded and an ICMP Time Exceeded message is sent back to the source. This prevents packets from looping forever. Traceroute exploits this to discover hops.

**Protocol (8 bits):** Identifies the payload protocol:
```
1  = ICMP
6  = TCP
17 = UDP
47 = GRE
89 = OSPF
```

**Header Checksum (16 bits):** A one's-complement checksum of the IPv4 header only (not the payload). Routers verify and recompute this after decrementing TTL.

**Source Address (32 bits):** IP address of the sender.

**Destination Address (32 bits):** IP address of the intended recipient.

**Options (0–40 bytes):** Rarely used. Includes features like Record Route, Timestamp, Strict Source Routing. Present only when IHL > 5.

### struct format strings

Python's `struct.unpack()` parses binary data according to a format string. Each character represents a field:

```
B  = unsigned char (1 byte)
H  = unsigned short (2 bytes, big-endian with !)
I  = unsigned int (4 bytes, big-endian with !)
!  = network byte order (big-endian) — always use this for network parsing
```

The IPv4 header first 20 bytes map to: `"!BBHHHBBH4s4s"`

```
!           — big-endian
B           — version_ihl (1 byte, version in upper 4 bits, IHL in lower 4 bits)
B           — tos (1 byte)
H           — total_length (2 bytes)
H           — identification (2 bytes)
H           — flags_frag_offset (2 bytes, flags in upper 3 bits, offset in lower 13)
B           — ttl (1 byte)
B           — protocol (1 byte)
H           — checksum (2 bytes)
4s          — src_addr (4 bytes, raw bytes)
4s          — dst_addr (4 bytes, raw bytes)
```

Total: 1+1+2+2+2+1+1+2+4+4 = 20 bytes. Correct.

### pcap file format

A `.pcap` file starts with a global header, followed by packets. Each packet has a 16-byte record header followed by the captured bytes. For Ethernet frames, the IPv4 header starts at byte 14 (after the 14-byte Ethernet header: 6 bytes dst MAC, 6 bytes src MAC, 2 bytes EtherType).

```
pcap file:
  [Global Header — 24 bytes]
  [Packet Record Header — 16 bytes] [Packet Data — N bytes]
  [Packet Record Header — 16 bytes] [Packet Data — N bytes]
  ...

Packet Data (Ethernet frame):
  [Dst MAC — 6 bytes]
  [Src MAC — 6 bytes]
  [EtherType — 2 bytes]  (0x0800 = IPv4)
  [IPv4 Header — 20+ bytes]
  [Payload ...]
```

## Build It

We will write a parser without any third-party libraries. First, generate a small test pcap by capturing a ping:

```bash
# In terminal 1 — capture 5 ICMP packets to a file
sudo tcpdump -i any -c 5 -w /tmp/ping_test.pcap icmp

# In terminal 2 — send the pings
ping -c 5 8.8.8.8
```

Now create `ipv4_header_parser.py`:

```python
#!/usr/bin/env python3
"""
ipv4_header_parser.py — parse every IPv4 packet in a pcap file.

Usage:
    python3 ipv4_header_parser.py /tmp/ping_test.pcap
"""

import struct
import socket
import sys
from dataclasses import dataclass


# ── protocol name lookup ──────────────────────────────────────────────────────

PROTOCOLS = {
    1:  "ICMP",
    6:  "TCP",
    17: "UDP",
    47: "GRE",
    89: "OSPF",
    132: "SCTP",
}


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class IPv4Header:
    version: int          # should be 4
    ihl: int              # header length in 32-bit words (minimum 5)
    tos: int              # type of service / DSCP
    total_length: int     # total packet size in bytes
    identification: int   # fragment group identifier
    flags_df: bool        # Don't Fragment bit
    flags_mf: bool        # More Fragments bit
    frag_offset: int      # fragment offset in 8-byte units
    ttl: int              # time to live
    protocol: int         # next-layer protocol number
    checksum: int         # header checksum (hex)
    src: str              # source IP (dotted-decimal)
    dst: str              # destination IP (dotted-decimal)
    header_bytes: int     # actual header byte length = ihl * 4

    def protocol_name(self) -> str:
        return PROTOCOLS.get(self.protocol, f"Unknown({self.protocol})")

    def flags_str(self) -> str:
        parts = []
        if self.flags_df:
            parts.append("DF")
        if self.flags_mf:
            parts.append("MF")
        return "|".join(parts) if parts else "none"


def parse_ipv4_header(raw: bytes) -> IPv4Header:
    """
    Unpack the first 20 bytes of raw into an IPv4Header.

    struct format "!BBHHHBBH4s4s":
      B  = version_ihl   (1 byte: top 4 bits = version, bottom 4 bits = IHL)
      B  = tos           (1 byte)
      H  = total_length  (2 bytes)
      H  = identification (2 bytes)
      H  = flags_frag    (2 bytes: top 3 bits = flags, bottom 13 = frag offset)
      B  = ttl           (1 byte)
      B  = protocol      (1 byte)
      H  = checksum      (2 bytes)
      4s = src_addr_bytes (4 bytes)
      4s = dst_addr_bytes (4 bytes)
    """
    if len(raw) < 20:
        raise ValueError(f"Too short for IPv4 header: {len(raw)} bytes")

    (version_ihl, tos, total_length, identification,
     flags_frag, ttl, protocol, checksum,
     src_bytes, dst_bytes) = struct.unpack("!BBHHHBBH4s4s", raw[:20])

    version = (version_ihl >> 4) & 0xF   # upper 4 bits
    ihl     = version_ihl & 0xF           # lower 4 bits

    # flags_frag is 16 bits: [3 bits flags][13 bits frag offset]
    # Bit 15 (MSB of 16-bit field): reserved, always 0
    # Bit 14: DF (Don't Fragment)
    # Bit 13: MF (More Fragments)
    # Bits 12-0: fragment offset
    df = bool(flags_frag & 0x4000)        # bit 14
    mf = bool(flags_frag & 0x2000)        # bit 13
    frag_offset = flags_frag & 0x1FFF     # bits 12-0

    # Convert 4-byte raw addresses to dotted-decimal using socket.inet_ntoa
    src = socket.inet_ntoa(src_bytes)
    dst = socket.inet_ntoa(dst_bytes)

    return IPv4Header(
        version=version,
        ihl=ihl,
        tos=tos,
        total_length=total_length,
        identification=identification,
        flags_df=df,
        flags_mf=mf,
        frag_offset=frag_offset,
        ttl=ttl,
        protocol=protocol,
        checksum=checksum,
        src=src,
        dst=dst,
        header_bytes=ihl * 4,
    )


def print_header(h: IPv4Header, pkt_num: int):
    """Print a formatted summary of one IPv4 header."""
    print(f"\nPacket #{pkt_num}")
    print(f"  Version:        {h.version}")
    print(f"  IHL:            {h.ihl} words = {h.header_bytes} bytes")
    print(f"  ToS/DSCP:       0x{h.tos:02X}")
    print(f"  Total Length:   {h.total_length} bytes")
    print(f"  Identification: 0x{h.identification:04X} ({h.identification})")
    print(f"  Flags:          {h.flags_str()}")
    print(f"  Frag Offset:    {h.frag_offset} (× 8 = {h.frag_offset * 8} bytes)")
    print(f"  TTL:            {h.ttl}")
    print(f"  Protocol:       {h.protocol} ({h.protocol_name()})")
    print(f"  Checksum:       0x{h.checksum:04X}")
    print(f"  Source:         {h.src}")
    print(f"  Destination:    {h.dst}")


# ── pcap reader ───────────────────────────────────────────────────────────────

PCAP_GLOBAL_MAGIC   = 0xA1B2C3D4   # little-endian pcap magic
PCAP_GLOBAL_MAGIC_BE = 0xD4C3B2A1  # big-endian (less common)
ETHERNET_HEADER_LEN = 14           # 6 dst + 6 src + 2 EtherType
ETHERTYPE_IPV4      = 0x0800


def read_pcap(path: str):
    """
    Generator that yields (packet_number, raw_bytes) for each packet.

    pcap global header (24 bytes):
      I  magic_number
      H  version_major
      H  version_minor
      i  thiszone (GMT offset)
      I  sigfigs (timestamp accuracy)
      I  snaplen (max captured length)
      I  network (link-layer type; 1 = Ethernet)

    Per-packet record header (16 bytes):
      I  ts_sec
      I  ts_usec
      I  incl_len (bytes saved in file)
      I  orig_len (original packet length)
    """
    with open(path, "rb") as f:
        global_header = f.read(24)
        if len(global_header) < 24:
            raise ValueError("File too short to be a pcap")

        magic = struct.unpack("<I", global_header[:4])[0]
        if magic == PCAP_GLOBAL_MAGIC:
            endian = "<"   # little-endian
        elif magic == PCAP_GLOBAL_MAGIC_BE:
            endian = ">"   # big-endian
        else:
            raise ValueError(f"Not a pcap file (magic={magic:#010x})")

        link_type = struct.unpack(f"{endian}I", global_header[20:24])[0]
        if link_type != 1:
            print(f"Warning: link type {link_type} is not Ethernet (1). "
                  f"Ethernet header offset assumed but may be wrong.")

        pkt_num = 0
        while True:
            rec_header = f.read(16)
            if len(rec_header) == 0:
                break   # end of file
            if len(rec_header) < 16:
                print("Warning: truncated record header at end of file")
                break

            _, _, incl_len, _ = struct.unpack(f"{endian}IIII", rec_header)
            pkt_data = f.read(incl_len)
            if len(pkt_data) < incl_len:
                print(f"Warning: packet {pkt_num+1} truncated")

            pkt_num += 1
            yield pkt_num, pkt_data


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 ipv4_header_parser.py <file.pcap>")
        sys.exit(1)

    path = sys.argv[1]
    ipv4_count = 0
    other_count = 0

    print(f"Parsing: {path}")
    print("=" * 60)

    for pkt_num, raw in read_pcap(path):
        # Skip packets too short for Ethernet + IPv4 headers
        if len(raw) < ETHERNET_HEADER_LEN + 20:
            other_count += 1
            continue

        # Read EtherType from bytes 12-13 of the Ethernet frame
        ethertype = struct.unpack("!H", raw[12:14])[0]

        if ethertype != ETHERTYPE_IPV4:
            other_count += 1
            continue  # skip ARP, IPv6, etc.

        # IPv4 header starts after the 14-byte Ethernet header
        ip_raw = raw[ETHERNET_HEADER_LEN:]

        try:
            hdr = parse_ipv4_header(ip_raw)
            if hdr.version != 4:
                other_count += 1
                continue
            print_header(hdr, pkt_num)
            ipv4_count += 1
        except (struct.error, ValueError) as e:
            print(f"Packet #{pkt_num}: parse error — {e}")
            other_count += 1

    print("\n" + "=" * 60)
    print(f"Total packets: {ipv4_count + other_count}")
    print(f"  IPv4 parsed: {ipv4_count}")
    print(f"  Skipped:     {other_count}")


if __name__ == "__main__":
    main()
```

Create a small synthetic test (no root required):

```python
# test_parse.py — create a synthetic IPv4 header and parse it

import struct, socket, sys
sys.path.insert(0, ".")
from ipv4_header_parser import parse_ipv4_header, print_header

def make_ipv4_header(src="192.168.1.1", dst="8.8.8.8",
                     protocol=1, ttl=64, total_length=60,
                     identification=0x1234, df=True):
    """Manually construct a 20-byte IPv4 header with no options."""
    version_ihl = (4 << 4) | 5          # version=4, IHL=5 (20 bytes)
    tos = 0
    flags_frag = 0x4000 if df else 0    # DF flag
    checksum = 0                         # skip computation for test

    raw = struct.pack("!BBHHHBBH4s4s",
        version_ihl, tos, total_length, identification,
        flags_frag, ttl, protocol, checksum,
        socket.inet_aton(src),
        socket.inet_aton(dst),
    )
    return raw

header_bytes = make_ipv4_header(
    src="10.0.0.1", dst="93.184.216.34",
    protocol=6,   # TCP
    ttl=128,
    df=True,
)

h = parse_ipv4_header(header_bytes)
print_header(h, 1)
```

```bash
python3 test_parse.py
```

Expected output:

```
Packet #1
  Version:        4
  IHL:            5 words = 20 bytes
  ToS/DSCP:       0x00
  Total Length:   60 bytes
  Identification: 0x1234 (4660)
  Flags:          DF
  Frag Offset:    0 (× 8 = 0 bytes)
  TTL:            128
  Protocol:       6 (TCP)
  Checksum:       0x0000
  Source:         10.0.0.1
  Destination:    93.184.216.34
```

## Exercises

1. **TTL census.** Parse a pcap and print a histogram of TTL values seen. What TTL values appear? Can you infer the original TTL (Linux defaults to 64, Windows to 128, routers often to 255)?

2. **Fragmented packet.** Look at your pcap — are any packets fragmented (MF flag set, or frag_offset > 0)? If not, use `ping -M dont -s 1500 8.8.8.8` on a network with a smaller MTU to force fragmentation. Parse the fragments and show how to reassemble them using Identification + offset.

3. **Checksum verification.** Implement the IPv4 header checksum algorithm (one's complement sum of 16-bit words, then one's complement of the result). Verify the checksum of each parsed packet and flag any that fail.

4. **Protocol breakdown.** Parse a longer capture and print a count of packets by protocol (ICMP, TCP, UDP, other). Which protocol dominates your capture?

5. **Options parsing.** When IHL > 5, there are options. Write a function that reads the options bytes (from byte 20 to `IHL * 4`) and identifies option types: 0 = End, 1 = NOP, 7 = Record Route, 68 = Timestamp.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| IHL | "Header length" | Internet Header Length in 32-bit words; minimum 5 (= 20 bytes); multiply by 4 to get bytes |
| TTL | "Time to live" | A counter decremented by each router; when it reaches 0 the packet is discarded, preventing infinite loops |
| Protocol field | "What's inside" | An 8-bit number identifying the transport-layer protocol in the payload (1=ICMP, 6=TCP, 17=UDP) |
| DF bit | "Don't Fragment" | Tells routers: if this packet is too big for the next link, drop it and send an error instead of splitting it |
| MF bit | "More Fragments" | Set on every fragment except the last; tells the receiver more data is coming with the same Identification |
| Fragment offset | "Where this piece goes" | The byte position of this fragment's data in the original datagram, measured in 8-byte units |
| struct.unpack | "Deserialise bytes" | Python standard-library function that reads binary data according to a format string |
| pcap | "Packet capture" | A file format (`.pcap`) produced by tcpdump/Wireshark containing raw captured frames with timestamps |

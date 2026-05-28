# Dissect an Ethernet Frame

> An Ethernet frame is a precisely structured sequence of bytes — destination MAC, source MAC, type, payload, checksum — and you can parse every one of those fields in 20 lines of Python.

**Type:** Learn
**Languages:** Python
**Prerequisites:** Phase 0, Lesson 02 — Capture Your First Packet
**Time:** ~40 minutes

## Learning Objectives
- Describe the six fields of an Ethernet II frame and the purpose of each
- Write a Python script that parses a raw Ethernet frame from a pcap file
- Print each field (destination MAC, source MAC, EtherType, payload length) in human-readable form
- Recognize common EtherType values (IPv4, IPv6, ARP)
- Explain the Frame Check Sequence (FCS) and why most tools do not show it

## The Problem

Every packet that travels over a wired Ethernet network — whether it contains an HTTP request, a DNS query, or a video stream — is wrapped in an Ethernet frame before it touches the wire. The Ethernet frame is Layer 2: it handles getting data from one NIC to the next NIC on the same local network segment.

If you cannot read an Ethernet frame, you cannot answer questions like:
- Why is this host's traffic going to `ff:ff:ff:ff:ff:ff` (broadcast)?
- Is this ARP request going to the right destination MAC?
- Why is the EtherType `0x8100` instead of `0x0800`? (Answer: it has a VLAN tag)

Parsing Ethernet frames in Python forces you to understand the exact byte layout. There is no abstraction layer to hide behind — you must know that bytes 0–5 are the destination MAC, bytes 6–11 are the source MAC, and bytes 12–13 are the EtherType.

## The Concept

### The Ethernet II Frame Structure

The modern Ethernet frame format (called Ethernet II or DIX Ethernet) looks like this:

```
Byte offset   Field               Size      Notes
-----------   -----------------   --------  ------------------------------------
0–5           Destination MAC     6 bytes   Who should receive this frame
6–11          Source MAC          6 bytes   Who sent this frame
12–13         EtherType           2 bytes   Which L3 protocol is in the payload
14–N          Payload             46–1500B  The IP packet (or ARP, etc.)
N+1 to N+4    FCS                 4 bytes   CRC-32 checksum (usually stripped)
```

Total minimum frame: 64 bytes (including the 4-byte FCS)
Total maximum frame: 1518 bytes (standard MTU 1500 + 14-byte header + 4-byte FCS)

### The Preamble (not shown in captures)

Before the destination MAC, a real Ethernet frame starts with:
- **Preamble**: 7 bytes of alternating 1s and 0s (`10101010...`) — helps the receiver's clock synchronize
- **Start Frame Delimiter (SFD)**: 1 byte `10101011` — signals that the actual frame data starts next

These 8 bytes are stripped by the NIC before the frame reaches the kernel. You will never see them in tcpdump or Wireshark captures.

### The Frame Check Sequence (FCS)

The last 4 bytes of a real Ethernet frame are a CRC-32 checksum over the entire frame (excluding preamble and FCS itself). If the checksum fails, the NIC discards the frame silently — no error is reported up the stack.

Like the preamble, the FCS is typically stripped by the NIC driver before the frame reaches the kernel. pcap captures usually do not include the FCS. This is why pcap files appear to have 14-byte Ethernet headers (no preamble, no FCS).

### EtherType Values

The 2-byte EtherType field tells the receiving NIC driver which Layer 3 protocol to pass the payload to:

```
EtherType   Protocol
----------  -----------------------
0x0800      IPv4
0x0806      ARP (Address Resolution Protocol)
0x86DD      IPv6
0x8100      IEEE 802.1Q VLAN tag (the "payload" starts with a VLAN tag)
0x0842      Wake-on-LAN
0x88CC      LLDP (Link Layer Discovery Protocol)
0x8863      PPPoE Discovery
0x8864      PPPoE Session
```

If the value in bytes 12–13 is less than 0x0600 (decimal 1536), it is actually a frame length field (used in the older IEEE 802.3 format, not Ethernet II). Values ≥ 0x0600 are EtherType values.

### Reading a pcap File in Python

pcap files have a global header followed by packet records. Each packet record has:
- A 16-byte per-packet header (timestamp seconds, timestamp microseconds, captured length, original length)
- The raw packet bytes

The `dpkt` library handles the pcap format parsing for us. Alternatively, the `scapy` library offers a higher-level interface.

## Build It

### Step 1 — Create a pcap file to parse

```bash
# Capture 10 packets on loopback
sudo tcpdump -i lo -n -w /tmp/ethernet-lab.pcap -c 10 &

# Generate some traffic
ping -c 3 127.0.0.1
ncat -l 7777 &
echo "test" | ncat 127.0.0.1 7777

sleep 1
sudo pkill tcpdump
sudo pkill ncat 2>/dev/null
echo "Capture saved to /tmp/ethernet-lab.pcap"
```

### Step 2 — Install the dpkt library

```bash
pip3 install dpkt
```

If pip3 is not available:
```bash
sudo apt-get install python3-dpkt
```

### Step 3 — Write the Ethernet frame parser

Create a file called `parse_ethernet.py`:

```python
# parse_ethernet.py
# Parse raw Ethernet frames from a pcap file and print each field.

import struct
import dpkt
import sys


def mac_to_str(mac_bytes: bytes) -> str:
    """Convert 6 raw bytes to a colon-separated MAC address string."""
    # Each byte is formatted as a 2-digit hex number, all joined by colons.
    return ":".join(f"{b:02x}" for b in mac_bytes)


def ethertype_name(ethertype: int) -> str:
    """Return a human-readable name for a common EtherType value."""
    known = {
        0x0800: "IPv4",
        0x0806: "ARP",
        0x86DD: "IPv6",
        0x8100: "802.1Q VLAN",
        0x0842: "Wake-on-LAN",
        0x88CC: "LLDP",
    }
    return known.get(ethertype, f"Unknown (0x{ethertype:04x})")


def parse_ethernet_frame(raw_frame: bytes) -> dict:
    """
    Parse a raw Ethernet II frame.
    Returns a dict with all parsed fields.
    Raises ValueError if the frame is too short.
    """
    if len(raw_frame) < 14:
        raise ValueError(
            f"Frame too short: {len(raw_frame)} bytes (minimum 14)"
        )

    # Bytes 0-5: Destination MAC address (6 bytes)
    dst_mac = raw_frame[0:6]

    # Bytes 6-11: Source MAC address (6 bytes)
    src_mac = raw_frame[6:12]

    # Bytes 12-13: EtherType (2 bytes, big-endian unsigned short)
    # struct.unpack returns a tuple, so we take index [0]
    ethertype = struct.unpack("!H", raw_frame[12:14])[0]
    # The "!" means network byte order (big-endian).
    # "H" means unsigned short (2 bytes).

    # Bytes 14 onwards: Payload (the actual IP packet, ARP message, etc.)
    payload = raw_frame[14:]

    return {
        "dst_mac": mac_to_str(dst_mac),
        "src_mac": mac_to_str(src_mac),
        "ethertype": ethertype,
        "ethertype_name": ethertype_name(ethertype),
        "payload_length": len(payload),
        "payload_hex": payload[:16].hex(),  # First 16 bytes for preview
    }


def print_frame(frame_num: int, parsed: dict) -> None:
    """Print a formatted summary of a parsed Ethernet frame."""
    print(f"\n{'─' * 50}")
    print(f"Frame #{frame_num}")
    print(f"{'─' * 50}")
    print(f"  Destination MAC : {parsed['dst_mac']}")
    print(f"  Source MAC      : {parsed['src_mac']}")
    print(f"  EtherType       : 0x{parsed['ethertype']:04x}  ({parsed['ethertype_name']})")
    print(f"  Payload length  : {parsed['payload_length']} bytes")
    print(f"  Payload (first 16B hex): {parsed['payload_hex']}")

    # Check for special destination MACs
    if parsed["dst_mac"] == "ff:ff:ff:ff:ff:ff":
        print("  *** BROADCAST frame ***")
    elif parsed["dst_mac"].startswith(("01:", "03:", "05:", "07:")):
        print("  *** MULTICAST frame ***")


def main(pcap_file: str) -> None:
    """Open a pcap file and parse each Ethernet frame."""
    print(f"Parsing Ethernet frames from: {pcap_file}\n")

    frame_count = 0
    arp_count = 0
    ipv4_count = 0
    ipv6_count = 0

    with open(pcap_file, "rb") as f:
        # dpkt.pcap.Reader handles the pcap file format for us.
        # It yields (timestamp, raw_bytes) tuples for each packet.
        pcap = dpkt.pcap.Reader(f)

        for timestamp, raw_bytes in pcap:
            frame_count += 1
            try:
                parsed = parse_ethernet_frame(raw_bytes)
                print_frame(frame_count, parsed)

                # Count protocol types
                if parsed["ethertype"] == 0x0800:
                    ipv4_count += 1
                elif parsed["ethertype"] == 0x0806:
                    arp_count += 1
                elif parsed["ethertype"] == 0x86DD:
                    ipv6_count += 1

            except ValueError as e:
                print(f"\nFrame #{frame_count}: Parse error — {e}")

    # Summary statistics
    print(f"\n{'=' * 50}")
    print(f"Summary: {frame_count} frames parsed")
    print(f"  IPv4 frames : {ipv4_count}")
    print(f"  ARP frames  : {arp_count}")
    print(f"  IPv6 frames : {ipv6_count}")
    print(f"  Other frames: {frame_count - ipv4_count - arp_count - ipv6_count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <pcap_file>")
        print(f"Example: python3 {sys.argv[0]} /tmp/ethernet-lab.pcap")
        sys.exit(1)

    main(sys.argv[1])
```

Run the parser:
```bash
python3 parse_ethernet.py /tmp/ethernet-lab.pcap
```

### Step 4 — Understand the output

For a loopback capture, you will see frames with:
- Destination MAC: `00:00:00:00:00:00` — loopback has no real hardware, so all-zeros MAC
- Source MAC: `00:00:00:00:00:00` — same reason
- EtherType: `0x0800` (IPv4) for ping and TCP traffic

For a capture on a real Ethernet interface (eth0, wlan0), you would see:
- Real MAC addresses like `aa:bb:cc:dd:ee:ff`
- Possibly ARP frames (`0x0806`) when the network resolves addresses
- IPv6 frames (`0x86DD`) alongside IPv4

### Step 5 — Capture on a real interface and reparse

If your machine has an Ethernet interface:
```bash
# Capture on eth0 (change to your actual interface name)
IFACE=$(ip -brief link show | grep -v lo | head -1 | awk '{print $1}')
sudo tcpdump -i "$IFACE" -n -w /tmp/eth0-capture.pcap -c 20 &

# Generate some traffic
curl -s http://example.com > /dev/null

sleep 2
sudo pkill tcpdump
python3 parse_ethernet.py /tmp/eth0-capture.pcap
```

On a real interface, you will see non-zero MAC addresses and possibly ARP frames.

## Exercises

1. **Manual hex decode** — Take the first packet from your pcap and print it with `sudo tcpdump -r /tmp/ethernet-lab.pcap -xx -c 1`. Manually decode bytes 0–13 (Ethernet header) using the field table from this lesson. Compare to your Python parser's output.

2. **ARP frame decoder** — ARP frames have a specific structure inside the Ethernet payload. Extend `parse_ethernet.py` to detect ARP frames (EtherType 0x0806) and parse the ARP header fields: hardware type, protocol type, sender IP, target IP, sender MAC, target MAC.

3. **Broadcast filter** — Modify the script to count and list all frames where the destination MAC is `ff:ff:ff:ff:ff:ff`. On a real network capture, you will see ARP requests always use broadcast.

4. **VLAN tag detection** — If the EtherType is `0x8100`, the frame contains an 802.1Q VLAN tag. The next 2 bytes are the tag (12-bit VLAN ID + 3-bit priority), and the 2 bytes after that are the real EtherType. Extend the parser to handle double-tagged frames.

5. **Write your own pcap** — Write a function `create_fake_frame(src_mac, dst_mac, ethertype, payload)` that constructs a valid Ethernet frame as bytes. Use `struct.pack("!6s6sH", dst, src, etype)`. Write a simple test that creates a frame and immediately parses it with `parse_ethernet_frame()`.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Ethernet II | "standard Ethernet" | The frame format defined by DIX (Digital, Intel, Xerox) and codified in IEEE 802.3. Uses a 2-byte EtherType field. The format used by virtually all modern Ethernet networks. |
| EtherType | "the type field" | A 2-byte field in the Ethernet header that identifies the Layer 3 protocol in the payload. Values ≥ 0x0600 are EtherType values; values < 0x0600 are frame length (IEEE 802.3 format). |
| FCS | "the checksum at the end" | Frame Check Sequence. A 4-byte CRC-32 appended to the end of every Ethernet frame. The NIC hardware checks it and drops corrupted frames. Usually stripped before the frame reaches the OS kernel, so rarely visible in captures. |
| broadcast MAC | "ff:ff:ff:ff:ff:ff" | A destination MAC address where all bits are 1. Every NIC on the local network segment accepts and processes broadcast frames. Used for ARP requests, DHCP discovery, and other protocols that need to reach all hosts. |
| preamble | "the sync bytes" | 7 bytes of `10101010` followed by 1 byte of `10101011` (SFD) that precede every Ethernet frame on the wire. Used for clock synchronization. Stripped by the NIC before reaching the kernel — invisible in pcap captures. |
| dpkt | "Python pcap parser" | A Python library for parsing pcap files and network protocol headers. Lightweight and fast. `scapy` is an alternative with a higher-level API and more protocols supported. |

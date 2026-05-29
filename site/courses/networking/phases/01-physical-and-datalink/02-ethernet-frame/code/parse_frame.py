# Run: python3 parse_frame.py
#!/usr/bin/env python3
"""
parse_frame.py — Parse a raw Ethernet II frame from a hardcoded hex string
and print every field with its name, byte offset, value, and description.

The example frame encodes:
  Dst MAC: ff:ff:ff:ff:ff:ff  (broadcast)
  Src MAC: aa:bb:cc:dd:ee:ff  (example unicast)
  EtherType: 0x0806            (ARP)
  Payload: a small ARP request body (28 bytes)

No third-party libraries required — uses only struct from the stdlib.

Usage:
    python3 parse_frame.py                   # parse the built-in example
    python3 parse_frame.py <hex_string>      # parse a hex string you provide
                                             # (spaces are ignored)
"""

import struct
import sys
from typing import Optional

# ── EtherType lookup ─────────────────────────────────────────────────────────

ETHERTYPES: dict[int, str] = {
    0x0800: "IPv4",
    0x0806: "ARP",
    0x86DD: "IPv6",
    0x8100: "802.1Q VLAN tag",
    0x0842: "Wake-on-LAN",
    0x88CC: "LLDP",
    0x8863: "PPPoE Discovery",
    0x8864: "PPPoE Session",
}


def ethertype_name(value: int) -> str:
    if value < 0x0600:
        return f"IEEE 802.3 length field ({value} bytes)"
    return ETHERTYPES.get(value, f"Unknown (0x{value:04x})")


# ── MAC helpers ───────────────────────────────────────────────────────────────

def bytes_to_mac(b: bytes) -> str:
    """Convert 6 raw bytes to a colon-separated MAC string."""
    return ":".join(f"{x:02x}" for x in b)


def mac_type(mac: str) -> str:
    """Classify a MAC address as Unicast / Multicast / Broadcast."""
    if mac == "ff:ff:ff:ff:ff:ff":
        return "BROADCAST"
    first_byte = int(mac.split(":")[0], 16)
    if first_byte & 0x01:
        return "MULTICAST"
    return "UNICAST"


# ── ARP payload decoder (EtherType 0x0806) ───────────────────────────────────

def decode_arp(payload: bytes) -> Optional[dict]:
    """
    Decode an ARP packet (RFC 826).
    Returns a dict of fields, or None if the payload is too short.

    ARP header (for Ethernet/IPv4):
      H  hardware_type  (1 = Ethernet)
      H  protocol_type  (0x0800 = IPv4)
      B  hw_addr_len    (6 for Ethernet)
      B  proto_addr_len (4 for IPv4)
      H  operation      (1 = request, 2 = reply)
      6s sender_hw_addr
      4s sender_proto_addr
      6s target_hw_addr
      4s target_proto_addr
    """
    if len(payload) < 28:
        return None
    (hw_type, proto_type, hw_len, proto_len, operation,
     sender_mac, sender_ip_raw,
     target_mac, target_ip_raw) = struct.unpack("!HHBBH6s4s6s4s", payload[:28])

    sender_ip = ".".join(str(b) for b in sender_ip_raw)
    target_ip = ".".join(str(b) for b in target_ip_raw)
    op_name = {1: "REQUEST", 2: "REPLY"}.get(operation, f"UNKNOWN({operation})")

    return {
        "hw_type":    f"0x{hw_type:04x} ({'Ethernet' if hw_type == 1 else '?'})",
        "proto_type": f"0x{proto_type:04x} ({'IPv4' if proto_type == 0x0800 else '?'})",
        "hw_len":     hw_len,
        "proto_len":  proto_len,
        "operation":  f"{operation} ({op_name})",
        "sender_mac": bytes_to_mac(sender_mac),
        "sender_ip":  sender_ip,
        "target_mac": bytes_to_mac(target_mac),
        "target_ip":  target_ip,
    }


# ── IPv4 header brief decoder ─────────────────────────────────────────────────

def decode_ipv4_brief(payload: bytes) -> Optional[dict]:
    """Extract the key fields from an IPv4 header (first 20 bytes)."""
    if len(payload) < 20:
        return None
    (ver_ihl, tos, total_len, ident, flags_frag, ttl, protocol,
     checksum, src_raw, dst_raw) = struct.unpack("!BBHHHBBH4s4s", payload[:20])
    version = (ver_ihl >> 4) & 0xF
    ihl     = ver_ihl & 0xF
    src     = ".".join(str(b) for b in src_raw)
    dst     = ".".join(str(b) for b in dst_raw)
    proto   = {1: "ICMP", 6: "TCP", 17: "UDP"}.get(protocol, str(protocol))
    return {
        "version":      version,
        "ihl_bytes":    ihl * 4,
        "total_length": total_len,
        "ttl":          ttl,
        "protocol":     f"{protocol} ({proto})",
        "src":          src,
        "dst":          dst,
    }


# ── Frame parser ──────────────────────────────────────────────────────────────

def parse_ethernet_frame(raw: bytes) -> None:
    """
    Parse a raw Ethernet II frame byte string.
    Prints each field with offset, size, value, and description.
    """
    if len(raw) < 14:
        print(f"ERROR: Frame too short ({len(raw)} bytes; minimum Ethernet header is 14)")
        sys.exit(1)

    dst_mac_bytes = raw[0:6]
    src_mac_bytes = raw[6:12]
    ethertype     = struct.unpack("!H", raw[12:14])[0]
    payload       = raw[14:]

    dst_mac = bytes_to_mac(dst_mac_bytes)
    src_mac = bytes_to_mac(src_mac_bytes)

    print("=" * 62)
    print("  Ethernet II Frame Parser")
    print("=" * 62)
    print(f"  Frame size: {len(raw)} bytes  "
          f"(header=14 B, payload={len(payload)} B)")
    print()

    # Header fields table
    fields = [
        ("0–5",   "Destination MAC", dst_mac,
         f"[{mac_type(dst_mac)}]"),
        ("6–11",  "Source MAC",      src_mac,
         f"[{mac_type(src_mac)}]"),
        ("12–13", "EtherType",       f"0x{ethertype:04x}",
         ethertype_name(ethertype)),
        ("14+",   "Payload",         f"{len(payload)} bytes",
         "see decoded payload below"),
    ]

    col = [10, 20, 22, 0]
    header_line = (f"  {'Offset':<{col[0]}}  {'Field':<{col[1]}}"
                   f"  {'Value':<{col[2]}}  Description")
    print(header_line)
    print("  " + "─" * (sum(col[:3]) + 8))
    for offset, name, value, desc in fields:
        print(f"  {offset:<{col[0]}}  {name:<{col[1]}}  {value:<{col[2]}}  {desc}")

    # Raw hex display
    print()
    print("  Raw hex dump:")
    for i in range(0, len(raw), 16):
        chunk  = raw[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"    0x{i:04x}:  {hex_part:<48}  {asc_part}")

    # Decoded payload
    print()
    print(f"  Decoded payload (EtherType = 0x{ethertype:04x}):")
    if ethertype == 0x0806:
        arp = decode_arp(payload)
        if arp:
            print("  ARP Packet:")
            for k, v in arp.items():
                print(f"    {k:<20} {v}")
        else:
            print("  (ARP payload too short to decode)")
    elif ethertype == 0x0800:
        ip = decode_ipv4_brief(payload)
        if ip:
            print("  IPv4 Header (brief):")
            for k, v in ip.items():
                print(f"    {k:<20} {v}")
        else:
            print("  (IPv4 payload too short to decode)")
    elif ethertype == 0x8100:
        if len(payload) >= 4:
            vlan_tag = struct.unpack("!H", payload[0:2])[0]
            vlan_id  = vlan_tag & 0x0FFF
            pcp      = (vlan_tag >> 13) & 0x7
            inner_et = struct.unpack("!H", payload[2:4])[0]
            print(f"  802.1Q VLAN tag present:")
            print(f"    VLAN ID:  {vlan_id}")
            print(f"    PCP:      {pcp}")
            print(f"    Inner EtherType: 0x{inner_et:04x} ({ethertype_name(inner_et)})")
        else:
            print("  (VLAN tag payload too short)")
    else:
        print(f"  (payload decoding not implemented for 0x{ethertype:04x})")
        print(f"  First 16 bytes: {payload[:16].hex()}")

    print()
    print("=" * 62)


# ── built-in example frame ────────────────────────────────────────────────────

# A complete ARP request frame:
#   Dst:      ff:ff:ff:ff:ff:ff  (broadcast)
#   Src:      aa:bb:cc:dd:ee:ff  (example host)
#   EtherType: 0x0806            (ARP)
#   ARP body: "who has 192.168.1.1? tell 192.168.1.50"
EXAMPLE_FRAME_HEX = (
    "ffffffffffff"          # dst MAC
    "aabbccddeeff"          # src MAC
    "0806"                  # EtherType: ARP
    # ARP body (28 bytes):
    "0001"                  # hardware type: Ethernet
    "0800"                  # protocol type: IPv4
    "06"                    # hw addr len
    "04"                    # proto addr len
    "0001"                  # operation: REQUEST
    "aabbccddeeff"          # sender MAC
    "c0a80132"              # sender IP: 192.168.1.50
    "000000000000"          # target MAC: unknown (all zeros for request)
    "c0a80101"              # target IP: 192.168.1.1
)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) >= 2:
        # User supplied a hex string on the command line
        hex_str = sys.argv[1].replace(" ", "").replace(":", "")
        try:
            raw = bytes.fromhex(hex_str)
        except ValueError as e:
            print(f"ERROR: Invalid hex string — {e}")
            sys.exit(1)
        print(f"Parsing user-supplied frame ({len(raw)} bytes)\n")
    else:
        # Use the built-in ARP example
        raw = bytes.fromhex(EXAMPLE_FRAME_HEX)
        print("Parsing built-in ARP request example\n")
        print(f"  (pass your own hex string as an argument to parse a different frame)\n")

    parse_ethernet_frame(raw)


if __name__ == "__main__":
    main()

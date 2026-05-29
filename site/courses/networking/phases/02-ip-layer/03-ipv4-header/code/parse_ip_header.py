# Run: python3 parse_ip_header.py
#!/usr/bin/env python3
"""
parse_ip_header.py — Parse every field in a hardcoded IPv4 header hex string.

Demonstrates:
  - struct.unpack() for parsing binary network data
  - All 13 IPv4 header fields with names, values, and descriptions
  - Flag bits (DF/MF) and fragment offset parsing
  - IHL calculation (words → bytes)
  - Protocol number lookup

No third-party libraries. Python 3.8+ stdlib only.

Usage:
    python3 parse_ip_header.py              # parse the built-in example
    python3 parse_ip_header.py <hex_string> # parse your own IP packet hex
                                            # (spaces are stripped)
"""

import socket
import struct
import sys


# ── Protocol number lookup ────────────────────────────────────────────────────

PROTOCOLS: dict[int, str] = {
    1:   "ICMP  (Internet Control Message Protocol)",
    2:   "IGMP  (Internet Group Management Protocol)",
    6:   "TCP   (Transmission Control Protocol)",
    17:  "UDP   (User Datagram Protocol)",
    41:  "IPv6  encapsulated in IPv4",
    47:  "GRE   (Generic Routing Encapsulation)",
    50:  "ESP   (IPsec Encapsulating Security Payload)",
    51:  "AH    (IPsec Authentication Header)",
    89:  "OSPF  (Open Shortest Path First)",
    132: "SCTP  (Stream Control Transmission Protocol)",
}

DSCP_NAMES: dict[int, str] = {
    0:  "CS0/BE (Best Effort)",
    8:  "CS1 (Low Priority)",
    16: "CS2",
    24: "CS3",
    32: "CS4",
    40: "CS5",
    46: "EF  (Expedited Forwarding — voice/video)",
    48: "CS6 (Network Control)",
    56: "CS7",
}


# ── Checksum verification ─────────────────────────────────────────────────────

def verify_checksum(header_bytes: bytes) -> bool:
    """
    Verify IPv4 header checksum using the one's-complement sum algorithm.
    The sum of all 16-bit words (including the checksum field) should be 0xFFFF.
    Returns True if the checksum is valid.
    """
    if len(header_bytes) % 2 != 0:
        header_bytes += b'\x00'
    total = 0
    for i in range(0, len(header_bytes), 2):
        word = (header_bytes[i] << 8) | header_bytes[i + 1]
        total += word
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return total == 0xFFFF


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_ipv4_header(raw: bytes) -> None:
    """
    Parse and print every field of an IPv4 header.
    raw must start with the IP header (no Ethernet header prepended).
    """
    if len(raw) < 20:
        print(f"ERROR: Need at least 20 bytes, got {len(raw)}")
        sys.exit(1)

    # Unpack the fixed 20-byte IPv4 header
    # Format: !BBHHHBBH4s4s
    #   B  version_ihl     (1 byte)
    #   B  tos             (1 byte)
    #   H  total_length    (2 bytes)
    #   H  identification  (2 bytes)
    #   H  flags_frag      (2 bytes)
    #   B  ttl             (1 byte)
    #   B  protocol        (1 byte)
    #   H  checksum        (2 bytes)
    #   4s src_addr        (4 bytes)
    #   4s dst_addr        (4 bytes)
    (ver_ihl, tos, total_len, ident, flags_frag,
     ttl, protocol, checksum,
     src_bytes, dst_bytes) = struct.unpack("!BBHHHBBH4s4s", raw[:20])

    version = (ver_ihl >> 4) & 0xF
    ihl     = ver_ihl & 0xF
    ihl_bytes = ihl * 4

    # DSCP and ECN are packed into the ToS byte
    dscp = (tos >> 2) & 0x3F
    ecn  = tos & 0x03

    # Flags (top 3 bits of flags_frag) and fragment offset (low 13 bits)
    reserved = bool(flags_frag & 0x8000)
    df       = bool(flags_frag & 0x4000)
    mf       = bool(flags_frag & 0x2000)
    frag_off = flags_frag & 0x1FFF

    src = socket.inet_ntoa(src_bytes)
    dst = socket.inet_ntoa(dst_bytes)

    # Checksum verification
    chk_valid = verify_checksum(raw[:ihl_bytes])

    # ── Print field table ─────────────────────────────────────────────────────
    W = 64
    print("=" * W)
    print("  IPv4 Header Parser")
    print("=" * W)
    print(f"  Raw bytes (first 20): {raw[:20].hex()}")
    print()

    rows = [
        # (offset, size, field_name, raw_value, description)
        ("0",     "4 bits", "Version",
         str(version),
         f"{'IPv4' if version == 4 else 'IPv6' if version == 6 else 'unknown'}"),
        ("0",     "4 bits", "IHL (Internet Header Length)",
         str(ihl),
         f"{ihl} × 4 = {ihl_bytes} bytes"
         + (" (standard, no options)" if ihl == 5 else " (options present)")),
        ("1",     "6 bits", "DSCP",
         f"0x{dscp:02X} ({dscp})",
         DSCP_NAMES.get(dscp, "Custom QoS marking")),
        ("1",     "2 bits", "ECN",
         str(ecn),
         "00=non-ECT, 01/10=ECT capable, 11=congestion"),
        ("2–3",   "2 bytes","Total Length",
         str(total_len),
         f"IP header ({ihl_bytes} B) + payload ({total_len - ihl_bytes} B)"),
        ("4–5",   "2 bytes","Identification",
         f"0x{ident:04X} ({ident})",
         "Fragment group ID — all fragments of same datagram share this value"),
        ("6",     "1 bit",  "Reserved flag",
         "1" if reserved else "0",
         "Must be 0"),
        ("6",     "1 bit",  "DF (Don't Fragment)",
         "1" if df else "0",
         "1 = drop packet if too big instead of fragmenting"),
        ("6",     "1 bit",  "MF (More Fragments)",
         "1" if mf else "0",
         "1 = more fragments follow; 0 = this is the last fragment"),
        ("6–7",   "13 bits","Fragment Offset",
         str(frag_off),
         f"{frag_off} × 8 = {frag_off * 8} bytes from start of original datagram"),
        ("8",     "1 byte", "TTL (Time to Live)",
         str(ttl),
         f"Hops remaining; 64/128 are common starting values"),
        ("9",     "1 byte", "Protocol",
         f"{protocol}",
         PROTOCOLS.get(protocol, f"Unknown protocol {protocol}")),
        ("10–11", "2 bytes","Header Checksum",
         f"0x{checksum:04X}",
         f"{'VALID' if chk_valid else 'INVALID — header may be corrupted'}"),
        ("12–15", "4 bytes","Source IP",
         src,
         "Sender's IP address"),
        ("16–19", "4 bytes","Destination IP",
         dst,
         "Intended recipient's IP address"),
    ]

    col = (6, 9, 30, 16, 0)
    hdr = (f"  {'Offset':<{col[0]}}  {'Size':<{col[1]}}  "
           f"{'Field':<{col[2]}}  {'Value':<{col[3]}}  Description")
    print(hdr)
    print("  " + "─" * (sum(col[:4]) + 10))
    for off, sz, name, val, desc in rows:
        print(f"  {off:<{col[0]}}  {sz:<{col[1]}}  {name:<{col[2]}}"
              f"  {val:<{col[3]}}  {desc}")

    # ── Flags in binary ───────────────────────────────────────────────────────
    print()
    flags_byte = (flags_frag >> 8) & 0xFF
    print(f"  Flags+FragOffset word (bytes 6–7): 0x{flags_frag:04X}  "
          f"= {format(flags_frag, '016b')}")
    print(f"    Bit 15 (reserved):  {int(reserved)}")
    print(f"    Bit 14 (DF):        {int(df)}")
    print(f"    Bit 13 (MF):        {int(mf)}")
    print(f"    Bits 12–0 (offset): {frag_off}")

    # ── Options ───────────────────────────────────────────────────────────────
    if ihl_bytes > 20:
        options = raw[20:ihl_bytes]
        print(f"\n  Options ({len(options)} bytes): {options.hex()}")
    else:
        print("\n  Options: none (IHL = 5, standard 20-byte header)")

    print()
    print(f"  Payload starts at byte {ihl_bytes} (length = {total_len - ihl_bytes} bytes)")
    print("=" * W)
    print()


# ── Built-in example ──────────────────────────────────────────────────────────

# A synthetic IPv4 header for a TCP packet:
#   Src: 10.0.0.1  Dst: 93.184.216.34 (example.com)
#   Protocol: TCP (6), TTL: 128, DF flag set, ID: 0x1234
#   Total length: 60 (20-byte header + 40-byte TCP payload)
#   Checksum: 0 (we skip real computation in this static example)
EXAMPLE_HEX = (
    "45"      # version=4, IHL=5
    "00"      # DSCP/ECN = 0 (best effort)
    "003c"    # total length = 60
    "1234"    # identification = 0x1234
    "4000"    # flags=0x40 (DF=1, MF=0), frag_offset=0
    "80"      # TTL = 128
    "06"      # protocol = 6 (TCP)
    "0000"    # checksum = 0 (skipped for static example)
    "0a000001"  # source IP: 10.0.0.1
    "5db8d822"  # dest IP: 93.184.216.34 (example.com)
)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) >= 2:
        hex_str = sys.argv[1].replace(" ", "")
        try:
            raw = bytes.fromhex(hex_str)
        except ValueError as e:
            print(f"ERROR: Invalid hex string — {e}")
            sys.exit(1)
        print(f"Parsing user-supplied IP header ({len(raw)} bytes)\n")
    else:
        raw = bytes.fromhex(EXAMPLE_HEX)
        print("Parsing built-in example:")
        print("  Src=10.0.0.1  Dst=93.184.216.34  Protocol=TCP  TTL=128  DF=1\n")

    parse_ipv4_header(raw)


if __name__ == "__main__":
    main()

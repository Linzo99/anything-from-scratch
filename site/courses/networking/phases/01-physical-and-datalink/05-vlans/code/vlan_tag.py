# Run: python3 vlan_tag.py
#!/usr/bin/env python3
"""
vlan_tag.py — Parse and construct 802.1Q VLAN-tagged Ethernet frames.

Demonstrates:
  - The 4-byte 802.1Q tag structure: TPID(2) + TCI(2)
  - TCI breakdown: PCP(3 bits) + DEI(1 bit) + VID(12 bits)
  - How the tag is inserted between Source MAC and EtherType
  - Stripping a VLAN tag to get the inner Ethernet frame
  - Constructing a tagged frame from an untagged one

No third-party libraries. Python 3.8+ stdlib only.

Usage:
    python3 vlan_tag.py           # demonstrate with built-in examples
    python3 vlan_tag.py --vlan 42 --pcp 5   # tag an example frame with VLAN 42, priority 5
"""

import argparse
import struct
import sys


# ── Constants ─────────────────────────────────────────────────────────────────

TPID_8021Q = 0x8100    # Tag Protocol ID — identifies an 802.1Q tagged frame
ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP  = 0x0806
ETHERTYPE_IPV6 = 0x86DD

ETHERTYPE_NAMES: dict[int, str] = {
    ETHERTYPE_IPV4: "IPv4",
    ETHERTYPE_ARP:  "ARP",
    ETHERTYPE_IPV6: "IPv6",
    TPID_8021Q:     "802.1Q VLAN",
}


def ethertype_name(value: int) -> str:
    return ETHERTYPE_NAMES.get(value, f"0x{value:04x}")


# ── MAC helpers ───────────────────────────────────────────────────────────────

def bytes_to_mac(b: bytes) -> str:
    return ":".join(f"{x:02x}" for x in b)


def mac_to_bytes(mac: str) -> bytes:
    parts = mac.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    return bytes(int(p, 16) for p in parts)


# ── 802.1Q tag parsing ────────────────────────────────────────────────────────

def decode_8021q_tag(tag_bytes: bytes) -> dict:
    """
    Decode a 4-byte 802.1Q tag.

    Layout (big-endian):
      Bytes 0-1: TPID  = 0x8100
      Byte  2:   [PCP: 3 bits][DEI: 1 bit][VID high: 4 bits]
      Byte  3:   [VID low: 8 bits]

    PCP = Priority Code Point (0–7, QoS)
    DEI = Drop Eligible Indicator (0 or 1)
    VID = VLAN ID (0–4095; 0 = no VLAN, 4095 = reserved)
    """
    if len(tag_bytes) < 4:
        raise ValueError("VLAN tag must be 4 bytes")

    tpid = struct.unpack("!H", tag_bytes[0:2])[0]
    tci  = struct.unpack("!H", tag_bytes[2:4])[0]

    pcp = (tci >> 13) & 0x07   # top 3 bits
    dei = (tci >> 12) & 0x01   # next 1 bit
    vid = tci & 0x0FFF          # bottom 12 bits

    return {
        "tpid": tpid,
        "tci":  tci,
        "pcp":  pcp,
        "dei":  dei,
        "vid":  vid,
    }


def encode_8021q_tag(vid: int, pcp: int = 0, dei: int = 0) -> bytes:
    """
    Construct a 4-byte 802.1Q tag.

    Args:
        vid: VLAN ID (1–4094)
        pcp: Priority Code Point (0–7)
        dei: Drop Eligible Indicator (0 or 1)
    """
    if not 0 <= vid <= 4095:
        raise ValueError(f"VID must be 0–4095, got {vid}")
    if not 0 <= pcp <= 7:
        raise ValueError(f"PCP must be 0–7, got {pcp}")
    if dei not in (0, 1):
        raise ValueError(f"DEI must be 0 or 1, got {dei}")

    tci = (pcp << 13) | (dei << 12) | vid
    return struct.pack("!HH", TPID_8021Q, tci)


# ── Frame parsing ─────────────────────────────────────────────────────────────

def parse_frame(raw: bytes) -> dict:
    """
    Parse an Ethernet frame (tagged or untagged).
    Returns a dict with all fields.
    """
    if len(raw) < 14:
        raise ValueError(f"Frame too short: {len(raw)} bytes")

    dst_mac = bytes_to_mac(raw[0:6])
    src_mac = bytes_to_mac(raw[6:12])
    ethertype = struct.unpack("!H", raw[12:14])[0]

    result = {
        "dst_mac":   dst_mac,
        "src_mac":   src_mac,
        "ethertype": ethertype,
        "tagged":    False,
        "vlan":      None,
        "payload":   raw[14:],
    }

    if ethertype == TPID_8021Q:
        # Tagged frame — bytes 12-13 are TPID, bytes 14-15 contain TCI,
        # bytes 16-17 contain the real inner EtherType
        if len(raw) < 18:
            raise ValueError("Tagged frame too short to contain inner EtherType")
        vlan_info = decode_8021q_tag(raw[12:16])
        inner_ethertype = struct.unpack("!H", raw[16:18])[0]
        result["tagged"]          = True
        result["vlan"]            = vlan_info
        result["inner_ethertype"] = inner_ethertype
        result["payload"]         = raw[18:]

    return result


def print_frame(frame: dict, label: str = "") -> None:
    """Pretty-print a parsed Ethernet frame."""
    if label:
        print(f"\n{label}")
    print("  " + "─" * 56)
    print(f"  Destination MAC : {frame['dst_mac']}")
    print(f"  Source MAC      : {frame['src_mac']}")

    if frame["tagged"]:
        v = frame["vlan"]
        print(f"  EtherType       : 0x{v['tpid']:04x}  (802.1Q VLAN tag)")
        print(f"  ┌─ 802.1Q Tag ────────────────────────────────────")
        print(f"  │  TPID (Tag Protocol ID): 0x{v['tpid']:04x}  (always 0x8100)")
        print(f"  │  TCI  (Tag Control Info): 0x{v['tci']:04x}")
        print(f"  │    PCP  (Priority):  {v['pcp']}  (0=best-effort, 7=highest)")
        print(f"  │    DEI  (Drop Elig): {v['dei']}  (0=keep, 1=drop if congested)")
        print(f"  │    VID  (VLAN ID):  {v['vid']}")
        print(f"  └──────────────────────────────────────────────────")
        inner = frame["inner_ethertype"]
        print(f"  Inner EtherType : 0x{inner:04x}  ({ethertype_name(inner)})")
    else:
        et = frame["ethertype"]
        print(f"  EtherType       : 0x{et:04x}  ({ethertype_name(et)})")

    print(f"  Payload         : {len(frame['payload'])} bytes")
    if frame["payload"]:
        preview = frame["payload"][:16].hex()
        print(f"    First 16B hex : {preview}")
    print("  " + "─" * 56)


# ── Tag / untag helpers ───────────────────────────────────────────────────────

def insert_vlan_tag(raw_untagged: bytes, vid: int,
                    pcp: int = 0, dei: int = 0) -> bytes:
    """
    Insert an 802.1Q VLAN tag into an untagged Ethernet frame.

    Untagged:  [dst(6)] [src(6)] [EtherType(2)] [payload]
    Tagged:    [dst(6)] [src(6)] [TPID(2)] [TCI(2)] [EtherType(2)] [payload]
    """
    if len(raw_untagged) < 14:
        raise ValueError("Frame too short to tag")
    dst_src   = raw_untagged[0:12]    # first 12 bytes unchanged
    ethertype = raw_untagged[12:14]   # original EtherType becomes inner EtherType
    payload   = raw_untagged[14:]
    tag       = encode_8021q_tag(vid, pcp, dei)
    return dst_src + tag + ethertype + payload


def strip_vlan_tag(raw_tagged: bytes) -> bytes:
    """
    Remove the 802.1Q VLAN tag from a tagged Ethernet frame.
    Raises ValueError if the frame is not tagged.
    """
    if len(raw_tagged) < 18:
        raise ValueError("Frame too short to be tagged")
    ethertype = struct.unpack("!H", raw_tagged[12:14])[0]
    if ethertype != TPID_8021Q:
        raise ValueError(f"Frame is not 802.1Q tagged (EtherType=0x{ethertype:04x})")
    dst_src       = raw_tagged[0:12]
    inner_etype   = raw_tagged[16:18]
    payload       = raw_tagged[18:]
    return dst_src + inner_etype + payload


# ── Main demonstration ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="802.1Q VLAN tag construction and parsing demo"
    )
    parser.add_argument("--vlan", type=int, default=10, metavar="VID",
                        help="VLAN ID to use in the demo (1–4094, default: 10)")
    parser.add_argument("--pcp",  type=int, default=0,  metavar="PCP",
                        help="Priority Code Point (0–7, default: 0)")
    args = parser.parse_args()

    VID = args.vlan
    PCP = args.pcp

    print("=" * 60)
    print("  802.1Q VLAN Tag — Construction and Parsing Demo")
    print("=" * 60)

    # ── Example 1: untagged frame ─────────────────────────────────────────────
    print("\n[1] Building an untagged Ethernet frame (IPv4)")
    untagged_hex = (
        "aabbccddeeff"   # dst MAC
        "112233445566"   # src MAC
        "0800"           # EtherType: IPv4
        "deadbeef"       # payload (4 bytes, representative)
    )
    raw_untagged = bytes.fromhex(untagged_hex)
    print_frame(parse_frame(raw_untagged), label="Untagged frame:")
    print(f"  Raw bytes: {raw_untagged.hex()}")

    # ── Example 2: insert tag ─────────────────────────────────────────────────
    print(f"\n[2] Inserting 802.1Q tag  VID={VID}  PCP={PCP}  DEI=0")
    raw_tagged = insert_vlan_tag(raw_untagged, vid=VID, pcp=PCP)
    print_frame(parse_frame(raw_tagged), label="Tagged frame:")
    print(f"  Raw bytes: {raw_tagged.hex()}")

    # Show the tag bytes explicitly
    tag_bytes = raw_tagged[12:16]
    decoded_tag = decode_8021q_tag(tag_bytes)
    print(f"\n  The 4-byte tag in binary:")
    tci_bits = format(decoded_tag["tci"], "016b")
    print(f"    {format(TPID_8021Q, '016b')}  ← TPID = 0x8100")
    print(f"    {tci_bits[:3]} {tci_bits[3]} {tci_bits[4:]}  ← TCI: PCP={tci_bits[:3]} DEI={tci_bits[3]} VID={tci_bits[4:]}")
    print(f"                                  VID={int(tci_bits[4:], 2)} (decimal)")

    # ── Example 3: strip tag ──────────────────────────────────────────────────
    print("\n[3] Stripping the VLAN tag back to untagged frame")
    raw_stripped = strip_vlan_tag(raw_tagged)
    print_frame(parse_frame(raw_stripped), label="Stripped frame:")
    print(f"  Raw bytes: {raw_stripped.hex()}")

    match = (raw_stripped == raw_untagged)
    print(f"\n  Stripped == original: {match}  ({'PASS' if match else 'FAIL'})")

    # ── Example 4: parse a pre-made tagged frame ──────────────────────────────
    print("\n[4] Parsing a known tagged frame  (VLAN 20, PCP=3)")
    known_tagged = bytes.fromhex(
        "ffffffffffff"   # dst: broadcast
        "aabbccddeeff"   # src
        "8100"           # TPID: 802.1Q
        "6014"           # TCI: PCP=3, DEI=0, VID=20  (0x6014 = 0110 0000 0001 0100)
        "0806"           # inner EtherType: ARP
        "00010800060400010000000000001234567890abcdef12345678"  # ARP body
    )
    print_frame(parse_frame(known_tagged), label="Pre-built tagged frame:")

    # ── Example 5: range of VLAN IDs ─────────────────────────────────────────
    print("\n[5] VLAN ID range reference:")
    ranges = [
        (0,    0,    "Reserved — no VLAN"),
        (1,    1,    "Default VLAN (avoid for security)"),
        (2,    1001, "Normal user VLANs"),
        (1002, 1005, "FDDI and Token Ring (legacy)"),
        (1006, 4094, "Extended range (IOS only on some platforms)"),
        (4095, 4095, "Reserved"),
    ]
    for lo, hi, desc in ranges:
        print(f"  {lo:>4}–{hi:<4}  {desc}")

    print()


if __name__ == "__main__":
    main()

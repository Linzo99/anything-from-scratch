# Run: python3 dns_parser.py [domain]
"""
dns_parser.py — Parse a raw DNS message from wire bytes.

Sends a real DNS A-record query to 8.8.8.8, captures the raw UDP response,
then parses it by hand using struct.  Prints:
  - Transaction ID and flags
  - Question section (name, type, class)
  - Answer records (name, TTL, type, class, RDATA)

A hardcoded hex example is also included so the parser can run offline.

Usage:
    python3 dns_parser.py              # queries example.com
    python3 dns_parser.py github.com
    python3 dns_parser.py --offline    # parse the hardcoded hex example only
"""

import socket as socket_module
import struct
import sys


# ── hardcoded DNS response for offline demo ───────────────────────────────────
# This is an actual response to "A example.com" captured from 8.8.8.8.
# Transaction ID: 0x1234  RCODE: NOERROR  Answer: 93.184.216.34
EXAMPLE_HEX = (
    "12348180000100010000000007657861"
    "6d706c6503636f6d0000010001c00c00"
    "01000100015180000493b8d822"
)


# ── header parser ─────────────────────────────────────────────────────────────

def parse_header(data: bytes) -> dict:
    """Parse the 12-byte DNS header."""
    if len(data) < 12:
        raise ValueError(f"Packet too short ({len(data)} bytes, need ≥12)")
    txid, flags, qdcount, ancount, nscount, arcount = \
        struct.unpack(">HHHHHH", data[:12])

    qr     = (flags >> 15) & 1
    opcode = (flags >> 11) & 0xF
    aa     = (flags >> 10) & 1
    tc     = (flags >>  9) & 1
    rd     = (flags >>  8) & 1
    ra     = (flags >>  7) & 1
    rcode  = flags & 0xF

    rcode_names = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL",
                   3: "NXDOMAIN", 4: "NOTIMP", 5: "REFUSED"}

    return {
        "transaction_id": txid,
        "is_response":    bool(qr),
        "authoritative":  bool(aa),
        "truncated":      bool(tc),
        "recursion_desired":   bool(rd),
        "recursion_available": bool(ra),
        "rcode":    rcode_names.get(rcode, f"UNKNOWN({rcode})"),
        "qdcount":  qdcount,
        "ancount":  ancount,
        "nscount":  nscount,
        "arcount":  arcount,
    }


# ── domain-name parser (handles compression) ─────────────────────────────────

def parse_name(data: bytes, offset: int) -> tuple:
    """
    Parse a DNS label-encoded name starting at `offset`.
    Returns (name_string, offset_after_name).
    Handles compression pointers (top bits 0b11).
    """
    labels = []
    return_offset = None
    jumps = 0

    while True:
        if offset >= len(data):
            raise ValueError(f"Name parse overran packet at offset {offset}")
        length = data[offset]

        if length == 0:
            offset += 1
            break
        elif (length & 0xC0) == 0xC0:
            # Compression pointer: 14-bit offset into the full message
            jumps += 1
            if jumps > 10:
                raise ValueError("Too many compression pointer hops")
            if offset + 1 >= len(data):
                raise ValueError("Truncated compression pointer")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if return_offset is None:
                return_offset = offset + 2
            offset = pointer
        else:
            end = offset + 1 + length
            if end > len(data):
                raise ValueError("Label extends past end of packet")
            labels.append(data[offset + 1:end].decode("ascii", errors="replace"))
            offset = end

    final_offset = return_offset if return_offset is not None else offset
    return ".".join(labels), final_offset


# ── question-section parser ───────────────────────────────────────────────────

TYPE_NAMES  = {1: "A", 2: "NS", 5: "CNAME", 15: "MX",
               16: "TXT", 28: "AAAA", 255: "ANY"}
CLASS_NAMES = {1: "IN"}


def parse_question(data: bytes, offset: int) -> tuple:
    """Parse one question entry. Returns (question_dict, new_offset)."""
    name, offset = parse_name(data, offset)
    if offset + 4 > len(data):
        raise ValueError("Question section truncated")
    qtype, qclass = struct.unpack(">HH", data[offset:offset + 4])
    offset += 4
    return {
        "name":  name,
        "type":  TYPE_NAMES.get(qtype, f"TYPE{qtype}"),
        "class": CLASS_NAMES.get(qclass, f"CLASS{qclass}"),
    }, offset


# ── RDATA decoder ─────────────────────────────────────────────────────────────

def decode_rdata(rtype: int, rdata: bytes, full_msg: bytes, rdata_offset: int) -> str:
    """Decode RDATA based on record type."""
    if rtype == 1:   # A
        return socket_module.inet_ntoa(rdata) if len(rdata) == 4 \
               else f"<malformed A: {rdata.hex()}>"
    if rtype == 28:  # AAAA
        return socket_module.inet_ntop(socket_module.AF_INET6, rdata) \
               if len(rdata) == 16 else f"<malformed AAAA: {rdata.hex()}>"
    if rtype in (5, 2):   # CNAME / NS
        name, _ = parse_name(full_msg, rdata_offset)
        return name
    if rtype == 15:  # MX
        if len(rdata) < 3:
            return f"<malformed MX>"
        pref = struct.unpack(">H", rdata[:2])[0]
        exchange, _ = parse_name(full_msg, rdata_offset + 2)
        return f"priority={pref} exchange={exchange}"
    if rtype == 16:  # TXT
        parts, pos = [], 0
        while pos < len(rdata):
            l = rdata[pos]; pos += 1
            parts.append(rdata[pos:pos + l].decode("utf-8", errors="replace"))
            pos += l
        return " ".join(f'"{s}"' for s in parts)
    return rdata.hex()


def parse_rr(data: bytes, offset: int) -> tuple:
    """Parse one Resource Record. Returns (rr_dict, new_offset)."""
    name, offset = parse_name(data, offset)
    if offset + 10 > len(data):
        raise ValueError(f"RR header truncated at offset {offset}")
    rtype, rclass, ttl, rdlength = struct.unpack(">HHIH", data[offset:offset + 10])
    offset += 10
    rdata_offset = offset
    rdata = data[offset:offset + rdlength]
    offset += rdlength
    return {
        "name":  name,
        "type":  TYPE_NAMES.get(rtype, f"TYPE{rtype}"),
        "class": CLASS_NAMES.get(rclass, f"CLASS{rclass}"),
        "ttl":   ttl,
        "rdata": decode_rdata(rtype, rdata, data, rdata_offset),
    }, offset


# ── full message parser ───────────────────────────────────────────────────────

def parse_dns_message(data: bytes) -> dict:
    """Parse a complete DNS message from raw bytes."""
    header = parse_header(data)
    offset = 12

    questions = []
    for _ in range(header["qdcount"]):
        q, offset = parse_question(data, offset)
        questions.append(q)

    answers = []
    for _ in range(header["ancount"]):
        rr, offset = parse_rr(data, offset)
        answers.append(rr)

    return {"header": header, "questions": questions, "answers": answers}


def print_dns_message(msg: dict, label: str = "") -> None:
    if label:
        print(f"\n{'='*55}")
        print(f"  {label}")
        print(f"{'='*55}")

    h = msg["header"]
    print(f"Transaction ID : 0x{h['transaction_id']:04x}")
    print(f"Type           : {'Response' if h['is_response'] else 'Query'}")
    print(f"RCODE          : {h['rcode']}")
    print(f"Authoritative  : {h['authoritative']}")
    print(f"Truncated      : {h['truncated']}")
    print(f"Counts         : "
          f"QD={h['qdcount']} AN={h['ancount']} NS={h['nscount']} AR={h['arcount']}")

    print("\nQUESTION SECTION:")
    for q in msg["questions"]:
        print(f"  {q['name']:<35} {q['class']}  {q['type']}")

    print("\nANSWER SECTION:")
    if not msg["answers"]:
        print("  (no answers)")
    for rr in msg["answers"]:
        print(f"  {rr['name']:<35} {rr['ttl']:<8} {rr['class']}  {rr['type']:<8} {rr['rdata']}")


# ── network query ─────────────────────────────────────────────────────────────

def build_query(domain: str, qtype: int = 1) -> tuple:
    txid  = 0xABCD
    flags = 0x0100   # RD=1 (recursion desired)
    header = struct.pack(">HHHHHH", txid, flags, 1, 0, 0, 0)
    name_bytes = b""
    for label in domain.rstrip(".").split("."):
        enc = label.encode("ascii")
        name_bytes += bytes([len(enc)]) + enc
    name_bytes += b"\x00"
    question = struct.pack(">HH", qtype, 1)
    return header + name_bytes + question, txid


def send_query(domain: str, server: str = "8.8.8.8") -> bytes:
    """Send a DNS query over UDP and return raw response bytes."""
    packet, _ = build_query(domain)
    sock = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)
    sock.settimeout(5.0)
    try:
        sock.sendto(packet, (server, 53))
        response, _ = sock.recvfrom(512)
    finally:
        sock.close()
    return response


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    offline = "--offline" in sys.argv
    domain  = next((a for a in sys.argv[1:] if not a.startswith("--")), "example.com")

    # Always show the hardcoded offline example first
    print("\n--- Parsing hardcoded hex example (offline) ---")
    try:
        raw = bytes.fromhex(EXAMPLE_HEX)
        msg = parse_dns_message(raw)
        print_dns_message(msg, "Hardcoded example.com A response")
        print(f"\n  Raw bytes ({len(raw)} total): {raw.hex()}")
    except Exception as exc:
        print(f"  Error parsing hardcoded example: {exc}")

    if offline:
        return

    # Live query
    print(f"\n--- Querying A record for: {domain} ---")
    try:
        raw = send_query(domain)
        msg = parse_dns_message(raw)
        print_dns_message(msg, f"Live response for {domain}")
        print(f"\n  Raw bytes ({len(raw)} total): {raw.hex()}")
    except socket_module.timeout:
        print("  Timeout — check your network connection.")
    except Exception as exc:
        print(f"  Error: {exc}")


if __name__ == "__main__":
    main()

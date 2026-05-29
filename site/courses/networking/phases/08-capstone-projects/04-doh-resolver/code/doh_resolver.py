#!/usr/bin/env python3
# Run: python3 doh_resolver.py
"""
DNS-over-HTTPS (DoH) Resolver
Sends DNS queries to https://1.1.1.1/dns-query (Cloudflare DoH).

Two modes:
  1. Command-line lookup: python3 doh_resolver.py example.com [A|AAAA|MX|TXT|NS]
  2. Local DoH proxy:     python3 doh_resolver.py --proxy [port]
     Listens on UDP 127.0.0.1:5353 and forwards queries to Cloudflare DoH.
     Test with: dig @127.0.0.1 -p 5353 example.com

Constructs DNS wire-format queries, sends as POST with
Content-Type: application/dns-message, parses A records from the response.

Requires: Python 3.8+, stdlib only (urllib.request, socket, struct).
"""

import sys
import socket
import struct
import base64
import random
import argparse
import urllib.request
import urllib.error

DOH_SERVER = "https://1.1.1.1/dns-query"

# DNS record type codes
QTYPES = {
    "A":     1,
    "NS":    2,
    "CNAME": 5,
    "MX":    15,
    "TXT":   16,
    "AAAA":  28,
}
QTYPE_NAMES = {v: k for k, v in QTYPES.items()}

# DNS RCODE names
RCODES = {
    0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL",
    3: "NXDOMAIN", 4: "NOTIMP", 5: "REFUSED",
}


# ── DNS wire format builders ──────────────────────────────────────────────────

def encode_name(domain: str) -> bytes:
    """
    Encode a domain name in DNS wire format.
    example.com → b'\x07example\x03com\x00'
    """
    labels = b""
    for part in domain.rstrip(".").encode().split(b"."):
        labels += bytes([len(part)]) + part
    labels += b"\x00"
    return labels


def build_query(domain: str, qtype: int = 1) -> tuple:
    """
    Build a DNS query packet.
    Returns (raw_bytes, query_id).

    Header (12 bytes):
      ID (2)  flags (2)  QDCOUNT (2)  ANCOUNT (2)  NSCOUNT (2)  ARCOUNT (2)

    Question section:
      QNAME (variable)  QTYPE (2)  QCLASS (2, 1=IN)
    """
    query_id = random.randint(1, 65535)
    flags    = 0x0100   # QR=0 (query), RD=1 (recursion desired)
    header   = struct.pack("!HHHHHH", query_id, flags, 1, 0, 0, 0)
    question = encode_name(domain) + struct.pack("!HH", qtype, 1)
    return header + question, query_id


# ── DoH transport ─────────────────────────────────────────────────────────────

def resolve_via_doh(raw_query: bytes, server: str = DOH_SERVER) -> bytes:
    """
    Send raw_query to a DoH server using POST with application/dns-message.
    Returns the raw DNS response bytes, or raises on error.

    RFC 8484 specifies two methods:
      GET  ?dns=<base64url-encoded-query>
      POST body=<raw-bytes>  Content-Type: application/dns-message

    We use POST because it's cleaner for large queries.
    """
    req = urllib.request.Request(
        server,
        data=raw_query,
        headers={
            "Content-Type": "application/dns-message",
            "Accept":        "application/dns-message",
            "User-Agent":    "doh-resolver-py/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"DoH HTTP error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"DoH network error: {e.reason}")


# ── DNS response parser ───────────────────────────────────────────────────────

def parse_name(data: bytes, offset: int) -> tuple:
    """
    Parse a DNS domain name from data starting at offset.
    Handles compression pointers (two high bits = 11).
    Returns (name_str, new_offset).
    """
    labels = []
    visited = set()   # loop detection for pointers
    jumped  = False
    orig_offset = offset

    while True:
        if offset >= len(data):
            break
        length = data[offset]

        if length == 0:
            offset += 1
            break

        if (length & 0xC0) == 0xC0:
            # Compression pointer
            if offset + 1 >= len(data):
                break
            ptr = struct.unpack("!H", data[offset:offset + 2])[0] & 0x3FFF
            if ptr in visited:
                break  # loop — bail out
            visited.add(ptr)
            if not jumped:
                orig_offset = offset + 2
                jumped = True
            offset = ptr
            continue

        offset += 1
        end = offset + length
        if end > len(data):
            break
        labels.append(data[offset:end].decode("utf-8", errors="replace"))
        offset = end

    name = ".".join(labels) if labels else "."
    return name, (orig_offset if jumped else offset)


def parse_rdata_a(data: bytes) -> str:
    """Parse a 4-byte A record RDATA into dotted-decimal."""
    if len(data) != 4:
        return "(invalid)"
    return socket.inet_ntoa(data)


def parse_rdata_aaaa(data: bytes) -> str:
    """Parse a 16-byte AAAA record."""
    if len(data) != 16:
        return "(invalid)"
    return socket.inet_ntop(socket.AF_INET6, data)


def parse_rdata_mx(data: bytes, full_packet: bytes, offset: int) -> str:
    """Parse an MX RDATA (2-byte preference + domain name)."""
    if len(data) < 3:
        return "(invalid)"
    preference = struct.unpack("!H", data[:2])[0]
    name, _ = parse_name(full_packet, offset + 2)
    return f"{preference} {name}"


def parse_dns_response(data: bytes) -> dict:
    """
    Parse a raw DNS response.
    Returns a dict: {
      "id", "rcode", "rcode_name", "answers": [
        {"name", "type", "type_name", "ttl", "rdata"}
      ]
    }
    """
    if len(data) < 12:
        raise ValueError("DNS response too short")

    hdr = struct.unpack("!HHHHHH", data[:12])
    query_id  = hdr[0]
    flags     = hdr[1]
    qdcount   = hdr[2]
    ancount   = hdr[3]
    rcode     = flags & 0x000F

    result = {
        "id":         query_id,
        "rcode":      rcode,
        "rcode_name": RCODES.get(rcode, f"RCODE{rcode}"),
        "answers":    [],
    }

    offset = 12

    # Skip question section
    for _ in range(qdcount):
        _, offset = parse_name(data, offset)
        offset += 4   # QTYPE (2) + QCLASS (2)

    # Parse answer section
    for _ in range(ancount):
        name, offset = parse_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10

        rdata_raw = data[offset:offset + rdlength]
        offset   += rdlength

        type_name = QTYPE_NAMES.get(rtype, f"TYPE{rtype}")

        if rtype == 1 and rdlength == 4:    # A
            rdata = parse_rdata_a(rdata_raw)
        elif rtype == 28 and rdlength == 16: # AAAA
            rdata = parse_rdata_aaaa(rdata_raw)
        elif rtype in (2, 5):               # NS, CNAME
            rdata, _ = parse_name(data, offset - rdlength)
        elif rtype == 15:                   # MX
            rdata = parse_rdata_mx(rdata_raw, data, offset - rdlength)
        elif rtype == 16:                   # TXT
            # TXT RDATA: each string is prefixed by 1-byte length
            txt_parts = []
            pos = 0
            while pos < len(rdata_raw):
                slen = rdata_raw[pos]
                pos += 1
                txt_parts.append(rdata_raw[pos:pos + slen].decode("utf-8", errors="replace"))
                pos += slen
            rdata = " ".join(txt_parts)
        else:
            rdata = rdata_raw.hex()

        result["answers"].append({
            "name":      name,
            "type":      rtype,
            "type_name": type_name,
            "ttl":       ttl,
            "rdata":     rdata,
        })

    return result


# ── Command-line lookup ───────────────────────────────────────────────────────

def lookup(domain: str, qtype_str: str = "A") -> None:
    """Resolve domain and print results to stdout."""
    qtype = QTYPES.get(qtype_str.upper(), 1)
    qtype_name = qtype_str.upper()

    print(f"\nResolving {domain} {qtype_name} via DoH ({DOH_SERVER})")
    print(f"{'─'*50}")

    raw_query, query_id = build_query(domain, qtype)
    try:
        raw_response = resolve_via_doh(raw_query)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        result = parse_dns_response(raw_response)
    except ValueError as e:
        print(f"Parse error: {e}")
        sys.exit(1)

    rcode_name = result["rcode_name"]
    answers    = result["answers"]

    if result["rcode"] != 0:
        print(f"Status: {rcode_name} (no records)")
        return

    if not answers:
        print(f"Status: NOERROR, but no answer records")
        return

    print(f"Status: {rcode_name}")
    print(f"Answers ({len(answers)}):")
    for ans in answers:
        print(f"  {ans['name']:<30}  TTL={ans['ttl']:<6}  {ans['type_name']:<6}  {ans['rdata']}")
    print()


# ── Local DoH proxy ───────────────────────────────────────────────────────────

def parse_query_name_offset(data: bytes) -> int:
    """
    Skip past the QNAME in the question section to find the QTYPE.
    Returns offset just before QTYPE.
    """
    offset = 12  # skip DNS header
    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if (length & 0xC0) == 0xC0:
            offset += 2
            break
        offset += 1 + length
    return offset


def run_proxy(host: str = "127.0.0.1", port: int = 5353) -> None:
    """
    UDP DNS proxy: receives standard DNS queries and forwards them via DoH.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    print(f"DoH proxy listening on UDP {host}:{port}")
    print(f"Forwarding to: {DOH_SERVER}")
    print(f"Test: dig @{host} -p {port} example.com A")
    print(f"Test: dig @{host} -p {port} google.com AAAA")
    print("Ctrl+C to stop\n")

    while True:
        try:
            data, addr = sock.recvfrom(512)
        except KeyboardInterrupt:
            print("\nProxy stopped.")
            break

        # Log the query
        try:
            name, _ = parse_name(data, 12)
            qtype_offset = parse_query_name_offset(data)
            qtype_val = struct.unpack("!H", data[qtype_offset:qtype_offset + 2])[0]
            qtype_name = QTYPE_NAMES.get(qtype_val, f"TYPE{qtype_val}")
            print(f"Query: {name} {qtype_name} from {addr[0]}:{addr[1]}", flush=True)
        except Exception:
            print(f"Query from {addr[0]}:{addr[1]} (parse error)", flush=True)

        # Forward via DoH
        try:
            response = resolve_via_doh(data)
            sock.sendto(response, addr)
        except RuntimeError as e:
            print(f"  DoH error: {e} — sending SERVFAIL")
            # Build a minimal SERVFAIL response (RCODE=2)
            query_id = data[:2]
            servfail = query_id + b"\x80\x02" + b"\x00\x00" * 4
            sock.sendto(servfail, addr)

    sock.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="DNS-over-HTTPS resolver (lookup + local proxy mode)"
    )
    parser.add_argument("domain",   nargs="?",   help="Domain to resolve (lookup mode)")
    parser.add_argument("qtype",    nargs="?",   default="A",
                        help="Query type: A, AAAA, MX, TXT, NS, CNAME (default: A)")
    parser.add_argument("--proxy",  action="store_true",
                        help="Run as local DoH proxy (listens on UDP 127.0.0.1:5353)")
    parser.add_argument("--port",   type=int,    default=5353,
                        help="Proxy listen port (default: 5353)")
    parser.add_argument("--server", default=DOH_SERVER,
                        help=f"DoH server URL (default: {DOH_SERVER})")
    args = parser.parse_args()

    global DOH_SERVER
    DOH_SERVER = args.server

    if args.proxy:
        run_proxy(port=args.port)
    elif args.domain:
        lookup(args.domain, args.qtype)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python3 doh_resolver.py example.com")
        print("  python3 doh_resolver.py example.com AAAA")
        print("  python3 doh_resolver.py google.com MX")
        print("  python3 doh_resolver.py --proxy")
        print("  python3 doh_resolver.py --proxy --port 5353")
        sys.exit(0)


if __name__ == "__main__":
    main()

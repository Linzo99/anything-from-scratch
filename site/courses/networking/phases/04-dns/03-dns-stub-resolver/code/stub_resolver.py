# Run: python3 stub_resolver.py example.com
"""
stub_resolver.py — Minimal DNS stub resolver using raw sockets.

Builds a DNS query packet from scratch (binary struct packing), sends it
to 8.8.8.8:53 via UDP, parses the response, and prints the IP addresses.
No external libraries.

A stub resolver sends queries to one configured recursive resolver and
trusts it to do the full root→TLD→authoritative walk.

Usage:
    python3 stub_resolver.py <domain> [type] [nameserver]
    python3 stub_resolver.py example.com
    python3 stub_resolver.py google.com AAAA
    python3 stub_resolver.py gmail.com MX
    python3 stub_resolver.py github.com NS
    python3 stub_resolver.py github.com TXT
    python3 stub_resolver.py example.com A 1.1.1.1
    python3 stub_resolver.py thisdoesnotexist99999.com    # expect NXDOMAIN
"""

import socket
import struct
import random
import sys
import time

# ── record type constants ─────────────────────────────────────────────────────

TYPE_A     = 1
TYPE_NS    = 2
TYPE_CNAME = 5
TYPE_MX    = 15
TYPE_TXT   = 16
TYPE_AAAA  = 28

TYPE_NAMES = {1: "A", 2: "NS", 5: "CNAME", 15: "MX", 16: "TXT", 28: "AAAA"}

RCODE_NAMES = {
    0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL",
    3: "NXDOMAIN", 4: "NOTIMP", 5: "REFUSED",
}


class DNSError(Exception):
    pass


# ── query builder ─────────────────────────────────────────────────────────────

def encode_name(domain: str) -> bytes:
    """Encode 'www.example.com' as DNS label format."""
    result = b""
    for label in domain.rstrip(".").split("."):
        if not label:
            continue
        enc = label.encode("ascii")
        if len(enc) > 63:
            raise ValueError(f"Label '{label}' exceeds 63-byte limit")
        result += bytes([len(enc)]) + enc
    return result + b"\x00"


def build_query(domain: str, qtype: int = TYPE_A) -> tuple:
    """Build a DNS query packet. Returns (packet_bytes, transaction_id)."""
    txid   = random.randint(1, 65535)
    flags  = 0x0100    # QR=0, RD=1 (request recursion)
    header = struct.pack(">HHHHHH", txid, flags, 1, 0, 0, 0)
    packet = header + encode_name(domain) + struct.pack(">HH", qtype, 1)
    return packet, txid


# ── response parser ───────────────────────────────────────────────────────────

def parse_name(data: bytes, offset: int) -> tuple:
    """Parse a DNS label-encoded name (with compression). Returns (name, offset)."""
    labels = []
    return_offset = None
    jumps = 0

    while True:
        if offset >= len(data):
            raise DNSError("Name parse overran packet")
        length = data[offset]

        if length == 0:
            offset += 1
            break
        elif (length & 0xC0) == 0xC0:
            jumps += 1
            if jumps > 10:
                raise DNSError("Compression pointer loop detected")
            if offset + 1 >= len(data):
                raise DNSError("Truncated compression pointer")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if return_offset is None:
                return_offset = offset + 2
            offset = pointer
        else:
            end = offset + 1 + length
            labels.append(data[offset + 1:end].decode("ascii", errors="replace"))
            offset = end

    return ".".join(labels), (return_offset if return_offset is not None else offset)


def parse_header(data: bytes) -> dict:
    if len(data) < 12:
        raise DNSError(f"Response too short: {len(data)} bytes")
    txid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    return {
        "id":      txid,
        "qr":      (flags >> 15) & 1,
        "aa":      (flags >> 10) & 1,
        "tc":      (flags >>  9) & 1,
        "ra":      (flags >>  7) & 1,
        "rcode":   flags & 0xF,
        "qdcount": qd,
        "ancount": an,
        "nscount": ns,
        "arcount": ar,
    }


def parse_rr(data: bytes, offset: int) -> tuple:
    """Parse one Resource Record. Returns (rr_dict, new_offset)."""
    name, offset = parse_name(data, offset)
    if offset + 10 > len(data):
        raise DNSError("RR header truncated")
    rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
    offset += 10
    rdata_offset = offset
    rdata = data[offset:offset + rdlen]
    offset += rdlen

    # Decode RDATA
    if rtype == TYPE_A and len(rdata) == 4:
        value = socket.inet_ntoa(rdata)
    elif rtype == TYPE_AAAA and len(rdata) == 16:
        value = socket.inet_ntop(socket.AF_INET6, rdata)
    elif rtype in (TYPE_CNAME, TYPE_NS):
        value, _ = parse_name(data, rdata_offset)
    elif rtype == TYPE_MX and len(rdata) >= 3:
        pref = struct.unpack(">H", rdata[:2])[0]
        exchange, _ = parse_name(data, rdata_offset + 2)
        value = f"{exchange} (priority {pref})"
    elif rtype == TYPE_TXT:
        parts, pos = [], 0
        while pos < len(rdata):
            l = rdata[pos]; pos += 1
            parts.append(rdata[pos:pos + l].decode("utf-8", errors="replace"))
            pos += l
        value = " ".join(parts)
    else:
        value = rdata.hex()

    return {
        "name":  name,
        "type":  TYPE_NAMES.get(rtype, f"TYPE{rtype}"),
        "ttl":   ttl,
        "value": value,
    }, offset


# ── stub resolver class ───────────────────────────────────────────────────────

class StubResolver:
    """
    Minimal DNS stub resolver.
    Sends queries to one configured recursive resolver (default: 8.8.8.8).
    Retries on timeout; raises DNSError on DNS-level failures.
    """

    def __init__(self, nameserver: str = "8.8.8.8", port: int = 53,
                 timeout: float = 3.0, retries: int = 3):
        self.nameserver = nameserver
        self.port       = port
        self.timeout    = timeout
        self.retries    = retries

    def query(self, domain: str, qtype: int = TYPE_A) -> list:
        """Send a DNS query and return list of answer RRs."""
        packet, txid = build_query(domain, qtype)
        last_err = "unknown error"

        for attempt in range(self.retries):
            try:
                raw = self._send(packet)
                return self._parse_response(raw, txid, domain)
            except socket.timeout:
                last_err = f"timeout on attempt {attempt + 1}"
                if attempt < self.retries - 1:
                    time.sleep(0.3)
            except DNSError:
                raise   # DNS-level errors don't benefit from retry
            except Exception as exc:
                last_err = str(exc)

        raise DNSError(f"All {self.retries} attempts failed. Last: {last_err}")

    def _send(self, packet: bytes) -> bytes:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            sock.sendto(packet, (self.nameserver, self.port))
            response, _ = sock.recvfrom(512)
            return response
        finally:
            sock.close()

    def _parse_response(self, data: bytes, expected_txid: int, domain: str) -> list:
        header = parse_header(data)

        if header["id"] != expected_txid:
            raise DNSError(
                f"Transaction ID mismatch: expected 0x{expected_txid:04x}, "
                f"got 0x{header['id']:04x}"
            )
        if header["qr"] != 1:
            raise DNSError("Response has QR=0 (this is a query, not a response)")

        rcode = header["rcode"]
        if rcode != 0:
            raise DNSError(f"DNS error for '{domain}': "
                           f"{RCODE_NAMES.get(rcode, f'RCODE_{rcode}')}")

        if header["tc"]:
            print("Warning: response was truncated (TC=1). Use TCP for full response.")

        # Skip question section
        offset = 12
        for _ in range(header["qdcount"]):
            _, offset = parse_name(data, offset)
            offset += 4   # skip QTYPE and QCLASS

        answers = []
        for _ in range(header["ancount"]):
            rr, offset = parse_rr(data, offset)
            answers.append(rr)
        return answers

    def resolve_a(self, domain: str) -> list:
        """Return list of IPv4 addresses."""
        return [r["value"] for r in self.query(domain, TYPE_A) if r["type"] == "A"]

    def resolve_aaaa(self, domain: str) -> list:
        """Return list of IPv6 addresses."""
        return [r["value"] for r in self.query(domain, TYPE_AAAA) if r["type"] == "AAAA"]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    domain     = sys.argv[1]
    qtype_str  = sys.argv[2].upper() if len(sys.argv) > 2 else "A"
    nameserver = sys.argv[3] if len(sys.argv) > 3 else "8.8.8.8"

    type_map = {
        "A": TYPE_A, "AAAA": TYPE_AAAA, "NS": TYPE_NS,
        "CNAME": TYPE_CNAME, "MX": TYPE_MX, "TXT": TYPE_TXT,
    }
    if qtype_str not in type_map:
        print(f"Unknown type '{qtype_str}'. Supported: {', '.join(type_map)}")
        sys.exit(1)

    qtype    = type_map[qtype_str]
    resolver = StubResolver(nameserver=nameserver)

    print(f"Querying {qtype_str} record for {domain} via {nameserver}:53 …")
    print()

    try:
        records = resolver.query(domain, qtype)
        if not records:
            print("No records found in answer section.")
        else:
            print(f"{'NAME':<35} {'TTL':<8} {'TYPE':<8} VALUE")
            print("-" * 70)
            for rr in records:
                print(f"{rr['name']:<35} {rr['ttl']:<8} {rr['type']:<8} {rr['value']}")

        # Compare with OS resolver for A queries
        if qtype == TYPE_A:
            print()
            os_addrs = sorted(set(
                addr[4][0]
                for addr in socket.getaddrinfo(domain, None, socket.AF_INET)
            ))
            stub_addrs = sorted(set(r["value"] for r in records if r["type"] == "A"))
            print(f"OS resolver:   {os_addrs}")
            print(f"Stub resolver: {stub_addrs}")
            match = set(os_addrs) == set(stub_addrs)
            print(f"Match: {match}")

    except DNSError as exc:
        print(f"DNS Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

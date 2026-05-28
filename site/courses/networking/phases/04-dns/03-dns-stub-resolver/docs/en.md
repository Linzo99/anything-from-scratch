# Build a DNS Stub Resolver

> Your OS has a built-in DNS client — now you'll write your own from scratch in 100 lines of Python.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 4, Lesson 02 — Parse a DNS Wire-Format Message
**Time:** ~50 minutes

## Learning Objectives
- Construct a valid DNS query packet from scratch using `struct`
- Send a UDP datagram to a DNS server and receive the response
- Parse the response to extract A record IP addresses
- Handle common error cases: timeout, SERVFAIL, NXDOMAIN, truncated responses
- Understand what makes a stub resolver different from a full recursive resolver

## The Problem

Every time your Python script calls `socket.getaddrinfo('example.com', 80)`, the OS stub resolver is invoked. It constructs a DNS query, sends it to your configured resolver (from `/etc/resolv.conf` or the system settings), and returns the result.

What if you want to bypass the OS resolver? What if you're building a tool that needs to use a specific upstream resolver, needs raw control over query parameters, or needs to run in a container where `/etc/resolv.conf` is misconfigured?

Writing your own stub resolver also forces you to understand the failure modes that the OS hides from you. A stub resolver doesn't walk the hierarchy — that's the recursive resolver's job. A stub resolver does exactly two things: build a query, send it to one configured resolver, and parse the reply. Simple in concept, instructive in implementation.

## The Concept

### Stub vs Full Recursive Resolver

A **stub resolver** is the minimal DNS client. It:
- Does not walk the root → TLD → authoritative chain itself
- Sends queries to exactly one configured recursive resolver (like 8.8.8.8)
- Trusts that resolver to do all the heavy lifting
- May cache results (but many OS stubs don't)

A **full recursive resolver** (like BIND, Unbound, or the one inside 8.8.8.8):
- Starts from root servers
- Follows every referral itself
- Maintains a cache of results
- Is far more complex

Your OS resolver is a stub resolver. 8.8.8.8 is a full recursive resolver.

```
Your App
   │
   │ getaddrinfo("example.com")
   ▼
OS Stub Resolver
   │
   │ DNS query (UDP, port 53) ──────────────▶ 8.8.8.8
   │                                         (recursive resolver)
   │                                              │
   │                                    walks root → TLD → auth
   │                                              │
   │ DNS response ◀─────────────────────────────── │
   ▼
Your App receives IP address
```

### Query ID — Matching Requests to Responses

DNS over UDP is connectionless. You send a query, and a response arrives. But UDP gives you no built-in way to match them — if you have multiple outstanding queries, how do you know which response belongs to which query?

The answer: the **Transaction ID** (also called Query ID). You pick any 16-bit number, put it in the query header, and the server copies it verbatim into the response header. You verify that the response ID matches your query ID.

```python
import random
transaction_id = random.randint(0, 65535)
```

### Retry Logic

UDP is unreliable. A DNS query can be lost. A real stub resolver retries 2-3 times before giving up, with short timeouts.

```
Attempt 1: send query, wait 1s → no response (packet lost)
Attempt 2: send query, wait 2s → response received
```

### The UDP Size Limit

RFC 1035 limits DNS over UDP to 512 bytes. Responses larger than 512 bytes are truncated (the `TC` flag is set in the header). When truncation occurs, the resolver should retry over TCP. For this lesson we stay with UDP and accept the 512-byte limit.

## Build It

### Step 1: The Query Builder

```python
# stub_resolver.py
import socket
import struct
import random
import time


# DNS record type constants
TYPE_A     = 1
TYPE_NS    = 2
TYPE_CNAME = 5
TYPE_MX    = 15
TYPE_TXT   = 16
TYPE_AAAA  = 28

# Response code constants
RCODE_NOERROR  = 0
RCODE_FORMERR  = 1
RCODE_SERVFAIL = 2
RCODE_NXDOMAIN = 3
RCODE_NOTIMP   = 4
RCODE_REFUSED  = 5

RCODE_NAMES = {
    0: 'NOERROR',
    1: 'FORMERR',
    2: 'SERVFAIL',
    3: 'NXDOMAIN',
    4: 'NOTIMP',
    5: 'REFUSED',
}


def build_query(domain: str, qtype: int = TYPE_A) -> tuple[bytes, int]:
    """
    Build a DNS query packet.
    Returns (packet_bytes, transaction_id).
    """
    transaction_id = random.randint(1, 65535)

    # Flags: QR=0 (query), OPCODE=0, AA=0, TC=0, RD=1 (recursion desired)
    # RD=1 tells the recursive resolver to do the full lookup for us
    flags = 0x0100

    # One question, zero answers/authority/additional
    header = struct.pack('>HHHHHH',
                         transaction_id,  # ID
                         flags,           # Flags
                         1,               # QDCOUNT: one question
                         0,               # ANCOUNT
                         0,               # NSCOUNT
                         0)               # ARCOUNT

    # Encode domain name as DNS labels
    encoded_name = encode_name(domain)

    # Question: QTYPE (2 bytes) + QCLASS=1/IN (2 bytes)
    question = struct.pack('>HH', qtype, 1)

    packet = header + encoded_name + question
    return packet, transaction_id


def encode_name(domain: str) -> bytes:
    """Encode a domain name as DNS label format."""
    result = b''
    # Strip trailing dot if present (FQDN form)
    domain = domain.rstrip('.')
    for label in domain.split('.'):
        if not label:
            continue
        encoded_label = label.encode('ascii')
        if len(encoded_label) > 63:
            raise ValueError(f"Label '{label}' exceeds 63-byte limit")
        result += bytes([len(encoded_label)]) + encoded_label
    result += b'\x00'  # Root label (null terminator)
    return result
```

### Step 2: The Response Parser

We reuse the parser logic from Lesson 02, consolidated into one file:

```python
def parse_name(data: bytes, offset: int) -> tuple[str, int]:
    """
    Parse a DNS-encoded name, handling compression pointers.
    Returns (name, offset_after_name).
    """
    labels = []
    return_offset = None
    max_jumps = 10  # Prevent infinite loops from malformed/malicious packets
    jumps = 0

    while True:
        if offset >= len(data):
            raise ValueError("Name parsing exceeded packet boundary")

        length = data[offset]

        if length == 0:
            offset += 1
            break
        elif (length & 0xC0) == 0xC0:
            # Compression pointer
            jumps += 1
            if jumps > max_jumps:
                raise ValueError("Too many compression pointer hops (possible loop)")
            if offset + 1 >= len(data):
                raise ValueError("Truncated compression pointer")
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if return_offset is None:
                return_offset = offset + 2
            offset = pointer
        else:
            # Regular label
            end = offset + 1 + length
            if end > len(data):
                raise ValueError("Label extends past end of packet")
            label = data[offset + 1:end].decode('ascii', errors='replace')
            labels.append(label)
            offset = end

    final_offset = return_offset if return_offset is not None else offset
    return '.'.join(labels), final_offset


def parse_header(data: bytes) -> dict:
    """Parse the 12-byte DNS message header."""
    if len(data) < 12:
        raise ValueError(f"Packet too short: {len(data)} bytes")

    txid, flags, qdcount, ancount, nscount, arcount = struct.unpack('>HHHHHH', data[:12])

    return {
        'id': txid,
        'qr': (flags >> 15) & 1,       # 1 = response
        'aa': (flags >> 10) & 1,       # authoritative answer
        'tc': (flags >> 9) & 1,        # truncated
        'ra': (flags >> 7) & 1,        # recursion available
        'rcode': flags & 0xF,          # response code
        'qdcount': qdcount,
        'ancount': ancount,
        'nscount': nscount,
        'arcount': arcount,
    }


def parse_rr(data: bytes, offset: int) -> tuple[dict, int]:
    """Parse one Resource Record. Returns (rr, new_offset)."""
    name, offset = parse_name(data, offset)

    if offset + 10 > len(data):
        raise ValueError("RR fixed section truncated")

    rtype, rclass, ttl, rdlength = struct.unpack('>HHIH', data[offset:offset+10])
    offset += 10

    rdata_start = offset
    rdata = data[offset:offset + rdlength]
    offset += rdlength

    # Decode RDATA based on type
    if rtype == TYPE_A and len(rdata) == 4:
        value = socket.inet_ntoa(rdata)
    elif rtype == TYPE_AAAA and len(rdata) == 16:
        value = socket.inet_ntop(socket.AF_INET6, rdata)
    elif rtype in (TYPE_CNAME, TYPE_NS):
        value, _ = parse_name(data, rdata_start)
    elif rtype == TYPE_MX and len(rdata) >= 3:
        pref = struct.unpack('>H', rdata[:2])[0]
        exchange, _ = parse_name(data, rdata_start + 2)
        value = f"{exchange} (priority {pref})"
    elif rtype == TYPE_TXT:
        parts = []
        pos = 0
        while pos < len(rdata):
            l = rdata[pos]
            pos += 1
            parts.append(rdata[pos:pos+l].decode('utf-8', errors='replace'))
            pos += l
        value = ' '.join(parts)
    else:
        value = rdata.hex()

    type_names = {1: 'A', 2: 'NS', 5: 'CNAME', 15: 'MX', 16: 'TXT', 28: 'AAAA'}

    return {
        'name': name,
        'type': type_names.get(rtype, f'TYPE{rtype}'),
        'ttl': ttl,
        'value': value,
    }, offset
```

### Step 3: The Resolver Core

```python
class DNSError(Exception):
    """Raised when a DNS lookup fails."""
    pass


class StubResolver:
    """
    A minimal DNS stub resolver.
    Sends queries to a single configured recursive resolver.
    """

    def __init__(self, nameserver: str = '8.8.8.8', port: int = 53,
                 timeout: float = 3.0, retries: int = 3):
        self.nameserver = nameserver
        self.port = port
        self.timeout = timeout
        self.retries = retries

    def query(self, domain: str, qtype: int = TYPE_A) -> list[dict]:
        """
        Query a DNS record type for a domain.
        Returns a list of answer RRs.
        Raises DNSError on failure.
        """
        packet, txid = build_query(domain, qtype)

        last_error = None
        for attempt in range(self.retries):
            try:
                response = self._send_udp(packet)
                return self._parse_response(response, txid, domain)
            except socket.timeout:
                last_error = f"Timeout on attempt {attempt + 1}"
                # Brief pause before retry, but don't sleep excessively
                if attempt < self.retries - 1:
                    time.sleep(0.5)
            except DNSError:
                raise  # DNS-level errors don't benefit from retry
            except Exception as e:
                last_error = str(e)

        raise DNSError(f"All {self.retries} attempts failed. Last error: {last_error}")

    def _send_udp(self, packet: bytes) -> bytes:
        """Send a UDP DNS query and return the raw response."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            sock.sendto(packet, (self.nameserver, self.port))
            response, _ = sock.recvfrom(512)
            return response
        finally:
            sock.close()

    def _parse_response(self, data: bytes, expected_txid: int, domain: str) -> list[dict]:
        """Parse and validate a DNS response, returning answer records."""
        header = parse_header(data)

        # Validate transaction ID to ensure this response matches our query
        if header['id'] != expected_txid:
            raise DNSError(
                f"Transaction ID mismatch: expected 0x{expected_txid:04x}, "
                f"got 0x{header['id']:04x}"
            )

        # Must be a response (QR=1), not a query (QR=0)
        if header['qr'] != 1:
            raise DNSError("Response has QR=0 (this is a query, not a response)")

        # Check response code
        rcode = header['rcode']
        if rcode != RCODE_NOERROR:
            rcode_name = RCODE_NAMES.get(rcode, f'RCODE_{rcode}')
            raise DNSError(f"DNS error for '{domain}': {rcode_name}")

        # Warn about truncation (response was cut off at 512 bytes)
        if header['tc']:
            print(f"Warning: response was truncated (TC=1). "
                  f"Use TCP for the full response.")

        # Skip the question section
        offset = 12
        for _ in range(header['qdcount']):
            _, offset = parse_name(data, offset)
            offset += 4  # Skip QTYPE and QCLASS

        # Parse all answer records
        answers = []
        for _ in range(header['ancount']):
            rr, offset = parse_rr(data, offset)
            answers.append(rr)

        return answers

    def resolve_a(self, domain: str) -> list[str]:
        """Convenience method: return a list of IPv4 addresses for a domain."""
        records = self.query(domain, TYPE_A)
        return [rr['value'] for rr in records if rr['type'] == 'A']

    def resolve_aaaa(self, domain: str) -> list[str]:
        """Return a list of IPv6 addresses for a domain."""
        records = self.query(domain, TYPE_AAAA)
        return [rr['value'] for rr in records if rr['type'] == 'AAAA']
```

### Step 4: The CLI Interface

```python
def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 stub_resolver.py <domain> [type] [nameserver]")
        print("  type: A, AAAA, MX, NS, CNAME, TXT (default: A)")
        print("  nameserver: IPv4 address (default: 8.8.8.8)")
        sys.exit(1)

    domain = sys.argv[1]
    qtype_str = sys.argv[2].upper() if len(sys.argv) > 2 else 'A'
    nameserver = sys.argv[3] if len(sys.argv) > 3 else '8.8.8.8'

    type_map = {
        'A': TYPE_A, 'AAAA': TYPE_AAAA, 'NS': TYPE_NS,
        'CNAME': TYPE_CNAME, 'MX': TYPE_MX, 'TXT': TYPE_TXT,
    }

    if qtype_str not in type_map:
        print(f"Unknown record type '{qtype_str}'. "
              f"Supported: {', '.join(type_map.keys())}")
        sys.exit(1)

    qtype = type_map[qtype_str]
    resolver = StubResolver(nameserver=nameserver)

    print(f"Querying {qtype_str} record for {domain} via {nameserver}...")
    print()

    try:
        records = resolver.query(domain, qtype)
        if not records:
            print("No records found in answer section.")
        else:
            print(f"{'NAME':<35} {'TTL':<8} {'TYPE':<8} VALUE")
            print('-' * 70)
            for rr in records:
                print(f"{rr['name']:<35} {rr['ttl']:<8} {rr['type']:<8} {rr['value']}")
    except DNSError as e:
        print(f"DNS Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
```

### Step 5: Run It

```bash
# Basic A record query
python3 stub_resolver.py example.com

# IPv6 addresses
python3 stub_resolver.py google.com AAAA

# Mail server records
python3 stub_resolver.py gmail.com MX

# Name server records
python3 stub_resolver.py cloudflare.com NS

# Text records
python3 stub_resolver.py github.com TXT

# Use Cloudflare's resolver instead of Google's
python3 stub_resolver.py example.com A 1.1.1.1

# Test a nonexistent domain (expect NXDOMAIN error)
python3 stub_resolver.py thisdomaindoesnotexist99999.com
```

### Step 6: Compare With the OS Resolver

Verify that your resolver gives the same answers as Python's built-in:

```python
# compare.py
import socket as os_socket
import sys
sys.path.insert(0, '.')
from stub_resolver import StubResolver

domain = 'example.com'

# OS resolver
os_addrs = [addr[4][0] for addr in os_socket.getaddrinfo(domain, None, os_socket.AF_INET)]
print(f"OS resolver:   {os_addrs}")

# Our stub resolver
resolver = StubResolver()
our_addrs = resolver.resolve_a(domain)
print(f"Stub resolver: {our_addrs}")

print(f"Match: {set(os_addrs) == set(our_addrs)}")
```

```bash
python3 compare.py
```

You should see `Match: True`.

## Exercises

1. **CNAME following**: Some domains return a CNAME record in the answer section instead of an A record directly. Modify `resolve_a` to detect CNAME answers and send a follow-up A query for the CNAME target. Test with `www.github.com` (which may CNAME to another name).

2. **Read from /etc/resolv.conf**: Add a `StubResolver.from_system()` class method that reads the nameserver IP from `/etc/resolv.conf` (on Linux) or uses `127.0.0.1` as fallback. This makes your resolver use the same upstream server as the OS.

3. **TTL-based cache**: Add a simple in-memory cache to `StubResolver`. Store results in a dict keyed by `(domain, qtype)`. On each call, check if a cached result exists and whether the TTL has expired. Use `time.time()` to track when entries were stored.

4. **TCP fallback**: When the response has the `TC` (truncated) flag set, implement a TCP retry. DNS over TCP uses the same wire format, but prefixed with a 2-byte message length. Hint: `struct.pack('>H', len(packet))` gives the length prefix.

5. **Concurrent queries**: Use Python's `threading` module to resolve 10 domains simultaneously and compare the wall-clock time against sequential resolution. How much faster is the parallel version?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Stub resolver | "the DNS client" | A minimal resolver that forwards all queries to one configured recursive resolver; does not walk the hierarchy itself |
| Transaction ID | "query ID" | A 16-bit number in the DNS header that matches responses to queries; critical for UDP where multiple queries may be outstanding simultaneously |
| RCODE | "DNS error code" | A 4-bit field in the response header indicating the query result: 0=success, 3=NXDOMAIN (no such domain), 2=SERVFAIL (resolver error) |
| NXDOMAIN | "domain not found" | RCODE 3 — the authoritative server confirmed the domain does not exist; distinct from a timeout or SERVFAIL |
| Truncation (TC bit) | "response too big" | The TC flag is set when the response exceeded 512 bytes and was cut off; the resolver should retry over TCP |
| UDP port 53 | "DNS port" | The standard port for DNS queries and responses; UDP is used for most queries, TCP for large responses and zone transfers |

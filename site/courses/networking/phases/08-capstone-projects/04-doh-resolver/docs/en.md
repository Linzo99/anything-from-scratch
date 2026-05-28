# Deploy a DNS-over-HTTPS Resolver

> DNS is one of the last plaintext protocols left on the internet — build the encrypted alternative yourself.

**Type:** Capstone
**Languages:** Python
**Prerequisites:** Phase 4, Lesson 03 — Build a DNS Stub Resolver; Phase 5, Lesson 05 — Add TLS to the HTTP Server
**Time:** ~90 minutes

## Learning Objectives

- Explain what DNS-over-HTTPS (DoH) is and why it protects user privacy
- Implement a local DNS server that accepts standard UDP DNS queries
- Forward those queries to a public DoH resolver (Cloudflare 1.1.1.1 or Google 8.8.8.8) over HTTPS
- Parse and return the decoded DNS response to the original client
- Test the resolver by pointing your system's DNS at it

## The Problem

Every time you visit a website, your computer first sends a DNS query to resolve the hostname to an IP address. By default, this query is sent in plaintext UDP to port 53. Anyone on your network — your ISP, a coffee shop router, a nation-state firewall — can read every DNS query you make and build a complete browsing history.

```
You                ISP                 DNS Server
 |-- who is github.com? (plaintext) -->|
 |                                     |
 ISP logs: "user visited github.com at 14:23"
```

DNS-over-HTTPS (RFC 8484) fixes this by wrapping DNS queries inside HTTPS requests. The query goes to `https://1.1.1.1/dns-query`, encrypted by TLS. Your ISP sees an HTTPS connection to Cloudflare — not the domain you're resolving.

The challenge: your operating system speaks plain UDP DNS on port 53. DoH resolvers speak HTTPS on port 443. To use DoH everywhere without reconfiguring every app, you run a local proxy that bridges the gap:

```
App → UDP DNS:53 → [Your DoH proxy] → HTTPS:443 → Cloudflare
```

## The Concept

### DNS-over-HTTPS wire format

DoH supports two request formats. The simplest is GET with a base64url-encoded DNS query:

```
GET /dns-query?dns=<base64url(raw_dns_query)> HTTP/2
Host: 1.1.1.1
Accept: application/dns-message
```

The response body is the raw DNS response (same binary format you already parsed in Phase 4).

### DoH request flow

```
1. Client sends UDP DNS query to 127.0.0.1:5353
2. Your proxy receives the raw DNS bytes
3. Base64url-encode the query bytes
4. GET https://1.1.1.1/dns-query?dns=<encoded>
   with Accept: application/dns-message
5. Response body = raw DNS response bytes
6. Send those bytes back to the client via UDP
```

The proxy is transparent — from the client's point of view, it's talking to a normal DNS server.

### Base64url encoding

DoH uses base64url (URL-safe base64: `+` → `-`, `/` → `_`, no padding `=`). Python provides this in the standard library:

```python
import base64

dns_query_bytes = b'\x00\x01...'   # raw DNS query
encoded = base64.urlsafe_b64encode(dns_query_bytes).rstrip(b'=').decode()
url = f"https://1.1.1.1/dns-query?dns={encoded}"
```

### DNS query construction (recap from Phase 4)

```
Header (12 bytes):
  ID (2)      flags (2)     QDCOUNT (2)
  ANCOUNT (2) NSCOUNT (2)   ARCOUNT (2)

Question section:
  QNAME (variable, dot-separated labels)
  QTYPE (2)   QCLASS (2)
```

To query `example.com` for A records:
```python
import struct, random

def build_query(domain, qtype=1):
    """Build a DNS query. qtype=1 (A), qtype=28 (AAAA), qtype=15 (MX)."""
    query_id = random.randint(0, 65535)
    flags = 0x0100        # standard query, recursion desired
    header = struct.pack('!HHHHHH', query_id, flags, 1, 0, 0, 0)

    # Encode domain name as labels: example.com → \x07example\x03com\x00
    labels = b''
    for part in domain.encode().split(b'.'):
        labels += bytes([len(part)]) + part
    labels += b'\x00'

    question = labels + struct.pack('!HH', qtype, 1)  # QTYPE, QCLASS (IN=1)
    return header + question, query_id
```

## Build It

### Step 1: DoH client function

Create `doh_resolver.py`:

```python
import socket
import struct
import base64
import random
import urllib.request
import urllib.error

DOH_SERVER = 'https://1.1.1.1/dns-query'

def build_query(domain, qtype=1):
    query_id = random.randint(0, 65535)
    flags = 0x0100
    header = struct.pack('!HHHHHH', query_id, flags, 1, 0, 0, 0)
    labels = b''
    for part in domain.encode().split(b'.'):
        labels += bytes([len(part)]) + part
    labels += b'\x00'
    question = labels + struct.pack('!HH', qtype, 1)
    return header + question, query_id

def resolve_via_doh(raw_dns_query):
    """Send a raw DNS query to a DoH server and return the raw DNS response."""
    encoded = base64.urlsafe_b64encode(raw_dns_query).rstrip(b'=').decode()
    url = f"{DOH_SERVER}?dns={encoded}"

    req = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/dns-message',
            'User-Agent': 'mini-doh-proxy/1.0'
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        print(f"DoH request failed: {e}")
        return None
```

### Step 2: UDP DNS server

```python
def parse_query_name(data, offset):
    """Decode a DNS name from the wire format starting at offset."""
    labels = []
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            # Pointer — follow it
            ptr = struct.unpack('!H', data[offset:offset+2])[0] & 0x3FFF
            label, _ = parse_query_name(data, ptr)
            labels.append(label)
            offset += 2
            break
        offset += 1
        labels.append(data[offset:offset+length].decode('utf-8', errors='replace'))
        offset += length
    return '.'.join(labels), offset

def run_dns_proxy(listen_host='127.0.0.1', listen_port=5353):
    """Run a UDP DNS server that forwards queries to DoH."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_host, listen_port))
    print(f"DoH proxy listening on UDP {listen_host}:{listen_port}")
    print(f"Test: dig @{listen_host} -p {listen_port} example.com")

    while True:
        data, addr = sock.recvfrom(512)

        # Quick parse to log the query name
        try:
            qname, _ = parse_query_name(data, 12)  # DNS header is 12 bytes
            qtype_offset = 12
            while data[qtype_offset] != 0:
                qtype_offset += data[qtype_offset] + 1
            qtype_offset += 1
            qtype = struct.unpack('!H', data[qtype_offset:qtype_offset+2])[0]
            type_names = {1: 'A', 28: 'AAAA', 15: 'MX', 5: 'CNAME', 16: 'TXT', 2: 'NS'}
            print(f"Query: {qname} {type_names.get(qtype, str(qtype))} from {addr[0]}")
        except Exception:
            qname = '(parse error)'

        response = resolve_via_doh(data)

        if response:
            sock.sendto(response, addr)
        else:
            # Return SERVFAIL (RCODE=2) if DoH fails
            query_id = data[:2]
            servfail = query_id + b'\x80\x02' + b'\x00' * 8
            sock.sendto(servfail, addr)

if __name__ == '__main__':
    run_dns_proxy()
```

### Step 3: Run and test

```bash
# Start the proxy (no root needed with port 5353)
python doh_resolver.py

# In another terminal, query through it
dig @127.0.0.1 -p 5353 example.com A
dig @127.0.0.1 -p 5353 google.com AAAA
dig @127.0.0.1 -p 5353 gmail.com MX

# Verify DNS traffic is NOT going to your normal resolver
# Open Wireshark and filter for: udp.port == 5353 or tcp.port == 443
# You'll see UDP to 127.0.0.1:5353 and HTTPS to 1.1.1.1 — no plaintext port 53
```

### Step 4: Point your system DNS at it (optional)

On Linux:
```bash
# Temporary — resets on reboot
sudo bash -c 'echo "nameserver 127.0.0.1" > /etc/resolv.conf'
# You'll need to run the proxy on port 53 (requires root):
sudo python doh_resolver.py --port 53
```

Or configure it only for testing:
```bash
# Override DNS for a single command
DNS_SERVER=127.0.0.1 dig @127.0.0.1 -p 5353 github.com
```

## Exercises

1. Run `dig @127.0.0.1 -p 5353 cloudflare.com A` and verify you get an IP address back.
2. Open Wireshark and capture on the loopback interface. Filter for `udp.port == 5353`. Make a DNS query and confirm no plaintext DNS appears on port 53.
3. Switch from Cloudflare (`1.1.1.1`) to Google (`8.8.8.8`) DoH: `https://8.8.8.8/dns-query`. Do results differ?
4. Add response caching: store `{domain: (response_bytes, timestamp)}` and return cached responses for repeated queries within the TTL window.
5. Extend the proxy to handle NXDOMAIN (non-existent domain) responses correctly and log them distinctly.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| DoH | "Encrypted DNS" | DNS-over-HTTPS (RFC 8484) — DNS queries sent as HTTPS GET or POST requests to port 443, encrypted by TLS. Hides DNS from network observers. |
| DNS-over-TLS | "DoT — the other encrypted DNS" | An alternative to DoH that wraps DNS directly in TLS on port 853, without HTTP. DoH is harder to block (uses port 443); DoT is easier to deploy. |
| SERVFAIL | "The DNS server failed" | DNS response code 2, meaning the server encountered a problem it couldn't resolve. Returned to the client when the proxy cannot reach the DoH server. |
| base64url | "URL-safe base64" | Base64 encoding with `+`→`-` and `/`→`_` substitutions and no `=` padding, so the encoded string can appear in a URL query parameter without percent-encoding. |
| Recursive resolver | "Your ISP's DNS server" | The DNS server that receives your queries and performs the full resolution on your behalf. With DoH, this is Cloudflare or Google rather than your ISP. |
| Privacy proxy | "A DNS privacy tool" | Any system that prevents your DNS queries from being observed by your network provider. DoH proxies, VPNs, and Tor all provide some form of DNS privacy. |

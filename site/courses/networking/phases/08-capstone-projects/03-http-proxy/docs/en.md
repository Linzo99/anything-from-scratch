# Implement a Mini HTTP Proxy

> Every corporate network, every Kubernetes cluster, and every CDN has a proxy in the middle — now you build one.

**Type:** Capstone
**Languages:** Python
**Prerequisites:** Phase 5, Lesson 02 — Build a Minimal HTTP Server; Phase 3, Lesson 02 — Build a TCP Echo Server
**Time:** ~90 minutes

## Learning Objectives

- Explain what a forward proxy does and how it differs from a reverse proxy
- Implement a TCP server that accepts HTTP requests from clients and forwards them to origin servers
- Parse HTTP request lines to extract the target host, port, and path
- Rewrite or add HTTP headers (e.g., X-Forwarded-For) before forwarding
- Log each proxied request to a structured JSON file

## The Problem

When your browser sends a request through a corporate proxy, the flow is:

```
Browser → Proxy → Internet → Server → Proxy → Browser
```

The browser connects to the proxy (not the server directly). It sends an HTTP request with the full URL as the path: `GET http://example.com/page HTTP/1.1`. The proxy strips the host, opens its own connection to `example.com`, forwards the request, receives the response, and relays it back.

This seemingly simple intermediary is responsible for caching, filtering, logging, security scanning, and load distribution across most of the internet. Understanding how it works at the socket level demystifies every proxy tool — Nginx, Squid, Envoy, mitmproxy — you'll ever configure.

## The Concept

### Forward vs reverse proxy

```
Forward proxy                        Reverse proxy
(client-side)                        (server-side)

Client → [Proxy] → Server A          Client → [Proxy] → Server A
                 → Server B                           → Server B
                 → Server C                           → Server C

Client configures proxy.             Server operator configures proxy.
Proxy speaks for many clients.       Proxy speaks for many servers.
Use: corporate filtering, caching.   Use: load balancing, TLS termination.
```

This lesson builds a forward proxy. The client (curl or browser) explicitly points at the proxy.

### HTTP request anatomy in a proxied context

A normal direct request:
```
GET /index.html HTTP/1.1
Host: example.com
```

A proxied request (browser → proxy):
```
GET http://example.com/index.html HTTP/1.1
Host: example.com
```

The difference: the request-line contains the full URL, not just the path. The proxy uses this to know where to connect.

### Proxy request processing pipeline

```
1. Accept TCP connection from client
2. Read HTTP request (headers + body if POST)
3. Parse request line → extract host, port, path
4. Optionally rewrite headers (add X-Forwarded-For, strip Connection: keep-alive)
5. Open TCP connection to origin server
6. Forward modified request
7. Read response from origin
8. Relay response to client
9. Log the transaction
10. Close connections
```

### Header rewriting

Two common transformations:

**Add X-Forwarded-For**: tells the origin server the real client IP (since from the origin's perspective, the proxy is the client):
```
X-Forwarded-For: 192.168.1.100
```

**Rewrite request-line**: the origin server expects a path, not a full URL:
```
Before: GET http://example.com/page HTTP/1.1
After:  GET /page HTTP/1.1
```

## Build It

### Step 1: Parse an HTTP request

Create `proxy.py`. Start with a helper to parse an incoming HTTP request:

```python
import socket
import struct
import json
import re
import time
from datetime import datetime, timezone

def recv_http_request(sock):
    """Read a full HTTP request (headers + optional body) from a socket."""
    raw = b''
    # Read until we have the full header section (ends with \r\n\r\n)
    while b'\r\n\r\n' not in raw:
        chunk = sock.recv(4096)
        if not chunk:
            return None
        raw += chunk

    header_end = raw.index(b'\r\n\r\n') + 4
    headers_raw = raw[:header_end]
    body = raw[header_end:]

    lines = headers_raw.decode('utf-8', errors='replace').split('\r\n')
    request_line = lines[0]
    headers = {}
    for line in lines[1:]:
        if ': ' in line:
            k, v = line.split(': ', 1)
            headers[k.lower()] = v

    # Check Content-Length for POST body
    content_length = int(headers.get('content-length', 0))
    while len(body) < content_length:
        chunk = sock.recv(4096)
        if not chunk:
            break
        body += chunk

    return request_line, headers, body

def parse_request_line(request_line):
    """Extract method, scheme, host, port, path from a proxy request line."""
    # Example: GET http://example.com:8080/path?q=1 HTTP/1.1
    m = re.match(r'(\w+)\s+http://([^/:]+)(?::(\d+))?(/[^\s]*)?\s+HTTP/(\S+)', request_line)
    if not m:
        # Direct request (non-proxy): GET /path HTTP/1.1
        m2 = re.match(r'(\w+)\s+(/[^\s]*)\s+HTTP/(\S+)', request_line)
        if m2:
            return m2.group(1), None, None, 80, m2.group(2), m2.group(3)
        return None
    method = m.group(1)
    host = m.group(2)
    port = int(m.group(3)) if m.group(3) else 80
    path = m.group(4) if m.group(4) else '/'
    version = m.group(5)
    return method, 'http', host, port, path, version
```

### Step 2: Forward the request and relay the response

```python
def forward_request(method, host, port, path, headers, body, client_addr):
    """Open a connection to the origin, forward the request, return the response."""
    # Connect to origin
    origin = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    origin.settimeout(10)
    origin.connect((host, port))

    # Rewrite request line to use path only (not full URL)
    # Add X-Forwarded-For header
    headers['x-forwarded-for'] = client_addr[0]

    # Remove hop-by-hop headers that shouldn't be forwarded
    for h in ['proxy-connection', 'connection', 'keep-alive', 'transfer-encoding']:
        headers.pop(h, None)

    # Reconstruct the request
    header_lines = f"{method} {path} HTTP/1.1\r\n"
    header_lines += f"Host: {host}\r\n"
    for k, v in headers.items():
        if k.lower() != 'host':
            header_lines += f"{k}: {v}\r\n"
    header_lines += "\r\n"

    origin.sendall(header_lines.encode() + body)

    # Read the full response
    response = b''
    while True:
        chunk = origin.recv(4096)
        if not chunk:
            break
        response += chunk

    origin.close()
    return response

def log_request(method, host, path, status_code, duration_ms, log_file='proxy.log'):
    entry = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'method': method,
        'host': host,
        'path': path,
        'status': status_code,
        'duration_ms': round(duration_ms, 2)
    }
    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    print(f"[{entry['ts']}] {method} http://{host}{path} → {status_code} ({duration_ms:.0f}ms)")
```

### Step 3: Main proxy server loop

```python
def handle_client(client_sock, client_addr):
    try:
        result = recv_http_request(client_sock)
        if not result:
            return
        request_line, headers, body = result

        parsed = parse_request_line(request_line)
        if not parsed:
            client_sock.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return

        method, scheme, host, port, path, version = parsed

        if not host:
            host = headers.get('host', 'unknown')

        t_start = time.time()
        response = forward_request(method, host, port, path, headers, body, client_addr)
        duration_ms = (time.time() - t_start) * 1000

        # Extract status code from response
        status_code = 0
        if response:
            first_line = response.split(b'\r\n', 1)[0].decode('utf-8', errors='replace')
            m = re.match(r'HTTP/\S+\s+(\d+)', first_line)
            if m:
                status_code = int(m.group(1))

        client_sock.sendall(response)
        log_request(method, host, path, status_code, duration_ms)

    except Exception as e:
        print(f"Error handling {client_addr}: {e}")
        try:
            client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception:
            pass
    finally:
        client_sock.close()


def main():
    import threading

    HOST = '127.0.0.1'
    PORT = 8080

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)
    print(f"HTTP proxy listening on {HOST}:{PORT}")
    print(f"Test with: curl -x http://{HOST}:{PORT} http://example.com/")

    while True:
        client_sock, client_addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True)
        t.start()

if __name__ == '__main__':
    main()
```

### Step 4: Test it

```bash
# Start the proxy
python proxy.py

# In another terminal, use curl through the proxy
curl -x http://127.0.0.1:8080 http://example.com/
curl -x http://127.0.0.1:8080 http://httpbin.org/get
curl -x http://127.0.0.1:8080 http://httpbin.org/headers

# Check the log
cat proxy.log
```

`httpbin.org/headers` will show the request headers as the origin server sees them — you should see `X-Forwarded-For` with your IP.

## Exercises

1. Run `curl -x http://127.0.0.1:8080 http://httpbin.org/headers` and verify `X-Forwarded-For` appears in the response body.
2. Add a blocklist: if the host is in `['ads.example.com', 'tracker.example.com']`, return a 403 instead of forwarding.
3. Add response caching: store responses keyed by `(method, host, path)` in a dict and return cached responses for identical subsequent GET requests.
4. Implement `proxy_pass` header rewriting: add a custom `Via: 1.1 mini-proxy` header to every forwarded request.
5. Extend the log to include the response `Content-Type` header and response body size in bytes.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Forward proxy | "A proxy" | A proxy that the client explicitly points at. Speaks on behalf of the client to servers. Used for filtering, caching, and anonymization. |
| Reverse proxy | "A load balancer" | A proxy that clients connect to without knowing about the backend servers. Speaks on behalf of servers to clients. Used for load balancing and TLS termination. |
| X-Forwarded-For | "The client IP header" | An HTTP header added by proxies to carry the original client's IP address to the origin server, since from the origin's view the proxy is the client. |
| Hop-by-hop headers | "Headers that die at each proxy" | Headers like Connection and Transfer-Encoding that apply only to the current connection, not end-to-end. Proxies must strip them before forwarding. |
| 502 Bad Gateway | "Proxy can't reach the server" | An HTTP status code meaning the proxy received an invalid response (or no response) from the upstream server it forwarded the request to. |

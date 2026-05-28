# Understand HTTP/2 Multiplexing

> HTTP/1.1 makes you wait in line; HTTP/2 lets all your requests run at the same time — on the same connection.

**Type:** Learn
**Languages:** Python, Bash
**Prerequisites:** Phase 5, Lesson 03 — HTTP Methods and Status Codes
**Time:** ~40 minutes

## Learning Objectives
- Explain what head-of-line blocking is and why it degrades HTTP/1.1 performance
- Describe how HTTP/2 multiplexing solves head-of-line blocking using streams
- Use the `h2` library to make parallel HTTP/2 requests over a single connection
- Measure waterfall timing differences between HTTP/1.1 and HTTP/2
- Identify the role of HPACK header compression in HTTP/2

## The Problem

Load a webpage with 30 resources (images, CSS, JS). In HTTP/1.1, each resource requires its own TCP connection (browsers open up to 6 per domain) or waits behind other requests in the same connection. This is called **head-of-line blocking**: a slow resource blocks everything behind it in the queue.

HTTP/2 fixes this with multiplexing: multiple requests and responses interleave over a single TCP connection, none blocking the others. A slow response doesn't delay fast ones. The result: significantly faster page loads on high-latency connections.

Understanding HTTP/2 matters because:
- Modern APIs default to HTTP/2 over HTTPS
- gRPC uses HTTP/2 as its transport
- Server-sent events and push use HTTP/2 streams
- Debugging multiplexed connections requires understanding streams

## The Concept

### The HTTP/1.1 Problem: Head-of-Line Blocking

With HTTP/1.1 persistent connections, requests and responses are strictly ordered:

```
HTTP/1.1 — one request at a time per connection:

Connection 1:
  Client: GET /large-image.jpg  ──▶
  (waiting... 200ms)
  ◀── Server: 200 OK + 500KB image

  Client: GET /small-script.js  ──▶  (had to wait!)
  (waiting... 5ms)
  ◀── Server: 200 OK + 2KB script

  Client: GET /tiny-icon.png    ──▶  (still waiting!)
  ...
```

The small, fast resources (5ms) are blocked behind the large, slow one (200ms). Browsers work around this by opening 6 parallel connections, but that's 6 TCP handshakes and 6 TLS handshakes — expensive.

### HTTP/2 Streams and Multiplexing

HTTP/2 introduces **streams**: independent, bidirectional sequences of frames within one TCP connection. Each request/response pair has its own stream ID (odd numbers for client-initiated streams: 1, 3, 5, ...).

```
HTTP/2 — multiple streams on one connection:

One TCP Connection:
  Stream 1: GET /large-image.jpg  ──▶
  Stream 3: GET /small-script.js  ──▶   (same connection!)
  Stream 5: GET /tiny-icon.png    ──▶   (same connection!)

  ◀── Stream 5: 200 OK (tiny-icon.png arrives first!)
  ◀── Stream 3: 200 OK (small-script.js arrives)
  ◀── Stream 1: 200 OK (large-image.jpg arrives last)
```

The server responds to each stream independently, in whatever order they complete. Fast resources arrive first.

### HTTP/2 Framing

HTTP/2 is a **binary** protocol (unlike HTTP/1.1's text). Every message is a frame:

```
+-----------------------------------------------+
|                 Length (24 bits)               |
+---------------+---------------+---------------+
|   Type (8)    |   Flags (8)   |
+-+-------------+---------------+-------------------------------+
|R|                 Stream Identifier (31 bits)                  |
+=+=============================================================+
|                   Frame Payload (Length octets)               |
+---------------------------------------------------------------+
```

Frame types:
- `HEADERS` — HTTP headers (equivalent to request/status line + headers in HTTP/1.1)
- `DATA` — body chunks
- `SETTINGS` — connection settings negotiation
- `WINDOW_UPDATE` — flow control
- `RST_STREAM` — cancel a stream
- `GOAWAY` — close the connection

### HPACK Header Compression

HTTP headers are repetitive. Every request sends `Accept-Encoding: gzip`, `User-Agent: Chrome/...`, etc. HTTP/2 uses **HPACK** compression to avoid sending the same headers repeatedly:

1. Both sides maintain a **header table** of previously seen headers
2. Instead of sending `"Accept-Encoding: gzip"` (23 bytes), send index `16` (2 bytes)
3. New, unique headers are added to the table

This reduces header overhead by 30-90% on typical traffic.

### HTTP/2 and TLS

HTTP/2 can technically run without TLS (called h2c — HTTP/2 cleartext), but in practice all browsers require TLS for HTTP/2. The TLS ALPN extension (`Application-Layer Protocol Negotiation`) is how client and server agree to use HTTP/2 during the TLS handshake.

```
TLS ClientHello extension:
  ALPN: ["h2", "http/1.1"]  ← client supports both

TLS ServerHello extension:
  ALPN: "h2"  ← server chooses HTTP/2
```

After the TLS handshake, HTTP/2 begins with a connection preface:
- Client sends: `PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n` (24 bytes, "magic" string)
- Followed by: SETTINGS frame

## Build It

### Step 1: Install the h2 Library

The `h2` library is a pure-Python implementation of the HTTP/2 state machine. It handles all the framing and state tracking — you provide the sockets.

```bash
pip install h2
```

Verify:

```python
import h2.connection
import h2.config
import h2.events
print("h2 library loaded successfully")
```

### Step 2: HTTP/1.1 Baseline Timing

First, measure how long it takes to fetch multiple resources sequentially over HTTP/1.1:

```python
# timing_http1.py
import socket
import time
import ssl

# Test domains and paths to fetch
REQUESTS = [
    ('httpbin.org', '/get', 443),
    ('httpbin.org', '/delay/0', 443),
    ('httpbin.org', '/uuid', 443),
    ('httpbin.org', '/headers', 443),
]


def fetch_http1(host: str, path: str, port: int = 443) -> tuple[int, float]:
    """Fetch one resource over HTTP/1.1. Returns (status_code, elapsed_ms)."""
    start = time.perf_counter()

    ctx = ssl.create_default_context()
    raw = socket.create_connection((host, port), timeout=10)
    tls = ctx.wrap_socket(raw, server_hostname=host)

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('ascii')

    tls.sendall(request)

    response = b''
    while True:
        chunk = tls.recv(4096)
        if not chunk:
            break
        response += chunk
    tls.close()

    elapsed = (time.perf_counter() - start) * 1000

    # Extract status code from first line
    status_line = response.split(b'\r\n')[0].decode('ascii', errors='replace')
    status_code = int(status_line.split(' ')[1]) if ' ' in status_line else 0

    return status_code, elapsed


if __name__ == '__main__':
    print("HTTP/1.1 Sequential Requests (separate connections)")
    print("-" * 55)

    total_start = time.perf_counter()

    results = []
    for host, path, port in REQUESTS:
        status, elapsed = fetch_http1(host, path, port)
        results.append(elapsed)
        print(f"  {host}{path:<20} {status}  {elapsed:6.1f}ms")

    total = (time.perf_counter() - total_start) * 1000
    print("-" * 55)
    print(f"  Total:                              {total:6.1f}ms")
    print(f"  Sum of individual:                  {sum(results):6.1f}ms")
```

```bash
python3 timing_http1.py
```

### Step 3: HTTP/2 Client with h2

```python
# http2_client.py
import socket
import ssl
import time
import h2.connection
import h2.config
import h2.events


def create_h2_connection(host: str, port: int = 443) -> tuple[ssl.SSLSocket, h2.connection.H2Connection]:
    """
    Open a TLS connection and negotiate HTTP/2 via ALPN.
    Returns (tls_socket, h2_connection).
    """
    # Create TLS context with HTTP/2 ALPN support
    ctx = ssl.create_default_context()
    # Advertise that we support HTTP/2 ("h2") and HTTP/1.1 as fallback
    ctx.set_alpn_protocols(['h2', 'http/1.1'])

    raw = socket.create_connection((host, port), timeout=15)
    tls = ctx.wrap_socket(raw, server_hostname=host)

    # Check which protocol was negotiated
    negotiated = tls.selected_alpn_protocol()
    if negotiated != 'h2':
        raise ConnectionError(
            f"Server did not negotiate HTTP/2 (got: {negotiated!r}). "
            f"Try a server that supports HTTP/2."
        )

    # Create the h2 connection state machine (CLIENT mode)
    config = h2.config.H2Configuration(client_side=True)
    conn = h2.connection.H2Connection(config=config)

    # Initiate the HTTP/2 connection:
    # This sends the connection preface (magic string + SETTINGS frame)
    conn.initiate_connection()
    tls.sendall(conn.data_to_send(65535))

    return tls, conn


def send_request(conn: h2.connection.H2Connection, tls: ssl.SSLSocket,
                 host: str, path: str) -> int:
    """
    Send one HTTP/2 GET request.
    Returns the stream_id assigned to this request.
    """
    # In HTTP/2, headers are sent as a HEADERS frame
    # Pseudo-headers (starting with :) replace the request line
    headers = [
        (':method', 'GET'),
        (':path', path),
        (':scheme', 'https'),
        (':authority', host),
        ('user-agent', 'h2-python-client/1.0'),
        ('accept', '*/*'),
    ]

    # send_headers() returns the stream_id for this request
    # end_stream=True means this is a GET with no body
    stream_id = conn.send_headers(headers, end_stream=True)

    # Actually send the frames to the server
    tls.sendall(conn.data_to_send(65535))

    return stream_id


def receive_responses(conn: h2.connection.H2Connection,
                      tls: ssl.SSLSocket,
                      expected_streams: set[int]) -> dict[int, dict]:
    """
    Receive responses for all expected streams.
    Returns dict mapping stream_id → {'status': int, 'body': bytes, 'elapsed': float}.
    """
    start_times = {sid: time.perf_counter() for sid in expected_streams}
    results = {}
    bodies = {sid: b'' for sid in expected_streams}
    completed = set()

    while len(completed) < len(expected_streams):
        # Receive data from the server
        data = tls.recv(65535)
        if not data:
            break

        # Feed the data to the h2 state machine
        # h2 parses the frames and returns a list of events
        events = conn.receive_data(data)

        for event in events:
            if isinstance(event, h2.events.ResponseReceived):
                # Headers arrived for this stream
                sid = event.stream_id
                if sid in expected_streams:
                    headers = dict(event.headers)
                    status = int(headers.get(b':status', b'0').decode())
                    results.setdefault(sid, {})['status'] = status

            elif isinstance(event, h2.events.DataReceived):
                # Body chunk arrived for this stream
                sid = event.stream_id
                if sid in expected_streams:
                    bodies[sid] += event.data
                    # Tell the server we consumed this data (flow control)
                    conn.acknowledge_received_data(event.flow_controlled_length, sid)

            elif isinstance(event, h2.events.StreamEnded):
                # This stream is complete
                sid = event.stream_id
                if sid in expected_streams and sid not in completed:
                    completed.add(sid)
                    elapsed = (time.perf_counter() - start_times[sid]) * 1000
                    results.setdefault(sid, {}).update({
                        'body': bodies[sid],
                        'elapsed': elapsed,
                    })

            elif isinstance(event, h2.events.WindowUpdated):
                pass  # Flow control update, no action needed for simple cases

        # Send any pending frames (e.g., WINDOW_UPDATE acknowledgments)
        pending = conn.data_to_send(65535)
        if pending:
            tls.sendall(pending)

    return results


def fetch_http2_parallel(host: str, paths: list[str],
                         port: int = 443) -> dict[str, dict]:
    """
    Fetch multiple paths in parallel over one HTTP/2 connection.
    Returns dict mapping path → response info.
    """
    tls, conn = create_h2_connection(host, port)

    try:
        # Send ALL requests before waiting for ANY response
        # This is the key: we pipeline all requests on different streams
        stream_to_path = {}
        expected = set()

        print(f"Sending {len(paths)} requests in parallel on one connection...")
        for path in paths:
            sid = send_request(conn, tls, host, path)
            stream_to_path[sid] = path
            expected.add(sid)
            print(f"  Stream {sid}: GET {path}")

        # Now receive all responses (they may arrive in any order)
        print("\nWaiting for responses...")
        results = receive_responses(conn, tls, expected)

        # Map back to paths
        return {stream_to_path[sid]: info for sid, info in results.items()}

    finally:
        conn.close_connection()
        tls.sendall(conn.data_to_send(65535))
        tls.close()


if __name__ == '__main__':
    host = 'httpbin.org'
    paths = ['/get', '/uuid', '/headers', '/ip']

    print(f"HTTP/2 Parallel Requests to {host}")
    print("=" * 50)

    total_start = time.perf_counter()
    results = fetch_http2_parallel(host, paths)
    total_elapsed = (time.perf_counter() - total_start) * 1000

    print("\nResults:")
    print("-" * 50)
    for path, info in results.items():
        status = info.get('status', '?')
        elapsed = info.get('elapsed', 0)
        body_len = len(info.get('body', b''))
        print(f"  {path:<25} {status}  {elapsed:6.1f}ms  ({body_len} bytes)")

    print("-" * 50)
    print(f"  Total wall time: {total_elapsed:6.1f}ms")
    print(f"\n  With HTTP/1.1, total would be: ~{total_elapsed * len(paths):.0f}ms")
    print(f"  (approximately {len(paths)}x slower for {len(paths)} sequential connections)")
```

### Step 4: Run the Comparison

```bash
# HTTP/1.1 baseline
python3 timing_http1.py

# HTTP/2 parallel
python3 http2_client.py
```

The HTTP/2 total time should be roughly the same as the SINGLE SLOWEST individual request in HTTP/1.1, because all requests run in parallel.

### Step 5: Verify HTTP/2 with curl

```bash
# Check HTTP version used
curl -v --http2 https://httpbin.org/get 2>&1 | grep -E "Using HTTP|HTTP/2|< HTTP"

# Force HTTP/1.1 for comparison
curl -v --http1.1 https://httpbin.org/get 2>&1 | grep -E "Using HTTP|HTTP/|< HTTP"

# Time multiple requests with HTTP/1.1 (sequential)
time curl --http1.1 -o /dev/null -s \
  https://httpbin.org/get \
  https://httpbin.org/uuid \
  https://httpbin.org/headers

# With HTTP/2 (parallel over one connection)
time curl --http2 -o /dev/null -s \
  https://httpbin.org/get \
  https://httpbin.org/uuid \
  https://httpbin.org/headers
```

## Exercises

1. **Stream priority**: HTTP/2 has a stream priority mechanism (deprecated in HTTP/2 but still widely implemented). Research `conn.prioritize(stream_id, depends_on=..., weight=...)` in the h2 library. Send requests with different priorities and observe if the server respects them.

2. **HPACK inspection**: The h2 library exposes the header table via `conn.encoder.header_table`. Print the header table before and after making several requests to the same server. What headers get indexed?

3. **Server push**: Some HTTP/2 servers proactively push resources before the client requests them (e.g., pushing CSS when you request HTML). Set up a local HTTP/2 server using Python's `hyper` or a Caddy server, enable push, and handle `h2.events.PushedStreamReceived` events in the client.

4. **HTTP/2 vs HTTP/1.1 with artificial latency**: Use `tc netem delay 50ms` (Linux) or a proxy to add 50ms latency. Compare HTTP/1.1 (6 connections × 4 requests = limited parallelism) against HTTP/2 (all parallel on one connection). The difference should be dramatic.

5. **Stream cancellation**: Send 5 requests, then cancel 2 of them with `conn.reset_stream(stream_id)` before the responses arrive. Handle `h2.events.StreamReset` in your response loop. Verify that cancelled streams don't block the remaining responses.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Head-of-line blocking | "slow resource blocks others" | A problem in HTTP/1.1 where a slow or large response blocks all subsequent responses queued behind it on the same connection; solved by HTTP/2 streams |
| Stream | "HTTP/2 request channel" | An independent, bidirectional logical channel within one HTTP/2 connection; each request/response pair has a unique stream ID; streams don't block each other |
| Multiplexing | "parallel requests on one connection" | The ability to interleave multiple request/response exchanges over a single TCP connection simultaneously, in any order |
| HPACK | "HTTP/2 header compression" | A binary compression format specific to HTTP/2 that reduces repeated headers by maintaining a shared header table on both client and server |
| ALPN | "protocol negotiation in TLS" | Application-Layer Protocol Negotiation — a TLS extension where client and server agree on whether to use HTTP/2 or HTTP/1.1 during the TLS handshake |
| h2c | "HTTP/2 without TLS" | HTTP/2 over cleartext TCP; technically valid but not supported by any browser; used in internal microservice communication where TLS overhead is undesirable |
| Frame | "HTTP/2 packet" | The basic unit of HTTP/2 communication; a binary structure with a 9-byte header (length, type, flags, stream ID) followed by payload |

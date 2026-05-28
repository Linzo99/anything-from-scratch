# Send a Raw HTTP/1.1 Request

> Every HTTP library hides the same simple text protocol — once you write it by hand, you'll never be confused by an HTTP error again.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 3, Lesson 01 — TCP Three-Way Handshake
**Time:** ~40 minutes

## Learning Objectives
- Open a TCP socket and send a hand-crafted HTTP/1.1 GET request as bytes
- Explain the structure of an HTTP request: request line, headers, blank line, body
- Parse the response status line, headers, and body from a raw socket
- Understand what `Content-Length`, `Transfer-Encoding: chunked`, and `Connection: close` mean at the socket level
- Identify why `\r\n` (CRLF) is required rather than `\n` alone

## The Problem

Every time you call `requests.get('http://example.com')`, this exact sequence happens: a TCP socket opens to port 80, bytes are sent that look like `GET / HTTP/1.1\r\nHost: example.com\r\n\r\n`, and a response arrives as bytes that you then parse.

Python's `requests` library does all of this for you. But what happens when you get a malformed response and can't tell if it's an encoding error, a missing header, or a redirect loop? What happens when you need to send a precise sequence of bytes to test a server's behavior? What happens when you're working with a system that doesn't have `requests` available?

Understanding raw HTTP means you can debug any HTTP issue with nothing but a TCP socket. It also means HTTP/2 and HTTP/3 make sense because you understand what they replaced.

## The Concept

### HTTP/1.1 is a Text Protocol

HTTP/1.1 is a human-readable text protocol layered on top of TCP. A request and its response are just strings with a specific format. There is no binary encoding, no special framing — it's plain text.

```
CLIENT SENDS:
──────────────────────────────────────────────────
GET /index.html HTTP/1.1\r\n      ← request line
Host: example.com\r\n             ← required header
Connection: close\r\n             ← header
\r\n                              ← blank line = end of headers
                                  ← (no body for GET)
──────────────────────────────────────────────────

SERVER RESPONDS:
──────────────────────────────────────────────────
HTTP/1.1 200 OK\r\n               ← status line
Content-Type: text/html\r\n       ← header
Content-Length: 1256\r\n          ← header
\r\n                              ← blank line = end of headers
<!DOCTYPE html>...                ← response body (1256 bytes)
──────────────────────────────────────────────────
```

### The Request Line

The first line of an HTTP request has three parts separated by single spaces:

```
METHOD SP Request-URI SP HTTP-Version CRLF
GET    /  index.html     HTTP/1.1      \r\n
```

- **Method**: GET, POST, PUT, DELETE, etc.
- **Request-URI**: the path (and optionally query string): `/`, `/api/users`, `/search?q=hello`
- **HTTP-Version**: always `HTTP/1.1` for our purposes

### Headers

Headers are key-value pairs:

```
Header-Name: header value\r\n
```

The `Host` header is REQUIRED in HTTP/1.1. It tells the server which virtual host you're requesting. A single IP address can serve hundreds of different domains — the `Host` header is how the server knows which site you want.

Headers end with a blank line: `\r\n\r\n` (the first `\r\n` ends the last header, the second is the blank line).

### CRLF — Why \r\n, Not \n?

HTTP uses CRLF (Carriage Return + Line Feed) as the line terminator, not just LF. This comes from the Teletype tradition and was standardized to work across different operating systems (Windows uses `\r\n` natively; Unix uses `\n`). If you send `\n` only, many HTTP servers will still work (they're lenient) but it's technically malformed HTTP.

### Reading the Response Body

Two common patterns for knowing when the body ends:

**Content-Length**: The server says "the body is exactly N bytes." You read exactly N bytes after the blank line.

**Connection: close**: No Content-Length? If the server closes the connection when done, you know the body ended when the socket closes. Read until EOF.

**Transfer-Encoding: chunked**: The body is sent in variable-size chunks, each prefixed with its size in hex. You read until you see a zero-size chunk `0\r\n\r\n`.

## Build It

### Step 1: Open a TCP Socket and Send the Request

```python
# raw_http.py
import socket


def send_raw_http_request(host: str, path: str = '/', port: int = 80) -> tuple[str, dict, bytes]:
    """
    Send a raw HTTP/1.1 GET request over a TCP socket.
    Returns (status_line, headers_dict, body_bytes).
    """
    # Build the request as a string, then encode to bytes
    # We use Connection: close so the server closes the socket after the response
    # Without this, HTTP/1.1 uses persistent connections and we'd need to parse
    # Content-Length to know when the response ends.
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"User-Agent: raw-http-client/1.0\r\n"
        f"\r\n"
    )

    # Convert string to bytes (HTTP/1.1 uses ISO-8859-1 / ASCII for headers)
    request_bytes = request.encode('ascii')

    print(f"Connecting to {host}:{port}...")
    print(f"Sending request:")
    print("-" * 40)
    # Show the request with visible escape sequences for clarity
    print(request.replace('\r\n', '\\r\\n\n').replace('\r', '\\r'))
    print("-" * 40)

    # Create TCP socket (AF_INET = IPv4, SOCK_STREAM = TCP)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)

    try:
        # Connect: this performs the TCP three-way handshake
        sock.connect((host, port))

        # Send the entire request in one call
        # sendall() ensures all bytes are sent, even if the kernel buffers them
        sock.sendall(request_bytes)

        # Read the complete response
        # Since we sent Connection: close, the server closes the socket after
        # sending all data. We read until EOF (empty bytes from recv).
        raw_response = b''
        while True:
            chunk = sock.recv(4096)  # Read up to 4096 bytes at a time
            if not chunk:
                break  # EOF — server closed the connection
            raw_response += chunk

    finally:
        sock.close()

    return raw_response
```

### Step 2: Parse the Response

```python
def parse_response(raw: bytes) -> tuple[str, dict, bytes]:
    """
    Parse raw HTTP response bytes into (status_line, headers, body).
    """
    # The header section ends at the first blank line (\r\n\r\n)
    # Everything after that is the body
    header_end = raw.find(b'\r\n\r\n')
    if header_end == -1:
        # Malformed response — no blank line separator
        raise ValueError("No header/body separator found in response")

    # Split into header section and body
    header_bytes = raw[:header_end]
    body_bytes = raw[header_end + 4:]  # +4 to skip the \r\n\r\n itself

    # Decode header bytes as ASCII (headers are always ASCII in HTTP/1.1)
    header_text = header_bytes.decode('ascii', errors='replace')

    # Split into individual lines
    lines = header_text.split('\r\n')

    # First line is the status line
    status_line = lines[0]

    # Parse the status line: "HTTP/1.1 200 OK"
    parts = status_line.split(' ', 2)  # Split into at most 3 parts
    if len(parts) < 2:
        raise ValueError(f"Malformed status line: {status_line!r}")

    http_version = parts[0]   # e.g. "HTTP/1.1"
    status_code = parts[1]    # e.g. "200"
    reason_phrase = parts[2] if len(parts) > 2 else ''  # e.g. "OK"

    # Parse headers into a dictionary
    headers = {}
    for line in lines[1:]:
        if not line:
            continue  # Skip empty lines
        if ':' not in line:
            continue  # Malformed header, skip
        name, _, value = line.partition(':')
        # Header names are case-insensitive; store in lowercase
        headers[name.strip().lower()] = value.strip()

    return status_line, headers, body_bytes


def print_response(status_line: str, headers: dict, body: bytes) -> None:
    """Display the parsed response in a readable format."""
    print("\nRESPONSE STATUS:")
    print(f"  {status_line}")

    print("\nRESPONSE HEADERS:")
    for name, value in headers.items():
        print(f"  {name}: {value}")

    print(f"\nRESPONSE BODY: ({len(body)} bytes)")
    # Print body as text if it looks like text, otherwise show hex
    content_type = headers.get('content-type', '')
    if 'text' in content_type or 'json' in content_type or 'xml' in content_type:
        # Detect encoding from Content-Type or default to UTF-8
        encoding = 'utf-8'
        if 'charset=' in content_type:
            encoding = content_type.split('charset=')[-1].split(';')[0].strip()
        try:
            body_text = body.decode(encoding, errors='replace')
            # Print first 500 chars to avoid flooding the terminal
            preview = body_text[:500]
            print(preview)
            if len(body_text) > 500:
                print(f"\n... [{len(body_text) - 500} more characters]")
        except Exception:
            print(body[:200].hex())
    else:
        print(f"  (binary data, first 64 bytes: {body[:64].hex()})")
```

### Step 3: Handle Redirects

Many domains redirect HTTP to HTTPS (301/302). Let's detect and follow one level of redirect:

```python
def follow_redirect(status_line: str, headers: dict) -> str | None:
    """
    If the response is a redirect (3xx), return the new Location URL.
    Otherwise return None.
    """
    parts = status_line.split(' ', 2)
    if len(parts) < 2:
        return None

    status_code = parts[1]
    if status_code.startswith('3') and 'location' in headers:
        return headers['location']
    return None
```

### Step 4: The Full Client

```python
def http_get(host: str, path: str = '/', port: int = 80,
             follow_redirects: bool = True) -> tuple[str, dict, bytes]:
    """
    Perform an HTTP GET request, optionally following one level of redirect.
    """
    raw = send_raw_http_request(host, path, port)
    status_line, headers, body = parse_response(raw)

    if follow_redirects:
        new_url = follow_redirect(status_line, headers)
        if new_url:
            print(f"\nRedirect to: {new_url}")
            # For simplicity, only follow http:// redirects (not https)
            if new_url.startswith('http://'):
                # Parse the new URL
                url_without_scheme = new_url[len('http://'):]
                if '/' in url_without_scheme:
                    new_host, new_path = url_without_scheme.split('/', 1)
                    new_path = '/' + new_path
                else:
                    new_host = url_without_scheme
                    new_path = '/'
                print(f"Following redirect to {new_host}{new_path}")
                raw = send_raw_http_request(new_host, new_path)
                status_line, headers, body = parse_response(raw)
            else:
                print("(Redirect to HTTPS — not following in raw HTTP mode)")

    return status_line, headers, body


if __name__ == '__main__':
    import sys

    # Default to example.com if no argument given
    host = sys.argv[1] if len(sys.argv) > 1 else 'example.com'
    path = sys.argv[2] if len(sys.argv) > 2 else '/'

    status_line, headers, body = http_get(host, path)
    print_response(status_line, headers, body)
```

### Step 5: Run It

```bash
# Fetch example.com
python3 raw_http.py example.com /

# Fetch httpbin.org (a test HTTP service)
python3 raw_http.py httpbin.org /get

# Look at headers from a specific server
python3 raw_http.py httpbin.org /headers
```

### Step 6: Use Telnet to Manually Type an HTTP Request

To really feel the protocol, try it with telnet (a raw TCP terminal):

```bash
telnet example.com 80
```

After connecting, type these lines exactly (including the blank line at the end):

```
GET / HTTP/1.1
Host: example.com
Connection: close

```

Press Enter twice after the blank line. You'll see the raw HTTP response stream into your terminal.

If telnet isn't available:

```bash
# Use netcat instead
echo -e "GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n" | nc example.com 80
```

## Exercises

1. **Chunked transfer encoding**: Query `httpbin.org /stream/3` — it returns a chunked response. Modify your parser to handle the chunked encoding format (each chunk is preceded by its hex size on a line, then the chunk data, then `\r\n`).

2. **Request headers inspection**: Fetch `httpbin.org /headers` — it echoes back the headers your client sent. Try modifying the `User-Agent` and `Accept` headers in your request and see the changes reflected in the response body.

3. **POST request**: Modify `send_raw_http_request` to accept a body and method parameter. Send a POST request to `httpbin.org /post` with a JSON body. You'll need to add `Content-Type: application/json` and `Content-Length: N` headers.

4. **Measure round-trip time**: Use `time.perf_counter()` to measure the time from `sock.connect()` to receiving the first byte of the response. Compare against `ping example.com`. Is the HTTP time approximately `ping_time + processing_time`?

5. **Compare with requests library**: Install `pip install requests` and make the same request with `requests.get('http://example.com')`. Set `verbose=True` or use `requests.PreparedRequest` to inspect what headers it sends. How does it differ from yours?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Request line | "the HTTP method and path" | The first line of an HTTP request: `METHOD SP Request-URI SP HTTP-version CRLF` — exactly three tokens separated by single spaces |
| CRLF | "line ending" | Carriage Return + Line Feed (`\r\n`, bytes 0x0D 0x0A); the required line terminator in HTTP headers per RFC 7230 |
| Host header | "the domain in the URL" | A required HTTP/1.1 header telling the server which virtual host you want; allows one IP to serve many domains |
| Status line | "the HTTP status" | The first line of an HTTP response: `HTTP-version SP status-code SP reason-phrase CRLF` (e.g., `HTTP/1.1 200 OK`) |
| Content-Length | "response size" | A response header telling the client exactly how many bytes are in the body; allows the client to know when reading is complete without waiting for the connection to close |
| Connection: close | "close after response" | A header instructing the server to close the TCP connection after the response; simplifies body reading since EOF signals end of body |
| Header terminator | "blank line" | An empty `\r\n` line that separates the header section from the body; in bytes: `\r\n\r\n` at the end of the last header |

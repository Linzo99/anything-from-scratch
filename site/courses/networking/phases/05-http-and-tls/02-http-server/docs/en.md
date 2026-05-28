# Build a Minimal HTTP Server

> Every web server in the world — Nginx, Apache, Node.js — does what you're about to do: listen on a socket, parse a request, and send bytes back.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 5, Lesson 01 — Send a Raw HTTP/1.1 Request
**Time:** ~50 minutes

## Learning Objectives
- Create a TCP server socket that accepts multiple connections
- Parse incoming HTTP GET requests to extract the method, path, and headers
- Serve static files from a directory with correct `Content-Type` headers
- Return proper `404 Not Found` responses for missing files
- Understand why a server loop must handle each connection without blocking others

## The Problem

You've written a client that sends HTTP requests. The natural next step is the other side: a server that receives requests and sends responses. Understanding the server side is essential for backend debugging, for writing test servers, for understanding how frameworks like Flask and Django work under the hood, and for writing custom HTTP handlers in embedded or constrained environments.

Real web servers have to solve hard problems: concurrency, TLS, authentication, routing, compression. We'll solve none of those hard problems in this lesson — but we'll get the fundamentals exactly right. A working HTTP server in 100 lines of Python is not a toy; it is the skeleton that every web framework is built on.

## The Concept

### The Server Loop

An HTTP server's core structure:

```
1. Create socket
2. Bind to address/port
3. Listen (mark as passive)
4. Loop forever:
   a. Accept a new connection → get client socket
   b. Read request bytes from client socket
   c. Parse the HTTP request
   d. Handle the request (find file, build response)
   e. Send response bytes
   f. Close client socket
   g. Go to step 4
```

```
Server socket (listening on port 8080)
         │
         │ accept()
         ▼
Client socket ←──────── TCP connection from browser/curl
         │
         │ recv() → "GET /index.html HTTP/1.1\r\nHost: ..."
         │
  parse request
         │
  find file on disk
         │
         │ send() → "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n..."
         │
         │ close()
         ▼
     (next accept)
```

### Socket Options: SO_REUSEADDR

When you stop a server and restart it immediately, the OS may keep the port in a `TIME_WAIT` state for ~60 seconds. Without `SO_REUSEADDR`, you'll get `OSError: [Errno 98] Address already in use`. Setting this option allows the socket to bind even while the port is in `TIME_WAIT`.

### Content-Type: Why It Matters

When a browser receives bytes, it looks at the `Content-Type` header to decide how to interpret them:

- `text/html` → render as HTML
- `text/plain` → show as plain text
- `application/json` → treat as JSON
- `image/png` → show as image

If you serve an HTML file with `Content-Type: text/plain`, the browser shows the raw HTML source code instead of rendering it. Always set the correct content type.

### HTTP Status Codes for File Serving

```
200 OK             — File found and sent
400 Bad Request    — Malformed request (can't parse)
403 Forbidden      — File exists but not readable (permissions)
404 Not Found      — File does not exist
500 Internal Error — Unexpected server-side exception
```

## Build It

### Step 1: The Basic Server Skeleton

```python
# http_server.py
import socket
import os
import mimetypes
from datetime import datetime


# Initialize mimetypes database (maps file extensions to Content-Type values)
mimetypes.init()

# Fallback MIME types for common extensions
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.htm':  'text/html; charset=utf-8',
    '.css':  'text/css',
    '.js':   'application/javascript',
    '.json': 'application/json',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.svg':  'image/svg+xml',
    '.ico':  'image/x-icon',
    '.txt':  'text/plain; charset=utf-8',
    '.pdf':  'application/pdf',
}


def get_content_type(path: str) -> str:
    """Determine the Content-Type for a file path."""
    _, ext = os.path.splitext(path.lower())
    # Check our custom map first, then fall back to mimetypes module
    if ext in MIME_TYPES:
        return MIME_TYPES[ext]
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or 'application/octet-stream'


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {message}")
```

### Step 2: Request Parser

```python
def parse_request(raw: bytes) -> tuple[str, str, dict] | None:
    """
    Parse raw HTTP request bytes.
    Returns (method, path, headers) or None if malformed.
    """
    try:
        # Find the end of the header section
        header_end = raw.find(b'\r\n\r\n')
        if header_end == -1:
            return None  # Incomplete request

        header_bytes = raw[:header_end]
        header_text = header_bytes.decode('ascii', errors='replace')
        lines = header_text.split('\r\n')

        if not lines:
            return None

        # Parse the request line: "GET /path HTTP/1.1"
        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) < 2:
            return None

        method = parts[0].upper()
        raw_path = parts[1]

        # Strip query string from path (we don't use it in this lesson)
        path = raw_path.split('?')[0]

        # Normalize path: remove dangerous ".." components
        # This prevents path traversal attacks (e.g., "/../../../etc/passwd")
        path = os.path.normpath(path)

        # os.path.normpath on "/../../etc" returns "/etc" on Unix
        # We want to ensure the path stays within the served directory
        # (handled later when we join with the root directory)

        # Parse headers into a dict
        headers = {}
        for line in lines[1:]:
            if ':' in line:
                name, _, value = line.partition(':')
                headers[name.strip().lower()] = value.strip()

        return method, path, headers

    except Exception:
        return None
```

### Step 3: Response Builder

```python
def build_response(status_code: int, reason: str, headers: dict,
                   body: bytes) -> bytes:
    """
    Build a complete HTTP response as bytes.
    """
    # Status line
    status_line = f"HTTP/1.1 {status_code} {reason}\r\n"

    # Standard headers we always include
    default_headers = {
        'server': 'raw-python-server/1.0',
        'connection': 'close',
        'content-length': str(len(body)),
    }
    # Merge: caller's headers override defaults
    all_headers = {**default_headers, **headers}

    # Format headers
    header_lines = ''.join(
        f"{name}: {value}\r\n"
        for name, value in all_headers.items()
    )

    # Blank line + body
    response = status_line.encode('ascii') + header_lines.encode('ascii') + b'\r\n' + body
    return response


def make_error_response(status_code: int, reason: str, message: str) -> bytes:
    """Build a simple HTML error response."""
    body = f"""<!DOCTYPE html>
<html>
<head><title>{status_code} {reason}</title></head>
<body>
<h1>{status_code} {reason}</h1>
<p>{message}</p>
</body>
</html>""".encode('utf-8')

    return build_response(
        status_code, reason,
        {'content-type': 'text/html; charset=utf-8'},
        body
    )
```

### Step 4: File Handler

```python
def handle_get(path: str, root_dir: str) -> bytes:
    """
    Handle a GET request for 'path', serving files from 'root_dir'.
    Returns a complete HTTP response as bytes.
    """
    # Construct the filesystem path
    # os.path.join(root_dir, path.lstrip('/')) combines them safely
    # The lstrip('/') is necessary because os.path.join('/srv', '/etc/passwd')
    # returns '/etc/passwd' — the absolute path wins. We strip the leading /
    # to make the path relative.
    relative_path = path.lstrip('/')
    if not relative_path:
        relative_path = 'index.html'  # Default document

    fs_path = os.path.join(root_dir, relative_path)

    # Security: resolve symlinks and ensure the path stays within root_dir
    # os.path.realpath resolves all symlinks and ".." components
    fs_path_real = os.path.realpath(fs_path)
    root_real = os.path.realpath(root_dir)

    if not fs_path_real.startswith(root_real):
        # Path traversal attempt detected
        log(f"  403 Path traversal attempt: {path}")
        return make_error_response(403, 'Forbidden', 'Access denied.')

    # Check if the file exists
    if not os.path.exists(fs_path_real):
        log(f"  404 Not Found: {fs_path_real}")
        return make_error_response(404, 'Not Found',
                                   f"The requested path '{path}' was not found.")

    # Check if it's a directory (serve index.html from it if present)
    if os.path.isdir(fs_path_real):
        index_path = os.path.join(fs_path_real, 'index.html')
        if os.path.exists(index_path):
            fs_path_real = index_path
        else:
            # No index.html — return a simple directory listing
            entries = os.listdir(fs_path_real)
            listing = '\n'.join(
                f'<li><a href="{path.rstrip("/")}/{e}">{e}</a></li>'
                for e in sorted(entries)
            )
            body = f"""<!DOCTYPE html>
<html><head><title>Directory: {path}</title></head>
<body><h1>Directory: {path}</h1><ul>{listing}</ul></body>
</html>""".encode('utf-8')
            return build_response(200, 'OK',
                                  {'content-type': 'text/html; charset=utf-8'}, body)

    # Read the file
    try:
        with open(fs_path_real, 'rb') as f:
            body = f.read()
    except PermissionError:
        log(f"  403 Permission denied: {fs_path_real}")
        return make_error_response(403, 'Forbidden', 'Permission denied.')
    except OSError as e:
        log(f"  500 OS error reading file: {e}")
        return make_error_response(500, 'Internal Server Error',
                                   'Error reading file.')

    content_type = get_content_type(fs_path_real)
    log(f"  200 OK: {fs_path_real} ({len(body)} bytes, {content_type})")

    return build_response(200, 'OK', {'content-type': content_type}, body)
```

### Step 5: The Connection Handler

```python
def handle_connection(client_sock: socket.socket, client_addr: tuple,
                      root_dir: str) -> None:
    """Handle one complete HTTP request/response cycle."""
    try:
        # Receive the request (up to 8KB for headers)
        # Real servers handle larger headers, but 8KB covers 99% of cases
        raw_request = b''
        while b'\r\n\r\n' not in raw_request:
            chunk = client_sock.recv(4096)
            if not chunk:
                return  # Client disconnected before sending a complete request
            raw_request += chunk
            if len(raw_request) > 8192:
                # Header too large — return 400
                client_sock.sendall(make_error_response(400, 'Bad Request',
                                                        'Request headers too large.'))
                return

        parsed = parse_request(raw_request)
        if parsed is None:
            client_sock.sendall(make_error_response(400, 'Bad Request',
                                                    'Could not parse request.'))
            return

        method, path, headers = parsed
        host = headers.get('host', client_addr[0])
        log(f"{client_addr[0]} {method} {path} (Host: {host})")

        if method == 'GET':
            response = handle_get(path, root_dir)
        else:
            # We only support GET in this lesson
            response = make_error_response(405, 'Method Not Allowed',
                                           f"Method '{method}' is not supported.")

        client_sock.sendall(response)

    except ConnectionResetError:
        log(f"{client_addr[0]} Connection reset by client")
    except BrokenPipeError:
        log(f"{client_addr[0]} Client closed connection before response was sent")
    finally:
        client_sock.close()
```

### Step 6: The Server Entry Point

```python
def run_server(host: str = '', port: int = 8080, root_dir: str = '.') -> None:
    """
    Start the HTTP server.
    host='' means listen on all interfaces (0.0.0.0).
    """
    root_dir = os.path.abspath(root_dir)

    if not os.path.isdir(root_dir):
        print(f"Error: '{root_dir}' is not a directory")
        return

    # Create the server socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # SO_REUSEADDR: allows reuse of the port immediately after server restarts
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))

        # backlog=5: OS can queue up to 5 connection requests before refusing new ones
        server_sock.listen(5)

        listen_addr = host or '0.0.0.0'
        print(f"Serving '{root_dir}' at http://{listen_addr}:{port}")
        print("Press Ctrl+C to stop.\n")

        while True:
            # accept() blocks until a client connects
            # Returns a NEW socket for this specific client + client address
            client_sock, client_addr = server_sock.accept()
            # Handle the connection (single-threaded — one at a time)
            handle_connection(client_sock, client_addr, root_dir)

    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server_sock.close()


if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    root = sys.argv[2] if len(sys.argv) > 2 else '.'

    run_server(port=port, root_dir=root)
```

### Step 7: Test It

Create some test files:

```bash
mkdir -p test_site
echo '<html><body><h1>Hello from raw Python server!</h1></body></html>' > test_site/index.html
echo '{"status": "ok"}' > test_site/api.json
echo 'Hello, plain text!' > test_site/hello.txt
```

Start the server:

```bash
python3 http_server.py 8080 test_site
```

In another terminal:

```bash
# Test basic GET
curl -v http://localhost:8080/

# Test file serving
curl http://localhost:8080/api.json
curl http://localhost:8080/hello.txt

# Test 404
curl -v http://localhost:8080/notexist.html

# Open in browser
open http://localhost:8080/
```

Watch the server terminal — you'll see every request logged.

### Step 8: Load Test with Multiple Requests

```bash
# Send 10 sequential requests and time them
time for i in $(seq 1 10); do curl -s http://localhost:8080/ > /dev/null; done

# Try two simultaneous requests (the second will wait for the first to finish)
curl http://localhost:8080/ & curl http://localhost:8080/ &
wait
```

Notice: the second request waits because our server is single-threaded. This is a real limitation addressed in the concurrency lesson.

## Exercises

1. **Concurrent server**: Wrap `handle_connection` in a `threading.Thread`. Call `thread.start()` instead of calling `handle_connection` directly. Re-run the simultaneous curl test — both requests should complete at the same time.

2. **Custom 404 page**: Create a file `test_site/404.html` with a custom error page. Modify `handle_get` to serve this file (if it exists) instead of the generic error response.

3. **Range requests**: Many clients request file byte ranges (for video seeking). Add support for the `Range: bytes=start-end` header. Serve only the requested byte range and respond with `206 Partial Content`.

4. **If-Modified-Since**: Check the file's modification time with `os.path.getmtime()`. If the request includes `If-Modified-Since` header and the file hasn't changed, return `304 Not Modified` with no body.

5. **Access log**: Write every request to an `access.log` file in Apache Combined Log Format: `IP - - [timestamp] "METHOD path HTTP/1.1" status_code response_size`.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| SO_REUSEADDR | "socket option" | A socket option that allows a server to bind to a port that is still in TIME_WAIT state; prevents "address already in use" errors on server restart |
| listen() backlog | "connection queue size" | The number of connection requests the OS can queue while the server is busy in accept(); not the maximum concurrent connections |
| accept() | "accept a connection" | A blocking system call that waits for a client to connect; returns a new socket for that specific client and the client's address tuple |
| Path traversal | "directory traversal attack" | An attack where a client requests `/../../../etc/passwd` to access files outside the intended directory; prevented by checking that realpath(request) starts with realpath(root) |
| Content-Type | "MIME type" | A response header telling the client how to interpret the body bytes; without it, browsers may guess incorrectly or refuse to display the content |
| 404 Not Found | "page not found" | An HTTP status code meaning the server understood the request but the resource (file, endpoint) does not exist |

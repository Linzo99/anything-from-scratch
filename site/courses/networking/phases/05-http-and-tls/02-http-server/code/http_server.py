# Run: python3 http_server.py 8080
"""
http_server.py — Minimal HTTP/1.1 server using only the socket stdlib.

No http.server, no http.client, no frameworks.
Handles GET requests, serves static content (a hardcoded HTML page and a
few additional paths), returns proper:
  - Status line (HTTP/1.1 200 OK, 404 Not Found, 405 Method Not Allowed)
  - Headers: Content-Type, Content-Length, Connection, Server, Date
  - Body

Usage:
    python3 http_server.py [port]    (default: 8080)

Test with:
    curl -v http://localhost:8080/
    curl http://localhost:8080/hello
    curl http://localhost:8080/data.json
    curl -v http://localhost:8080/notfound
"""

import socket
import sys
from datetime import datetime, timezone


# ── static content store ──────────────────────────────────────────────────────

PAGES: dict[str, tuple] = {
    "/": (
        "text/html; charset=utf-8",
        b"""<!DOCTYPE html>
<html>
<head><title>Minimal HTTP Server</title></head>
<body>
<h1>Minimal HTTP/1.1 Server</h1>
<p>Built with Python socket stdlib only — no http.server module.</p>
<ul>
  <li><a href="/hello">GET /hello</a> — plain text response</li>
  <li><a href="/data.json">GET /data.json</a> — JSON response</li>
  <li><a href="/notfound">GET /notfound</a> — 404 example</li>
</ul>
</body>
</html>
""",
    ),
    "/hello": (
        "text/plain; charset=utf-8",
        b"Hello from the minimal HTTP server!\n",
    ),
    "/data.json": (
        "application/json",
        b'{"server":"raw-python","version":"1.0","status":"ok"}\n',
    ),
}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def http_date() -> str:
    """Return an RFC 7231 formatted date string."""
    now = datetime.now(tz=timezone.utc)
    return now.strftime("%a, %d %b %Y %H:%M:%S GMT")


def build_response(
    status_code: int,
    reason: str,
    content_type: str,
    body: bytes,
) -> bytes:
    """
    Build a complete HTTP/1.1 response as bytes.

    Structure:
        HTTP/1.1 <code> <reason>\r\n
        <header>: <value>\r\n
        ...
        \r\n
        <body>
    """
    status_line = f"HTTP/1.1 {status_code} {reason}"
    headers = {
        "Server":         "raw-python-http/1.0",
        "Date":           http_date(),
        "Content-Type":   content_type,
        "Content-Length": str(len(body)),
        "Connection":     "close",
    }
    header_block = "\r\n".join(f"{k}: {v}" for k, v in headers.items())
    # Status line + CRLF + headers + blank line (CRLF CRLF) + body
    response = (
        status_line + "\r\n" +
        header_block + "\r\n" +
        "\r\n"
    ).encode("ascii") + body
    return response


def error_response(code: int, reason: str, detail: str) -> bytes:
    body = (
        f"<!DOCTYPE html><html><head><title>{code} {reason}</title></head>"
        f"<body><h1>{code} {reason}</h1><p>{detail}</p></body></html>\n"
    ).encode("utf-8")
    return build_response(code, reason, "text/html; charset=utf-8", body)


# ── request parser ────────────────────────────────────────────────────────────

def parse_request(raw: bytes) -> tuple:
    """
    Parse the request line and headers from raw bytes.
    Returns (method, path, headers_dict) or raises ValueError.

    TCP is a stream: we only call this once we've seen the header terminator
    \\r\\n\\r\\n in the buffer.
    """
    end = raw.find(b"\r\n\r\n")
    if end == -1:
        raise ValueError("Incomplete request headers")

    header_bytes = raw[:end]
    try:
        text = header_bytes.decode("ascii", errors="replace")
    except Exception as exc:
        raise ValueError(f"Cannot decode headers: {exc}")

    lines = text.split("\r\n")
    if not lines:
        raise ValueError("Empty request")

    # Request line: "GET /path HTTP/1.1"
    parts = lines[0].split(" ", 2)
    if len(parts) < 2:
        raise ValueError(f"Malformed request line: {lines[0]!r}")

    method = parts[0].upper()
    path   = parts[1].split("?")[0]   # strip query string

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()

    return method, path, headers


# ── connection handler ────────────────────────────────────────────────────────

def handle_connection(conn: socket.socket, addr: tuple) -> None:
    """Read one HTTP request and send one response."""
    try:
        # Accumulate bytes until we see the end-of-headers marker
        buf = b""
        conn.settimeout(5.0)
        while b"\r\n\r\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                return
            buf += chunk
            if len(buf) > 8192:
                conn.sendall(error_response(431, "Request Header Fields Too Large",
                                            "Headers exceed 8 KB."))
                return

        try:
            method, path, headers = parse_request(buf)
        except ValueError as exc:
            conn.sendall(error_response(400, "Bad Request", str(exc)))
            return

        host = headers.get("host", addr[0])
        ts   = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] {addr[0]}  {method} {path}  (Host: {host})")

        if method != "GET":
            conn.sendall(error_response(
                405, "Method Not Allowed",
                f"Only GET is supported by this server.  Received: {method}"
            ))
            return

        if path in PAGES:
            content_type, body = PAGES[path]
            response = build_response(200, "OK", content_type, body)
        else:
            response = error_response(
                404, "Not Found",
                f"The path <code>{path}</code> was not found on this server."
            )

        conn.sendall(response)

    except (ConnectionResetError, BrokenPipeError, socket.timeout):
        pass   # client disconnected mid-flight
    except Exception as exc:
        try:
            conn.sendall(error_response(500, "Internal Server Error", str(exc)))
        except Exception:
            pass
    finally:
        conn.close()


# ── server loop ───────────────────────────────────────────────────────────────

def run_server(port: int = 8080) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # SO_REUSEADDR: lets us restart immediately without waiting for TIME_WAIT
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("", port))
    srv.listen(5)

    print(f"Minimal HTTP/1.1 server running at http://localhost:{port}")
    print(f"  Serving {len(PAGES)} paths: {', '.join(PAGES)}")
    print("  Press Ctrl-C to stop\n")

    try:
        while True:
            conn, addr = srv.accept()
            handle_connection(conn, addr)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        srv.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)

#!/usr/bin/env python3
# Run: python3 http_proxy.py
"""
HTTP Forward Proxy
Listens on port 8888, parses incoming HTTP requests with full URLs
(e.g., GET http://example.com/path HTTP/1.1), opens a new TCP connection
to the target host, forwards the request, and streams the response back.

Features:
  - Correct Host header handling
  - X-Forwarded-For injection
  - Strips hop-by-hop headers (Connection, Keep-Alive, Transfer-Encoding)
  - Logs each transaction to stdout in a structured format
  - Handles persistent connections via threading (one thread per client)

Requires: Python 3.8+, stdlib only.

Usage:
  python3 http_proxy.py [port]          (default: port 8888)

Test:
  curl -x http://127.0.0.1:8888 http://example.com/
  curl -x http://127.0.0.1:8888 http://httpbin.org/get
  curl -x http://127.0.0.1:8888 http://httpbin.org/headers
"""

import sys
import socket
import threading
import re
import time
import json
import datetime
import logging

LISTEN_HOST  = "127.0.0.1"
LISTEN_PORT  = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
BUFFER_SIZE  = 4096
CONNECT_TIMEOUT = 10   # seconds to connect to origin
READ_TIMEOUT    = 15   # seconds to read response from origin

# Hop-by-hop headers that must NOT be forwarded
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "proxy-connection", "te", "trailers", "transfer-encoding", "upgrade",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("http-proxy")


# ── HTTP request parsing ──────────────────────────────────────────────────────

def recv_http_headers(sock: socket.socket) -> bytes:
    """
    Read from sock until we have the complete HTTP headers (ending with \\r\\n\\r\\n).
    Returns the raw bytes of headers + any initial body bytes received.
    """
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            break
        buf += chunk
        if len(buf) > 1024 * 1024:   # 1 MB header limit
            raise ValueError("HTTP headers exceed 1 MB limit")
    return buf


def parse_request(raw: bytes) -> dict:
    """
    Parse a raw HTTP request into a dict with keys:
      method, url, version, host, port, path, headers (dict), body_prefix
    Handles both proxied requests (full URL) and direct requests (path only).
    """
    if b"\r\n\r\n" not in raw:
        raise ValueError("incomplete HTTP request")

    header_end = raw.index(b"\r\n\r\n")
    headers_raw = raw[:header_end].decode("utf-8", errors="replace")
    body_prefix = raw[header_end + 4:]

    lines = headers_raw.split("\r\n")
    request_line = lines[0]

    # Parse request line
    parts = request_line.split(" ", 2)
    if len(parts) != 3:
        raise ValueError(f"malformed request line: {request_line!r}")
    method, url, version = parts

    # Extract host, port, path from URL
    # Full proxy URL: http://example.com:8080/path
    m = re.match(r"https?://([^/:]+)(?::(\d+))?((?:/[^\s]*)?)", url)
    if m:
        host    = m.group(1)
        port    = int(m.group(2)) if m.group(2) else 80
        path    = m.group(3) or "/"
    else:
        # Direct request (non-proxy path): GET /path HTTP/1.1
        host = None
        port = 80
        path = url

    # Parse headers
    headers = {}
    for line in lines[1:]:
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k.lower()] = v

    # Host from header if not in URL
    if not host:
        host = headers.get("host", "")
        if ":" in host:
            host, port_str = host.rsplit(":", 1)
            port = int(port_str)

    return {
        "method":       method,
        "url":          url,
        "version":      version,
        "host":         host,
        "port":         port,
        "path":         path,
        "headers":      headers,
        "body_prefix":  body_prefix,
    }


# ── Request forwarding ────────────────────────────────────────────────────────

def build_forwarded_request(req: dict, client_addr: tuple) -> bytes:
    """
    Rewrite the request for forwarding:
    - Change request line to use path only (not full URL)
    - Add/update Host header
    - Add X-Forwarded-For header
    - Remove hop-by-hop headers
    """
    headers = dict(req["headers"])   # copy

    # Remove hop-by-hop headers
    for h in list(headers.keys()):
        if h in HOP_BY_HOP:
            del headers[h]

    # Inject X-Forwarded-For
    client_ip = client_addr[0]
    if "x-forwarded-for" in headers:
        headers["x-forwarded-for"] = f"{headers['x-forwarded-for']}, {client_ip}"
    else:
        headers["x-forwarded-for"] = client_ip

    # Force HTTP/1.0 to avoid chunked transfer-encoding complications
    # (simplification for a teaching proxy)
    version = "HTTP/1.0"

    # Build request
    lines = [f"{req['method']} {req['path']} {version}"]
    lines.append(f"Host: {req['host']}")
    for k, v in headers.items():
        if k.lower() != "host":
            lines.append(f"{k}: {v}")
    lines.append("")  # blank line before body
    lines.append("")

    raw = "\r\n".join(lines).encode("utf-8")

    # Append any body bytes we already received
    body = req["body_prefix"]
    content_length = int(headers.get("content-length", 0))
    if body and content_length > 0:
        raw += body[:content_length]

    return raw


def forward_to_origin(req: dict, forwarded_req: bytes) -> bytes:
    """
    Open a TCP connection to the origin server, send the request,
    and return the full response as raw bytes.
    """
    origin = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    origin.settimeout(CONNECT_TIMEOUT)

    try:
        origin.connect((req["host"], req["port"]))
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        raise ConnectionError(f"cannot connect to {req['host']}:{req['port']}: {e}")

    origin.settimeout(READ_TIMEOUT)
    origin.sendall(forwarded_req)

    # Read full response
    response = b""
    while True:
        try:
            chunk = origin.recv(BUFFER_SIZE)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break

    origin.close()
    return response


def extract_status_code(response: bytes) -> int:
    """Extract the HTTP status code from the response first line."""
    try:
        first_line = response.split(b"\r\n", 1)[0].decode("utf-8", errors="replace")
        m = re.match(r"HTTP/\S+\s+(\d+)", first_line)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


# ── Client handler ────────────────────────────────────────────────────────────

def handle_client(client_sock: socket.socket, client_addr: tuple) -> None:
    """Handle one client connection (runs in its own thread)."""
    try:
        raw = recv_http_headers(client_sock)
        if not raw or b"\r\n\r\n" not in raw:
            return

        req = parse_request(raw)

        if not req["host"]:
            client_sock.sendall(b"HTTP/1.0 400 Bad Request\r\n\r\nMissing Host\n")
            return

        t_start = time.time()

        forwarded = build_forwarded_request(req, client_addr)

        try:
            response = forward_to_origin(req, forwarded)
        except ConnectionError as e:
            err_body = str(e).encode()
            client_sock.sendall(
                b"HTTP/1.0 502 Bad Gateway\r\n"
                b"Content-Type: text/plain\r\n"
                b"\r\n" + err_body
            )
            log.warning(f"502  {req['method']} http://{req['host']}{req['path']}  ({e})")
            return

        duration_ms = (time.time() - t_start) * 1000
        status_code = extract_status_code(response)

        client_sock.sendall(response)

        # Log the transaction
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        log.info(
            f"{status_code}  {req['method']} "
            f"http://{req['host']}{req['path']}  "
            f"({duration_ms:.0f}ms)  client={client_addr[0]}"
        )

    except (ValueError, UnicodeDecodeError) as e:
        try:
            client_sock.sendall(b"HTTP/1.0 400 Bad Request\r\n\r\n")
        except OSError:
            pass
        log.debug(f"400 parse error from {client_addr}: {e}")

    except Exception as e:
        try:
            client_sock.sendall(b"HTTP/1.0 500 Internal Server Error\r\n\r\n")
        except OSError:
            pass
        log.error(f"500 unexpected error for {client_addr}: {e}")

    finally:
        try:
            client_sock.close()
        except OSError:
            pass


# ── Main proxy server ─────────────────────────────────────────────────────────

def main() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, LISTEN_PORT))
    srv.listen(50)

    log.info(f"HTTP forward proxy listening on {LISTEN_HOST}:{LISTEN_PORT}")
    log.info(f"Test: curl -x http://{LISTEN_HOST}:{LISTEN_PORT} http://example.com/")
    log.info(f"Test: curl -x http://{LISTEN_HOST}:{LISTEN_PORT} http://httpbin.org/headers")
    log.info("Ctrl+C to stop\n")

    try:
        while True:
            try:
                client_sock, client_addr = srv.accept()
                t = threading.Thread(
                    target=handle_client,
                    args=(client_sock, client_addr),
                    daemon=True,
                )
                t.start()
            except OSError:
                break
    except KeyboardInterrupt:
        log.info("Proxy stopped.")
    finally:
        srv.close()


if __name__ == "__main__":
    main()

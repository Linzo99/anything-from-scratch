# Run: python3 https_server.py
"""
https_server.py — Minimal HTTPS server using ssl.SSLContext.

Generates a self-signed certificate with openssl (via subprocess), then
wraps a plain TCP socket with ssl.SSLContext to create an HTTPS server.
The client connects and gets an HTML response over TLS.

Usage:
    python3 https_server.py [port] [certfile] [keyfile]
    python3 https_server.py                      # port 8443, auto-gen cert
    python3 https_server.py 8443 my.crt my.key   # use existing cert/key

Test with:
    curl --cacert server.crt https://localhost:8443/
    curl -k https://localhost:8443/               # skip verification (insecure)
    openssl s_client -connect localhost:8443 -CAfile server.crt

The certificate is auto-generated if it does not already exist.
"""

import os
import socket
import ssl
import subprocess
import sys
from datetime import datetime


# ── certificate generation ────────────────────────────────────────────────────

def generate_self_signed_cert(certfile: str = "server.crt",
                               keyfile:  str = "server.key") -> None:
    """
    Generate a self-signed TLS certificate and private key using openssl.

    -x509:          output a certificate (not a CSR)
    -nodes:         no passphrase on the private key
    -days 365:      valid for 1 year
    -newkey rsa:2048: new 2048-bit RSA key
    -subj:          subject fields (CN=localhost for local testing)
    -addext:        Subject Alternative Names so modern clients accept it
    """
    if os.path.exists(certfile) and os.path.exists(keyfile):
        print(f"Certificate already exists: {certfile}  (skipping generation)")
        return

    print(f"Generating self-signed certificate → {certfile}, {keyfile} …")
    cmd = [
        "openssl", "req", "-x509", "-nodes", "-days", "365",
        "-newkey", "rsa:2048",
        "-keyout", keyfile,
        "-out",    certfile,
        "-subj",   "/C=US/ST=Dev/L=Local/O=Dev/CN=localhost",
        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        print(f"Certificate generated.  Key file: {keyfile}  Cert file: {certfile}")
    except FileNotFoundError:
        raise SystemExit(
            "Error: openssl not found.\n"
            "Install:  sudo apt-get install -y openssl  (Ubuntu)\n"
            "          brew install openssl               (macOS)"
        )


# ── HTTP response builder ─────────────────────────────────────────────────────

def http_date() -> str:
    return datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")


def build_response(code: int, reason: str, content_type: str, body: bytes) -> bytes:
    headers = {
        "Server":         "https-server/1.0",
        "Date":           http_date(),
        "Content-Type":   content_type,
        "Content-Length": str(len(body)),
        "Connection":     "close",
    }
    header_str = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    return (f"HTTP/1.1 {code} {reason}\r\n" + header_str + "\r\n").encode("ascii") + body


HOMEPAGE = b"""<!DOCTYPE html>
<html>
<head><title>HTTPS Server Demo</title></head>
<body>
<h1>HTTPS Works!</h1>
<p>You connected over TLS using a self-signed certificate.</p>
<p>This response travelled over an encrypted connection.</p>
<ul>
  <li><a href="/cert">GET /cert</a> — show certificate info</li>
  <li><a href="/info">GET /info</a> — show connection info</li>
</ul>
</body>
</html>
"""

ROUTES = {
    "/":     ("text/html; charset=utf-8", HOMEPAGE),
    "/hello": ("text/plain; charset=utf-8",
               b"Hello from HTTPS! Your connection is encrypted.\n"),
}


# ── request handler ───────────────────────────────────────────────────────────

def handle_connection(tls_sock: ssl.SSLSocket, addr: tuple,
                      certfile: str) -> None:
    """Handle one HTTPS request over the TLS-wrapped socket."""
    try:
        buf = b""
        tls_sock.settimeout(5.0)
        while b"\r\n\r\n" not in buf:
            chunk = tls_sock.recv(4096)
            if not chunk:
                return
            buf += chunk

        # Parse request line
        lines = buf[:buf.find(b"\r\n\r\n")].decode("ascii", errors="replace").split("\r\n")
        parts = lines[0].split(" ", 2) if lines else []
        method = parts[0].upper() if parts else "?"
        path   = parts[1].split("?")[0] if len(parts) > 1 else "/"

        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] TLS {addr[0]}  {method} {path} "
              f"({tls_sock.version()}, {tls_sock.cipher()[0]})")

        if method != "GET":
            body = f"Method {method} not allowed.\n".encode()
            tls_sock.sendall(build_response(405, "Method Not Allowed",
                                            "text/plain", body))
            return

        # Special routes
        if path == "/cert":
            # Show certificate info
            cert_info = subprocess.run(
                ["openssl", "x509", "-in", certfile, "-noout",
                 "-subject", "-issuer", "-dates"],
                capture_output=True, text=True
            ).stdout
            body = (
                f"Certificate Info:\n\n{cert_info}\n"
                f"Note: Subject == Issuer (self-signed)\n"
            ).encode()
            tls_sock.sendall(build_response(200, "OK", "text/plain; charset=utf-8", body))
            return

        if path == "/info":
            body = (
                f"TLS Version : {tls_sock.version()}\n"
                f"Cipher Suite: {tls_sock.cipher()[0]}\n"
                f"Client addr : {addr[0]}:{addr[1]}\n"
            ).encode()
            tls_sock.sendall(build_response(200, "OK", "text/plain; charset=utf-8", body))
            return

        if path in ROUTES:
            ctype, rbody = ROUTES[path]
            tls_sock.sendall(build_response(200, "OK", ctype, rbody))
        else:
            body = f"404 Not Found: {path}\n".encode()
            tls_sock.sendall(build_response(404, "Not Found",
                                            "text/plain; charset=utf-8", body))

    except (ssl.SSLError, ConnectionResetError, BrokenPipeError, socket.timeout) as exc:
        print(f"  [{addr[0]}] connection error: {exc}")
    except Exception as exc:
        print(f"  [{addr[0]}] handler error: {exc}")
        try:
            body = str(exc).encode()
            tls_sock.sendall(build_response(500, "Internal Server Error",
                                            "text/plain", body))
        except Exception:
            pass
    finally:
        tls_sock.close()


# ── HTTPS server ──────────────────────────────────────────────────────────────

def run_https_server(port: int = 8443,
                     certfile: str = "server.crt",
                     keyfile:  str = "server.key") -> None:
    # Generate cert if needed
    generate_self_signed_cert(certfile, keyfile)

    # Build SSL context
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    # Plain TCP socket
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("", port))
    srv.listen(5)

    print(f"\nHTTPS server at https://localhost:{port}")
    print(f"  Certificate: {certfile}  Key: {keyfile}")
    print(f"\nTest commands:")
    print(f"  curl --cacert {certfile} https://localhost:{port}/")
    print(f"  curl -k https://localhost:{port}/")
    print(f"  openssl s_client -connect localhost:{port} -CAfile {certfile}")
    print(f"\nPress Ctrl-C to stop\n")

    try:
        while True:
            raw_sock, addr = srv.accept()
            try:
                # Wrap the plain socket in TLS — this performs the handshake
                tls_sock = ctx.wrap_socket(raw_sock, server_side=True)
            except ssl.SSLError as exc:
                print(f"  [{addr[0]}] TLS handshake failed: {exc}")
                raw_sock.close()
                continue
            print(f"  [{addr[0]}] TLS connected — {tls_sock.version()} {tls_sock.cipher()[0]}")
            handle_connection(tls_sock, addr, certfile)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        srv.close()


if __name__ == "__main__":
    port     = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    certfile = sys.argv[2] if len(sys.argv) > 2 else "server.crt"
    keyfile  = sys.argv[3] if len(sys.argv) > 3 else "server.key"
    run_https_server(port=port, certfile=certfile, keyfile=keyfile)

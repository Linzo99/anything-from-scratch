# Add TLS to the HTTP Server

> Wrapping a plain socket in TLS takes five lines of Python — understanding what those five lines do takes this whole lesson.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 5, Lesson 04 — Trace a TLS Handshake; Phase 5, Lesson 02 — Build a Minimal HTTP Server
**Time:** ~45 minutes

## Learning Objectives
- Generate a self-signed TLS certificate with OpenSSL
- Wrap a Python socket with `ssl.SSLContext` to create an HTTPS server
- Connect to the server with `curl --cacert` to verify the certificate
- Explain the difference between self-signed and CA-signed certificates
- Describe why browsers show a warning for self-signed certs but `curl --cacert` does not

## The Problem

Your HTTP server from Lesson 02 sends everything in plaintext — anyone between client and server can read the passwords, session tokens, and page content. TLS solves this by encrypting the connection. Every production HTTP server uses TLS.

Python's `ssl` module lets you add TLS to any TCP socket with minimal code. Understanding what's happening under the hood — certificate validation, SNI, cipher negotiation — means you won't be lost when it fails.

## The Concept

### Self-Signed vs CA-Signed Certificates

A TLS certificate is a file that binds a public key to a domain name, signed by a Certificate Authority.

**CA-signed certificate**: Signed by a CA whose root certificate is pre-installed in operating systems (DigiCert, Let's Encrypt, etc.). Browsers and `curl` trust these by default.

**Self-signed certificate**: Signed by your own private key, not by any CA. Functionally identical — the encryption is just as strong. But clients don't trust it by default because there's no third party vouching for it.

```
CA-signed:
  server.crt ← signed by → DigiCert Intermediate CA
  DigiCert Intermediate CA ← signed by → DigiCert Root CA
  DigiCert Root CA ← self-signed, pre-installed in OS

Self-signed:
  server.crt ← signed by → server.key (same key, no chain)
```

For development and testing, self-signed certificates are perfectly fine. You explicitly tell your client "trust this specific certificate" — that's what `curl --cacert` does.

### Python's ssl Module

Python's `ssl` module wraps TCP sockets with TLS. The key objects:

**`ssl.SSLContext`** — holds TLS configuration: which protocol versions to use, which ciphers, certificate files, verification settings.

**`context.wrap_socket(socket)`** — wraps a plain socket in TLS. For servers, the socket returned by `accept()` must be wrapped. For clients, the socket before `connect()` must be wrapped.

```python
# Server side wrapping
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile='server.crt', keyfile='server.key')

# In the server loop, after accept():
raw_sock, addr = server_sock.accept()
tls_sock = context.wrap_socket(raw_sock, server_side=True)
# Now tls_sock is an encrypted connection — use it like a normal socket
```

### Certificate Verification Modes

```
ssl.CERT_NONE     — don't verify the server certificate (insecure, for testing)
ssl.CERT_OPTIONAL — verify if the server provides a cert
ssl.CERT_REQUIRED — always verify; raise exception if cert is invalid (default for clients)
```

For our server-side code, we don't need to verify the client (we're not doing mutual TLS). For clients connecting to our server, they need to verify our certificate.

## Build It

### Step 1: Generate a Self-Signed Certificate

```bash
# Create a private key and self-signed certificate in one command
# -x509: output a self-signed certificate (not a CSR)
# -nodes: no DES encryption on the private key (no passphrase required)
# -days 365: valid for 1 year
# -newkey rsa:2048: generate a new 2048-bit RSA key
# -subj: certificate subject (fill in real values if you like)
# -extensions v3_req: enable subject alternative names

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout server.key \
  -out server.crt \
  -subj "/C=US/ST=Dev/L=Local/O=Dev/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

This creates two files:
- `server.key` — the private key (keep this secret; never commit to git)
- `server.crt` — the public certificate (safe to share)

Verify the certificate:

```bash
openssl x509 -in server.crt -noout -text | grep -A5 "Subject:"
openssl x509 -in server.crt -noout -dates
openssl x509 -in server.crt -noout -subject -issuer
```

Note: Subject and Issuer will be the same (self-signed).

### Step 2: The HTTPS Server

Build on the HTTP server from Lesson 02. We only need to change the socket setup:

```python
# https_server.py
import socket
import ssl
import os
import mimetypes
from datetime import datetime


# Reuse all the helper functions from http_server.py
# (paste get_content_type, log, parse_request, build_response,
#  make_error_response, handle_get, handle_connection from Lesson 02)

# ---- paste Lesson 02 helpers here ----


def create_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    """
    Create an SSL context for a server.
    """
    # PROTOCOL_TLS_SERVER: configure as a TLS server (not client)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Load the certificate and private key
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)

    # Restrict to TLS 1.2+ (disable older, insecure versions)
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Set strong cipher suites (optional — Python's defaults are reasonable)
    # context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20')

    return context


def run_https_server(host: str = '', port: int = 8443,
                     root_dir: str = '.',
                     certfile: str = 'server.crt',
                     keyfile: str = 'server.key') -> None:
    """
    Start the HTTPS server.
    Default port 8443 (instead of 443 which requires root on Linux).
    """
    root_dir = os.path.abspath(root_dir)

    if not os.path.exists(certfile):
        print(f"Error: Certificate file '{certfile}' not found.")
        print("Generate with: openssl req -x509 -nodes -days 365 "
              "-newkey rsa:2048 -keyout server.key -out server.crt "
              "-subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'")
        return

    # Create the SSL context with our certificate
    ssl_context = create_ssl_context(certfile, keyfile)

    # Create the TCP server socket (same as HTTP server)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
        server_sock.listen(5)

        listen_addr = host or '0.0.0.0'
        print(f"HTTPS server started at https://{listen_addr}:{port}")
        print(f"Serving: {root_dir}")
        print(f"Certificate: {certfile}")
        print(f"Test with: curl --cacert {certfile} https://localhost:{port}/")
        print("Press Ctrl+C to stop.\n")

        while True:
            # Accept a plain TCP connection
            raw_sock, client_addr = server_sock.accept()

            # Wrap the socket in TLS
            # This performs the TLS handshake automatically
            try:
                tls_sock = ssl_context.wrap_socket(
                    raw_sock,
                    server_side=True  # We are the server
                )
            except ssl.SSLError as e:
                # TLS handshake failed (e.g., client doesn't trust our cert,
                # or tried to connect with HTTP instead of HTTPS)
                log(f"{client_addr[0]} TLS handshake failed: {e}")
                raw_sock.close()
                continue

            log(f"TLS connection from {client_addr[0]} "
                f"({tls_sock.version()}, {tls_sock.cipher()[0]})")

            # Handle the connection just like HTTP — the encryption is transparent
            handle_connection(tls_sock, client_addr, root_dir)

    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server_sock.close()


if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    root = sys.argv[2] if len(sys.argv) > 2 else '.'
    cert = sys.argv[3] if len(sys.argv) > 3 else 'server.crt'
    key  = sys.argv[4] if len(sys.argv) > 4 else 'server.key'

    run_https_server(port=port, root_dir=root, certfile=cert, keyfile=key)
```

Notice: `handle_connection` is unchanged from Lesson 02. The TLS layer is completely transparent — once the handshake is done, `tls_sock.recv()` and `tls_sock.sendall()` work exactly like a plain socket from the application's perspective.

### Step 3: Full File — Paste the Lesson 02 Helpers

Here is the complete `https_server.py` with all helpers included:

```python
# https_server.py — complete file
import socket
import ssl
import os
import mimetypes
from datetime import datetime

mimetypes.init()

MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css':  'text/css',
    '.js':   'application/javascript',
    '.json': 'application/json',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.txt':  'text/plain; charset=utf-8',
}


def get_content_type(path: str) -> str:
    _, ext = os.path.splitext(path.lower())
    return MIME_TYPES.get(ext, mimetypes.guess_type(path)[0] or 'application/octet-stream')


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def parse_request(raw: bytes):
    header_end = raw.find(b'\r\n\r\n')
    if header_end == -1:
        return None
    try:
        lines = raw[:header_end].decode('ascii', errors='replace').split('\r\n')
        parts = lines[0].split(' ')
        if len(parts) < 2:
            return None
        method = parts[0].upper()
        path = os.path.normpath(parts[1].split('?')[0])
        headers = {}
        for line in lines[1:]:
            if ':' in line:
                n, _, v = line.partition(':')
                headers[n.strip().lower()] = v.strip()
        return method, path, headers
    except Exception:
        return None


def build_response(code: int, reason: str, headers: dict, body: bytes) -> bytes:
    h = {'server': 'https-server/1.0', 'connection': 'close',
         'content-length': str(len(body)), **headers}
    header_str = ''.join(f"{k}: {v}\r\n" for k, v in h.items())
    return f"HTTP/1.1 {code} {reason}\r\n".encode() + header_str.encode() + b'\r\n' + body


def make_error_response(code: int, reason: str, msg: str) -> bytes:
    body = f"<html><body><h1>{code} {reason}</h1><p>{msg}</p></body></html>".encode()
    return build_response(code, reason, {'content-type': 'text/html; charset=utf-8'}, body)


def handle_get(path: str, root_dir: str) -> bytes:
    rel = path.lstrip('/')
    if not rel:
        rel = 'index.html'
    fs = os.path.realpath(os.path.join(root_dir, rel))
    root_real = os.path.realpath(root_dir)
    if not fs.startswith(root_real):
        return make_error_response(403, 'Forbidden', 'Access denied.')
    if not os.path.exists(fs):
        return make_error_response(404, 'Not Found', f"'{path}' not found.")
    if os.path.isdir(fs):
        idx = os.path.join(fs, 'index.html')
        if os.path.exists(idx):
            fs = idx
        else:
            entries = sorted(os.listdir(fs))
            links = ''.join(f'<li><a href="{path.rstrip("/")}/{e}">{e}</a></li>' for e in entries)
            body = f"<html><body><h1>{path}</h1><ul>{links}</ul></body></html>".encode()
            return build_response(200, 'OK', {'content-type': 'text/html; charset=utf-8'}, body)
    try:
        with open(fs, 'rb') as f:
            body = f.read()
    except PermissionError:
        return make_error_response(403, 'Forbidden', 'Permission denied.')
    log(f"  200 OK: {fs} ({len(body)}b)")
    return build_response(200, 'OK', {'content-type': get_content_type(fs)}, body)


def handle_connection(client_sock, client_addr: tuple, root_dir: str) -> None:
    try:
        raw = b''
        while b'\r\n\r\n' not in raw:
            chunk = client_sock.recv(4096)
            if not chunk:
                return
            raw += chunk
        parsed = parse_request(raw)
        if not parsed:
            client_sock.sendall(make_error_response(400, 'Bad Request', 'Malformed request.'))
            return
        method, path, headers = parsed
        log(f"{client_addr[0]} {method} {path}")
        if method == 'GET':
            client_sock.sendall(handle_get(path, root_dir))
        else:
            client_sock.sendall(make_error_response(405, 'Method Not Allowed', f"'{method}' not supported."))
    except (ssl.SSLError, ConnectionResetError, BrokenPipeError) as e:
        log(f"Connection error: {e}")
    finally:
        client_sock.close()


def create_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def run_https_server(host: str = '', port: int = 8443,
                     root_dir: str = '.', certfile: str = 'server.crt',
                     keyfile: str = 'server.key') -> None:
    root_dir = os.path.abspath(root_dir)
    ssl_ctx = create_ssl_context(certfile, keyfile)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((host, port))
        srv.listen(5)
        print(f"HTTPS at https://localhost:{port}  root={root_dir}")
        print(f"Test: curl --cacert {certfile} https://localhost:{port}/\n")
        while True:
            raw_sock, addr = srv.accept()
            try:
                tls_sock = ssl_ctx.wrap_socket(raw_sock, server_side=True)
            except ssl.SSLError as e:
                log(f"{addr[0]} handshake failed: {e}")
                raw_sock.close()
                continue
            log(f"TLS {addr[0]} — {tls_sock.version()} {tls_sock.cipher()[0]}")
            handle_connection(tls_sock, addr, root_dir)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        srv.close()


if __name__ == '__main__':
    import sys
    run_https_server(
        port=int(sys.argv[1]) if len(sys.argv) > 1 else 8443,
        root_dir=sys.argv[2] if len(sys.argv) > 2 else '.',
        certfile=sys.argv[3] if len(sys.argv) > 3 else 'server.crt',
        keyfile=sys.argv[4] if len(sys.argv) > 4 else 'server.key',
    )
```

### Step 4: Run and Test

```bash
# Generate certificate (if not done in Step 1)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server.key -out server.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

# Create a test page
mkdir -p test_site
echo '<html><body><h1>HTTPS Works!</h1></body></html>' > test_site/index.html

# Start the server
python3 https_server.py 8443 test_site server.crt server.key
```

In another terminal:

```bash
# This works — we tell curl to trust our self-signed cert
curl --cacert server.crt https://localhost:8443/

# This fails — curl doesn't trust self-signed certs by default
curl https://localhost:8443/
# error: SSL certificate problem: self-signed certificate

# This works but is INSECURE — skips certificate verification entirely
curl -k https://localhost:8443/
# -k means "insecure" — never use in production

# Try connecting with HTTP (not HTTPS) — should see a TLS error
curl http://localhost:8443/
```

### Step 5: Inspect the Handshake

```bash
# See the full TLS handshake details
openssl s_client -connect localhost:8443 -CAfile server.crt

# Verify the cert details
openssl s_client -connect localhost:8443 -CAfile server.crt 2>/dev/null | \
  openssl x509 -noout -subject -issuer -dates
```

The output confirms our self-signed certificate:
- Subject and Issuer are the same (`CN=localhost`)
- Dates show the 365-day validity period

## Exercises

1. **SNI in the server**: Modify the server to load different certificates based on the SNI hostname. Use `ssl.SSLContext` with `sni_callback` to pick the right context based on `server_name`. Create two separate certificates for `localhost` and `127.0.0.1` and serve the correct one.

2. **HSTS header**: Add a `Strict-Transport-Security: max-age=31536000` header to every HTTPS response. This tells browsers to always use HTTPS for this domain. What would happen if you added this header on an HTTP server?

3. **Let's Encrypt on a real domain**: If you have a domain name pointing to a server, use `certbot certonly --standalone -d yourdomain.com` to get a free, CA-signed certificate from Let's Encrypt. Replace your self-signed cert with the Let's Encrypt cert and verify that curl works without `--cacert`.

4. **Client certificate authentication**: Configure the SSLContext with `context.verify_mode = ssl.CERT_REQUIRED` and `context.load_verify_locations('client_ca.crt')`. Generate a client certificate and connect with `curl --cert client.crt --key client.key`. This is "mutual TLS" (mTLS).

5. **HTTP to HTTPS redirect**: Run both an HTTP server (port 8080) and your HTTPS server (port 8443). Modify the HTTP server to return `301 Moved Permanently` with `Location: https://localhost:8443/` for all requests. Test with curl and verify it follows the redirect.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| SSLContext | "SSL settings" | A Python object that holds TLS configuration: certificate files, allowed protocol versions, cipher preferences, and verification mode |
| wrap_socket | "add TLS to socket" | A method that takes a plain TCP socket and returns a new socket-like object that transparently encrypts/decrypts all data using TLS |
| Self-signed certificate | "dev cert" | A TLS certificate signed by its own private key; encryption is identical to CA-signed, but clients reject it by default because no trusted CA vouches for it |
| --cacert | "trust this cert" | A curl flag that specifies a CA certificate (or in our case, the self-signed cert itself) to trust for this connection; overrides the system certificate store |
| -k / --insecure | "skip TLS verification" | Tells curl to skip all certificate validation; the connection is still encrypted but there is no authentication — vulnerable to man-in-the-middle attacks |
| TLSv1_2 minimum | "minimum TLS version" | Configuring the server to reject connections from clients that only support older, insecure TLS versions (TLS 1.0, 1.1); set via context.minimum_version |
| Mutual TLS (mTLS) | "two-way TLS" | TLS where both client and server present certificates; typically used for service-to-service authentication where you control both ends |

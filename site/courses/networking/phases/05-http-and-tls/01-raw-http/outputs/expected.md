# Expected Output

Running `bash raw_http.sh` should produce:

```
================================================================
  Raw HTTP/1.1 Demo — server on 127.0.0.1:8080
================================================================

────────────────────────────────────────────────────────
  REQUEST: GET /
────────────────────────────────────────────────────────

  Bytes sent (\r\n shown as ↵):
    GET / HTTP/1.1↵
    Host: 127.0.0.1:8080↵
    Connection: close↵
    User-Agent: raw-http-demo/1.0↵
    Accept: */*↵
    ↵

  Bytes received:

    HTTP/1.1 200 OK
    Server: SimpleHTTP/0.6 Python/3.10.12
    Date: Fri, 29 May 2026 12:00:00 GMT
    Content-type: text/html
    Content-Length: 143
    Last-Modified: Fri, 29 May 2026 12:00:00 GMT
    Connection: close

    <!DOCTYPE html>
    <html>
    <head><title>Raw HTTP Demo</title></head>
    <body>
    <h1>Hello from raw HTTP!</h1>
    <p>This page was served by python3 -m http.server</p>
    </body>
    </html>

────────────────────────────────────────────────────────
  REQUEST: GET /api.json
────────────────────────────────────────────────────────

  Bytes received:

    HTTP/1.1 200 OK
    Content-type: application/json
    Content-Length: 37

    {"status":"ok","lesson":"raw-http"}

────────────────────────────────────────────────────────
  REQUEST: GET /notexist.html
────────────────────────────────────────────────────────

  Bytes received:

    HTTP/1.1 404 File not found
    Content-type: text/html;charset=utf-8
    Content-Length: 469

    <!DOCTYPE HTML>
    ...

────────────────────────────────────────────────────────
  Key observations
────────────────────────────────────────────────────────

  REQUEST LINE:   METHOD SP path SP HTTP/1.1 CRLF
  HEADERS:        Key: Value CRLF  (each header ends with \r\n)
  BLANK LINE:     \r\n  (signals end of headers)
  BODY:           Content-Length bytes follow (or until connection close)

  Status codes observed:
    200 OK         — resource found and returned
    404 Not Found  — no file at that path
```

## Common issues

- **Issue**: `Warning: neither ncat nor nc found.  Using Python socket instead.` → **Fix**: Install ncat: `sudo apt-get install -y ncat` (Ubuntu) or `brew install nmap` (macOS).  The Python fallback still works but does not show the raw byte-by-byte view.
- **Issue**: `Connection refused` or script hangs → **Fix**: Port 8080 may already be in use.  Change `PORT=8080` at the top of the script to an unused port (e.g., `PORT=8181`).
- **Issue**: `python3 -m http.server` output floods the terminal → **Fix**: The server stderr is redirected to `/dev/null` by the script.  If you see server logs, check that your shell version supports `&>/dev/null`.

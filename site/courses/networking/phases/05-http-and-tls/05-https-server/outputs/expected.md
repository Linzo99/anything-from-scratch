# Expected Output

## Server terminal

Running `python3 https_server.py` should produce:

```
Generating self-signed certificate → server.crt, server.key …
Certificate generated.  Key file: server.key  Cert file: server.crt

HTTPS server at https://localhost:8443
  Certificate: server.crt  Key: server.key

Test commands:
  curl --cacert server.crt https://localhost:8443/
  curl -k https://localhost:8443/
  openssl s_client -connect localhost:8443 -CAfile server.crt

Press Ctrl-C to stop

  [127.0.0.1] TLS connected — TLSv1.3 TLS_AES_128_GCM_SHA256
  [12:00:01] TLS 127.0.0.1  GET /  (TLSv1.3, TLS_AES_128_GCM_SHA256)
  [127.0.0.1] TLS connected — TLSv1.3 TLS_AES_128_GCM_SHA256
  [12:00:02] TLS 127.0.0.1  GET /cert  (TLSv1.3, TLS_AES_128_GCM_SHA256)
```

## `curl --cacert server.crt https://localhost:8443/`

```
<!DOCTYPE html>
<html>
<head><title>HTTPS Server Demo</title></head>
<body>
<h1>HTTPS Works!</h1>
<p>You connected over TLS using a self-signed certificate.</p>
...
```

## `curl https://localhost:8443/` (without --cacert, should fail)

```
curl: (60) SSL certificate problem: self-signed certificate
More details here: https://curl.se/docs/sslcerts.html
```

## `curl -k https://localhost:8443/cert`

```
Certificate Info:

subject=C = US, ST = Dev, L = Local, O = Dev, CN = localhost
issuer=C = US, ST = Dev, L = Local, O = Dev, CN = localhost
notBefore=May 29 12:00:00 2026 GMT
notAfter=May 29 12:00:00 2027 GMT

Note: Subject == Issuer (self-signed)
```

## `openssl s_client -connect localhost:8443 -CAfile server.crt`

```
CONNECTED(00000003)
depth=0 C = US, ST = Dev, L = Local, O = Dev, CN = localhost
verify return:1
---
Certificate chain
 0 s:CN = localhost
   i:CN = localhost
---
...
Protocol  : TLSv1.3
Cipher    : TLS_AES_128_GCM_SHA256
```

Note that `Subject == Issuer` confirms this is a self-signed certificate.

## Common issues

- **Issue**: `Error: openssl not found` → **Fix**: Install openssl: `sudo apt-get install -y openssl` (Ubuntu) or `brew install openssl` (macOS).
- **Issue**: `curl: (60) SSL certificate problem: self-signed certificate` → **Fix**: This is expected when you do NOT pass `--cacert server.crt`.  Use `curl --cacert server.crt https://localhost:8443/` or `curl -k` (insecure).
- **Issue**: `ssl.SSLError: [SSL: UNKNOWN_PROTOCOL]` in server log → **Fix**: A client connected with plain HTTP instead of HTTPS.  Make sure the URL starts with `https://`, not `http://`.
- **Issue**: `OSError: [Errno 98] Address already in use` → **Fix**: A previous instance is still running.  Kill it: `pkill -f https_server.py` and re-run.

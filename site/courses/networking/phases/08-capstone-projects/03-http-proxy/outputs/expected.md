# Expected Output

**Terminal 1 — Start the proxy:**
```
$ python3 http_proxy.py
14:55:00  HTTP forward proxy listening on 127.0.0.1:8888
14:55:00  Test: curl -x http://127.0.0.1:8888 http://example.com/
14:55:00  Test: curl -x http://127.0.0.1:8888 http://httpbin.org/headers
14:55:00  Ctrl+C to stop
```

**Terminal 2 — Send requests through the proxy:**
```
$ curl -s -x http://127.0.0.1:8888 http://example.com/
<!doctype html>
<html>
<head>
    <title>Example Domain</title>
...

$ curl -s -x http://127.0.0.1:8888 http://httpbin.org/headers
{
  "headers": {
    "Host": "httpbin.org",
    "User-Agent": "curl/7.88.1",
    "X-Forwarded-For": "127.0.0.1"
  }
}
```

**Back in Terminal 1 — Proxy log output:**
```
14:55:12  200  GET http://example.com/  (342ms)  client=127.0.0.1
14:55:15  200  GET http://httpbin.org/headers  (523ms)  client=127.0.0.1
```

The `X-Forwarded-For: 127.0.0.1` header in the httpbin.org response confirms the proxy is injecting the client IP correctly.

## Common issues

- **Issue**: `502 Bad Gateway` — **Fix**: The origin server is unreachable. Check your internet connection. For local testing, start a simple HTTP server: `python3 -m http.server 8080` and proxy to `http://127.0.0.1:8080/`.
- **Issue**: HTTPS requests fail (e.g., `curl -x ... https://example.com`) — **Fix**: This proxy only handles plain HTTP (`http://`). HTTPS requires the `CONNECT` tunnel method, which is not implemented. Use `http://` URLs for testing.
- **Issue**: `Address already in use` on port 8888 — **Fix**: Change the port: `python3 http_proxy.py 9999`, then `curl -x http://127.0.0.1:9999 http://example.com/`.

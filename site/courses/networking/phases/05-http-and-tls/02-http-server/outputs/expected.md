# Expected Output

## Server terminal

Running `python3 http_server.py 8080` should produce:

```
Minimal HTTP/1.1 server running at http://localhost:8080
  Serving 3 paths: /, /hello, /data.json
  Press Ctrl-C to stop

  [12:00:01] 127.0.0.1  GET /  (Host: localhost:8080)
  [12:00:02] 127.0.0.1  GET /hello  (Host: localhost:8080)
  [12:00:03] 127.0.0.1  GET /data.json  (Host: localhost:8080)
  [12:00:04] 127.0.0.1  GET /notfound  (Host: localhost:8080)
```

## Client output (curl -v http://localhost:8080/)

```
* Connected to localhost (127.0.0.1) port 8080
> GET / HTTP/1.1
> Host: localhost:8080
> User-Agent: curl/7.88.1
> Accept: */*
>
< HTTP/1.1 200 OK
< Server: raw-python-http/1.0
< Date: Fri, 29 May 2026 12:00:01 GMT
< Content-Type: text/html; charset=utf-8
< Content-Length: 312
< Connection: close
<
<!DOCTYPE html>
<html>
<head><title>Minimal HTTP Server</title></head>
<body>
<h1>Minimal HTTP/1.1 Server</h1>
...
```

## curl http://localhost:8080/data.json

```
{"server":"raw-python","version":"1.0","status":"ok"}
```

## curl -v http://localhost:8080/notfound

```
< HTTP/1.1 404 Not Found
< Content-Type: text/html; charset=utf-8
< Content-Length: 115
```

## Common issues

- **Issue**: `OSError: [Errno 98] Address already in use` → **Fix**: Another process holds port 8080.  Use a different port: `python3 http_server.py 8181`.  The server sets `SO_REUSEADDR` so this error only appears if a different process is running on that port.
- **Issue**: curl shows `Empty reply from server` → **Fix**: The server may have crashed on startup.  Check for Python syntax errors or import issues above the error.
- **Issue**: Browser shows the raw HTML source instead of rendering → **Fix**: Make sure the `Content-Type` is `text/html; charset=utf-8` (not `text/plain`).  Check the `build_response` function.

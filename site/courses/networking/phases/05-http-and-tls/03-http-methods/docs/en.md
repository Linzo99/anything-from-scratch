# Understand HTTP Methods and Status Codes

> HTTP methods are a contract — POST means "create", DELETE means "remove", and the status code is the server's signed receipt.

**Type:** Learn
**Languages:** Python
**Prerequisites:** Phase 5, Lesson 02 — Build a Minimal HTTP Server
**Time:** ~40 minutes

## Learning Objectives
- Implement POST and DELETE handlers in the HTTP server from Lesson 02
- Return the semantically correct status codes: 201, 204, 400, 405
- Use `curl` to test each method and status code
- Explain the difference between safe, idempotent, and unsafe HTTP methods
- Describe what "RESTful" means at the HTTP level (not framework-level)

## The Problem

You've built a GET-only server. Real APIs use multiple HTTP methods — POST to create resources, PUT to replace them, PATCH to update them, DELETE to remove them. Each method carries specific semantics: what it means, whether it's safe to retry, and what status code the server should return.

Developers who don't know these semantics write APIs where DELETE creates data, POST is used for everything, and every response returns 200 even on failure. This breaks HTTP clients, caching, browser behavior, and the entire ecosystem of tools (load balancers, reverse proxies, monitoring) that depend on correct HTTP semantics.

## The Concept

### HTTP Methods and Their Properties

```
Method   Safe  Idempotent  Has Body  Typical Use
──────────────────────────────────────────────────────────────
GET      Yes   Yes         No        Retrieve a resource
HEAD     Yes   Yes         No        Like GET, headers only
POST     No    No          Yes       Create a new resource
PUT      No    Yes         Yes       Replace a resource entirely
PATCH    No    No          Yes       Partially update a resource
DELETE   No    Yes         No        Remove a resource
OPTIONS  Yes   Yes         No        Query allowed methods
```

**Safe**: The method does not modify server state. Safe methods can be prefetched, bookmarked, and cached by intermediaries without side effects.

**Idempotent**: Calling the method multiple times produces the same result as calling it once. PUT `{"name": "Alice"}` twice leaves exactly one `{"name": "Alice"}` — same as calling it once. POST twice may create two resources.

**Why this matters**: Retry logic, caching proxies, and browser behavior all depend on these properties. A browser will warn you "Are you sure you want to resubmit the form?" for POST but will silently retry GET. Load balancers can safely retry GET or PUT on failure but must not retry POST (it might create duplicates).

### Status Codes by Category

```
1xx  Informational   Request received, continuing
2xx  Success         Request understood and processed
3xx  Redirection     Client must take additional action
4xx  Client Error    Client made a mistake
5xx  Server Error    Server failed to handle a valid request
```

**Critical 2xx codes:**
```
200 OK              — Generic success with body
201 Created         — Resource successfully created (for POST)
204 No Content      — Success with no response body (for DELETE, PUT)
206 Partial Content — Partial range served
```

**Critical 4xx codes:**
```
400 Bad Request     — Client sent malformed data
401 Unauthorized    — Authentication required
403 Forbidden       — Authenticated but not authorized
404 Not Found       — Resource doesn't exist
405 Method Not Allowed  — Method not supported for this path
409 Conflict        — Conflict with current state (e.g., duplicate)
422 Unprocessable   — Valid format but semantic errors
429 Too Many Requests — Rate limit exceeded
```

**The Location header for 201**: When you respond with 201 Created, include a `Location` header with the URL of the newly created resource:

```
HTTP/1.1 201 Created
Location: /items/42
Content-Type: application/json

{"id": 42, "name": "Widget"}
```

### REST at the HTTP Level

REST (Representational State Transfer) is often confused with "JSON API." At the HTTP level, REST means:

- Resources are identified by URLs (`/items/42`)
- Operations are expressed with HTTP methods (GET, POST, PUT, DELETE)
- Responses carry the resource representation (JSON, XML, HTML)

A RESTful API for a to-do list:

```
GET    /todos         → 200 + list of all todos
POST   /todos         → 201 + new todo (with Location header)
GET    /todos/5       → 200 + todo #5 (or 404)
PUT    /todos/5       → 204 (or 200) + updated todo #5
DELETE /todos/5       → 204 (no body)
```

## Build It

### Step 1: Extend the Server from Lesson 02

We'll extend `http_server.py` to add a simple in-memory key-value store and support POST, PUT, and DELETE.

```python
# extended_server.py
import socket
import json
import os
from datetime import datetime


# In-memory store: a simple dict
# key = item ID (integer), value = item dict
store: dict[int, dict] = {}
next_id: int = 1


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def build_response(status_code: int, reason: str,
                   headers: dict, body: bytes) -> bytes:
    """Build a complete HTTP response."""
    status_line = f"HTTP/1.1 {status_code} {reason}\r\n"
    default_headers = {
        'server': 'extended-server/1.0',
        'connection': 'close',
        'content-length': str(len(body)),
    }
    all_headers = {**default_headers, **headers}
    header_str = ''.join(f"{k}: {v}\r\n" for k, v in all_headers.items())
    return status_line.encode('ascii') + header_str.encode('ascii') + b'\r\n' + body


def json_response(status_code: int, reason: str, data: dict,
                  extra_headers: dict | None = None) -> bytes:
    """Convenience: build a JSON response."""
    body = json.dumps(data, indent=2).encode('utf-8')
    headers = {'content-type': 'application/json; charset=utf-8'}
    if extra_headers:
        headers.update(extra_headers)
    return build_response(status_code, reason, headers, body)


def error_response(status_code: int, reason: str, message: str) -> bytes:
    """Build a JSON error response."""
    return json_response(status_code, reason, {'error': message})
```

### Step 2: Parse the Request Including Body

```python
def parse_request(raw: bytes) -> tuple[str, str, dict, bytes] | None:
    """
    Parse raw HTTP request bytes.
    Returns (method, path, headers, body_bytes) or None if malformed.
    """
    header_end = raw.find(b'\r\n\r\n')
    if header_end == -1:
        return None

    header_bytes = raw[:header_end]
    body_bytes = raw[header_end + 4:]

    try:
        header_text = header_bytes.decode('ascii', errors='replace')
    except Exception:
        return None

    lines = header_text.split('\r\n')
    if not lines:
        return None

    # Parse request line
    parts = lines[0].split(' ')
    if len(parts) < 2:
        return None
    method = parts[0].upper()
    path = parts[1].split('?')[0]  # Ignore query string

    # Parse headers
    headers = {}
    for line in lines[1:]:
        if ':' in line:
            name, _, value = line.partition(':')
            headers[name.strip().lower()] = value.strip()

    # If Content-Length is set, read exactly that many bytes of body
    content_length = headers.get('content-length')
    if content_length:
        try:
            length = int(content_length)
            body_bytes = body_bytes[:length]
        except ValueError:
            pass

    return method, path, headers, body_bytes
```

### Step 3: Implement GET, POST, PUT, DELETE

```python
def handle_get_item(item_id: int | None) -> bytes:
    """GET /items or GET /items/{id}"""
    if item_id is None:
        # List all items
        return json_response(200, 'OK', {'items': list(store.values())})
    
    if item_id not in store:
        return error_response(404, 'Not Found', f"Item {item_id} not found")
    
    return json_response(200, 'OK', store[item_id])


def handle_post_item(body: bytes, headers: dict) -> bytes:
    """POST /items — create a new item"""
    global next_id

    content_type = headers.get('content-type', '')
    if 'application/json' not in content_type:
        return error_response(400, 'Bad Request',
                              "Content-Type must be application/json")

    try:
        data = json.loads(body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return error_response(400, 'Bad Request', f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        return error_response(400, 'Bad Request', "Body must be a JSON object")

    # Assign a new ID
    item_id = next_id
    next_id += 1
    item = {'id': item_id, **data}
    store[item_id] = item

    log(f"  Created item {item_id}: {item}")

    # 201 Created with Location header pointing to the new resource
    return json_response(
        201, 'Created', item,
        extra_headers={'location': f'/items/{item_id}'}
    )


def handle_put_item(item_id: int, body: bytes, headers: dict) -> bytes:
    """PUT /items/{id} — replace an item entirely"""
    content_type = headers.get('content-type', '')
    if 'application/json' not in content_type:
        return error_response(400, 'Bad Request',
                              "Content-Type must be application/json")

    try:
        data = json.loads(body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return error_response(400, 'Bad Request', f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        return error_response(400, 'Bad Request', "Body must be a JSON object")

    is_new = item_id not in store
    item = {'id': item_id, **data}
    store[item_id] = item

    log(f"  {'Created' if is_new else 'Replaced'} item {item_id}: {item}")

    # 201 if created, 200 if replaced
    status = 201 if is_new else 200
    reason = 'Created' if is_new else 'OK'
    return json_response(status, reason, item)


def handle_delete_item(item_id: int) -> bytes:
    """DELETE /items/{id} — remove an item"""
    if item_id not in store:
        return error_response(404, 'Not Found', f"Item {item_id} not found")

    del store[item_id]
    log(f"  Deleted item {item_id}")

    # 204 No Content — success, but no body to send
    # This is the correct status code for DELETE
    return build_response(204, 'No Content', {}, b'')
```

### Step 4: The Router

```python
def route_request(method: str, path: str,
                  headers: dict, body: bytes) -> bytes:
    """
    Route a request to the appropriate handler based on method and path.
    Returns a complete HTTP response.
    """
    # Parse path: /items or /items/{id}
    parts = path.strip('/').split('/')

    if parts[0] == 'items':
        item_id = None
        if len(parts) >= 2:
            try:
                item_id = int(parts[1])
            except ValueError:
                return error_response(400, 'Bad Request',
                                      f"Invalid item ID: '{parts[1]}'")

        if method == 'GET':
            return handle_get_item(item_id)
        elif method == 'POST':
            if item_id is not None:
                return error_response(405, 'Method Not Allowed',
                                      "POST not allowed on /items/{id}")
            return handle_post_item(body, headers)
        elif method == 'PUT':
            if item_id is None:
                return error_response(405, 'Method Not Allowed',
                                      "PUT requires an item ID: /items/{id}")
            return handle_put_item(item_id, body, headers)
        elif method == 'DELETE':
            if item_id is None:
                return error_response(405, 'Method Not Allowed',
                                      "DELETE requires an item ID: /items/{id}")
            return handle_delete_item(item_id)
        else:
            # The Allow header lists which methods ARE supported
            response = error_response(405, 'Method Not Allowed',
                                      f"Method '{method}' not supported")
            # Add Allow header (RFC 7231 requires it on 405)
            return response  # Simplified: real server would add Allow header

    elif parts[0] == '':
        # Root path
        if method == 'GET':
            return json_response(200, 'OK', {
                'message': 'Extended HTTP Server',
                'endpoints': {
                    'GET /items': 'list all items',
                    'POST /items': 'create an item',
                    'GET /items/{id}': 'get one item',
                    'PUT /items/{id}': 'replace an item',
                    'DELETE /items/{id}': 'delete an item',
                }
            })
        else:
            return error_response(405, 'Method Not Allowed',
                                  "Only GET is supported at /")
    else:
        return error_response(404, 'Not Found', f"Path '{path}' not found")
```

### Step 5: The Server Loop

```python
def handle_connection(client_sock: socket.socket, addr: tuple) -> None:
    """Handle one HTTP connection."""
    try:
        raw = b''
        while b'\r\n\r\n' not in raw:
            chunk = client_sock.recv(4096)
            if not chunk:
                return
            raw += chunk
            if len(raw) > 65536:
                client_sock.sendall(error_response(400, 'Bad Request',
                                                   'Request too large'))
                return

        # If there's a body, read it too based on Content-Length
        result = parse_request(raw)
        if result is None:
            client_sock.sendall(error_response(400, 'Bad Request',
                                               'Malformed request'))
            return

        method, path, headers, body = result
        log(f"{addr[0]} {method} {path}")

        # Read remaining body bytes if Content-Length > what we already have
        content_length = int(headers.get('content-length', 0))
        header_end = raw.find(b'\r\n\r\n') + 4
        body_so_far = raw[header_end:]
        while len(body_so_far) < content_length:
            chunk = client_sock.recv(4096)
            if not chunk:
                break
            body_so_far += chunk
        body = body_so_far[:content_length]

        response = route_request(method, path, headers, body)
        client_sock.sendall(response)

    except Exception as e:
        log(f"Error handling connection: {e}")
        try:
            client_sock.sendall(error_response(500, 'Internal Server Error', str(e)))
        except Exception:
            pass
    finally:
        client_sock.close()


def run_server(port: int = 8080) -> None:
    """Start the extended HTTP server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', port))
    sock.listen(5)
    log(f"Server started on http://localhost:{port}")
    log("Endpoints: GET/POST /items  GET/PUT/DELETE /items/{{id}}")

    try:
        while True:
            client_sock, addr = sock.accept()
            handle_connection(client_sock, addr)
    except KeyboardInterrupt:
        log("Server stopped.")
    finally:
        sock.close()


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
```

### Step 6: Test With curl

```bash
# Start the server
python3 extended_server.py 8080

# In another terminal:

# GET root
curl http://localhost:8080/

# Create items with POST
curl -X POST http://localhost:8080/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget", "price": 9.99}'

curl -X POST http://localhost:8080/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Gadget", "price": 24.99}'

# List all items
curl http://localhost:8080/items

# Get one item
curl http://localhost:8080/items/1

# Replace an item with PUT
curl -X PUT http://localhost:8080/items/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Super Widget", "price": 14.99}'

# Delete an item
curl -X DELETE http://localhost:8080/items/2

# Verify deletion
curl http://localhost:8080/items

# Test 404
curl -v http://localhost:8080/items/999

# Test 405
curl -v -X DELETE http://localhost:8080/items
```

Check the status codes in curl's output (the `-v` flag shows them).

## Exercises

1. **PATCH support**: Add a PATCH handler that partially updates an item. Unlike PUT (which replaces the whole item), PATCH should merge the provided fields into the existing item using `{**existing, **patch_data}`.

2. **Allow header on 405**: RFC 7231 requires that a `405 Method Not Allowed` response include an `Allow` header listing the permitted methods (e.g., `Allow: GET, POST`). Add this to your 405 responses.

3. **Input validation**: Add validation that every POST/PUT body must have a `name` field of type string. Return `422 Unprocessable Entity` with a descriptive error if validation fails.

4. **Idempotency test**: Demonstrate PUT's idempotency by calling `PUT /items/5` three times with the same body. Show that the store ends up with exactly one item at ID 5 regardless of how many times you call it.

5. **Content negotiation**: The `Accept` request header lets clients specify what format they want. Add support for `Accept: text/plain` that returns items as a human-readable table instead of JSON.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Idempotent | "safe to retry" | A method where applying it N times produces the same result as applying it once; GET, PUT, DELETE are idempotent; POST is not |
| Safe method | "read-only" | A method that must not change server state; GET, HEAD, OPTIONS are safe; safe methods can be prefetched and cached freely |
| 201 Created | "resource was made" | The status code for a successful POST that created a new resource; must be accompanied by a Location header pointing to the new resource |
| 204 No Content | "success, nothing to return" | Used when the operation succeeded but there is no response body to send; typical for DELETE and sometimes PUT |
| 405 Method Not Allowed | "wrong verb" | The server understands the URL but doesn't support that HTTP method on it; must include an Allow header listing supported methods |
| 422 Unprocessable Entity | "valid format, bad data" | The request is well-formed (valid JSON) but semantically wrong (missing required field, invalid value); more specific than 400 Bad Request |
| REST | "RESTful API" | An architectural style where resources are identified by URLs and operations are expressed with HTTP methods; not a standard or protocol, just a set of design principles |

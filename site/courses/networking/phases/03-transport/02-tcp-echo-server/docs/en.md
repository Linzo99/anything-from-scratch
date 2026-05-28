# Build a TCP Echo Server

> The simplest possible server — one that just sends back whatever you send it — teaches you every concept you need to build any TCP server: binding, listening, accepting, reading, writing, and closing.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 3, Lesson 01 — Dissect a TCP Three-Way Handshake
**Time:** ~45 minutes

## Learning Objectives
- Explain the difference between a server socket and a connection socket
- Write a Python TCP server that binds, listens, accepts, and handles multiple clients
- Use `recv()` correctly, accounting for the fact that TCP does not preserve message boundaries
- Handle client disconnection gracefully without crashing the server
- Test the server with `netcat` and a custom Python client

## The Problem

Every networked service — HTTP, SSH, Redis, PostgreSQL — is built on the same socket primitives. Nginx and Redis do not use magic; they call `socket()`, `bind()`, `listen()`, `accept()`, `recv()`, and `send()`, just as you will in this lesson.

The most common mistake beginners make with TCP is assuming that one `send()` on the sender side equals one `recv()` on the receiver side. TCP is a byte stream, not a message protocol. If you send 100 bytes, the receiver might get them in one call, or in three calls of 30+30+40 bytes, or in 100 calls of 1 byte each. Until you understand this, you will write servers that break mysteriously on slow connections or with large payloads.

## The Concept

### The server socket lifecycle

```
                           Server                          Client
                              |                               |
socket()                      |                               |
  Create an endpoint          |                               |
bind(host, port)              |                               |  socket()
  Reserve the address         |                               |
listen(backlog)               |                               |
  Start accepting connections |                               |
                              |                               |
          accept() ←──────────|──── three-way handshake ─────|──→ connect()
  Blocks until a client       |                               |
  connects; returns a NEW     |                               |
  socket for this connection  |                               |
                              |  ←─── data ─────────────────  |  send()
recv() reads data             |                               |
send() writes response        |  ──── data ──────────────── → |  recv()
                              |                               |
close() this connection       |  ←─── FIN ──────────────────  |  close()
          accept() again ─────|                               |
  (waiting for next client)   |
```

There are TWO kinds of sockets on the server:

1. **The listening socket** (sometimes called the "server socket"): created once, bound to a port, used only to accept new connections. You never `recv()` data on it.

2. **The connection socket**: returned by `accept()`, unique to one client. You `recv()` and `send()` data on this. When the client closes, you close this socket — but the listening socket stays open.

### Backlog parameter

`listen(backlog)` tells the OS how many connections to hold in the queue while your server is busy processing another connection. If the queue is full, new SYNs are dropped (client sees a timeout). A backlog of 5 is typical for single-threaded servers; production servers use larger values.

### TCP is a stream, not a message protocol

This is the most important TCP programming concept. Unlike UDP (where each `send()` produces exactly one `recv()` of the same size), TCP is a continuous byte stream:

```
Sender:
  sock.send(b"Hello World")   # 11 bytes

Receiver (possible outcomes):
  recv(4096) → b"Hello World"       # got all 11 bytes at once (common on localhost)
  recv(4096) → b"Hello"             # then
  recv(4096) → b" World"            # got it in two chunks (common over real networks)
  recv(4096) → b"H"                 # any split is possible
  recv(4096) → b"ello World"
```

The OS buffers TCP data and may coalesce or split it. The application is responsible for framing — deciding where one "message" ends and the next begins.

Common framing strategies:
- **Fixed-length messages**: always read exactly N bytes.
- **Length-prefixed messages**: first 4 bytes = length of the payload that follows.
- **Delimiter-based**: read until you see `\n` (HTTP headers, Redis RESP, SMTP).
- **HTTP**: headers end at `\r\n\r\n`; then parse Content-Length.

Our echo server uses line-based framing — it echoes each complete line back.

### recv() return value

`recv(bufsize)` returns:
- A non-empty `bytes` object: data received.
- An empty `bytes` object `b""`: the connection was closed by the other side.
- Raises `OSError`: the connection was aborted unexpectedly.

Always check for the empty-bytes case. Calling `recv()` in a loop without checking for `b""` causes an infinite loop when the client disconnects.

### The SO_REUSEADDR socket option

After your server crashes or you restart it, you often get:

```
OSError: [Errno 98] Address already in use
```

This happens because the port is still in `TIME_WAIT` state from the previous connection. The fix: set `SO_REUSEADDR` before binding:

```python
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
```

This tells the OS: it's OK to bind to this port even if a previous socket is in TIME_WAIT. Almost every server sets this.

## Build It

### Version 1: Single-client server

Start simple — handle one client at a time:

```python
#!/usr/bin/env python3
"""
echo_server_v1.py — single-client TCP echo server.

Reads lines from the client and echoes them back, one line at a time.
Only handles one client at a time — a second client must wait.

Usage:
    python3 echo_server_v1.py [port]
    python3 echo_server_v1.py 9090

Test with:
    netcat localhost 9090
    nc localhost 9090
"""

import socket
import sys


def run_server(host: str, port: int):
    # Create a TCP socket
    # AF_INET = IPv4
    # SOCK_STREAM = TCP (stream) — SOCK_DGRAM would be UDP
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Allow reuse of the address immediately after the server stops
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to (host, port) — '' or '0.0.0.0' means all interfaces
    server_sock.bind((host, port))

    # Start listening; allow up to 5 pending connections in the queue
    server_sock.listen(5)
    print(f"Echo server listening on {host}:{port}")
    print("Press Ctrl-C to stop\n")

    while True:
        # accept() blocks until a client connects
        # Returns a NEW socket (conn) specific to this client, and the client's address
        conn, client_addr = server_sock.accept()
        print(f"[+] Client connected: {client_addr[0]}:{client_addr[1]}")

        try:
            handle_client(conn, client_addr)
        except Exception as e:
            print(f"[!] Error handling {client_addr}: {e}")
        finally:
            conn.close()
            print(f"[-] Client disconnected: {client_addr[0]}:{client_addr[1]}\n")


def handle_client(conn: socket.socket, addr: tuple):
    """
    Read lines from the client and echo them back.

    We accumulate bytes in a buffer and look for newline characters.
    This handles the case where TCP delivers data in multiple recv() calls.
    """
    buffer = b""  # accumulate incoming bytes here

    while True:
        # Receive up to 4096 bytes at a time
        # recv() returns b"" when the client closes the connection
        chunk = conn.recv(4096)

        if not chunk:
            # Client closed connection (sent FIN)
            break

        buffer += chunk

        # Process all complete lines in the buffer
        # A line ends with b"\n" (or b"\r\n" from Windows/netcat)
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.rstrip(b"\r")  # strip carriage return if present

            if not line:
                continue  # skip empty lines

            message = line.decode("utf-8", errors="replace")
            print(f"  {addr[0]}:{addr[1]} → {message!r}")

            # Echo back: the original message + newline
            response = line + b"\n"
            conn.sendall(response)
            # sendall() keeps calling send() until all bytes are sent
            # (unlike send() which may send fewer bytes than requested)


def main():
    host = "0.0.0.0"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    try:
        run_server(host, port)
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
```

Test it:

```bash
# Terminal 1 — start the server
python3 echo_server_v1.py 9090

# Terminal 2 — connect with netcat
nc localhost 9090
hello world
# → server echoes: hello world
foo bar baz
# → server echoes: foo bar baz
# Press Ctrl-D to disconnect
```

### Version 2: Multi-client server with threading

The single-client version blocks on `handle_client()` — while one client is connected, no other client can connect. Fix with threads:

```python
#!/usr/bin/env python3
"""
echo_server_v2.py — multi-client TCP echo server using threads.

Each client gets its own thread so multiple clients can connect simultaneously.

Usage:
    python3 echo_server_v2.py [port]

Test with multiple terminals:
    nc localhost 9090   # Terminal 2
    nc localhost 9090   # Terminal 3 — simultaneous
"""

import socket
import sys
import threading


def handle_client(conn: socket.socket, addr: tuple):
    """Handle one client connection in its own thread."""
    print(f"[+] Thread started for {addr[0]}:{addr[1]}")
    buffer = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.rstrip(b"\r")
                if not line:
                    continue
                print(f"  {addr[0]}:{addr[1]} → {line.decode('utf-8', errors='replace')!r}")
                conn.sendall(line + b"\n")
    except OSError as e:
        print(f"[!] {addr}: {e}")
    finally:
        conn.close()
        print(f"[-] {addr[0]}:{addr[1]} disconnected")


def run_server(host: str, port: int):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(10)
    print(f"Multi-client echo server listening on {host}:{port}")
    print("Press Ctrl-C to stop\n")

    while True:
        conn, addr = server_sock.accept()
        # Create a new thread for each client
        # daemon=True means the thread dies when the main thread dies (Ctrl-C)
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()
        print(f"[*] Active clients: {threading.active_count() - 1}")


def main():
    host = "0.0.0.0"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    try:
        run_server(host, port)
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
```

### A Python test client

Test the server programmatically:

```python
#!/usr/bin/env python3
"""
echo_client.py — test client for the echo server.

Sends N messages and verifies each is echoed back correctly.

Usage:
    python3 echo_client.py localhost 9090 [num_messages]
"""

import socket
import sys
import time


def run_client(host: str, port: int, num_messages: int = 10):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print(f"Connected to {host}:{port}")

    # Use a file-like wrapper for line-by-line reading
    # makefile() wraps the socket so we can use readline()
    sock_file = sock.makefile("rb")  # read-binary mode

    successes = 0
    failures = 0

    for i in range(num_messages):
        message = f"message {i}: hello from the test client"
        payload = (message + "\n").encode("utf-8")

        # Send the message
        sock.sendall(payload)

        # Read the echoed line back
        # readline() reads until \n — handles partial recv() correctly
        response_bytes = sock_file.readline()
        response = response_bytes.rstrip(b"\n\r").decode("utf-8")

        if response == message:
            successes += 1
            print(f"  [{i:3d}] OK: {message!r}")
        else:
            failures += 1
            print(f"  [{i:3d}] MISMATCH: sent {message!r}, got {response!r}")

        time.sleep(0.01)  # small delay to see traffic in Wireshark

    sock.close()
    print(f"\nResults: {successes}/{num_messages} correct, {failures} failures")


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 echo_client.py <host> <port> [messages]")
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    run_client(host, port, n)


if __name__ == "__main__":
    main()
```

```bash
# Terminal 1
python3 echo_server_v2.py 9090

# Terminal 2
python3 echo_client.py localhost 9090 20
```

## Exercises

1. **Stress test.** Run 10 simultaneous clients each sending 1000 messages:
   ```bash
   for i in $(seq 1 10); do python3 echo_client.py localhost 9090 1000 & done
   wait
   ```
   Does the server handle all of them without dropping connections or mixing up responses?

2. **Framing bug.** Modify `echo_client.py` to send a 10,000-byte message without a newline. What happens on the server? How does your buffer accumulate? Add a maximum buffer size (e.g., 64KB) and close the connection with an error if exceeded.

3. **Slow client.** Write a client that sends one byte per second. Confirm the server correctly buffers the stream and only echoes the complete line after the `\n` arrives.

4. **Binary echo.** Extend the server to echo binary data (not just text lines). Use a 4-byte big-endian length prefix followed by the payload. The server reads the 4-byte length, then reads exactly that many bytes, then echoes the same length-prefixed payload back.

5. **Connection limit.** Modify the threaded server to reject connections when more than 10 clients are connected simultaneously. The server should send "Server full\n" before closing the excess connection.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| bind() | "Claim a port" | Associate a socket with a specific local (IP address, port) pair so the OS delivers incoming packets to it |
| listen() | "Start accepting" | Transition the socket to the listening state; the OS will complete TCP handshakes for you and queue them |
| accept() | "Get a connection" | Block until a client connects; return a new socket for that specific connection plus the client's address |
| recv() | "Read data" | Read up to N bytes from the socket; returns b"" when the peer closes the connection |
| sendall() | "Write all data" | Like send() but loops internally until all bytes are written or an error occurs |
| SO_REUSEADDR | "Restart without waiting" | A socket option that allows binding to a port that is still in TIME_WAIT state from a previous socket |
| Stream framing | "Where does one message end?" | The application-level protocol that determines message boundaries, since TCP delivers a continuous byte stream |

# Build a Chat App Over Raw TCP

> No WebSockets, no HTTP, no framework — just TCP sockets, select(), and a message framing protocol you design yourself.

**Type:** Capstone
**Languages:** Python
**Prerequisites:** Phase 3, Lesson 02 — TCP Socket Programming
**Time:** ~90 minutes

## Learning Objectives
- Implement a multi-client TCP chat server using `select()` for I/O multiplexing
- Design and implement a length-prefixed message framing protocol
- Handle partial reads and writes correctly over a stream socket
- Broadcast messages from one client to all others
- Implement a simple client that can send and receive messages concurrently

## Architecture Overview

```
                  ┌─────────────────────────────────────┐
                  │           Chat Server               │
                  │                                     │
  Client A ──────►│  read_socket                        │
  Client B ──────►│  read_socket  → parse frame         │
  Client C ──────►│  read_socket    → broadcast to all  │
                  │                   except sender     │
                  │                                     │
                  │  select() monitors all sockets:     │
                  │  - server socket (new connections)  │
                  │  - each client socket (messages)    │
                  └─────────────────────────────────────┘
```

The server uses `select()` — a system call that waits until one or more sockets have data ready. This is called **I/O multiplexing**: one thread handles many clients without blocking on any single one.

### Why select() and Not Threads?

The naive approach: one thread per client. Threads work, but they have overhead (OS thread = ~8 MB stack), and shared state (the broadcast list) needs locking. With `select()`, everything runs in a single thread. No locks needed. Scales to hundreds of clients easily. The trade-off: you cannot do CPU-intensive work during a select loop without blocking everyone.

### The Framing Problem

TCP is a byte stream, not a message protocol. When you `send(b"hello")` and `send(b"world")`, the receiver might get `b"hello"`, `b"helloworld"`, `b"hel"` + `b"loworld"`, or any other split. There is no concept of message boundaries in TCP.

We need framing: a way to mark where one message ends and the next begins. Two common approaches:
1. **Delimiter-based**: Messages end with `\n`. Simple, but breaks if the message contains `\n`.
2. **Length-prefix**: Each message is preceded by its length. The receiver reads the length first, then reads exactly that many bytes.

We use length-prefix with a 4-byte (unsigned int) header:

```
┌──────────────────────────────────────────────────────┐
│  4 bytes (big-endian uint32) │  N bytes payload      │
│  length of payload N         │  (UTF-8 text)         │
└──────────────────────────────────────────────────────┘
```

### Handling Partial Reads

A `recv(4096)` call might return fewer bytes than requested — especially over loopback, this is rare, but over a real network it is normal. We must read in a loop until we have all the bytes for one complete message:

```python
def recv_exactly(sock, n):
    """Read exactly n bytes from sock, or raise if connection closed."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf
```

## Build It

Save the server as `chat_server.py`:

```python
#!/usr/bin/env python3
"""
Multi-client TCP chat server using select() and length-prefixed framing.

Usage: python3 chat_server.py [port]
       python3 chat_server.py 9000
"""
import sys
import select
import socket
import struct
import logging
import datetime

PORT    = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
HEADER  = 4    # bytes for the length prefix (unsigned int, big-endian)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("chat-server")


# ── Framing helpers ────────────────────────────────────────────────────────────

def encode_message(text: str) -> bytes:
    """Encode a text message with a 4-byte length prefix."""
    payload = text.encode("utf-8")
    header  = struct.pack("!I", len(payload))   # !I = big-endian unsigned 32-bit int
    return header + payload


def recv_exactly(sock: socket.socket, n: int) -> bytes:
    """
    Read exactly n bytes from sock.
    Raises ConnectionError if the connection is closed mid-read.
    """
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("remote end closed connection")
        buf += chunk
    return buf


def recv_message(sock: socket.socket) -> str:
    """
    Read one complete framed message from sock.
    Returns the decoded text string.
    """
    # Step 1: read the 4-byte length header
    header_bytes = recv_exactly(sock, HEADER)
    (length,)    = struct.unpack("!I", header_bytes)

    # Sanity check: reject absurdly large messages (16 MB limit)
    if length > 16 * 1024 * 1024:
        raise ValueError(f"Message length {length} exceeds limit")

    # Step 2: read exactly 'length' bytes of payload
    payload = recv_exactly(sock, length)
    return payload.decode("utf-8")


# ── Client state ───────────────────────────────────────────────────────────────

class Client:
    """Tracks state for one connected client."""
    _id_counter = 0

    def __init__(self, sock: socket.socket, addr: tuple):
        Client._id_counter += 1
        self.id      = Client._id_counter
        self.sock    = sock
        self.addr    = addr
        self.nickname = f"User{self.id}"

    def __str__(self):
        return f"{self.nickname} ({self.addr[0]}:{self.addr[1]})"


# ── Server ─────────────────────────────────────────────────────────────────────

class ChatServer:
    def __init__(self, host: str = "0.0.0.0", port: int = PORT):
        self.host    = host
        self.port    = port
        # Map: socket → Client
        self.clients: dict = {}
        # The server's own listening socket
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((host, port))
        self.server_sock.listen(50)
        self.server_sock.setblocking(False)   # non-blocking for use with select()
        log.info(f"Chat server listening on {host}:{port}")

    def broadcast(self, message: str, exclude_sock: socket.socket = None) -> None:
        """Send a message to all connected clients, optionally excluding one."""
        encoded = encode_message(message)
        dead = []
        for sock, client in self.clients.items():
            if sock is exclude_sock:
                continue
            try:
                # sendall() loops internally until all bytes are written
                sock.sendall(encoded)
            except (BrokenPipeError, ConnectionResetError, OSError):
                dead.append(sock)
        for sock in dead:
            self._disconnect(sock)

    def _accept_new_client(self) -> None:
        client_sock, addr = self.server_sock.accept()
        client_sock.setblocking(False)
        client = Client(client_sock, addr)
        self.clients[client_sock] = client
        log.info(f"Connected: {client}")
        self.broadcast(
            f"*** {client.nickname} has joined the chat ***",
            exclude_sock=client_sock,
        )
        # Send welcome message to new client
        try:
            client_sock.sendall(encode_message(
                f"Welcome to the chat, {client.nickname}! "
                f"({len(self.clients)} users online)"
            ))
        except OSError:
            pass

    def _handle_client_data(self, sock: socket.socket) -> None:
        """Read one message from sock and process it."""
        client = self.clients[sock]
        try:
            # We must temporarily set the socket to blocking for recv_exactly.
            # In production you would use a proper async framework or buffer.
            # For a teaching implementation, blocking recv is acceptable here.
            sock.setblocking(True)
            try:
                raw = recv_message(sock)
            finally:
                sock.setblocking(False)

        except (ConnectionError, struct.error, ValueError, UnicodeDecodeError) as e:
            log.info(f"Disconnected: {client} ({e})")
            self._disconnect(sock)
            return

        # Parse simple commands
        if raw.startswith("/nick "):
            old_nick     = client.nickname
            client.nickname = raw[6:].strip()[:20]   # max 20 chars
            msg = f"*** {old_nick} is now known as {client.nickname} ***"
            log.info(msg)
            self.broadcast(msg)

        elif raw.strip() == "/quit":
            self._disconnect(sock)

        elif raw.strip() == "/users":
            user_list = ", ".join(c.nickname for c in self.clients.values())
            try:
                sock.sendall(encode_message(f"Online: {user_list}"))
            except OSError:
                pass

        else:
            # Regular chat message
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] {client.nickname}: {raw}"
            log.info(formatted)
            self.broadcast(formatted, exclude_sock=sock)

    def _disconnect(self, sock: socket.socket) -> None:
        client = self.clients.pop(sock, None)
        try:
            sock.close()
        except OSError:
            pass
        if client:
            log.info(f"Disconnected: {client}")
            self.broadcast(f"*** {client.nickname} has left the chat ***")

    def run(self) -> None:
        log.info("Server running. Ctrl+C to stop.")
        try:
            while True:
                # select() returns when any socket has data to read
                # watch_list = server socket + all client sockets
                watch_list = [self.server_sock] + list(self.clients.keys())
                readable, _, exceptional = select.select(watch_list, [], watch_list, 1.0)

                for sock in readable:
                    if sock is self.server_sock:
                        self._accept_new_client()
                    else:
                        self._handle_client_data(sock)

                for sock in exceptional:
                    self._disconnect(sock)

        except KeyboardInterrupt:
            log.info("\nShutting down.")
        finally:
            for sock in list(self.clients.keys()):
                self._disconnect(sock)
            self.server_sock.close()


if __name__ == "__main__":
    ChatServer().run()
```

Save the client as `chat_client.py`:

```python
#!/usr/bin/env python3
"""
TCP chat client. Connects to the server and lets you chat.

Usage: python3 chat_client.py [host] [port]
       python3 chat_client.py localhost 9000
"""
import sys
import select
import socket
import struct
import threading

HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
HEADER = 4


def encode_message(text: str) -> bytes:
    payload = text.encode("utf-8")
    return struct.pack("!I", len(payload)) + payload


def recv_exactly(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("server closed connection")
        buf += chunk
    return buf


def recv_loop(sock: socket.socket) -> None:
    """Background thread: receive messages from server and print them."""
    try:
        while True:
            header = recv_exactly(sock, HEADER)
            (length,) = struct.unpack("!I", header)
            payload   = recv_exactly(sock, length)
            print(f"\r{payload.decode('utf-8')}")
            print("> ", end="", flush=True)
    except (ConnectionError, OSError):
        print("\n[Disconnected from server]")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print(f"Cannot connect to {HOST}:{PORT}")
        sys.exit(1)

    print(f"Connected to {HOST}:{PORT}. Type messages and press Enter.")
    print("Commands: /nick <name>  /users  /quit\n")

    # Start background thread for receiving
    recv_thread = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    recv_thread.start()

    # Main thread: read user input and send
    try:
        while True:
            print("> ", end="", flush=True)
            line = input()
            if not line:
                continue
            sock.sendall(encode_message(line))
            if line.strip() == "/quit":
                break
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        sock.close()
        print("\nDisconnected.")


if __name__ == "__main__":
    main()
```

### Running the Chat

```bash
# Terminal 1: Start the server
python3 chat_server.py 9000

# Terminal 2: First client
python3 chat_client.py localhost 9000

# Terminal 3: Second client
python3 chat_client.py localhost 9000

# Now type messages in either client terminal.
# Try: /nick Alice  /users  /quit
```

### Understanding select()

The call `select.select(watch_list, [], watch_list, 1.0)` takes:
- `read_list`: sockets to watch for incoming data
- `write_list`: sockets to watch for write-readiness (empty here — we don't need it)
- `except_list`: sockets to watch for error conditions
- `timeout`: seconds to wait before returning even if nothing is ready (1.0 here)

It returns three lists of sockets that are ready. We iterate `readable` to process incoming data.

```
  select() call
       │
       │  (blocks until something is ready, or 1 second)
       │
       ▼
  [server_sock, client_a_sock, client_c_sock] ← readable sockets
  []                                           ← writable sockets
  []                                           ← exceptional sockets
       │
       ├─ server_sock ready? → accept new connection
       ├─ client_a_sock ready? → read message from A, broadcast
       └─ client_c_sock ready? → read message from C, broadcast
```

## Extension Ideas

1. **Private messages**: Add a `/msg <nick> <text>` command that sends a message only to the named user. Look up the target socket by iterating `self.clients.values()`.

2. **Chat rooms**: Extend the server to support multiple named rooms (`/join #general`, `/join #random`). Broadcasts only go to clients in the same room.

3. **Message history**: When a new client joins, send them the last 20 messages from a deque buffer. This requires storing messages server-side.

4. **TLS encryption**: Wrap the server socket with Python's `ssl` module. Use a self-signed certificate for testing. All traffic between client and server will be encrypted.

5. **Load test**: Write a script that spawns 100 concurrent clients using `asyncio` or threads, each sending a message every 100ms. Measure the server's throughput and check whether any messages are lost or out of order.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| select() | "I/O multiplexing" | System call that blocks until one or more file descriptors are ready for I/O, enabling a single thread to handle multiple connections |
| Framing | "message framing" | A convention that marks message boundaries in a byte stream; required because TCP has no inherent message concept |
| Length prefix | "length-prefixed protocol" | A framing method where each message is preceded by a fixed-size integer stating how many bytes follow |
| sendall() | "guaranteed send" | Python's socket method that loops until all bytes are sent; regular send() may send fewer bytes than requested |
| Non-blocking socket | "async socket" | A socket configured so that recv() and accept() return immediately even if no data is available (raise BlockingIOError) |
| Broadcast | "fan-out" | Sending a single message to all connected clients; requires iterating all client sockets |

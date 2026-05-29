#!/usr/bin/env python3
# Run: python3 tcp_chat_server.py [port]
#
# Multi-client TCP Chat Server using select() for I/O multiplexing.
# No threads — a single select() loop handles all clients.
#
# How to run:
#   python3 tcp_chat_server.py 9000        (server listens on port 9000)
#   python3 tcp_chat_client.py localhost 9000  (connect clients)
#
# Features:
#   - Length-prefixed framing (4-byte big-endian uint32 before each message)
#   - Broadcasts messages from any client to all others: "[client1] hello"
#   - /nick <name>  — change display name
#   - /users        — list connected users
#   - /quit         — disconnect
#   - Server sends join/leave announcements
#
# Requires: Python 3.8+, stdlib only.

import sys
import select
import socket
import struct
import logging
import datetime

PORT   = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
HEADER = 4       # bytes for the message length prefix (unsigned int, big-endian)
MAX_MSG_SIZE = 16 * 1024 * 1024   # 16 MB sanity limit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tcp-chat-server")


# ── Framing helpers ───────────────────────────────────────────────────────────

def encode_msg(text: str) -> bytes:
    """Encode text as length-prefixed frame: [4-byte len][UTF-8 payload]."""
    payload = text.encode("utf-8")
    return struct.pack("!I", len(payload)) + payload


def recv_exactly(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes. Raises ConnectionError on EOF."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def recv_msg(sock: socket.socket) -> str:
    """Read one complete framed message from sock. Returns decoded text."""
    header = recv_exactly(sock, HEADER)
    (length,) = struct.unpack("!I", header)
    if length > MAX_MSG_SIZE:
        raise ValueError(f"message too large: {length} bytes")
    payload = recv_exactly(sock, length)
    return payload.decode("utf-8")


# ── Client state ──────────────────────────────────────────────────────────────

class Client:
    _id_counter = 0

    def __init__(self, sock: socket.socket, addr: tuple):
        Client._id_counter += 1
        self.id       = Client._id_counter
        self.sock     = sock
        self.addr     = addr
        self.nickname = f"client{self.id}"

    def __str__(self):
        return f"{self.nickname} ({self.addr[0]}:{self.addr[1]})"


# ── Chat Server ───────────────────────────────────────────────────────────────

class ChatServer:
    def __init__(self, host: str = "0.0.0.0", port: int = PORT):
        self.host = host
        self.port = port
        # socket → Client mapping
        self.clients: dict = {}
        # Listening socket
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind((host, port))
        self.srv.listen(50)
        self.srv.setblocking(False)
        log.info(f"Chat server listening on {host}:{port}")
        log.info("Connect clients with: python3 tcp_chat_client.py localhost %d", port)

    def broadcast(self, text: str, exclude: socket.socket = None) -> None:
        """Send text to all connected clients except exclude."""
        data = encode_msg(text)
        dead = []
        for sock, client in self.clients.items():
            if sock is exclude:
                continue
            try:
                sock.sendall(data)
            except OSError:
                dead.append(sock)
        for sock in dead:
            self._remove_client(sock)

    def _accept(self) -> None:
        conn, addr = self.srv.accept()
        conn.setblocking(False)
        client = Client(conn, addr)
        self.clients[conn] = client
        log.info(f"+ connected: {client}")
        self.broadcast(f"*** {client.nickname} joined ***", exclude=conn)
        try:
            conn.sendall(encode_msg(
                f"Welcome, {client.nickname}! "
                f"({len(self.clients)} user(s) online)\n"
                f"Commands: /nick <name>  /users  /quit"
            ))
        except OSError:
            pass

    def _handle(self, sock: socket.socket) -> None:
        client = self.clients[sock]
        try:
            # Temporarily blocking for recv_msg (teaching implementation)
            sock.setblocking(True)
            try:
                text = recv_msg(sock)
            finally:
                sock.setblocking(False)
        except (ConnectionError, struct.error, ValueError, UnicodeDecodeError) as e:
            log.info(f"- disconnected: {client} ({e})")
            self._remove_client(sock)
            return

        if text.startswith("/nick "):
            old = client.nickname
            client.nickname = text[6:].strip()[:20]
            msg = f"*** {old} is now {client.nickname} ***"
            log.info(msg)
            self.broadcast(msg)
        elif text.strip() == "/quit":
            self._remove_client(sock)
        elif text.strip() == "/users":
            user_list = ", ".join(c.nickname for c in self.clients.values())
            try:
                sock.sendall(encode_msg(f"Online: {user_list}"))
            except OSError:
                pass
        else:
            ts  = datetime.datetime.now().strftime("%H:%M:%S")
            msg = f"[{client.nickname}] {text}"
            log.info(f"[{ts}] {msg}")
            self.broadcast(msg, exclude=sock)

    def _remove_client(self, sock: socket.socket) -> None:
        client = self.clients.pop(sock, None)
        try:
            sock.close()
        except OSError:
            pass
        if client:
            self.broadcast(f"*** {client.nickname} left ***")

    def run(self) -> None:
        log.info("Server running. Ctrl+C to stop.")
        try:
            while True:
                watch = [self.srv] + list(self.clients.keys())
                readable, _, exceptional = select.select(watch, [], watch, 1.0)
                for sock in readable:
                    if sock is self.srv:
                        self._accept()
                    else:
                        self._handle(sock)
                for sock in exceptional:
                    self._remove_client(sock)
        except KeyboardInterrupt:
            log.info("Shutting down.")
        finally:
            for sock in list(self.clients.keys()):
                self._remove_client(sock)
            self.srv.close()


if __name__ == "__main__":
    ChatServer().run()

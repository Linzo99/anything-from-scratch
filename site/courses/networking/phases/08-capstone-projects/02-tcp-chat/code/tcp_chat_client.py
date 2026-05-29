#!/usr/bin/env python3
# Run: python3 tcp_chat_client.py [host] [port]
#
# TCP Chat Client
# Connects to tcp_chat_server.py and allows chatting.
# Reads from stdin and the server socket simultaneously.
#
# How to run:
#   python3 tcp_chat_server.py 9000        (start server first)
#   python3 tcp_chat_client.py localhost 9000
#   python3 tcp_chat_client.py localhost 9000  (open multiple terminals)
#
# Commands (sent as text to the server):
#   /nick <name>   change your display name
#   /users         list connected users
#   /quit          disconnect
#
# Requires: Python 3.8+, stdlib only.

import sys
import socket
import struct
import threading

HOST   = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT   = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
HEADER = 4


# ── Framing helpers (must match server exactly) ───────────────────────────────

def encode_msg(text: str) -> bytes:
    payload = text.encode("utf-8")
    return struct.pack("!I", len(payload)) + payload


def recv_exactly(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("server closed connection")
        buf += chunk
    return buf


def recv_msg(sock: socket.socket) -> str:
    header = recv_exactly(sock, HEADER)
    (length,) = struct.unpack("!I", header)
    payload = recv_exactly(sock, length)
    return payload.decode("utf-8")


# ── Receive loop (runs in a background thread) ────────────────────────────────

def recv_loop(sock: socket.socket) -> None:
    """Background thread: receive and print messages from the server."""
    try:
        while True:
            msg = recv_msg(sock)
            # Clear the current input line, print message, restore prompt
            sys.stdout.write(f"\r{msg}\n> ")
            sys.stdout.flush()
    except (ConnectionError, OSError):
        sys.stdout.write("\n[disconnected from server]\n")
        sys.stdout.flush()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print(f"Cannot connect to {HOST}:{PORT} — is the server running?")
        sys.exit(1)

    print(f"Connected to {HOST}:{PORT}")
    print("Type messages and press Enter to send.")
    print("Commands: /nick <name>  /users  /quit\n")

    # Start background receive thread
    t = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    t.start()

    # Main thread: read stdin and send
    try:
        while True:
            sys.stdout.write("> ")
            sys.stdout.flush()
            try:
                line = input()
            except EOFError:
                break
            if not line.strip():
                continue
            try:
                sock.sendall(encode_msg(line))
            except OSError:
                print("[send error — disconnected]")
                break
            if line.strip() == "/quit":
                break
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("\nDisconnected.")


if __name__ == "__main__":
    main()

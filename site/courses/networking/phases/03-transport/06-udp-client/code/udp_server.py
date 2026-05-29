# Run: python3 udp_server.py
"""
udp_server.py — UDP echo server.

Echoes every datagram back to the sender unchanged.  No connection setup,
no teardown — each recvfrom/sendto is independent.

Usage:
    python3 udp_server.py [port]   (default: 9000)
"""

import socket
import sys

HOST    = "127.0.0.1"
PORT    = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
BUFSIZE = 1024

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # SOCK_DGRAM = UDP
sock.bind((HOST, PORT))

print(f"UDP echo server listening on {HOST}:{PORT}")
print("Press Ctrl-C to stop\n")

try:
    while True:
        data, addr = sock.recvfrom(BUFSIZE)   # blocks until a datagram arrives
        sock.sendto(data, addr)               # echo back unchanged
        print(f"  echoed {len(data)} bytes to {addr[0]}:{addr[1]}")
except KeyboardInterrupt:
    print("\nServer stopped.")
finally:
    sock.close()

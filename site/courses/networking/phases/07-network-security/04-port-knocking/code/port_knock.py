# Run: python3 port_knock.py server   (in one terminal, as root)
#      python3 port_knock.py client   (in another terminal)
"""
Port Knocking — Server and Client
Implements a port-knocking daemon (server) and client in pure Python.

The server listens for TCP connection attempts on knock ports [7000, 8000, 9000].
When the full sequence arrives from one IP within the timeout window, it prints
"PORT UNLOCKED" (simulating opening port 22).

The client sends the knock sequence, then attempts a connection on the open port.

Usage:
  Terminal 1: python3 port_knock.py server
  Terminal 2: python3 port_knock.py client [--host HOST]

No external dependencies — stdlib only.
Note: This demo uses bind() on the knock ports to simulate the server seeing
the connection attempts. A real production knockd uses pcap to capture SYNs
before the firewall drops them.
"""

import sys
import socket
import time
import threading
import argparse
from collections import defaultdict

# ── Configuration ─────────────────────────────────────────────────────────────
KNOCK_SEQUENCE = [7000, 8000, 9000]
KNOCK_WINDOW   = 10.0    # all knocks must arrive within this many seconds
OPEN_PORT      = 2200    # port to "unlock" (using 2200 instead of 22 to avoid root)
OPEN_DURATION  = 30.0    # seconds to keep the port "open"
SERVER_HOST    = "127.0.0.1"


# ─────────────────────────────────────────────────────────────────────────────
# SERVER
# ─────────────────────────────────────────────────────────────────────────────

class KnockState:
    def __init__(self):
        self.progress:    int   = 0
        self.first_knock: float = 0.0


class PortKnockServer:
    """
    Listens on each knock port using a non-blocking socket.
    Tracks knock sequences per source IP.
    When the full sequence is seen, prints "PORT UNLOCKED" and opens the
    service port (a simple echo socket).
    """

    def __init__(self, host: str = SERVER_HOST):
        self.host        = host
        self.states:     dict = defaultdict(KnockState)
        self.open_socks: dict = {}   # port -> socket
        self._lock       = threading.Lock()
        self._running    = True

    def _start_listener(self, port: int) -> None:
        """Start a TCP listener on a knock port. Accept and immediately close."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, port))
        srv.listen(10)
        srv.settimeout(1.0)
        print(f"[server] Listening on knock port {port}")

        while self._running:
            try:
                conn, addr = srv.accept()
                conn.close()   # immediately close — we just want to see the SYN
                src_ip = addr[0]
                print(f"[server] Knock from {src_ip} on port {port}")
                self._handle_knock(src_ip, port)
            except socket.timeout:
                continue
            except OSError:
                break
        srv.close()

    def _handle_knock(self, src_ip: str, port: int) -> None:
        with self._lock:
            state    = self.states[src_ip]
            now      = time.time()
            expected = KNOCK_SEQUENCE[state.progress]

            if port == expected:
                if state.progress == 0:
                    state.first_knock = now
                else:
                    if now - state.first_knock > KNOCK_WINDOW:
                        print(f"[server] {src_ip}: knock window expired, resetting")
                        state.progress   = 0
                        state.first_knock = now
                        return

                state.progress += 1
                print(f"[server] {src_ip}: knock {state.progress}/{len(KNOCK_SEQUENCE)} ✓ (port {port})")

                if state.progress == len(KNOCK_SEQUENCE):
                    state.progress = 0
                    # Launch unlock in a separate thread (avoid holding lock)
                    threading.Thread(
                        target=self._unlock_port,
                        args=(src_ip,),
                        daemon=True,
                    ).start()
            else:
                if state.progress > 0:
                    print(f"[server] {src_ip}: wrong port {port} (expected {expected}), sequence continues")

    def _unlock_port(self, src_ip: str) -> None:
        print(f"\n[server] *** PORT UNLOCKED for {src_ip} ***")
        print(f"[server] Opening port {OPEN_PORT} for {OPEN_DURATION:.0f}s\n")

        # Open a simple service socket on OPEN_PORT
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind((self.host, OPEN_PORT))
        except OSError as e:
            print(f"[server] Could not open port {OPEN_PORT}: {e}")
            return
        srv.listen(5)
        srv.settimeout(1.0)

        deadline = time.time() + OPEN_DURATION
        while time.time() < deadline:
            try:
                conn, addr = srv.accept()
                # Echo service — respond to any client
                try:
                    conn.sendall(f"[PORT {OPEN_PORT}] Access granted for {src_ip}. "
                                 f"Port closes in {int(deadline - time.time())}s\n".encode())
                    data = conn.recv(1024)
                    if data:
                        conn.sendall(b"Echo: " + data)
                except OSError:
                    pass
                finally:
                    conn.close()
            except socket.timeout:
                continue

        srv.close()
        print(f"\n[server] *** PORT {OPEN_PORT} LOCKED — timer expired for {src_ip} ***\n")

    def run(self) -> None:
        print(f"[server] Port Knock Daemon")
        print(f"[server] Sequence : {KNOCK_SEQUENCE}")
        print(f"[server] Window   : {KNOCK_WINDOW}s")
        print(f"[server] Unlocks  : port {OPEN_PORT} for {OPEN_DURATION:.0f}s")
        print(f"[server] Host     : {self.host}")
        print(f"[server] Press Ctrl+C to stop\n")

        threads = []
        for port in KNOCK_SEQUENCE:
            t = threading.Thread(target=self._start_listener, args=(port,), daemon=True)
            t.start()
            threads.append(t)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[server] Stopping...")
            self._running = False
        for t in threads:
            t.join(timeout=2)


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def knock_client(host: str = SERVER_HOST) -> None:
    print(f"[client] Port Knock Client")
    print(f"[client] Target  : {host}")
    print(f"[client] Sequence: {KNOCK_SEQUENCE}")
    print(f"[client] Sending knock sequence...\n")

    for port in KNOCK_SEQUENCE:
        print(f"[client] Knocking port {port}...", end=" ", flush=True)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect((host, port))
            sock.close()
        except (ConnectionRefusedError, socket.timeout, OSError):
            # Connection refused or timeout is expected — the port is "closed"
            # We just need the SYN to reach the server
            pass
        print("sent")
        time.sleep(0.3)  # small gap between knocks

    print(f"\n[client] Knock sequence complete.")
    print(f"[client] Waiting 2s for server to open port {OPEN_PORT}...")
    time.sleep(2)

    # Attempt connection to the unlocked port
    print(f"[client] Connecting to {host}:{OPEN_PORT}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, OPEN_PORT))
        banner = sock.recv(256).decode()
        print(f"[client] Connected! Server says: {banner.strip()}")
        sock.sendall(b"hello from client\n")
        reply = sock.recv(256).decode()
        print(f"[client] Echo reply: {reply.strip()}")
        sock.close()
        print(f"\n[client] SUCCESS: Port {OPEN_PORT} was unlocked by knock sequence")
    except (ConnectionRefusedError, socket.timeout) as e:
        print(f"[client] FAILED to connect to port {OPEN_PORT}: {e}")
        print("[client] Make sure the server is running in another terminal")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Port knocking server and client demo"
    )
    parser.add_argument(
        "mode",
        choices=["server", "client"],
        help="Run as 'server' (daemon) or 'client' (send knock + connect)"
    )
    parser.add_argument(
        "--host",
        default=SERVER_HOST,
        help=f"Server host (default: {SERVER_HOST})"
    )
    args = parser.parse_args()

    if args.mode == "server":
        PortKnockServer(host=args.host).run()
    else:
        knock_client(host=args.host)


if __name__ == "__main__":
    main()

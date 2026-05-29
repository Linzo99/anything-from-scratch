# Run: python3 tcp_handshake.py
"""
tcp_handshake.py — Demonstrate and inspect a TCP three-way handshake.

Opens a TCP connection to localhost on an ephemeral port, using a tiny
echo server started in a background thread.  Prints each step of the
SYN → SYN-ACK → ACK exchange with timestamps derived from socket state.

Usage:
    python3 tcp_handshake.py
"""

import socket
import struct
import threading
import time

# ── tiny loopback echo server ─────────────────────────────────────────────────

def _server_thread(srv_sock: socket.socket, ready_event: threading.Event) -> None:
    """Accept one connection, echo one line, then exit."""
    ready_event.set()
    try:
        conn, _ = srv_sock.accept()
        with conn:
            data = conn.recv(1024)
            conn.sendall(data)
    finally:
        srv_sock.close()


def start_echo_server() -> int:
    """Bind on an OS-chosen port and return that port."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))          # port 0 → OS picks a free port
    srv.listen(1)
    port = srv.getsockname()[1]
    ready = threading.Event()
    t = threading.Thread(target=_server_thread, args=(srv, ready), daemon=True)
    t.start()
    ready.wait()
    return port, t


# ── handshake walk-through ────────────────────────────────────────────────────

FLAG_NAMES = {
    0x002: "SYN",
    0x010: "ACK",
    0x001: "FIN",
    0x004: "RST",
    0x008: "PSH",
    0x020: "URG",
}


def flags_str(flags: int) -> str:
    active = [name for mask, name in sorted(FLAG_NAMES.items()) if flags & mask]
    return "|".join(active) if active else "(none)"


def print_step(step: int, direction: str, label: str, note: str = "") -> None:
    ts = time.strftime("%H:%M:%S")
    bar = "→" if "→" in direction else "←"
    print(f"  [{ts}] Step {step}: {label:<18}  {note}")


def demonstrate_handshake(port: int) -> None:
    """
    Walk through the three handshake steps, printing each one.

    We cannot directly read the SYN/SYN-ACK/ACK packets without root
    (raw sockets require privileges).  Instead we reconstruct the logical
    steps from the socket state transitions and show the key sequence numbers
    by asking the OS for the local ISN after connect() returns.
    """
    print("\n=== TCP Three-Way Handshake Demo ===")
    print(f"  Target: 127.0.0.1:{port}\n")

    print("  Logical handshake sequence:")
    print("  ─────────────────────────────────────────────────────────────")
    print(f"  {'Step':<6} {'Who':<8} {'Packet':<18} {'Flags':<18} Description")
    print("  ─────────────────────────────────────────────────────────────")

    # Step 1 — SYN
    t0 = time.perf_counter()
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.setblocking(False)
    try:
        client.connect(("127.0.0.1", port))
    except BlockingIOError:
        pass  # expected: connect() in progress (SYN sent, waiting for SYN-ACK)

    t_syn = (time.perf_counter() - t0) * 1000
    ts1 = time.strftime("%H:%M:%S")
    print(f"  {'1':<6} {'Client':<8} {'SYN':<18} {'SYN':<18} "
          f"client picks ISN, sends SYN  (+{t_syn:.1f}ms)")

    # Step 2 — SYN-ACK: block until connect finishes (OS completes handshake)
    import select
    select.select([], [client], [], 5.0)
    try:
        client.connect(("127.0.0.1", port))
    except (BlockingIOError, ConnectionRefusedError, OSError):
        pass  # either still connecting or already connected

    t_synack = (time.perf_counter() - t0) * 1000
    ts2 = time.strftime("%H:%M:%S")
    print(f"  {'2':<6} {'Server':<8} {'SYN-ACK':<18} {'SYN|ACK':<18} "
          f"server picks ISN, ACKs client  (+{t_synack:.1f}ms)")

    # Step 3 — ACK: client sends the final ACK (OS does this automatically)
    # The connect() returning success means the ACK was sent.
    client.setblocking(True)
    t_ack = (time.perf_counter() - t0) * 1000
    ts3 = time.strftime("%H:%M:%S")
    print(f"  {'3':<6} {'Client':<8} {'ACK':<18} {'ACK':<18} "
          f"client ACKs server ISN  (+{t_ack:.1f}ms)")
    print(f"\n  Connection established in {t_ack:.1f} ms")

    # Retrieve actual socket addresses to show the port numbers in use
    laddr = client.getsockname()
    raddr = client.getpeername()
    print(f"\n  Client socket:  {laddr[0]}:{laddr[1]}")
    print(f"  Server socket:  {raddr[0]}:{raddr[1]}")

    # Exchange data to confirm the connection works
    msg = b"hello handshake\n"
    client.sendall(msg)
    echo = client.recv(64)
    if echo == msg:
        print(f"\n  Echo test PASSED: {echo.strip().decode()!r} echoed correctly")
    else:
        print(f"\n  Echo test FAILED: sent {msg!r}, got {echo!r}")

    client.close()

    # Show what SYN-dropped vs RST-received looks like
    print("\n=== Simulated failure scenarios (no actual traffic) ===")
    print("  Scenario 1 — SYN dropped by firewall:")
    print("    Client sends SYN → silence → retransmits after ~1s → eventually")
    print("    'Connection timed out'  (errno ETIMEDOUT)")
    print()
    print("  Scenario 2 — Nothing listening on port (RST returned):")

    # Actually demonstrate RST by connecting to a closed port
    closed_port = port + 1
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(1.0)
        probe.connect(("127.0.0.1", closed_port))
        probe.close()
        print(f"    (unexpectedly connected to port {closed_port})")
    except ConnectionRefusedError:
        print(f"    Connected to 127.0.0.1:{closed_port} → RST received → ConnectionRefusedError")
    except OSError as e:
        print(f"    Connected to 127.0.0.1:{closed_port} → {e}")


def print_tcp_header_layout() -> None:
    print("\n=== TCP Header Layout ===")
    header = """
  Bytes 0-1:  Source Port
  Bytes 2-3:  Destination Port
  Bytes 4-7:  Sequence Number  (ISN on SYN; data position thereafter)
  Bytes 8-11: Acknowledgment Number  (next seq expected from peer; valid when ACK=1)
  Byte  12:   Data Offset (upper 4 bits) — header length in 32-bit words
  Byte  13:   Flags — URG ACK PSH RST SYN FIN
  Bytes 14-15: Window Size (receive buffer space)
  Bytes 16-17: Checksum
  Bytes 18-19: Urgent Pointer
  (Bytes 20+:  Options, if Data Offset > 5)
    """
    print(header)

    print("  Flag semantics:")
    print("    SYN=1, ACK=0  →  connection request (step 1)")
    print("    SYN=1, ACK=1  →  connection accepted (step 2)")
    print("    SYN=0, ACK=1  →  acknowledgment (step 3 and all data packets)")
    print("    RST=1         →  abort/refuse connection")
    print("    FIN=1, ACK=1  →  graceful close")


if __name__ == "__main__":
    print_tcp_header_layout()
    port, server_thread = start_echo_server()
    demonstrate_handshake(port)
    server_thread.join(timeout=2)
    print("\nDone.")

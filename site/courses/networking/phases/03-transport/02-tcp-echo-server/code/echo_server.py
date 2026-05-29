# Run: python3 echo_server.py
"""
echo_server.py — minimal TCP echo server, port 9999.

Listens on port 9999.  When a client connects and sends a line of text,
echoes it back prefixed with "[ECHO] ".  Handles one client at a time.

Usage:
    python3 echo_server.py [port]

Test with:
    # In another terminal:
    python3 echo_client.py localhost 9999
    # Or interactively:
    nc localhost 9999
"""

import socket
import sys


def handle_client(conn: socket.socket, addr: tuple) -> None:
    """
    Read newline-terminated lines from the client and echo each one back
    prefixed with '[ECHO] '.

    TCP is a byte stream, not a message protocol — we must buffer incoming
    bytes and look for the newline delimiter ourselves.
    """
    print(f"[+] Client connected: {addr[0]}:{addr[1]}")
    buf = b""

    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                # Empty bytes → client sent FIN (closed connection)
                break

            buf += chunk

            # Process all complete lines accumulated in the buffer
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.rstrip(b"\r")   # strip Windows CRLF if present

                if not line:
                    continue                 # skip blank lines

                text = line.decode("utf-8", errors="replace")
                print(f"  recv: {text!r}")

                response = f"[ECHO] {text}\n".encode("utf-8")
                conn.sendall(response)

    except OSError as exc:
        print(f"[!] Connection error: {exc}")
    finally:
        conn.close()
        print(f"[-] Client disconnected: {addr[0]}:{addr[1]}")


def run_server(host: str = "0.0.0.0", port: int = 9999) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(5)
    print(f"Echo server listening on {host}:{port}")
    print("Press Ctrl-C to stop\n")

    try:
        while True:
            conn, addr = srv.accept()
            try:
                handle_client(conn, addr)
            except Exception as exc:
                print(f"[!] Unhandled error: {exc}")
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        srv.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    run_server(port=port)

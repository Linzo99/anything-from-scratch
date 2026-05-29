# Run: python3 echo_client.py localhost 9999
"""
echo_client.py — test client for the TCP echo server.

Connects to the echo server, sends N messages, and verifies that each
one comes back prefixed with '[ECHO] '.

Usage:
    python3 echo_client.py <host> <port> [num_messages]
    python3 echo_client.py localhost 9999
    python3 echo_client.py localhost 9999 20
"""

import socket
import sys
import time


def run_client(host: str, port: int, num_messages: int = 10) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)

    print(f"Connecting to {host}:{port} …")
    sock.connect((host, port))
    print(f"Connected.  Sending {num_messages} messages.\n")

    # Use makefile() for convenient line-by-line reading.
    # This correctly handles the case where recv() delivers partial lines.
    sock_file = sock.makefile("rb")

    ok = 0
    fail = 0

    for i in range(num_messages):
        message = f"message {i:03d}: hello from echo_client"
        sock.sendall((message + "\n").encode("utf-8"))

        response_bytes = sock_file.readline()
        response = response_bytes.rstrip(b"\r\n").decode("utf-8")
        expected = f"[ECHO] {message}"

        if response == expected:
            ok += 1
            print(f"  [{i:03d}] OK      recv: {response!r}")
        else:
            fail += 1
            print(f"  [{i:03d}] FAIL    sent: {message!r}")
            print(f"             recv: {response!r}")
            print(f"             want: {expected!r}")

        time.sleep(0.02)   # small delay so output is readable

    sock.close()
    print(f"\nResult: {ok}/{num_messages} correct, {fail} failed")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python3 echo_client.py <host> <port> [messages]")
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    run_client(host, port, n)


if __name__ == "__main__":
    main()

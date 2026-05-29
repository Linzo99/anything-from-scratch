# Run: python3 port_scanner.py
"""
TCP Port Scanner
A Python implementation of a basic TCP port scanner using socket.connect_ex()
(simulates a connect scan, similar to nmap -sT).

Scans a range of ports on a target host, reports open/closed/filtered,
and measures total scan time.

Stdlib only — no external dependencies.

Usage:
  python3 port_scanner.py [host] [start_port] [end_port] [--timeout SECS] [--threads N]
  python3 port_scanner.py localhost 1 1024
  python3 port_scanner.py 127.0.0.1 20 100 --timeout 0.5 --threads 50

Note: This is a connect scan (full TCP handshake). Unlike a SYN scan,
it completes the handshake and is therefore visible in server logs.
SYN scans require raw sockets (root) and are not implemented here.
"""

import sys
import socket
import time
import argparse
import threading
from queue import Queue

# ── Well-known port names ─────────────────────────────────────────────────────
WELL_KNOWN = {
    20:  "ftp-data",   21: "ftp",      22: "ssh",       23: "telnet",
    25:  "smtp",       53: "dns",      80: "http",      110: "pop3",
    111: "rpc",       143: "imap",    443: "https",    445: "smb",
    465: "smtps",     587: "smtp",    993: "imaps",    995: "pop3s",
   1433: "mssql",    3306: "mysql",  3389: "rdp",     5432: "postgres",
   5900: "vnc",      6379: "redis",  8080: "http-alt",8443: "https-alt",
   9200: "elastic", 27017: "mongo",
}


def resolve_host(host: str) -> str:
    """Resolve hostname to IP. Exit with error if resolution fails."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror as e:
        print(f"Error: Cannot resolve host '{host}': {e}")
        sys.exit(1)


def scan_port(host: str, port: int, timeout: float) -> str:
    """
    Attempt a TCP connection to host:port.

    Returns one of:
      "open"     — connection succeeded (service is listening)
      "closed"   — connection refused (RST received — port is closed)
      "filtered" — timeout (firewall is silently dropping packets)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    result = sock.connect_ex((host, port))
    sock.close()

    if result == 0:
        return "open"
    elif result in (111, 61):   # ECONNREFUSED (Linux=111, macOS=61)
        return "closed"
    else:
        return "filtered"


def worker(host: str, timeout: float, port_queue: Queue, results: list,
           results_lock: threading.Lock) -> None:
    """Thread worker: pull ports from the queue and scan them."""
    while True:
        try:
            port = port_queue.get_nowait()
        except Exception:
            break
        state = scan_port(host, port, timeout)
        with results_lock:
            results.append((port, state))
        port_queue.task_done()


def run_scan(host: str, start: int, end: int, timeout: float,
             num_threads: int, show_closed: bool = False) -> list:
    """
    Scan ports start..end on host using num_threads concurrent threads.
    Returns list of (port, state) tuples for open ports.
    """
    print(f"\nScanning {host}  ports {start}–{end}")
    print(f"Timeout: {timeout}s per port   Threads: {num_threads}")
    print(f"Scan type: TCP connect scan (socket.connect_ex)\n")

    port_queue    = Queue()
    results       = []
    results_lock  = threading.Lock()
    t_start       = time.time()

    for port in range(start, end + 1):
        port_queue.put(port)

    threads = []
    for _ in range(min(num_threads, end - start + 1)):
        t = threading.Thread(
            target=worker,
            args=(host, timeout, port_queue, results, results_lock),
            daemon=True,
        )
        t.start()
        threads.append(t)

    port_queue.join()
    t_elapsed = time.time() - t_start

    # Sort results by port number
    results.sort(key=lambda x: x[0])

    # Print results
    open_ports = [(p, s) for p, s in results if s == "open"]
    filtered   = [(p, s) for p, s in results if s == "filtered"]

    print(f"{'PORT':<10} {'STATE':<12} {'SERVICE'}")
    print(f"{'-'*10} {'-'*12} {'-'*20}")

    if open_ports:
        for port, state in open_ports:
            service = WELL_KNOWN.get(port, "unknown")
            print(f"{port:<10} {'open':<12} {service}")
    else:
        print("  (no open ports found in range)")

    if show_closed:
        for port, state in results:
            if state == "closed":
                service = WELL_KNOWN.get(port, "")
                print(f"{port:<10} {'closed':<12} {service}")

    if filtered:
        print(f"\n  {len(filtered)} port(s) filtered (no response within {timeout}s timeout)")

    total_ports = end - start + 1
    print(f"\nScan complete: {total_ports} ports scanned in {t_elapsed:.2f}s")
    print(f"  Open: {len(open_ports)}   Closed: {len(results) - len(open_ports) - len(filtered)}   Filtered: {len(filtered)}")

    return open_ports


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TCP port scanner using socket.connect_ex()"
    )
    parser.add_argument("host",        nargs="?", default="127.0.0.1",
                        help="Target host (default: 127.0.0.1)")
    parser.add_argument("start_port",  nargs="?", type=int, default=1,
                        help="First port to scan (default: 1)")
    parser.add_argument("end_port",    nargs="?", type=int, default=1024,
                        help="Last port to scan (default: 1024)")
    parser.add_argument("--timeout",   type=float, default=0.5,
                        help="Connection timeout per port in seconds (default: 0.5)")
    parser.add_argument("--threads",   type=int, default=100,
                        help="Number of concurrent scan threads (default: 100)")
    parser.add_argument("--show-closed", action="store_true",
                        help="Also print closed ports")
    args = parser.parse_args()

    if args.start_port < 1 or args.end_port > 65535 or args.start_port > args.end_port:
        print("Error: port range must be 1–65535 with start <= end")
        sys.exit(1)

    host_ip = resolve_host(args.host)
    if host_ip != args.host:
        print(f"Resolved {args.host} → {host_ip}")

    run_scan(
        host        = host_ip,
        start       = args.start_port,
        end         = args.end_port,
        timeout     = args.timeout,
        num_threads = args.threads,
        show_closed = args.show_closed,
    )


if __name__ == "__main__":
    main()

# Run: sudo python3 packet_analyzer.py
"""
Packet Analyzer — Raw Socket Capture
Captures packets on the loopback interface using raw sockets.
Parses Ethernet (simulated) + IP + TCP/UDP/ICMP headers.
Prints a tcpdump-like one-line summary for each packet.
Runs until Ctrl+C.

Requires: Python 3.8+, root/sudo (for raw socket access)
Stdlib only — no external dependencies.

Usage:
  sudo python3 packet_analyzer.py [interface]
  sudo python3 packet_analyzer.py lo
  sudo python3 packet_analyzer.py eth0

Note: On Linux, raw sockets at the IP level (AF_INET/SOCK_RAW) require
IPPROTO_RAW or IPPROTO_TCP/UDP/ICMP depending on the approach.
We use AF_PACKET/SOCK_RAW to capture at Layer 2 (Ethernet frame level),
which gives access to all protocols including ICMP.
"""

import sys
import socket
import struct
import time
import signal
import os

# ── Constants ─────────────────────────────────────────────────────────────────
ETH_P_ALL  = 0x0003   # Capture all EtherTypes (Linux AF_PACKET)
ETH_P_IP   = 0x0800   # IPv4
IP_PROTO_ICMP = 1
IP_PROTO_TCP  = 6
IP_PROTO_UDP  = 17

# Well-known port names
PORT_NAMES = {
    20: "ftp-data", 21: "ftp",   22: "ssh",    23: "telnet",
    25: "smtp",     53: "dns",   80: "http",   110: "pop3",
    143: "imap",   443: "https", 445: "smb",  3306: "mysql",
    3389: "rdp",  5432: "pg",   8080: "http*", 8443: "https*",
}

# ICMP type names
ICMP_TYPES = {
    0: "echo-reply", 3: "dest-unreach", 8: "echo-request",
    11: "time-exceeded", 12: "param-problem",
}


# ── Packet counter ────────────────────────────────────────────────────────────
pkt_count   = 0
start_time  = time.time()


# ── Header parsers ────────────────────────────────────────────────────────────

def parse_ethernet(raw: bytes) -> tuple:
    """
    Parse a 14-byte Ethernet header.
    Returns (dst_mac, src_mac, ethertype, payload).
    """
    if len(raw) < 14:
        return None
    dst = ":".join(f"{b:02x}" for b in raw[:6])
    src = ":".join(f"{b:02x}" for b in raw[6:12])
    ethertype = struct.unpack("!H", raw[12:14])[0]
    payload   = raw[14:]
    return dst, src, ethertype, payload


def parse_ip(raw: bytes) -> tuple:
    """
    Parse an IPv4 header (20+ bytes).
    Returns (src_ip, dst_ip, proto, ttl, payload) or None.
    """
    if len(raw) < 20:
        return None
    ihl    = (raw[0] & 0x0F) * 4   # header length in bytes
    ttl    = raw[8]
    proto  = raw[9]
    src_ip = socket.inet_ntoa(raw[12:16])
    dst_ip = socket.inet_ntoa(raw[16:20])
    payload = raw[ihl:]
    return src_ip, dst_ip, proto, ttl, payload


def parse_tcp(raw: bytes) -> tuple:
    """
    Parse a TCP header (20+ bytes).
    Returns (src_port, dst_port, seq, ack, flags_str, payload) or None.
    """
    if len(raw) < 20:
        return None
    src_port, dst_port, seq, ack = struct.unpack("!HHLL", raw[:12])
    data_offset = (raw[12] >> 4) * 4
    flags_byte  = raw[13]
    flags = []
    if flags_byte & 0x02: flags.append("SYN")
    if flags_byte & 0x10: flags.append("ACK")
    if flags_byte & 0x01: flags.append("FIN")
    if flags_byte & 0x04: flags.append("RST")
    if flags_byte & 0x08: flags.append("PSH")
    if flags_byte & 0x20: flags.append("URG")
    flags_str = "|".join(flags) or "NONE"
    payload   = raw[data_offset:]
    return src_port, dst_port, seq, ack, flags_str, payload


def parse_udp(raw: bytes) -> tuple:
    """
    Parse a UDP header (8 bytes).
    Returns (src_port, dst_port, length, payload) or None.
    """
    if len(raw) < 8:
        return None
    src_port, dst_port, length, checksum = struct.unpack("!HHHH", raw[:8])
    payload = raw[8:]
    return src_port, dst_port, length, payload


def parse_icmp(raw: bytes) -> tuple:
    """
    Parse an ICMP header (8 bytes).
    Returns (type, code, checksum, id, seq) or None.
    """
    if len(raw) < 8:
        return None
    icmp_type, icmp_code, checksum = struct.unpack("!BBH", raw[:4])
    id_, seq = struct.unpack("!HH", raw[4:8])
    return icmp_type, icmp_code, checksum, id_, seq


# ── Summary line formatter ────────────────────────────────────────────────────

def port_label(port: int) -> str:
    name = PORT_NAMES.get(port, "")
    return f"{port}({name})" if name else str(port)


def format_tcp_line(ts: str, src_ip: str, dst_ip: str, ttl: int, payload: bytes) -> str:
    result = parse_tcp(payload)
    if not result:
        return f"{ts} IP {src_ip} > {dst_ip}: TCP (parse error)"
    src_port, dst_port, seq, ack, flags, tcp_payload = result
    data_len = len(tcp_payload)
    return (
        f"{ts} IP {src_ip}:{port_label(src_port)} > "
        f"{dst_ip}:{port_label(dst_port)}  "
        f"TCP [{flags}] seq={seq} ack={ack} "
        f"len={data_len} ttl={ttl}"
    )


def format_udp_line(ts: str, src_ip: str, dst_ip: str, ttl: int, payload: bytes) -> str:
    result = parse_udp(payload)
    if not result:
        return f"{ts} IP {src_ip} > {dst_ip}: UDP (parse error)"
    src_port, dst_port, length, udp_payload = result
    return (
        f"{ts} IP {src_ip}:{port_label(src_port)} > "
        f"{dst_ip}:{port_label(dst_port)}  "
        f"UDP len={length} ttl={ttl}"
    )


def format_icmp_line(ts: str, src_ip: str, dst_ip: str, ttl: int, payload: bytes) -> str:
    result = parse_icmp(payload)
    if not result:
        return f"{ts} IP {src_ip} > {dst_ip}: ICMP (parse error)"
    icmp_type, icmp_code, _, id_, seq = result
    type_name = ICMP_TYPES.get(icmp_type, f"type={icmp_type}")
    return (
        f"{ts} IP {src_ip} > {dst_ip}  "
        f"ICMP {type_name} code={icmp_code} id={id_} seq={seq} ttl={ttl}"
    )


def process_packet(raw: bytes) -> None:
    global pkt_count
    pkt_count += 1

    ts = time.strftime("%H:%M:%S")

    # Parse Ethernet frame
    eth = parse_ethernet(raw)
    if not eth:
        return
    dst_mac, src_mac, ethertype, ip_payload = eth

    # Only handle IPv4
    if ethertype != ETH_P_IP:
        return

    # Parse IP header
    ip = parse_ip(ip_payload)
    if not ip:
        return
    src_ip, dst_ip, proto, ttl, transport_payload = ip

    # Format protocol-specific summary
    if proto == IP_PROTO_TCP:
        line = format_tcp_line(ts, src_ip, dst_ip, ttl, transport_payload)
    elif proto == IP_PROTO_UDP:
        line = format_udp_line(ts, src_ip, dst_ip, ttl, transport_payload)
    elif proto == IP_PROTO_ICMP:
        line = format_icmp_line(ts, src_ip, dst_ip, ttl, transport_payload)
    else:
        line = f"{ts} IP {src_ip} > {dst_ip}: proto={proto} ttl={ttl}"

    print(f"  [{pkt_count:>6}] {line}")


# ── Signal handler ────────────────────────────────────────────────────────────

def handle_sigint(sig, frame):
    elapsed = time.time() - start_time
    print(f"\n\nCapture stopped.")
    print(f"  Packets captured : {pkt_count}")
    print(f"  Duration         : {elapsed:.1f}s")
    print(f"  Avg packet rate  : {pkt_count / max(elapsed, 0.001):.1f} pkt/s")
    sys.exit(0)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if os.geteuid() != 0:
        print("Error: Raw socket capture requires root privileges.")
        print("Run with: sudo python3 packet_analyzer.py")
        sys.exit(1)

    interface = sys.argv[1] if len(sys.argv) > 1 else None

    # Create raw socket at Layer 2 (Ethernet)
    # AF_PACKET captures all frames including loopback
    try:
        raw_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                 socket.htons(ETH_P_ALL))
    except AttributeError:
        # AF_PACKET is Linux-only
        print("Error: AF_PACKET is only available on Linux.")
        print("On macOS, use: sudo tcpdump -i lo0 -n")
        sys.exit(1)
    except PermissionError:
        print("Error: Permission denied. Run with sudo.")
        sys.exit(1)

    if interface:
        try:
            raw_sock.bind((interface, ETH_P_ALL))
            print(f"Capturing on interface: {interface}")
        except OSError as e:
            print(f"Error binding to interface '{interface}': {e}")
            sys.exit(1)
    else:
        print("Capturing on all interfaces")

    signal.signal(signal.SIGINT, handle_sigint)

    print(f"Packet Analyzer — running (Ctrl+C to stop)")
    print(f"{'─'*80}")
    print(f"  {'#':>6}  Timestamp  Summary")
    print(f"{'─'*80}")

    while True:
        try:
            raw, _ = raw_sock.recvfrom(65536)
            process_packet(raw)
        except KeyboardInterrupt:
            handle_sigint(None, None)
        except OSError as e:
            print(f"Socket error: {e}")
            break

    raw_sock.close()


if __name__ == "__main__":
    main()

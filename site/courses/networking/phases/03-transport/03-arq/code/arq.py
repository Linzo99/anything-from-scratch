# Run: python3 arq.py simulate
"""
arq.py — Stop-and-Wait ARQ simulation over a lossy channel.

Simulates the alternating-bit protocol in a single process.  A "channel"
function randomly drops packets to model loss.  Shows sequence numbers,
ACKs, retransmissions, and timeouts.

Usage:
    python3 arq.py simulate [loss_rate]   # default loss 20%
    python3 arq.py simulate 0.0           # perfect channel
    python3 arq.py simulate 0.3           # 30% loss

To run the real two-process UDP version:
    Terminal 1:  python3 arq.py receiver 9000
    Terminal 2:  python3 arq.py sender localhost 9000 0.3
"""

import random
import struct
import sys
import time
import socket
import collections

# ── protocol constants ────────────────────────────────────────────────────────

TYPE_DATA = 0
TYPE_ACK  = 1
HEADER_SIZE = 2          # 1 byte type + 1 byte seq
MAX_PAYLOAD = 64         # bytes per simulated packet
TIMEOUT     = 1.0        # seconds before retransmission
MAX_RETRIES = 10


# ── packet helpers ────────────────────────────────────────────────────────────

def make_data(seq: int, payload: bytes) -> bytes:
    return struct.pack("BB", TYPE_DATA, seq & 1) + payload


def make_ack(seq: int) -> bytes:
    return struct.pack("BB", TYPE_ACK, seq & 1)


def parse(raw: bytes) -> tuple:
    """Returns (pkt_type, seq, payload)."""
    if len(raw) < HEADER_SIZE:
        raise ValueError("Packet too short")
    pkt_type, seq = struct.unpack("BB", raw[:HEADER_SIZE])
    payload = raw[HEADER_SIZE:] if pkt_type == TYPE_DATA else b""
    return pkt_type, seq & 1, payload


# ── single-process simulation ─────────────────────────────────────────────────

def simulate(loss_rate: float = 0.20, num_packets: int = 12) -> None:
    """
    Simulate Stop-and-Wait ARQ in one process.

    The 'channel' randomly drops packets (both data and ACK directions).
    Prints every event: send, ACK, drop, timeout, retransmit.
    """
    rng = random.Random(42)   # fixed seed for reproducibility

    total_data  = num_packets * MAX_PAYLOAD
    chunks = [f"pkt{i:04d}".encode().ljust(MAX_PAYLOAD)[:MAX_PAYLOAD]
              for i in range(num_packets)]

    print(f"\nStop-and-Wait ARQ Simulation")
    print(f"  Packets:   {num_packets}")
    print(f"  Loss rate: {loss_rate:.0%}")
    print(f"  Timeout:   {TIMEOUT}s (simulated)")
    print()
    print(f"  {'Event':<10} {'seq':<5} {'chunk':<8} Details")
    print("  " + "-" * 55)

    seq = 0
    total_tx  = 0
    total_rtx = 0
    received  = []

    sim_time = 0.0   # logical simulation clock (seconds)
    RTT = 0.02       # simulated round-trip time

    for idx, chunk in enumerate(chunks):
        delivered = False
        attempt   = 0

        while not delivered:
            attempt += 1
            total_tx += 1
            if attempt > 1:
                total_rtx += 1

            pkt = make_data(seq, chunk)

            # ── transmit (may be lost) ─────────────────────────────────────
            data_lost = rng.random() < loss_rate
            if data_lost:
                print(f"  {'LOST-DATA':<10} {seq:<5} {idx:<8} "
                      f"DATA seq={seq} chunk={idx} dropped by channel")
                sim_time += TIMEOUT
                print(f"  {'TIMEOUT':<10} {seq:<5} {idx:<8} "
                      f"no ACK after {TIMEOUT}s, retransmitting …")
                continue

            sim_time += RTT / 2   # transmission delay to receiver

            # ── receiver side ─────────────────────────────────────────────
            _, recv_seq, payload = parse(pkt)
            if recv_seq == seq:
                # new packet — accept and send ACK
                received.append(payload)
                ack = make_ack(seq)
                ack_lost = rng.random() < loss_rate
                sim_time += RTT / 2   # propagation back

                if ack_lost:
                    print(f"  {'LOST-ACK':<10} {seq:<5} {idx:<8} "
                          f"ACK seq={seq} dropped on return path")
                    sim_time += TIMEOUT
                    print(f"  {'TIMEOUT':<10} {seq:<5} {idx:<8} "
                          f"no ACK after {TIMEOUT}s, retransmitting …")
                else:
                    print(f"  {'ACK':<10} {seq:<5} {idx:<8} "
                          f"receiver ACKed seq={seq}")
                    print(f"  {'OK':<10} {seq:<5} {idx:<8} "
                          f"chunk {idx} delivered  (attempt {attempt})")
                    seq = 1 - seq   # flip alternating bit
                    delivered = True
            else:
                # duplicate: receiver re-ACKs the old seq
                ack = make_ack(recv_seq)
                print(f"  {'DUP':<10} {recv_seq:<5} {idx:<8} "
                      f"receiver got duplicate seq={recv_seq}, re-ACKing")

    print()
    print("=== Simulation Results ===")
    print(f"  Chunks delivered:  {len(received)} / {num_packets}")
    print(f"  Total transmissions: {total_tx}  ({total_rtx} retransmits)")
    if total_tx > 0:
        print(f"  Retransmit rate:   {total_rtx/total_tx:.1%}")
    print(f"  Simulated time:    {sim_time:.2f}s")
    print(f"  Effective throughput: "
          f"{total_data / sim_time / 1024:.1f} KB/s  "
          f"(vs {total_data / (num_packets * RTT) / 1024:.1f} KB/s ideal)")


# ── real two-process UDP version ──────────────────────────────────────────────

def udp_sender(host: str, port: int, loss_rate: float = 0.0) -> None:
    """Send chunks using stop-and-wait ARQ over real UDP."""
    full = (b"Stop-and-wait ARQ over UDP. " * 10)[:512]
    chunks = [full[i:i+MAX_PAYLOAD] for i in range(0, len(full), MAX_PAYLOAD)]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)

    print(f"UDP Sender: {host}:{port}, loss={loss_rate:.0%}, {len(chunks)} chunks")

    seq = 0
    for idx, chunk in enumerate(chunks):
        pkt = make_data(seq, chunk)
        retries = 0
        while True:
            if random.random() >= loss_rate:
                sock.sendto(pkt, (host, port))
                print(f"  SEND seq={seq} chunk={idx}/{len(chunks)-1}")
            else:
                print(f"  DROP seq={seq} (simulated)")

            try:
                raw, _ = sock.recvfrom(16)
                _, ack_seq, _ = parse(raw)
                if ack_seq == seq:
                    print(f"  ACK  seq={seq}")
                    seq = 1 - seq
                    break
            except socket.timeout:
                retries += 1
                print(f"  TIMEOUT seq={seq} retry {retries}")
                if retries >= MAX_RETRIES:
                    print("Max retries, aborting.")
                    sock.close()
                    return

    sock.sendto(make_data(seq, b"__END__"), (host, port))
    sock.close()
    print("Transfer complete.")


def udp_receiver(port: int, loss_rate: float = 0.0) -> None:
    """Receive using stop-and-wait ARQ over real UDP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(30.0)

    print(f"UDP Receiver: port {port}, ack_loss={loss_rate:.0%}")
    expected = 0
    data_buf = b""
    duplicates = 0

    while True:
        try:
            raw, addr = sock.recvfrom(HEADER_SIZE + MAX_PAYLOAD + 4)
        except socket.timeout:
            print("Timeout waiting for sender.")
            break

        pkt_type, seq, payload = parse(raw)
        if pkt_type != TYPE_DATA:
            continue
        if payload == b"__END__":
            print("END signal received.")
            break

        if seq == expected:
            data_buf += payload
            print(f"  RCV  seq={seq} ({len(payload)}B) total={len(data_buf)}B")
            if random.random() >= loss_rate:
                sock.sendto(make_ack(seq), addr)
            else:
                print(f"  DROP ACK seq={seq} (simulated)")
            expected = 1 - expected
        else:
            duplicates += 1
            print(f"  DUP  seq={seq} — discarding, re-ACKing")
            sock.sendto(make_ack(seq), addr)

    sock.close()
    print(f"Received {len(data_buf)} bytes, {duplicates} duplicates discarded.")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "simulate":
        loss = float(sys.argv[2]) if len(sys.argv) > 2 else 0.20
        simulate(loss_rate=loss)

    elif mode == "sender":
        if len(sys.argv) < 3:
            print("Usage: python3 arq.py sender <host> [port] [loss]")
            sys.exit(1)
        host = sys.argv[2]
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 9000
        loss = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
        udp_sender(host, port, loss)

    elif mode == "receiver":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
        loss = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        udp_receiver(port, loss)

    else:
        print(f"Unknown mode: {mode!r}.  Use simulate | sender | receiver.")
        sys.exit(1)


if __name__ == "__main__":
    main()

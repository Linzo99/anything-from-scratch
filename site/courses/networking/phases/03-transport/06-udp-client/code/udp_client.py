# Run: python3 udp_client.py
"""
udp_client.py — UDP client that measures round-trip time and packet loss.

Sends NUM_PACKETS datagrams to a local UDP echo server, each stamped with
a sequence number and send timestamp.  Measures per-packet RTT, detects
dropped packets via a manual timeout, and prints a summary.

Usage:
    python3 udp_client.py [host [port [num_packets]]]
    python3 udp_client.py                           # defaults: localhost:9000, 20 packets
    python3 udp_client.py 127.0.0.1 9000 50

Requires udp_server.py to be running in another terminal first:
    python3 udp_server.py
"""

import socket
import struct
import time
import sys

HOST        = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT        = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
NUM_PACKETS = int(sys.argv[3]) if len(sys.argv) > 3 else 20
TIMEOUT     = 0.5    # seconds to wait for each reply before declaring loss

# Packet format: 4-byte uint32 seq + 8-byte double timestamp = 12 bytes
PACK_FMT = "!Id"     # ! = network byte order, I = unsigned int, d = double


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT)

sent     = 0
received = 0
rtts     = []

print(f"UDP client → {HOST}:{PORT}")
print(f"Sending {NUM_PACKETS} packets, timeout={TIMEOUT}s each\n")
print(f"  {'pkt':>5}  {'result':<8}  {'RTT':>10}  note")
print("  " + "-" * 45)

for seq in range(NUM_PACKETS):
    t_send  = time.time()
    payload = struct.pack(PACK_FMT, seq, t_send)

    try:
        sock.sendto(payload, (HOST, PORT))
        sent += 1

        data, _ = sock.recvfrom(256)
        t_recv  = time.time()

        recv_seq, t_orig = struct.unpack(PACK_FMT, data[:struct.calcsize(PACK_FMT)])
        rtt_ms = (t_recv - t_orig) * 1000

        if recv_seq == seq:
            received += 1
            rtts.append(rtt_ms)
            print(f"  {seq:>5}  {'OK':<8}  {rtt_ms:>8.3f}ms")
        else:
            print(f"  {seq:>5}  {'OUT-ORD':<8}  {rtt_ms:>8.3f}ms  "
                  f"(expected seq {seq}, got {recv_seq})")

    except socket.timeout:
        print(f"  {seq:>5}  {'LOST':<8}  {'—':>10}  no reply in {TIMEOUT}s")

sock.close()

# ── summary ───────────────────────────────────────────────────────────────────

loss_pct = (sent - received) / sent * 100 if sent else 0.0

print()
print("=== Summary ===")
print(f"  Sent:       {sent}")
print(f"  Received:   {received}")
print(f"  Lost:       {sent - received}  ({loss_pct:.1f}%)")

if rtts:
    avg = sum(rtts) / len(rtts)
    print(f"  RTT min:    {min(rtts):.3f}ms")
    print(f"  RTT avg:    {avg:.3f}ms")
    print(f"  RTT max:    {max(rtts):.3f}ms")

print()
print("Key observation:")
print("  No connection setup (no SYN/SYN-ACK/ACK before first packet).")
print("  If a packet is lost, this client detects it via timeout —")
print("  unlike TCP which handles retransmission transparently.")

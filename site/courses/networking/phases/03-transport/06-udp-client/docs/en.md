# Build a UDP Datagram Client

> TCP guarantees delivery — but what does the network look like without that guarantee?

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 0, Lesson 01 — Set Up a Linux Networking Lab
**Time:** ~35 minutes

## Learning Objectives

- Explain the fundamental differences between UDP and TCP at the socket API level
- Write a Python UDP client that sends datagrams and a server that receives them
- Measure round-trip time per packet using timestamps
- Calculate and report packet loss percentage over a batch of sends
- Explain why applications like DNS, video streaming, and games choose UDP over TCP

## The Problem

Every networking lesson up to this point has used TCP — a protocol that goes to great lengths to hide the unreliable nature of the underlying network. Packets get lost, reordered, and duplicated on the internet every second. TCP masks all of that with retransmission, sequencing, and flow control.

But that masking has a cost: latency. Before the first byte of data can flow, TCP needs a three-way handshake. If a packet is lost, TCP waits for a timeout before retransmitting, stalling everything behind it (head-of-line blocking). For a 40ms RTT connection, a single lost packet can pause the stream for 200ms.

For applications where latency matters more than completeness — live video, online games, DNS queries, VoIP — UDP is the right choice. A dropped video frame is preferable to the entire stream stalling. A DNS query that times out can simply be resent by the application, faster than TCP's retransmission timer fires.

To understand why UDP is used in these contexts, you need to feel the difference directly: write a UDP client, send 100 packets, and measure how many come back and how long each round trip takes.

## The Concept

### UDP vs TCP at the socket level

```
TCP socket lifecycle:              UDP socket lifecycle:
  socket()                           socket()
  connect()  ← 3-way handshake       (no connect needed)
  send()                             sendto(data, addr)
  recv()                             recvfrom()  → (data, addr)
  close()    ← 4-way teardown        close()
```

With TCP, `connect()` establishes a stateful connection. With UDP, there is no connection — you just call `sendto()` with a destination address, and the kernel sends the datagram. There is no guarantee it arrives.

### Datagram semantics

UDP preserves message boundaries. If you call `sendto()` with 100 bytes, the receiver gets exactly 100 bytes in one `recvfrom()` call. With TCP, `send(100 bytes)` might arrive as two `recv()` calls of 60 and 40 bytes — TCP is a byte stream, not a message protocol.

```
UDP: send(pkt1) send(pkt2) send(pkt3)
     recv → pkt1  recv → pkt2  recv → pkt3   (or some dropped)

TCP: send(100B) send(100B)
     recv → 200B  (may arrive together — no message boundary)
```

### Why packets get lost

On a local loopback interface, you'll rarely see loss. But on a real network:

- **Router buffer overflow**: a router's queue fills up, new packets are dropped
- **Link errors**: bit errors on Wi-Fi or long-haul fiber cause corrupted frames to be dropped
- **Rate limiting**: ISPs and firewalls silently drop packets over a quota
- **Reordering**: packets take different paths and arrive out of order

UDP gives you the raw view. TCP hides all of this with retransmission.

### Measuring RTT over UDP

To measure per-packet RTT, embed a send timestamp in the payload and read it back:

```
Client                              Server
  |                                   |
  |-- pkt(seq=1, t=1000ms) ---------->|
  |                                   | echo back exact payload
  |<-- pkt(seq=1, t=1000ms) ----------|
  |
  t_now = 1023ms
  RTT = 1023 - 1000 = 23ms
```

The server echoes the payload unchanged so the client can recover the send timestamp without needing clock synchronization between the two machines.

## Build It

### Step 1: Write the UDP echo server

Create `udp_server.py`:

```python
import socket
import struct

HOST = '127.0.0.1'
PORT = 9000
BUFSIZE = 1024

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # SOCK_DGRAM = UDP
sock.bind((HOST, PORT))

print(f"UDP echo server listening on {HOST}:{PORT}")

while True:
    data, addr = sock.recvfrom(BUFSIZE)  # blocks until a datagram arrives
    sock.sendto(data, addr)              # echo back to sender unchanged
```

`SOCK_DGRAM` is what makes this UDP. `SOCK_STREAM` would be TCP. `recvfrom` returns both the data and the sender's address, which we need to reply to.

### Step 2: Write the UDP client

Create `udp_client.py`:

```python
import socket
import struct
import time

HOST = '127.0.0.1'
PORT = 9000
NUM_PACKETS = 100
TIMEOUT = 0.5        # seconds to wait for each reply

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT)   # recvfrom raises socket.timeout if no reply arrives

sent = 0
received = 0
rtts = []

for seq in range(NUM_PACKETS):
    # Pack: sequence number (4 bytes) + send timestamp (8 bytes float)
    t_send = time.time()
    payload = struct.pack('!Id', seq, t_send)   # ! = network byte order, I = uint32, d = double

    try:
        sock.sendto(payload, (HOST, PORT))
        sent += 1

        data, _ = sock.recvfrom(1024)
        t_recv = time.time()

        # Unpack to verify we got our packet back (not a stray one)
        recv_seq, t_orig = struct.unpack('!Id', data)
        rtt_ms = (t_recv - t_orig) * 1000

        if recv_seq == seq:
            received += 1
            rtts.append(rtt_ms)
            print(f"pkt {seq:3d}: RTT = {rtt_ms:.2f} ms")
        else:
            print(f"pkt {seq:3d}: out-of-order reply (got seq {recv_seq})")

    except socket.timeout:
        print(f"pkt {seq:3d}: LOST (no reply within {TIMEOUT}s)")

sock.close()

# Summary
loss_pct = (sent - received) / sent * 100
avg_rtt = sum(rtts) / len(rtts) if rtts else 0
min_rtt = min(rtts) if rtts else 0
max_rtt = max(rtts) if rtts else 0

print()
print(f"Sent:     {sent}")
print(f"Received: {received}")
print(f"Lost:     {sent - received} ({loss_pct:.1f}%)")
if rtts:
    print(f"RTT min/avg/max: {min_rtt:.2f}/{avg_rtt:.2f}/{max_rtt:.2f} ms")
```

### Step 3: Run both together

In one terminal:
```bash
python udp_server.py
```

In another:
```bash
python udp_client.py
```

On loopback you should see near-zero loss and sub-1ms RTTs. That's expected — loopback never drops packets unless the receive buffer overflows.

### Step 4: Simulate loss with tc netem

To actually see loss and higher RTT (Linux only):

```bash
# Add 5% random loss and 10ms delay to loopback
sudo tc qdisc add dev lo root netem loss 5% delay 10ms

# Run the client
python udp_client.py

# Remove the rule when done
sudo tc qdisc del dev lo root
```

Now you'll see some packets marked LOST and RTTs around 20ms (10ms each way).

## Exercises

1. Run the client against the loopback server with no netem. Record the min/avg/max RTT.
2. Add `sudo tc qdisc add dev lo root netem loss 10% delay 20ms` and re-run. What changed?
3. Modify the client to send 1000 packets with a 1ms sleep between each (`time.sleep(0.001)`). Does loss change?
4. Remove `sock.settimeout()` so recvfrom blocks forever. What happens when a packet is lost?
5. Change the server to randomly drop 10% of packets: `if random.random() > 0.1: sock.sendto(data, addr)`. Does the client correctly count the loss?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| UDP | "The unreliable protocol" | A transport protocol that sends datagrams with no connection, ordering, or delivery guarantee. The application handles reliability if it needs it. |
| Datagram | "A UDP packet" | A self-contained, independent unit of data sent via UDP. Each datagram is routed independently and may arrive out of order or not at all. |
| SOCK_DGRAM | "The UDP socket type" | The socket type constant that selects UDP. SOCK_STREAM selects TCP. Set when creating the socket. |
| recvfrom | "UDP's recv" | The UDP equivalent of recv() — returns both the data and the sender's address, since UDP has no connection and replies need an explicit destination. |
| Packet loss | "When packets disappear" | The fraction of sent datagrams that never reach the destination. On the internet, 0.1–1% is normal. Above 5% causes noticeable quality degradation for audio/video. |
| RTT | "Ping time" | Round-trip time — the time for a packet to travel to the destination and a reply to come back. Dominated by propagation delay (speed of light) on long-haul paths. |
| tc netem | "Linux traffic shaper" | A Linux kernel queueing discipline (qdisc) that can inject artificial delay, loss, jitter, and reordering into network traffic for testing. |

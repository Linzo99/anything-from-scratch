# Capture Your First Packet

> A "packet" is not an abstract concept — it is a sequence of bytes with a very specific structure, and you can read every field by hand if you know where to look.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 0, Lesson 01 — Set Up a Linux Networking Lab
**Time:** ~30 minutes

## Learning Objectives
- Use tcpdump to capture a live ping exchange on the loopback interface
- Identify the Ethernet, IP, and ICMP headers in a raw hex dump
- Explain what each header layer adds and why it is necessary
- Save a capture to a `.pcap` file and replay it offline
- Read tcpdump's one-line summary format and know what each field means

## The Problem

When a network engineer says "the packet never arrived" or "the TTL was wrong," they are describing something they can *see* in a capture file. Without the ability to read a hex dump, you are entirely dependent on other people's interpretations of what happened on the wire.

The gap between "I know TCP/IP conceptually" and "I can diagnose a real problem" is almost always this: the ability to look at raw bytes and read them. Textbooks show you cleaned-up diagrams. Real traffic is a stream of hexadecimal digits. This lesson bridges that gap.

We will send the simplest possible network message — a ping — and then dissect it byte by byte. Ping uses ICMP (Internet Control Message Protocol), which sits directly inside an IP packet, which sits inside an Ethernet frame. Three layers, all visible in the hex dump.

## The Concept

### What tcpdump Shows You

When you run `tcpdump`, the kernel gives it a copy of every packet that passes through the specified interface. tcpdump prints a one-line summary by default. With the `-xx` flag, it also prints the raw bytes in hexadecimal.

A typical one-line summary looks like:
```
14:23:01.123456 IP 127.0.0.1 > 127.0.0.1: ICMP echo request, id 3, seq 1, length 64
```

Breaking this down:
```
14:23:01.123456         Timestamp (hours:minutes:seconds.microseconds)
IP                      This is an IP packet (Layer 3)
127.0.0.1               Source IP address
>                       Direction arrow
127.0.0.1               Destination IP address
ICMP echo request       The ICMP message type
id 3                    ICMP identifier (used to match request/reply pairs)
seq 1                   Sequence number (increments with each ping)
length 64               Payload length in bytes
```

### The Three Header Layers in a Ping Packet

When `ping 127.0.0.1` sends a packet, the kernel builds it from the inside out:

```
Application (ping) creates an ICMP message
         |
         v
Network layer wraps it in an IP header
         |
         v
Data Link layer wraps that in an Ethernet frame
         |
         v
Loopback interface sends it (loops back immediately)
```

On the wire (or loopback), the bytes are in the opposite order — outermost layer first:

```
+------------------+-------------------+------------------+---------+
|  Ethernet Header |    IP Header      |   ICMP Header    | Payload |
|    (14 bytes)    |   (20 bytes min)  |    (8 bytes)     | (56 B)  |
+------------------+-------------------+------------------+---------+
  ^                  ^                   ^
  Processed first    Processed second    Processed third
  by NIC driver      by IP stack         by ICMP handler
```

### The Ethernet Header (14 bytes)

```
Byte offset  Field             Size    Example value
-----------  ----------------  ------  ------------------
0–5          Destination MAC   6 bytes 00:00:00:00:00:00  (loopback)
6–11         Source MAC        6 bytes 00:00:00:00:00:00  (loopback)
12–13        EtherType         2 bytes 08 00 = IPv4
                                       08 6d = IPv6
                                       08 06 = ARP
```

On the loopback interface, both MAC addresses are all zeros — there is no real hardware, so no real MAC address is needed.

### The IP Header (20 bytes minimum)

```
Byte offset  Field             Size    Notes
-----------  ----------------  ------  ---------------------------------
0            Version + IHL     1 byte  0x45 = IPv4, 20-byte header
1            DSCP / ECN        1 byte  Quality of service bits
2–3          Total Length      2 bytes IP header + payload, in bytes
4–5          Identification    2 bytes Fragment reassembly ID
6–7          Flags + Frag Off  2 bytes Don't Fragment bit, fragment offset
8            TTL               1 byte  Decremented at each router hop
9            Protocol          1 byte  0x01 = ICMP, 0x06 = TCP, 0x11 = UDP
10–11        Header Checksum   2 bytes Error detection for header only
12–15        Source IP         4 bytes 127.0.0.1 = 7f 00 00 01
16–19        Destination IP    4 bytes 127.0.0.1 = 7f 00 00 01
```

### The ICMP Header (8 bytes)

```
Byte offset  Field             Size    Notes
-----------  ----------------  ------  ---------------------------------
0            Type              1 byte  8 = echo request, 0 = echo reply
1            Code              1 byte  0 for echo request/reply
2–3          Checksum          2 bytes Error detection over ICMP header+data
4–5          Identifier        2 bytes Set by ping, used to match pairs
6–7          Sequence Number   2 bytes Increments with each request
```

## Build It

### Step 1 — Start a capture to file

Writing the capture to a file lets you analyze it without losing data:

```bash
sudo tcpdump -i lo -n -w /tmp/ping-capture.pcap &
```

Flag breakdown:
- `-i lo` — loopback interface
- `-n` — no hostname resolution
- `-w /tmp/ping-capture.pcap` — write raw packets to file instead of printing
- `&` — run in the background so we can use the same terminal

### Step 2 — Generate ping traffic

```bash
ping -c 4 127.0.0.1
```

Expected output:
```
PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.052 ms
64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.044 ms
64 bytes from 127.0.0.1: icmp_seq=3 ttl=64 time=0.039 ms
64 bytes from 127.0.0.1: icmp_seq=4 ttl=64 time=0.041 ms

--- 127.0.0.1 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3076ms
```

Notice: `56(84) bytes` — you send 56 bytes of data, but the total IP packet is 84 bytes (56 data + 8 ICMP header + 20 IP header).

### Step 3 — Stop the capture

```bash
sudo pkill tcpdump
```

### Step 4 — Read the capture with human-readable output

```bash
sudo tcpdump -r /tmp/ping-capture.pcap -n -v
```

The `-v` flag adds verbosity — you will now see IP TTL, protocol number, and more.

Expected output for each packet:
```
14:23:01.123456 IP (tos 0x0, ttl 64, id 12345, offset 0, flags [DF], proto ICMP (1), length 84)
    127.0.0.1 > 127.0.0.1: ICMP echo request, id 3, seq 1, length 64
```

### Step 5 — Print the hex dump

This is where you see the raw bytes:

```bash
sudo tcpdump -r /tmp/ping-capture.pcap -n -xx -c 1
```

The `-xx` flag prints the Ethernet frame including the Ethernet header. Expected output:

```
reading from file /tmp/ping-capture.pcap, link-type EN10MB (Ethernet)
14:23:01.123456 IP 127.0.0.1 > 127.0.0.1: ICMP echo request, id 3, seq 1, length 64
        0x0000:  0000 0000 0000 0000 0000 0000 0800 4500   ..............E.
        0x0010:  0054 3039 4000 4001 f7c6 7f00 0001 7f00   .T09@.@.........
        0x0020:  0001 0800 f6d3 0003 0001 dc44 7267 0000   ...........Drg..
        0x0030:  0000 ad08 0b00 0000 0000 1011 1213 1415   ................
        0x0040:  1617 1819 1a1b 1c1d 1e1f 2021 2223 2425   ...........!"#$%
        0x0050:  2627 2829 2a2b 2c2d 2e2f 3031 3233 3435   &'()*+,-./012345
        0x0060:  3637                                       67
```

### Step 6 — Decode the hex manually

Let's decode the first line: `0000 0000 0000 0000 0000 0000 0800 4500`

```
Bytes (hex)    Field                  Value
-------------  ---------------------  ----------------------------
00 00 00 00    Destination MAC        00:00:00:00:00:00 (loopback)
00 00          (continued)
00 00 00 00    Source MAC             00:00:00:00:00:00 (loopback)
00 00          (continued)
08 00          EtherType              0x0800 = IPv4
45             IP Version + IHL       4=IPv4, 5=5×4=20 byte header
00             DSCP/ECN               0 (best effort)
```

Second line: `0054 3039 4000 4001 f7c6 7f00 0001 7f00`
```
Bytes (hex)    Field                  Value
-------------  ---------------------  ----------------------------
00 54          Total Length           0x0054 = 84 bytes
30 39          Identification         0x3039 = 12345
40 00          Flags + Fragment Off   0x4000 = Don't Fragment, offset 0
40             TTL                    0x40 = 64
01             Protocol               0x01 = ICMP
f7 c6          Header Checksum        0xf7c6
7f 00 00 01    Source IP              127.0.0.1
7f 00          (Destination IP next line)
```

Third line starts with destination IP then ICMP: `0001 0800 f6d3 0003 0001`
```
Bytes (hex)    Field                  Value
-------------  ---------------------  ----------------------------
00 01          Destination IP (end)   ...0.1 → 127.0.0.1
08 00          ICMP Type + Code       Type=8 (echo request), Code=0
f6 d3          ICMP Checksum          0xf6d3
00 03          ICMP Identifier        3
00 01          ICMP Sequence Number   1
```

## Exercises

1. **Capture a ping reply** — From your hex dump, find the echo reply packet. The ICMP Type byte should be `00` (type 0) instead of `08` (type 8). Confirm this.

2. **Calculate the payload size** — From the IP Total Length field in the hex dump, subtract the IP header size (20 bytes) and the ICMP header size (8 bytes). Does the result match the 56 bytes of ping data?

3. **Observe the TTL** — Run `ping -c 1 8.8.8.8` (requires internet access) and compare the TTL in the captured packet to the TTL when pinging localhost. Why does the remote ping TTL start lower?

4. **Find the protocol byte** — Capture a TCP packet by running `curl http://example.com` and capturing on your default interface. Find the Protocol byte in the IP header. It should be `0x06` (TCP) instead of `0x01` (ICMP).

5. **Read the pcap in Python** — Install `scapy` (`pip install scapy`) and run:
   ```python
   from scapy.all import rdpcap
   packets = rdpcap('/tmp/ping-capture.pcap')
   for pkt in packets[:2]:
       pkt.show()
   ```
   Compare scapy's parsed output to your manual hex decode.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| pcap | "packet capture file" | A file format (`.pcap`) that stores raw packet data with timestamps. Both tcpdump and Wireshark read and write this format. |
| hex dump | "the raw bytes" | A representation of binary data in base-16 (hexadecimal). Two hex digits = one byte. Used because binary is unreadable and decimal is awkward for byte-aligned fields. |
| ICMP | "ping protocol" | Internet Control Message Protocol. Lives inside IP packets (protocol number 1). Used for diagnostics: echo request/reply (ping), destination unreachable, time exceeded, etc. |
| TTL | "time to live" | An IP header field, initially set by the sender (usually 64 or 128). Every router that forwards the packet decrements it by 1. When it hits 0, the router drops the packet and sends an ICMP "time exceeded" back to the sender. Prevents routing loops from lasting forever. |
| EtherType | "the type field" | A 2-byte field in the Ethernet header that tells the receiver which Layer 3 protocol the payload contains. 0x0800=IPv4, 0x86DD=IPv6, 0x0806=ARP. |

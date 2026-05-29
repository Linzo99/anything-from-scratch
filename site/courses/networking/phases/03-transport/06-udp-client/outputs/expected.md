# Expected Output

## Server terminal

Running `python3 udp_server.py` should produce:

```
UDP echo server listening on 127.0.0.1:9000
Press Ctrl-C to stop

  echoed 12 bytes to 127.0.0.1:52100
  echoed 12 bytes to 127.0.0.1:52100
  ... (one line per packet)
```

## Client terminal

Running `python3 udp_client.py` (with the server already running) on loopback should produce near-zero loss and sub-millisecond RTTs:

```
UDP client → 127.0.0.1:9000
Sending 20 packets, timeout=0.5s each

    pkt  result      RTT  note
  ---------------------------------------------
      0  OK         0.141ms
      1  OK         0.098ms
      2  OK         0.112ms
      3  OK         0.089ms
      4  OK         0.105ms
      5  OK         0.093ms
      6  OK         0.101ms
      7  OK         0.099ms
      8  OK         0.108ms
      9  OK         0.095ms
     10  OK         0.102ms
     11  OK         0.098ms
     12  OK         0.097ms
     13  OK         0.094ms
     14  OK         0.100ms
     15  OK         0.099ms
     16  OK         0.108ms
     17  OK         0.091ms
     18  OK         0.103ms
     19  OK         0.096ms

=== Summary ===
  Sent:       20
  Received:   20
  Lost:       0  (0.0%)
  RTT min:    0.089ms
  RTT avg:    0.102ms
  RTT max:    0.141ms

Key observation:
  No connection setup (no SYN/SYN-ACK/ACK before first packet).
  If a packet is lost, this client detects it via timeout —
  unlike TCP which handles retransmission transparently.
```

With artificial loss added via `tc netem` (`sudo tc qdisc add dev lo root netem loss 10% delay 10ms`), some packets will show `LOST` and RTTs will be ~20ms.

## Common issues

- **Issue**: All packets show `LOST` → **Fix**: The server is not running.  Start `python3 udp_server.py` in a separate terminal first.
- **Issue**: `ConnectionRefusedError` (on some platforms) → **Fix**: On Linux, sending UDP to a port with nothing listening causes an ICMP "port unreachable" which Python translates to `ConnectionRefusedError`.  Start the server first.
- **Issue**: RTTs are very high (>5ms on loopback) → **Fix**: Your system may be under load.  On a quiet system, loopback UDP RTT is typically 0.05–0.5ms.

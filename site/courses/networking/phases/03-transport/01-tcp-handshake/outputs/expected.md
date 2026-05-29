# Expected Output

Running `python3 tcp_handshake.py` should produce:

```
=== TCP Header Layout ===

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

  Flag semantics:
    SYN=1, ACK=0  →  connection request (step 1)
    SYN=1, ACK=1  →  connection accepted (step 2)
    SYN=0, ACK=1  →  acknowledgment (step 3 and all data packets)
    RST=1         →  abort/refuse connection
    FIN=1, ACK=1  →  graceful close

=== TCP Three-Way Handshake Demo ===
  Target: 127.0.0.1:54321

  Logical handshake sequence:
  ─────────────────────────────────────────────────────────────
  Step   Who      Packet             Flags              Description
  ─────────────────────────────────────────────────────────────
  1      Client   SYN                SYN                client picks ISN, sends SYN  (+0.1ms)
  2      Server   SYN-ACK            SYN|ACK            server picks ISN, ACKs client  (+0.3ms)
  3      Client   ACK                ACK                client ACKs server ISN  (+0.4ms)

  Connection established in 0.4 ms

  Client socket:  127.0.0.1:52341
  Server socket:  127.0.0.1:54321

  Echo test PASSED: 'hello handshake' echoed correctly

=== Simulated failure scenarios (no actual traffic) ===
  Scenario 1 — SYN dropped by firewall:
    Client sends SYN → silence → retransmits after ~1s → eventually
    'Connection timed out'  (errno ETIMEDOUT)

  Scenario 2 — Nothing listening on port (RST returned):
    Connected to 127.0.0.1:54322 → RST received → ConnectionRefusedError

Done.
```

The port numbers and timestamps will differ each run. The key things to observe:

- Step 1 always arrives before step 2 (which arrives before step 3)
- The echo test confirms the connection is bidirectional and data flows correctly
- The RST scenario shows `ConnectionRefusedError`, not a timeout

## Common issues

- **Issue**: `ConnectionRefusedError` on step 1 (not the RST probe) → **Fix**: A previous run's server thread may still be holding the port; wait a second and re-run.
- **Issue**: Script hangs indefinitely → **Fix**: The background server thread may have crashed; kill the process with Ctrl-C and check for Python import errors above.
- **Issue**: Echo test FAILED → **Fix**: The OS may have delivered the ACK before the server called `accept()`; this is rare on loopback and should self-resolve on re-run.

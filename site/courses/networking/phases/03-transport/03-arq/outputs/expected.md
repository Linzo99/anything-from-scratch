# Expected Output

Running `python3 arq.py simulate` (default 20% loss) should produce output similar to:

```
Stop-and-Wait ARQ Simulation
  Packets:   12
  Loss rate: 20%
  Timeout:   1.0s (simulated)

  Event      seq   chunk    Details
  -------------------------------------------------------
  ACK        0     0        receiver ACKed seq=0
  OK         0     0        chunk 0 delivered  (attempt 1)
  LOST-DATA  1     1        DATA seq=1 chunk=1 dropped by channel
  TIMEOUT    1     1        no ACK after 1.0s, retransmitting …
  ACK        1     1        receiver ACKed seq=1
  OK         1     1        chunk 1 delivered  (attempt 2)
  ACK        0     2        receiver ACKed seq=0
  OK         0     2        chunk 2 delivered  (attempt 1)
  LOST-ACK   1     3        ACK seq=1 dropped on return path
  TIMEOUT    1     3        no ACK after 1.0s, retransmitting …
  DUP        1     3        receiver got duplicate seq=1, re-ACKing
  ACK        1     3        receiver ACKed seq=1
  OK         1     3        chunk 3 delivered  (attempt 3)
  ...

=== Simulation Results ===
  Chunks delivered:  12 / 12
  Total transmissions: 15  (3 retransmits)
  Retransmit rate:   20.0%
  Simulated time:    3.24s
  Effective throughput: 0.2 KB/s  (vs 38.4 KB/s ideal)
```

With 0% loss (`python3 arq.py simulate 0.0`):

```
  Every chunk shows ACK then OK on the first attempt.
  Retransmit rate: 0.0%
```

## Common issues

- **Issue**: All 12 chunks show multiple retransmissions even with `loss_rate=0.0` → **Fix**: The simulation uses a fixed random seed (`seed=42`); if you changed the seed, some loss may have been introduced.  Use `0.0` explicitly.
- **Issue**: Two-process UDP mode (`sender`/`receiver`) hangs → **Fix**: Start the receiver first, then the sender.  Both must be on the same machine or reachable via UDP port 9000 (check firewall rules if cross-machine).
- **Issue**: `Max retries, aborting` with a high loss rate → **Fix**: Reduce the loss rate or increase `MAX_RETRIES` at the top of the file.  With 50%+ loss, stop-and-wait becomes very inefficient.

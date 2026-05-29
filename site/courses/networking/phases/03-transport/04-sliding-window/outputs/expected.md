# Expected Output

Running `python3 sliding_window.py` (defaults: window=4, packets=20, loss=0, rtt=50ms) should produce:

```
Go-Back-N Sliding Window Simulation
  Packets:     20
  Window size: 4
  RTT:         50ms
  Loss rate:   0%
  RTO:         100ms

  Legend: A=acked  S=in-flight  .=sendable  _=beyond window

     t(ms)  Event                   una  nxt  flight  Window
  ------------------------------------------------------------------------------
      50.0  ACK 0                     1    4       3  [ASSS................]
     100.0  ACK 1                     2    5       3  [AASSS...............]
     150.0  ACK 2                     3    6       3  [AAASSS..............]
     200.0  ACK 3                     4    7       3  [AAAASSS.............]
     250.0  ACK 4                     5    8       3  [AAAAASSS............]
     300.0  ACK 5                     6    9       3  [AAAAAASSS...........]
     350.0  ACK 6                     7   10       3  [AAAAAAASS...........]
     ...

=== Simulation Complete ===
  Simulated time:  1050.0ms
  Transmissions:   20  (0 retransmits)
  Retransmit rate: 0.0%
  Goodput:         9.5 KB/s
```

Running `python3 sliding_window.py --compare --rtt 0.05 --loss 0.0`:

```
============================================================
Window comparison  RTT=50ms  loss=0%
============================================================
    Window    Time (ms)  Goodput (KB/s)
  --------  ----------  ---------------
         1      2000.0              1.0
         2      1000.0              2.0
         4       500.0              4.0
         8       250.0              8.0
        16       125.0             16.0
        32        62.5             32.0
```

Throughput roughly doubles with each window doubling (until link bandwidth becomes the limit).

Running with `--loss 0.2` (20% packet loss) will show RTO events and Go-Back-N retransmissions:

```
     225.0  RTO from 2              2    2           [AA__________________]
```

The window bar shows the simulation rewinding `snd_nxt` back to the lost packet.

## Common issues

- **Issue**: Script prints `[WARN] tick limit reached` and exits early → **Fix**: The combination of high loss + small window + large packet count can stall the simulation.  Reduce `--packets` or lower `--loss`.
- **Issue**: Goodput is much lower than expected with `--loss 0.3` → **Fix**: This is intentional — Go-Back-N retransmits all packets from the point of loss, so even one lost packet discards correctly delivered packets behind it.  This is the key inefficiency Go-Back-N vs Selective Repeat trades off.
- **Issue**: `--compare` table shows identical times for window=16 and window=32 → **Fix**: With 40 packets and no loss, window=32 can already saturate the pipe.  Increase `--packets` to 200 to see the difference more clearly.

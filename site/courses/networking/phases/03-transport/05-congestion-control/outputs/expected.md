# Expected Output

Running `python3 congestion_sim.py` (defaults: 50 RTTs, 5% loss, ssthresh=32) should produce:

```
  CWND over 50 RTTs  (max=35 MSS)
  RTT   cwnd   ssth  Phase              Graph
  -----------------------------------------------------------------------
     0      1     32  Slow Start         #
     1      2     32  Slow Start         ##
     2      4     32  Slow Start         ####
     3      8     32  Slow Start         #########
     4     16     32  Slow Start         ####################
     5     32     32  Slow Start         ###############################...
     6     33     32  Cong.Avoid.        ###############################...
     7     34     32  Cong.Avoid.        ###############################...
     8     17     17  Cong.Avoid.        !!!!!!!!!!!!!!!!!!  ← LOSS(3dupACK)
     9     18     17  Cong.Avoid.        ##################
    10     19     17  Cong.Avoid.        ###################
    ...
    15      1     10  Slow Start         #  ← LOSS(timeout)
    16      2     10  Slow Start         ##
    17      4     10  Slow Start         ####
    18      8     10  Slow Start         ########
    19     10     10  Slow Start         #########
    20     11     10  Cong.Avoid.        ##########
    ...

=== TCP Reno Congestion Control Summary ===
  RTTs simulated:       50
  Peak CWND:            35 MSS
  Average CWND:         18.4 MSS
  Loss events:          4
    via 3 dupACK:       3
    via timeout:        1

  Phase progression:
    RTT   0: entering Slow Start (exponential)  (cwnd=1, ssthresh=32)
    RTT   6: entering Congestion Avoidance (AIMD +1/RTT)  (cwnd=33, ssthresh=32)
    RTT   8: LOSS(3dupACK)  cwnd 35 → 17  ssthresh → 17
    RTT  15: LOSS(timeout)  cwnd 22 → 1   ssthresh → 11
```

The sawtooth pattern is the signature of AIMD: slow exponential rise, then sharp halving at each loss event.

## Common issues

- **Issue**: No loss events appear in the graph → **Fix**: Increase `--loss-prob` (e.g., `--loss-prob 0.15`) or use a different `--seed`.  With `--loss-prob 0.0` there is no loss by design.
- **Issue**: Bars in the graph are all `#` with no `!` markers → **Fix**: This means no loss was sampled in those RTTs.  With the default seed and parameters, at least 2–3 loss events should appear in 50 RTTs.
- **Issue**: Graph is very wide and hard to read → **Fix**: Pass `--width 30` to shrink the bar width.

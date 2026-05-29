# Expected Output

Running `python3 rip_sim.py` should produce:

```
RIP Distance-Vector Routing Simulation
Topology: A ── B ── C ── D  (linear, all costs = 1)

======================================================
  Round 0 — Initial state (each node knows only its own prefix)
======================================================
  [A] Round 0:
    * 192.168.1.0/24        metric=1    via=direct
      192.168.2.0/24        metric=∞    via=direct
      192.168.3.0/24        metric=∞    via=direct
      192.168.4.0/24        metric=∞    via=direct

  ... (B, C, D show similar — each knows only its own prefix)

======================================================
  Round 1
======================================================
  [A] Round 1:
    * 192.168.1.0/24        metric=1    via=direct
    * 192.168.2.0/24        metric=2    via=B
      192.168.3.0/24        metric=∞    via=...
      192.168.4.0/24        metric=∞    via=...

  ... (after round 3, all nodes have full tables)

  Converged after 3 rounds.
  (In real RIP: 30-second periodic updates would continue)

======================================================
  COUNT-TO-INFINITY DEMO (split horizon DISABLED)
  Scenario: Node D goes offline
======================================================

  t=0: D goes offline. D's own prefix 192.168.4.0/24 = ∞

  Round  1: D's prefix metric — A:4  B:3  C:2  D:16
  Round  2: D's prefix metric — A:4  B:3  C:4  D:16
  Round  3: D's prefix metric — A:5  B:4  C:5  D:16
  ...
  Round 14: D's prefix metric — A:∞  B:∞  C:∞  D:∞

  B and C counted all the way to 16 (infinity) before giving up.
  This is the count-to-infinity problem.

======================================================
  SPLIT HORIZON DEMO (split horizon ENABLED)
  Scenario: Node D goes offline
======================================================

  t=0: D goes offline.

  Round  1: D's prefix metric — A:4  B:3  C:∞  D:16
  Round  2: D's prefix metric — A:∞  B:∞  C:∞  D:16

  With split horizon, the route disappears quickly.
```

## Common issues

- **Issue**: Convergence takes more than 3 rounds — **Fix**: A 4-node linear chain converges in exactly 3 rounds (diameter of the network). If you add nodes, increase the expected round count accordingly.
- **Issue**: Count-to-infinity demo stops at a different round number — **Fix**: This is expected behaviour. The exact count depends on initial metric values. The key observation is that it takes many more rounds than with split horizon enabled.

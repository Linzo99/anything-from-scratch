# Expected Output

Running `python logical_clocks.py` should produce:

```
Lamport clocks:
  P1 local event a -> L=1
  P1 sends m       -> L=2
  P2 receives m    -> L=3 (max(0,2)+1)
  P2 local event d -> L=4
  a→...→c holds: L(a)=1 < L(c)=3  (causality respected)

Vector clocks (3 processes):
  P0 event a: [1, 0, 0]
  P0 sends:   [2, 0, 0]
  P1 recv->b: [2, 1, 0]  (knows of P0's event)
  P2 event c: [0, 0, 1]  (independent)

  b vs c: a ∥ b (CONCURRENT — conflict!)
  a vs b: a → b (a before b)
```

What to notice:
- **Lamport**: the receive sets the clock to `max(local, received) + 1`, so P2's
  clock jumps to 3 after receiving a message stamped 2. Causally ordered events
  always get increasing timestamps: L(a)=1 < L(c)=3.
- **Vector clocks** reveal what Lamport can't:
  - `b = [2,1,0]` knows about P0's event (the 2 in position 0) — so `a → b`
    (a's vector `[1,0,0]` is ≤ b's elementwise).
  - `c = [0,0,1]` was produced by P2 in total isolation. Comparing `b=[2,1,0]` and
    `c=[0,0,1]`: neither is ≤ the other, so they're **concurrent** — a genuine
    conflict that, in a real datastore, you'd resolve with app logic or CRDTs.

Lamport alone could give b and c some order by their integer values, but that
order would be meaningless — they never influenced each other. Only vector clocks
detect the concurrency.

Common issues:
- **b vs c shows an order instead of concurrent:** check that `receive` takes the
  elementwise max and that P2 never received any message (its vector stays
  `[0,0,1]`).
- **Vectors wrong length:** all processes must use the same N (here 3).

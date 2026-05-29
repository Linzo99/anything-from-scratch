# Expected Output

Running `python3 mac_switch.py` should produce:

```
==============================================================
SCENARIO 1: Alice → Bob  (CAM table empty — expect FLOOD)
==============================================================
  [SW1] IN     [aa:aa:aa:aa:aa:aa → bb:bb:bb:bb:bb:bb] payload='Hello Bob!' port=1
  [SW1] LEARN  aa:aa:aa:aa:aa:aa → port 1
  [SW1] FLOOD  bb:bb:bb:bb:bb:bb: unknown unicast → ports [2, 3, 4]
    Bob    (port 2) ← 'Hello Bob!'  from aa:aa:aa:aa:aa:aa
    Carol  (port 3) ← 'Hello Bob!'  from aa:aa:aa:aa:aa:aa   ← also receives (flood)
    Dave   (port 4) ← 'Hello Bob!'  from aa:aa:aa:aa:aa:aa   ← also receives (flood)

  [SW1] CAM Table (1 entries):
    MAC                   Port    Age(s)
    ────────────────────  ──────  ──────────
    aa:aa:aa:aa:aa:aa     1       0.00

==============================================================
SCENARIO 2: Bob → Alice  (Alice's port is now known — expect FORWARD)
==============================================================
  [SW1] IN     [bb:bb:bb:bb:bb:bb → aa:aa:aa:aa:aa:aa] payload='Hello Alice!' port=2
  [SW1] LEARN  bb:bb:bb:bb:bb:bb → port 2
  [SW1] FWD    aa:aa:aa:aa:aa:aa → port 1
    Alice  (port 1) ← 'Hello Alice!'  from bb:bb:bb:bb:bb:bb

  [SW1] CAM Table (2 entries):
    ...

==============================================================
SCENARIO 3: Carol → Dave  (Dave unknown — expect FLOOD to ports 1,2,4)
...
==============================================================
SCENARIO 4: Alice broadcasts ARP  (expect FLOOD to all other ports)
...
==============================================================
SCENARIO 5: Alice → Bob again  (Bob's port now known — expect FORWARD)
...

  [SW1] Stats: received=5  forwarded=2  flooded=3
```

Key observations:
- Scenario 1: Bob, Carol, and Dave all receive the frame (flooding before any learning)
- Scenario 2: Only Alice receives the frame (the switch learned her port from Scenario 1)
- Scenario 4: All three other hosts receive the ARP broadcast — always flooded
- Scenario 5: Only Bob receives the frame (both Alice and Bob's ports now known)

Run with `python3 mac_switch.py --flood` to see the MAC flooding attack demonstration.

## Common issues

- **Issue**: `SyntaxError` on `list[int]` type hints → **Fix**: Requires Python 3.9+. On Python 3.8, either run `python3.9 mac_switch.py` or add `from __future__ import annotations` at the top (already included).
- **Issue**: All frames show `FLOOD` even in Scenario 5 → **Fix**: This means the CAM table is not persisting between `send_frame()` calls. The `sw` object must be shared across all scenarios — check that you are not re-creating the switch between calls.
- **Issue**: `UNEXPECTED frame` log lines appear → **Fix**: This indicates the switch forwarded a unicast frame to a port that does not own that MAC. Check the `_is_multicast` method — the I/G bit check must only look at bit 0 of the first byte.

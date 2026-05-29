# Expected Output

Running `python3 reconvergence.py` should produce:

```
OSPF Reconvergence Simulation
Failure scenario: link B–C goes down

  ASCII Topology BEFORE failure:

         1         2         5
  A ─────── B ─────── C ─────── E
            │         │
          3 │       1 │
            │         │
            D ─────────
                 4


==============================
  ROUTING TABLES — BEFORE FAILURE
==============================

  Router B:
  Dest     Cost  NextHop     Path
  ------ ------  ----------  ------------------------------
  A           1  A           B → A
  C           2  C           B → C
  D           3  D           B → D
  E           7  C           B → C → E

  ... (tables for all 5 routers)

  ... network operating normally ...

============================================================
  LSA FLOOD — link B–C failure detected
============================================================

  t≈0ms  Router B detects link-down event
         Old LSA: B → [('A', 1), ('C', 2), ('D', 3)]
         New LSA: B → [('A', 1), ('D', 3)]
         Removed links: [('C', 2)]
         ➜ Router B floods updated Router LSA (seq++ ) to all reachable neighbors

  t≈0ms  Router C detects link-down event
         Old LSA: C → [('B', 2), ('D', 4), ('E', 5)]
         New LSA: C → [('D', 4), ('E', 5)]
         Removed links: [('B', 2)]
         ➜ Router C floods updated Router LSA (seq++ ) to all reachable neighbors

  t≈1ms  Updated LSAs propagate to all routers:
    Router A receives new LSAs, updates LSDB
    Router D receives new LSAs, updates LSDB
    Router E receives new LSAs, updates LSDB

  t≈2ms  All routers re-run SPF (Dijkstra) with updated LSDB
  t≈2ms  New routes installed via kernel (zebra → netlink)

  Total reconvergence time: ~2–5ms (carrier-loss, direct detection)
  (With default Dead Interval: same — interface-down is instant)

  ... (AFTER topology diagram) ...

============================================================
  CHANGES AFTER RECONVERGENCE
============================================================
  Router B → C:
    BEFORE: cost=2  nexthop=C  B → C
    AFTER:  cost=7  nexthop=D  B → D → C
  Router B → E:
    BEFORE: cost=7  nexthop=C  B → C → E
    AFTER:  cost=12  nexthop=D  B → D → C → E
  ...
```

## Common issues

- **Issue**: No changes shown in the diff section — **Fix**: Verify that `TOPOLOGY_AFTER` correctly removes both `("C", 2)` from B's links and `("B", 2)` from C's links. Both sides of the link must be removed.
- **Issue**: Path costs look wrong after failure — **Fix**: After B–C fails, B reaches C via D: cost = B→D(3) + D→C(4) = 7. B reaches E via D→C→E: 3+4+5 = 12. These are correct.

# Expected Output

Running `python3 ospf_sim.py` should produce:

```
OSPF Link-State Routing Simulation
Topology: A-B-C-D-E (see file header for diagram)

========================================================
  LINK STATE DATABASE (LSDB)
  (identical on every router — flooded network-wide)
========================================================
  Router A:  B(cost=1)
  Router B:  A(cost=1)  C(cost=2)  D(cost=3)
  Router C:  B(cost=2)  D(cost=4)  E(cost=5)
  Router D:  B(cost=3)  C(cost=4)
  Router E:  C(cost=5)

========================================================
  SPF ROUTING TABLES (computed by each router independently)
========================================================

  Router A  — SPF Routing Table
  Destination     Cost  Next Hop    Path
  -------------- ------  ----------  ------------------------------
  B                   1  B           A → B
  C                   3  B           A → B → C
  D                   4  B           A → B → D
  E                   8  B           A → B → C → E

  Router B  — SPF Routing Table
  Destination     Cost  Next Hop    Path
  -------------- ------  ----------  ------------------------------
  A                   1  A           B → A
  C                   2  C           B → C
  D                   3  D           B → D
  E                   7  C           B → C → E

  ... (tables for C, D, E follow)

========================================================
  SHORTEST PATH TREE rooted at A
========================================================
  A → B: cost=1  path=A → B
  A → C: cost=3  path=A → B → C
  A → D: cost=4  path=A → B → D
  A → E: cost=8  path=A → B → C → E
```

## Common issues

- **Issue**: `ModuleNotFoundError: No module named 'heapq'` — **Fix**: `heapq` is stdlib; check your Python version with `python3 --version`. Python 3.8+ required.
- **Issue**: Cost to E from A shows unexpected value — **Fix**: The path goes A→B→C→E with costs 1+2+5=8. If your topology was modified, re-check the `TOPOLOGY` dict at the top of the file.

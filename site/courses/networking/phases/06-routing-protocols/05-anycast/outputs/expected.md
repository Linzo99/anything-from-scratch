# Expected Output

Running `python3 anycast_sim.py` should produce:

```
Anycast Routing Simulation
Same prefix 10.9.9.0/24 announced from two locations

Topology:
  Client-West ── Router-West (AS65001) ── AnycastNode-A (AS65010)
  Client-East ── Router-East (AS65002) ── AnycastNode-B (AS65010)

AnycastNode-A and AnycastNode-B share AS 65010 and both announce
10.9.9.0/24 — the anycast prefix.

============================================================
  PHASE 1: Route propagation
============================================================

  BGP Table — Client-West (AS 65000):
  > 10.9.9.0/24           LP=200  AS_PATH=[65001, 65010]  via=Router-West
    10.9.9.0/24           LP=100  AS_PATH=[65002, 65001, 65010]  via=Router-East

  BGP Table — Client-East (AS 65000):
  > 10.9.9.0/24           LP=200  AS_PATH=[65002, 65010]  via=Router-East
    10.9.9.0/24           LP=100  AS_PATH=[65001, 65002, 65010]  via=Router-West

  Anycast routing result:
  Client-West → 10.9.9.1 routes via: Router-West  (AS_PATH: [65001, 65010])
    => REACHES: AnycastNode-A
  Client-East → 10.9.9.1 routes via: Router-East  (AS_PATH: [65002, 65010])
    => REACHES: AnycastNode-B

============================================================
  PHASE 2: Failover — AnycastNode-A goes offline
  BGP WITHDRAW sent for 10.9.9.0/24
============================================================

  Client-West BGP table after AnycastNode-A withdrawal:
  > 10.9.9.0/24           LP=100  AS_PATH=[65002, 65001, 65010]  via=Router-East

  Client-West now routes 10.9.9.1 via: Router-East
  => FAILOVER SUCCESSFUL: traffic now reaches AnycastNode-B

Key insight: No application change, no DNS change, no operator action needed.
BGP reconvergence automatically reroutes traffic to the surviving node.
```

## Common issues

- **Issue**: Both clients show the same best route — **Fix**: LOCAL_PREF must differ between the two paths. Client-West gets LP=200 from Router-West and LP=100 from Router-East. If LOCAL_PREF values are equal, AS_PATH length decides (shorter wins).
- **Issue**: Failover shows "no route to 10.9.9.0/24" — **Fix**: The backup path via Router-East must have been received by Client-West before the failure. Ensure Phase 1 propagation runs both the primary and backup paths to each client.

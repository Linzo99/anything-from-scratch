# Expected Output

Running `python3 bgp_sim.py` should produce:

```
BGP Path Selection Simulation
3 Autonomous Systems with eBGP peering

Topology:
  AS 65001 (R1) ──eBGP── AS 65002 (R2) ──eBGP── AS 65003 (R3)

==============================================================
  PHASE 1: Initial eBGP route exchange
==============================================================

  BGP Table for R1 (AS 65001)
  Pfx                    LP  AS_PATH                    From
  ---------------------- ---  --------------------------  ----------
> 10.1.0.0/24            100  AS_PATH=[]  ORIGIN=IGP  from=self
> 10.2.0.0/24            100  AS_PATH=[65002]  ORIGIN=IGP  from=R2
> 10.3.0.0/24            100  AS_PATH=[65002, 65003]  ORIGIN=IGP  from=R2

  BGP Table for R2 (AS 65002)
  ...
> 10.1.0.0/24            100  AS_PATH=[65001]  from=R1
> 10.2.0.0/24            100  AS_PATH=[]  from=self
> 10.3.0.0/24            100  AS_PATH=[65003]  from=R3

==============================================================
  PHASE 2: LOCAL_PREF demonstration
  R2 sets LOCAL_PREF=200 on routes received from R3
==============================================================

  BGP Table for R2 (AS 65002)
  ...
> 10.3.0.0/24            200  AS_PATH=[65003]  from=R3

  Note: 10.3.0.0/24 now has LOCAL_PREF=200 (preferred exit via R3)

==============================================================
  PHASE 3: AS_PATH Prepending
  R3 prepends its own ASN twice when advertising to R2
==============================================================

  BGP Table for R2 (AS 65002)
  ...
> 10.3.0.0/24            100  AS_PATH=[65003, 65003, 65003]  from=R3

  Note: 10.3.0.0/24 AS_PATH = [65003 65003 65003] — 3 hops vs 1
  If R2 had a shorter path to 10.3.0.0/24 it would prefer it.
```

## Common issues

- **Issue**: Routes not appearing in all three tables after Phase 1 — **Fix**: BGP route propagation requires two rounds (R2 must first receive from R1 and R3 before re-advertising to the other side). The simulation runs two passes; if you modify the code, ensure both passes complete.
- **Issue**: Best path marker `>` missing on some routes — **Fix**: The decision process runs automatically on `receive_update`. Verify `_run_decision_process` is called and that at least one route per prefix has `best=True`.

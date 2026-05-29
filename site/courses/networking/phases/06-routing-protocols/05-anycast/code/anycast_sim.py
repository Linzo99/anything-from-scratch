# Run: python3 anycast_sim.py
"""
Anycast Routing Simulation
Simulates anycast — multiple servers advertising the same IP prefix
from different locations. Shows how a client in different "regions"
gets routed to the topologically nearest server based on BGP path selection.

Topology:
  Client-West  ──── Router-West  ──── AnycastNode-A  (announces 10.9.9.0/24)
  Client-East  ──── Router-East  ──── AnycastNode-B  (announces 10.9.9.0/24)

Both AnycastNode-A and AnycastNode-B advertise the same prefix 10.9.9.0/24.
BGP best-path selection (shorter AS_PATH) routes each client to the closer node.

Demonstrates:
  1. Normal operation: each client reaches its local anycast node
  2. Failover: when AnycastNode-A goes down, Client-West fails over to Node-B
"""

from dataclasses import dataclass, field
from typing import Optional
import copy

# ── BGP Route ────────────────────────────────────────────────────────────────

@dataclass
class BGPRoute:
    prefix:     str
    as_path:    list
    local_pref: int = 100
    next_hop:   str = ""
    via_router: str = ""
    best:       bool = False

    @property
    def as_path_len(self) -> int:
        return len(self.as_path)

    def __repr__(self) -> str:
        mark = ">" if self.best else " "
        path = " ".join(str(a) for a in self.as_path) or "(local)"
        return f"  {mark} {self.prefix:<22} LP={self.local_pref:>3}  AS_PATH=[{path}]  via={self.via_router}"


# ── BGP Node ─────────────────────────────────────────────────────────────────

class BGPNode:
    def __init__(self, name: str, asn: int, owned_prefixes: list):
        self.name     = name
        self.asn      = asn
        self.table:   list = []
        self.peers:   dict = {}  # name -> asn

        for pfx in owned_prefixes:
            self.table.append(BGPRoute(
                prefix     = pfx,
                as_path    = [],
                local_pref = 100,
                next_hop   = "self",
                via_router = "self",
                best       = True,
            ))

    def add_peer(self, name: str, asn: int) -> None:
        self.peers[name] = asn

    def withdraw_prefix(self, prefix: str) -> None:
        """Simulate BGP WITHDRAW — remove all routes for this prefix."""
        self.table = [r for r in self.table if r.prefix != prefix]

    def receive_route(self, route: BGPRoute, from_name: str,
                      local_pref_override: int = None) -> None:
        # Loop prevention: skip if our own ASN is in the AS_PATH
        if self.asn in route.as_path:
            return
        r = copy.deepcopy(route)
        r.via_router = from_name
        r.best       = False
        if local_pref_override is not None:
            r.local_pref = local_pref_override
        self.table.append(r)
        self._select_best()

    def advertise_to(self, peer_name: str, peer_asn: int) -> list:
        """Return best routes to advertise to a peer (prepend our ASN)."""
        updates = []
        for r in self.table:
            if not r.best:
                continue
            if peer_asn in r.as_path:
                continue  # loop prevention
            exported = copy.deepcopy(r)
            exported.as_path    = [self.asn] + list(r.as_path)
            exported.next_hop   = self.name
            exported.via_router = self.name
            exported.best       = False
            updates.append(exported)
        return updates

    def best_route(self, prefix: str) -> Optional[BGPRoute]:
        for r in self.table:
            if r.prefix == prefix and r.best:
                return r
        return None

    def _select_best(self) -> None:
        by_prefix: dict = {}
        for r in self.table:
            by_prefix.setdefault(r.prefix, []).append(r)
        for r in self.table:
            r.best = False
        for pfx, candidates in by_prefix.items():
            best = min(candidates, key=lambda r: (-r.local_pref, r.as_path_len))
            best.best = True

    def print_table(self) -> None:
        print(f"  BGP Table — {self.name} (AS {self.asn}):")
        for r in sorted(self.table, key=lambda r: r.prefix):
            print(r)
        print()


# ── Simulation ────────────────────────────────────────────────────────────────

def build_and_run() -> None:
    print()
    print("Anycast Routing Simulation")
    print("Same prefix 10.9.9.0/24 announced from two locations")
    print()
    print("Topology:")
    print("  Client-West ── Router-West (AS65001) ── AnycastNode-A (AS65010)")
    print("  Client-East ── Router-East (AS65002) ── AnycastNode-B (AS65010)")
    print()
    print("AnycastNode-A and AnycastNode-B share AS 65010 and both announce")
    print("10.9.9.0/24 — the anycast prefix.")
    print()

    # Create nodes
    client_w = BGPNode("Client-West", 65000, [])
    client_e = BGPNode("Client-East", 65000, [])  # same ASN — they're one org
    router_w = BGPNode("Router-West", 65001, [])
    router_e = BGPNode("Router-East", 65002, [])
    anyA     = BGPNode("AnycastNode-A", 65010, ["10.9.9.0/24"])
    anyB     = BGPNode("AnycastNode-B", 65010, ["10.9.9.0/24"])

    # Establish peers
    client_w.add_peer("Router-West", 65001)
    client_e.add_peer("Router-East", 65002)
    router_w.add_peer("Client-West", 65000)
    router_w.add_peer("AnycastNode-A", 65010)
    router_e.add_peer("Client-East", 65000)
    router_e.add_peer("AnycastNode-B", 65010)

    # ── Phase 1: Route propagation ────────────────────────────────────────────
    print("=" * 60)
    print("  PHASE 1: Route propagation")
    print("=" * 60)

    # AnycastNode-A advertises to Router-West
    for r in anyA.advertise_to("Router-West", 65001):
        router_w.receive_route(r, "AnycastNode-A")

    # AnycastNode-B advertises to Router-East
    for r in anyB.advertise_to("Router-East", 65002):
        router_e.receive_route(r, "AnycastNode-B")

    # Router-West advertises to Client-West (LOCAL_PREF 200 — prefer west path)
    for r in router_w.advertise_to("Client-West", 65000):
        client_w.receive_route(r, "Router-West", local_pref_override=200)

    # Router-East also sends to Client-West (but Client-West is in same AS 65000)
    # Simulating a cross-connection path via AS65002 (longer path)
    for r in router_e.advertise_to("Client-West", 65000):
        # This would normally go through another hop — add Router-East ASN
        r.as_path = [65002] + r.as_path
        client_w.receive_route(r, "Router-East", local_pref_override=100)

    # Router-East advertises to Client-East (LOCAL_PREF 200 — prefer east path)
    for r in router_e.advertise_to("Client-East", 65000):
        client_e.receive_route(r, "Router-East", local_pref_override=200)

    # Router-West also sends to Client-East (longer path)
    for r in router_w.advertise_to("Client-East", 65000):
        r.as_path = [65001] + r.as_path
        client_e.receive_route(r, "Router-West", local_pref_override=100)

    print()
    client_w.print_table()
    client_e.print_table()

    # Determine which anycast node each client reaches
    best_w = client_w.best_route("10.9.9.0/24")
    best_e = client_e.best_route("10.9.9.0/24")

    print("  Anycast routing result:")
    if best_w:
        hops = " → ".join(str(a) for a in best_w.as_path)
        print(f"  Client-West → 10.9.9.1 routes via: {best_w.via_router}  (AS_PATH: [{hops}])")
        reached = "AnycastNode-A" if "65001" in hops or "Router-West" in best_w.via_router else "AnycastNode-B"
        print(f"    => REACHES: {reached}")
    if best_e:
        hops = " → ".join(str(a) for a in best_e.as_path)
        print(f"  Client-East → 10.9.9.1 routes via: {best_e.via_router}  (AS_PATH: [{hops}])")
        reached = "AnycastNode-B" if "65002" in hops or "Router-East" in best_e.via_router else "AnycastNode-A"
        print(f"    => REACHES: {reached}")

    # ── Phase 2: Failover ─────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  PHASE 2: Failover — AnycastNode-A goes offline")
    print("  BGP WITHDRAW sent for 10.9.9.0/24")
    print("=" * 60)
    print()

    # AnycastNode-A withdraws its prefix
    anyA.withdraw_prefix("10.9.9.0/24")

    # Router-West propagates the withdrawal to Client-West
    # (remove routes learned via Router-West from AnycastNode-A)
    client_w.table = [
        r for r in client_w.table
        if not (r.prefix == "10.9.9.0/24" and r.via_router == "Router-West")
    ]
    client_w._select_best()

    best_after = client_w.best_route("10.9.9.0/24")
    print("  Client-West BGP table after AnycastNode-A withdrawal:")
    client_w.print_table()

    if best_after:
        hops = " → ".join(str(a) for a in best_after.as_path)
        print(f"  Client-West now routes 10.9.9.1 via: {best_after.via_router}")
        print(f"  AS_PATH: [{hops}]")
        print(f"  => FAILOVER SUCCESSFUL: traffic now reaches AnycastNode-B")
    else:
        print("  ERROR: no route to 10.9.9.0/24 after failover")

    print()
    print("Key insight: No application change, no DNS change, no operator action needed.")
    print("BGP reconvergence automatically reroutes traffic to the surviving node.")
    print()


if __name__ == "__main__":
    build_and_run()

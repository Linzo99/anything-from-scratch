# Run: python3 bgp_sim.py
"""
BGP Path Selection Simulation
Simulates BGP between 3 autonomous systems (ASes).

Topology:
  AS 65001 (R1) ──eBGP── AS 65002 (R2) ──eBGP── AS 65003 (R3)
                          │
                 also has iBGP session within AS 65002 (not shown)

Each AS advertises its own prefixes.
Demonstrates:
  - eBGP peering and route exchange
  - AS_PATH attribute accumulation
  - Best-path selection: shortest AS_PATH
  - LOCAL_PREF influence (within an AS)
  - AS_PATH prepending
"""

from dataclasses import dataclass, field
from typing import Optional
import copy

# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class BGPRoute:
    """One entry in a BGP table."""
    prefix:       str
    as_path:      list        # list of ASN ints, left = most recent
    local_pref:   int = 100   # default LOCAL_PREF
    origin:       str = "IGP" # IGP | EGP | incomplete
    med:          int = 0
    next_hop:     str = ""
    learned_from: str = ""    # peer name
    best:         bool = False

    @property
    def as_path_len(self) -> int:
        return len(self.as_path)

    def __str__(self) -> str:
        best_marker = ">" if self.best else " "
        path_str = " ".join(str(a) for a in self.as_path) if self.as_path else "local"
        return (
            f"  {best_marker} {self.prefix:<22} "
            f"LP={self.local_pref:>3}  "
            f"AS_PATH=[{path_str}]  "
            f"ORIGIN={self.origin}  "
            f"from={self.learned_from or 'self'}"
        )


@dataclass
class BGPPeer:
    """eBGP or iBGP peer relationship."""
    name:       str
    asn:        int
    peer_type:  str  # "eBGP" or "iBGP"


class AS:
    """Represents one Autonomous System running BGP."""

    def __init__(self, name: str, asn: int, prefixes: list):
        self.name     = name
        self.asn      = asn
        self.prefixes = prefixes  # list of str (CIDR prefixes this AS owns)
        self.peers:   dict = {}   # { peer_name: BGPPeer }
        self.bgp_table: list = [] # list of BGPRoute

        # Install locally originated routes
        for pfx in self.prefixes:
            self.bgp_table.append(BGPRoute(
                prefix       = pfx,
                as_path      = [],            # locally originated = empty AS_PATH
                local_pref   = 100,
                next_hop     = "0.0.0.0",
                learned_from = "self",
                best         = True,
            ))

    def add_peer(self, peer_name: str, peer_asn: int, peer_type: str = "eBGP") -> None:
        self.peers[peer_name] = BGPPeer(peer_name, peer_asn, peer_type)

    def receive_update(self, route: BGPRoute, from_peer: str, local_pref_override: int = None) -> None:
        """
        Process an incoming BGP UPDATE from a peer.
        Applies standard eBGP processing:
          - Prepend the sending AS's ASN to AS_PATH
          - Apply LOCAL_PREF (default 100, or override)
          - Add to BGP table
        """
        new_route = copy.deepcopy(route)
        new_route.learned_from = from_peer

        peer = self.peers.get(from_peer)
        if peer and peer.peer_type == "eBGP":
            # eBGP: sender's ASN is already in AS_PATH from the sender's side
            # (the sender prepends its own ASN before advertising)
            pass  # AS_PATH already updated by sender in send_updates()

        if local_pref_override is not None:
            new_route.local_pref = local_pref_override

        new_route.best = False
        self.bgp_table.append(new_route)
        self._run_decision_process()

    def send_updates(self, to_peer_asn: int) -> list:
        """
        Generate UPDATE messages for a peer.
        For eBGP: prepend our own ASN to AS_PATH for each best route.
        For iBGP: do NOT prepend (iBGP leaves AS_PATH unchanged).
        Returns list of BGPRoute objects to send.
        """
        updates = []
        for route in self.bgp_table:
            if not route.best:
                continue
            # Loop prevention: don't advertise routes whose AS_PATH contains the peer's ASN
            if to_peer_asn in route.as_path:
                continue
            exported = copy.deepcopy(route)
            exported.as_path = [self.asn] + list(route.as_path)
            exported.next_hop = f"AS{self.asn}"
            updates.append(exported)
        return updates

    def _run_decision_process(self) -> None:
        """
        Run BGP best-path selection for each prefix.
        Simplified decision process (subset of RFC 4271):
          1. Highest LOCAL_PREF (local to this AS)
          2. Shortest AS_PATH
          3. Lowest ORIGIN (IGP=0 < EGP=1 < incomplete=2)
          4. Lowest MED
        """
        # Group routes by prefix
        by_prefix: dict = {}
        for route in self.bgp_table:
            by_prefix.setdefault(route.prefix, []).append(route)

        # Clear all best flags
        for route in self.bgp_table:
            route.best = False

        # Select best for each prefix
        for prefix, candidates in by_prefix.items():
            origin_order = {"IGP": 0, "EGP": 1, "incomplete": 2}

            def sort_key(r: BGPRoute):
                return (
                    -r.local_pref,        # highest LOCAL_PREF wins  (negate for min-sort)
                    r.as_path_len,        # shortest AS_PATH
                    origin_order.get(r.origin, 2),
                    r.med,
                )

            best = min(candidates, key=sort_key)
            best.best = True

    def print_bgp_table(self) -> None:
        print(f"\n  BGP Table for {self.name} (AS {self.asn})")
        print(f"  {'Pfx':<22} {'LP':>3}  AS_PATH                    From")
        print(f"  {'-'*22} {'-'*3}  {'-'*26}  {'-'*10}")
        for route in sorted(self.bgp_table, key=lambda r: r.prefix):
            print(route)
        print()


# ── Simulation ────────────────────────────────────────────────────────────────

def run_simulation() -> None:
    print()
    print("BGP Path Selection Simulation")
    print("3 Autonomous Systems with eBGP peering")
    print()
    print("Topology:")
    print("  AS 65001 (R1) ──eBGP── AS 65002 (R2) ──eBGP── AS 65003 (R3)")
    print()

    # Create the three ASes
    r1 = AS("R1", 65001, ["10.1.0.0/24"])
    r2 = AS("R2", 65002, ["10.2.0.0/24"])
    r3 = AS("R3", 65003, ["10.3.0.0/24"])

    # Establish eBGP peerings
    r1.add_peer("R2", 65002, "eBGP")
    r2.add_peer("R1", 65001, "eBGP")
    r2.add_peer("R3", 65003, "eBGP")
    r3.add_peer("R2", 65002, "eBGP")

    # ── Phase 1: Initial eBGP route exchange ──────────────────────────────────
    print("=" * 62)
    print("  PHASE 1: Initial eBGP route exchange")
    print("=" * 62)

    # R1 sends its prefix to R2
    for update in r1.send_updates(to_peer_asn=65002):
        r2.receive_update(update, from_peer="R1")

    # R2 sends its prefix to R1 and R3
    for update in r2.send_updates(to_peer_asn=65001):
        r1.receive_update(update, from_peer="R2")
    for update in r2.send_updates(to_peer_asn=65003):
        r3.receive_update(update, from_peer="R2")

    # R3 sends its prefix to R2
    for update in r3.send_updates(to_peer_asn=65002):
        r2.receive_update(update, from_peer="R3")

    # R2 now re-advertises R3's prefix to R1, and R1's prefix to R3
    for update in r2.send_updates(to_peer_asn=65001):
        r1.receive_update(update, from_peer="R2")
    for update in r2.send_updates(to_peer_asn=65003):
        r3.receive_update(update, from_peer="R2")

    r1.print_bgp_table()
    r2.print_bgp_table()
    r3.print_bgp_table()

    # ── Phase 2: Demonstrate LOCAL_PREF ──────────────────────────────────────
    print("=" * 62)
    print("  PHASE 2: LOCAL_PREF demonstration")
    print("  R2 sets LOCAL_PREF=200 on routes received from R3")
    print("=" * 62)

    # Reset R2's BGP table to only its local routes
    r2.bgp_table = [r for r in r2.bgp_table if r.learned_from == "self"]

    # Re-receive from R1 with default LOCAL_PREF (100)
    for update in r1.send_updates(to_peer_asn=65002):
        r2.receive_update(update, from_peer="R1", local_pref_override=100)

    # Re-receive from R3 with elevated LOCAL_PREF (200)
    for update in r3.send_updates(to_peer_asn=65002):
        r2.receive_update(update, from_peer="R3", local_pref_override=200)

    r2.print_bgp_table()
    print("  Note: 10.3.0.0/24 now has LOCAL_PREF=200 (preferred exit via R3)")

    # ── Phase 3: AS_PATH Prepending ───────────────────────────────────────────
    print()
    print("=" * 62)
    print("  PHASE 3: AS_PATH Prepending")
    print("  R3 prepends its own ASN twice when advertising to R2")
    print("  This makes R3's prefix look less preferred from R2's view")
    print("=" * 62)

    # Build a prepended route from R3
    prepended_route = BGPRoute(
        prefix       = "10.3.0.0/24",
        as_path      = [65003, 65003, 65003],  # prepended: 65003 65003 65003
        local_pref   = 100,
        next_hop     = "AS65003",
        learned_from = "R3",
        best         = False,
    )

    # Reset R2 again for a clean demonstration
    r2.bgp_table = [r for r in r2.bgp_table if r.learned_from == "self"]
    for update in r1.send_updates(to_peer_asn=65002):
        r2.receive_update(update, from_peer="R1")
    r2.receive_update(prepended_route, from_peer="R3")

    r2.print_bgp_table()
    print("  Note: 10.3.0.0/24 AS_PATH = [65003 65003 65003] — 3 hops vs 1")
    print("  If R2 had a shorter path to 10.3.0.0/24 it would prefer it.")
    print()


if __name__ == "__main__":
    run_simulation()

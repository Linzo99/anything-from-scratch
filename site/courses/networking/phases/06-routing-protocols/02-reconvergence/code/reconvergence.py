# Run: python3 reconvergence.py
"""
OSPF Reconvergence Simulation
Extends the OSPF link-state simulation by simulating a link failure.

Shows:
  1. Initial routing table (before failure)
  2. ASCII topology diagram (before and after)
  3. LSA flood log triggered by the link failure
  4. Reconvergence: new routing table after the failure

Topology (initial):
         1         2         5
  A ─────── B ─────── C ─────── E
            │         │
          3 │       1 │
            │         │
            D ────────┘
                 4

Failure scenario: link B–C goes down.
After failure, B must route to C and E via D.
"""
import heapq
import copy
import time

# ── Topology ──────────────────────────────────────────────────────────────────

TOPOLOGY_BEFORE = {
    "A": [("B", 1)],
    "B": [("A", 1), ("C", 2), ("D", 3)],
    "C": [("B", 2), ("D", 4), ("E", 5)],
    "D": [("B", 3), ("C", 4)],
    "E": [("C", 5)],
}

# After B–C link failure:
TOPOLOGY_AFTER = {
    "A": [("B", 1)],
    "B": [("A", 1), ("D", 3)],          # B–C link removed
    "C": [("D", 4), ("E", 5)],          # C–B link removed
    "D": [("B", 3), ("C", 4)],
    "E": [("C", 5)],
}

NODES = sorted(TOPOLOGY_BEFORE.keys())
FAILED_LINK = ("B", "C")


# ── Dijkstra ──────────────────────────────────────────────────────────────────

def dijkstra(lsdb: dict, source: str) -> tuple:
    dist = {n: float("inf") for n in lsdb}
    prev = {n: None for n in lsdb}
    dist[source] = 0
    pq = [(0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, cost in lsdb[u]:
            alt = dist[u] + cost
            if alt < dist[v]:
                dist[v] = alt
                prev[v] = u
                heapq.heappush(pq, (alt, v))
    return dist, prev


def reconstruct_path(prev, source, dest):
    path, node = [], dest
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path if path and path[0] == source else []


def next_hop(prev, source, dest):
    if source == dest:
        return "—"
    path = reconstruct_path(prev, source, dest)
    return path[1] if len(path) >= 2 else "unreachable"


# ── Routing table builders ────────────────────────────────────────────────────

def build_all_routing_tables(lsdb: dict) -> dict:
    """Return {router: [(dest, cost, nexthop, path), ...]}"""
    tables = {}
    for router in sorted(lsdb.keys()):
        dist, prev = dijkstra(lsdb, router)
        rows = []
        for dest in sorted(lsdb.keys()):
            if dest == router:
                continue
            cost = dist[dest]
            nh   = next_hop(prev, router, dest)
            path = " → ".join(reconstruct_path(prev, router, dest))
            rows.append((dest, cost, nh, path))
        tables[router] = rows
    return tables


def print_routing_tables(tables: dict, label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  ROUTING TABLES — {label}")
    print(f"{'='*60}")
    for router, rows in tables.items():
        print(f"\n  Router {router}:")
        print(f"  {'Dest':<6} {'Cost':>6}  {'NextHop':<10}  Path")
        print(f"  {'-'*6} {'-'*6}  {'-'*10}  {'-'*30}")
        for dest, cost, nh, path in rows:
            cost_str = str(cost) if cost != float("inf") else "∞"
            print(f"  {dest:<6} {cost_str:>6}  {nh:<10}  {path}")


# ── ASCII topology diagrams ───────────────────────────────────────────────────

DIAGRAM_BEFORE = """
  ASCII Topology BEFORE failure:

         1         2         5
  A ─────── B ─────── C ─────── E
            │         │
          3 │       1 │
            │         │
            D ─────────
                 4
"""

DIAGRAM_AFTER = """
  ASCII Topology AFTER failure (B–C link DOWN):

         1                   5
  A ─────── B    ✗    C ─────── E
            │         │
          3 │       1 │
            │         │
            D ─────────
                 4

  B–C link is severed. B now reaches C only via D.
  Path B→C: B → D → C  (cost 3+4=7, was 2)
  Path B→E: B → D → C → E  (cost 3+4+5=12, was 7)
"""


# ── LSA flood simulation ──────────────────────────────────────────────────────

def simulate_lsa_flood(failed_link: tuple, lsdb_before: dict, lsdb_after: dict) -> None:
    u, v = failed_link
    print(f"\n{'='*60}")
    print(f"  LSA FLOOD — link {u}–{v} failure detected")
    print(f"{'='*60}")

    # Both routers on the failed link detect the failure and re-originate their LSA
    for router in (u, v):
        old_links = sorted(lsdb_before[router])
        new_links = sorted(lsdb_after[router])
        removed = [l for l in old_links if l not in new_links]

        print(f"\n  t≈0ms  Router {router} detects link-down event")
        print(f"         Old LSA: {router} → {old_links}")
        print(f"         New LSA: {router} → {new_links}")
        print(f"         Removed links: {removed}")
        print(f"         ➜ Router {router} floods updated Router LSA (seq++ ) to all reachable neighbors")

    print()
    print("  t≈1ms  Updated LSAs propagate to all routers:")
    flooded = set()
    for router in sorted(lsdb_after.keys()):
        if router not in (u, v):
            flooded.add(router)
    for r in sorted(flooded):
        print(f"    Router {r} receives new LSAs, updates LSDB")

    print()
    print("  t≈2ms  All routers re-run SPF (Dijkstra) with updated LSDB")
    print("  t≈2ms  New routes installed via kernel (zebra → netlink)")
    print()
    print("  Total reconvergence time: ~2–5ms (carrier-loss, direct detection)")
    print("  (With default Dead Interval: same — interface-down is instant)")


# ── Diff routing tables ───────────────────────────────────────────────────────

def diff_routing_tables(before: dict, after: dict) -> None:
    print(f"\n{'='*60}")
    print(f"  CHANGES AFTER RECONVERGENCE")
    print(f"{'='*60}")
    changed = False
    for router in sorted(before.keys()):
        rows_before = {d: (c, nh, p) for d, c, nh, p in before[router]}
        rows_after  = {d: (c, nh, p) for d, c, nh, p in after[router]}
        for dest in sorted(rows_before.keys()):
            old = rows_before[dest]
            new = rows_after.get(dest, (float("inf"), "unreachable", ""))
            if old != new:
                changed = True
                print(f"  Router {router} → {dest}:")
                print(f"    BEFORE: cost={old[0]}  nexthop={old[1]}  {old[2]}")
                old_cost = new[0] if new[0] != float("inf") else "∞"
                print(f"    AFTER:  cost={old_cost}  nexthop={new[1]}  {new[2]}")
    if not changed:
        print("  (no routing table changes detected)")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("OSPF Reconvergence Simulation")
    print(f"Failure scenario: link {FAILED_LINK[0]}–{FAILED_LINK[1]} goes down")

    # Step 1: Before failure
    print(DIAGRAM_BEFORE)
    tables_before = build_all_routing_tables(TOPOLOGY_BEFORE)
    print_routing_tables(tables_before, "BEFORE FAILURE")

    # Simulate a brief delay to represent normal operation
    print("\n  ... network operating normally ...\n")

    # Step 2: Failure event + LSA flood
    simulate_lsa_flood(FAILED_LINK, TOPOLOGY_BEFORE, TOPOLOGY_AFTER)

    # Step 3: After reconvergence
    print(DIAGRAM_AFTER)
    tables_after = build_all_routing_tables(TOPOLOGY_AFTER)
    print_routing_tables(tables_after, "AFTER RECONVERGENCE")

    # Step 4: Show what changed
    diff_routing_tables(tables_before, tables_after)


if __name__ == "__main__":
    main()

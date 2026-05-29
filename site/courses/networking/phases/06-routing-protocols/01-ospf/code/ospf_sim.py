# Run: python3 ospf_sim.py
"""
OSPF Link-State Routing Simulation
Simulates OSPF on a 5-node hardcoded topology.
Implements Dijkstra's algorithm, prints the link-state database (LSDB)
and the resulting routing table for each node.

Topology:
         1         2         5
  A ─────── B ─────── C ─────── E
            │         │
          3 │       1 │
            │         │
            D ────────┘
                 4

Node  |  Links (neighbor, cost)
────────────────────────────────
A     |  B:1
B     |  A:1, C:2, D:3
C     |  B:2, D:4, E:5
D     |  B:3, C:4
E     |  C:5
"""
import heapq

# ── Topology definition ───────────────────────────────────────────────────────
# Adjacency list: { node: [(neighbor, cost), ...] }
TOPOLOGY = {
    "A": [("B", 1)],
    "B": [("A", 1), ("C", 2), ("D", 3)],
    "C": [("B", 2), ("D", 4), ("E", 5)],
    "D": [("B", 3), ("C", 4)],
    "E": [("C", 5)],
}
NODES = sorted(TOPOLOGY.keys())


# ── Link State Database ───────────────────────────────────────────────────────

def build_lsdb(topology: dict) -> dict:
    """
    Build the Link State Database (LSDB).
    In OSPF, each router floods an LSA describing its own links.
    Every router ends up with the same LSDB.

    Returns: { router_id: [(neighbor, cost), ...] }
    """
    return {node: sorted(links) for node, links in topology.items()}


def print_lsdb(lsdb: dict) -> None:
    print("=" * 56)
    print("  LINK STATE DATABASE (LSDB)")
    print("  (identical on every router — flooded network-wide)")
    print("=" * 56)
    for router_id in sorted(lsdb.keys()):
        links = lsdb[router_id]
        link_str = "  ".join(f"{nbr}(cost={cost})" for nbr, cost in links)
        print(f"  Router {router_id}:  {link_str}")
    print()


# ── Dijkstra's Shortest Path Algorithm ───────────────────────────────────────

def dijkstra(lsdb: dict, source: str) -> tuple:
    """
    Run Dijkstra's algorithm from 'source' using the LSDB as the graph.

    Returns:
        dist    — { node: shortest_distance }
        prev    — { node: previous_node_on_shortest_path }
    """
    dist = {node: float("inf") for node in lsdb}
    prev = {node: None for node in lsdb}
    dist[source] = 0

    # Priority queue: (distance, node)
    pq = [(0, source)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue  # stale entry

        for v, cost in lsdb[u]:
            alt = dist[u] + cost
            if alt < dist[v]:
                dist[v] = alt
                prev[v] = u
                heapq.heappush(pq, (alt, v))

    return dist, prev


def reconstruct_path(prev: dict, source: str, dest: str) -> list:
    """Trace back through 'prev' to build the full path from source to dest."""
    path = []
    node = dest
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    if path and path[0] == source:
        return path
    return []  # no path found


def next_hop(prev: dict, source: str, dest: str) -> str:
    """Return the first hop from source toward dest."""
    if source == dest:
        return "—"
    path = reconstruct_path(prev, source, dest)
    if len(path) < 2:
        return "unreachable"
    return path[1]


# ── Routing Table ─────────────────────────────────────────────────────────────

def build_routing_table(lsdb: dict, router: str) -> list:
    """
    Compute the SPF (Shortest Path First) routing table for 'router'.
    Returns list of (destination, cost, next_hop, full_path).
    """
    dist, prev = dijkstra(lsdb, router)
    table = []
    for dest in sorted(lsdb.keys()):
        if dest == router:
            continue
        cost = dist[dest]
        nh   = next_hop(prev, router, dest)
        path = " → ".join(reconstruct_path(prev, router, dest))
        table.append((dest, cost, nh, path))
    return table


def print_routing_table(router: str, table: list) -> None:
    print(f"  Router {router}  — SPF Routing Table")
    print(f"  {'Destination':<14} {'Cost':>6}  {'Next Hop':<10}  Path")
    print(f"  {'-'*14} {'-'*6}  {'-'*10}  {'-'*30}")
    for dest, cost, nh, path in table:
        cost_str = str(cost) if cost != float("inf") else "∞"
        print(f"  {dest:<14} {cost_str:>6}  {nh:<10}  {path}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("OSPF Link-State Routing Simulation")
    print("Topology: A-B-C-D-E (see file header for diagram)")
    print()

    lsdb = build_lsdb(TOPOLOGY)
    print_lsdb(lsdb)

    print("=" * 56)
    print("  SPF ROUTING TABLES (computed by each router independently)")
    print("=" * 56)
    print()
    for router in NODES:
        table = build_routing_table(lsdb, router)
        print_routing_table(router, table)

    # Extra: show the full shortest-path tree from A
    print("=" * 56)
    print("  SHORTEST PATH TREE rooted at A")
    print("=" * 56)
    dist, prev = dijkstra(lsdb, "A")
    for dest in sorted(NODES):
        if dest == "A":
            continue
        path = reconstruct_path(prev, "A", dest)
        print(f"  A → {dest}: cost={dist[dest]}  path={' → '.join(path)}")
    print()


if __name__ == "__main__":
    main()

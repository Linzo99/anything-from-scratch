# Run: python3 rip_sim.py
"""
RIP Distance-Vector Routing Simulation
Simulates RIP on a 4-node linear network without real UDP sockets.
Shows the routing table evolving over rounds (Bellman-Ford updates),
and demonstrates count-to-infinity with split horizon as the fix.

Topology:
  [A] ── [B] ── [C] ── [D]

All link costs are 1 (hop count, as in real RIP).
Maximum metric: 16 (infinity).

Run: python3 rip_sim.py
"""

import copy

# ── Constants ────────────────────────────────────────────────────────────────
RIP_INFINITY    = 16
UPDATE_INTERVAL = 1   # simulated rounds (not real seconds)

# 4-node linear topology: { node: [neighbors] }
NEIGHBORS = {
    "A": ["B"],
    "B": ["A", "C"],
    "C": ["B", "D"],
    "D": ["C"],
}
NODES = list(NEIGHBORS.keys())

# Each node's "prefix" (the network it directly owns)
OWN_PREFIX = {
    "A": "192.168.1.0/24",
    "B": "192.168.2.0/24",
    "C": "192.168.3.0/24",
    "D": "192.168.4.0/24",
}


# ── Routing Table ────────────────────────────────────────────────────────────

def initial_table(node: str) -> dict:
    """
    Each node starts knowing only its own directly connected prefix (metric 1).
    All other destinations are infinity.
    """
    table = {}
    for n in NODES:
        if n == node:
            table[OWN_PREFIX[n]] = {"metric": 1, "via": None}
        else:
            table[OWN_PREFIX[n]] = {"metric": RIP_INFINITY, "via": None}
    return table


def print_table(node: str, table: dict, round_num: int) -> None:
    """Print a node's routing table."""
    print(f"  [{node}] Round {round_num}:")
    for prefix in sorted(table.keys()):
        entry  = table[prefix]
        metric = entry["metric"]
        via    = entry["via"] or "direct"
        m_str  = str(metric) if metric < RIP_INFINITY else "∞"
        mark   = "*" if metric < RIP_INFINITY else " "
        print(f"    {mark} {prefix:<22}  metric={m_str:<3}  via={via}")
    print()


def print_all_tables(tables: dict, round_num: int, label: str = "") -> None:
    heading = f"Round {round_num}" + (f" — {label}" if label else "")
    print(f"\n{'='*54}")
    print(f"  {heading}")
    print(f"{'='*54}")
    for node in NODES:
        print_table(node, tables[node], round_num)


# ── Bellman-Ford Update ───────────────────────────────────────────────────────

def bellman_ford_round(tables: dict, split_horizon: bool = True) -> tuple:
    """
    One round of Bellman-Ford: each node sends its table to neighbors,
    and neighbors update their own tables if a better route is found.

    With split_horizon=True: a route learned from neighbor X is NOT advertised
    back to X (prevents simple routing loops).

    Returns: (new_tables, changed) where changed=True if any table changed.
    """
    new_tables = copy.deepcopy(tables)
    changed    = False

    for node in NODES:
        for neighbor in NEIGHBORS[node]:
            # Build the advertisement this node sends to 'neighbor'
            for prefix, entry in tables[node].items():
                # Split horizon: don't advertise back the route we learned from this neighbor
                if split_horizon and entry["via"] == neighbor:
                    continue

                advertised_metric = entry["metric"]
                if advertised_metric >= RIP_INFINITY:
                    continue  # don't advertise unreachable routes

                received_metric = advertised_metric + 1  # +1 for the link cost

                current = new_tables[neighbor][prefix]
                if received_metric < current["metric"]:
                    new_tables[neighbor][prefix] = {
                        "metric": min(received_metric, RIP_INFINITY),
                        "via":    node,
                    }
                    changed = True

    return new_tables, changed


# ── Count-to-Infinity Demo ───────────────────────────────────────────────────

def count_to_infinity_demo(tables: dict) -> None:
    """
    Simulate count-to-infinity WITHOUT split horizon.
    Kill node D (set all routes to D's prefix to infinity on D itself).
    Then watch B and C count up to 16 for D's prefix.
    """
    print("\n" + "=" * 54)
    print("  COUNT-TO-INFINITY DEMO (split horizon DISABLED)")
    print("  Scenario: Node D goes offline")
    print("=" * 54)

    # Mark D's own prefix as unreachable from D's perspective
    tables["D"][OWN_PREFIX["D"]] = {"metric": RIP_INFINITY, "via": None}
    print("\n  t=0: D goes offline. D's own prefix 192.168.4.0/24 = ∞")
    print("       B and C still think they can reach D in 2 and 1 hops.\n")

    for round_num in range(1, 20):
        new_tables, changed = bellman_ford_round(tables, split_horizon=False)
        # Show just D's prefix metric at each node
        metrics = {n: tables[n][OWN_PREFIX["D"]]["metric"] for n in NODES}
        d_b = metrics["B"]
        d_c = metrics["C"]
        b_str = str(d_b) if d_b < RIP_INFINITY else "∞"
        c_str = str(d_c) if d_c < RIP_INFINITY else "∞"
        print(f"  Round {round_num:>2}: D's prefix metric — A:{metrics['A']}  B:{b_str}  C:{c_str}  D:{metrics['D']}")
        tables = new_tables
        if not changed or (metrics["B"] >= RIP_INFINITY and metrics["C"] >= RIP_INFINITY):
            break
    print()
    print("  B and C counted all the way to 16 (infinity) before giving up.")
    print("  This is the count-to-infinity problem.")


def split_horizon_demo(converged_tables: dict) -> None:
    """
    Demonstrate split horizon preventing count-to-infinity.
    """
    print("\n" + "=" * 54)
    print("  SPLIT HORIZON DEMO (split horizon ENABLED)")
    print("  Scenario: Node D goes offline")
    print("=" * 54)

    tables = copy.deepcopy(converged_tables)
    # Kill D
    tables["D"][OWN_PREFIX["D"]] = {"metric": RIP_INFINITY, "via": None}
    print("\n  t=0: D goes offline.\n")

    for round_num in range(1, 6):
        new_tables, changed = bellman_ford_round(tables, split_horizon=True)
        metrics = {n: tables[n][OWN_PREFIX["D"]]["metric"] for n in NODES}
        d_b = metrics["B"]
        d_c = metrics["C"]
        b_str = str(d_b) if d_b < RIP_INFINITY else "∞"
        c_str = str(d_c) if d_c < RIP_INFINITY else "∞"
        print(f"  Round {round_num:>2}: D's prefix metric — A:{metrics['A']}  B:{b_str}  C:{c_str}  D:{metrics['D']}")
        tables = new_tables
        if not changed:
            break
    print()
    print("  With split horizon, the route disappears quickly.")
    print("  C does NOT advertise D back to B (learned it FROM B), so B")
    print("  cannot form a counting loop. Route converges to ∞ in 1-2 rounds.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("RIP Distance-Vector Routing Simulation")
    print("Topology: A ── B ── C ── D  (linear, all costs = 1)")
    print()

    # Initialize tables
    tables = {node: initial_table(node) for node in NODES}
    print_all_tables(tables, 0, "Initial state (each node knows only its own prefix)")

    # Run Bellman-Ford rounds until convergence
    round_num = 0
    while True:
        round_num += 1
        tables, changed = bellman_ford_round(tables, split_horizon=True)
        print_all_tables(tables, round_num)
        if not changed:
            print(f"\n  Converged after {round_num} rounds.")
            print("  (In real RIP: 30-second periodic updates would continue)")
            break
        if round_num > 20:
            print("  ERROR: Did not converge after 20 rounds!")
            break

    # Save converged tables for demos
    converged = copy.deepcopy(tables)

    # Count-to-infinity demo (without split horizon)
    cti_tables = copy.deepcopy(converged)
    count_to_infinity_demo(cti_tables)

    # Split horizon fix
    split_horizon_demo(converged)

    print()
    print("Summary:")
    print("  Without split horizon: count-to-infinity — takes up to 16 rounds")
    print("  With split horizon:    fast convergence — 1-2 rounds after failure")
    print()


if __name__ == "__main__":
    main()

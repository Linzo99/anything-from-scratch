# Run: python load_balancer.py
# Simulated load balancer comparing round-robin, weighted, and least-connections.
from dataclasses import dataclass


@dataclass
class Backend:
    name: str
    weight: int = 1
    healthy: bool = True
    active_connections: int = 0
    total_handled: int = 0


class RoundRobin:
    def __init__(self, backends):
        self.backends = backends
        self._i = 0

    def pick(self):
        healthy = [b for b in self.backends if b.healthy]
        b = healthy[self._i % len(healthy)]
        self._i += 1
        return b


class LeastConnections:
    def __init__(self, backends):
        self.backends = backends

    def pick(self):
        healthy = [b for b in self.backends if b.healthy]
        return min(healthy, key=lambda b: b.active_connections)


class Weighted:
    def __init__(self, backends):
        self.backends = backends
        # expand by weight: weight 3 -> appears 3 times
        self.pool = [b for b in backends for _ in range(b.weight)]
        self._i = 0

    def pick(self):
        healthy = [b for b in self.pool if b.healthy]
        b = healthy[self._i % len(healthy)]
        self._i += 1
        return b


def fresh():
    return [Backend("A", weight=1), Backend("B", weight=1), Backend("C", weight=3)]


def simulate(name, lb, n=1200):
    for _ in range(n):
        lb.pick().total_handled += 1
    print(f"\n=== {name} ({n} requests) ===")
    for b in lb.backends:
        pct = 100 * b.total_handled / n
        print(f"  {b.name:8} weight={b.weight}  handled={b.total_handled:5}  ({pct:4.1f}%)")


simulate("Round-robin (ignores weight)", RoundRobin(fresh()))
simulate("Weighted (C has weight 3)", Weighted(fresh()))

# Least-connections with a server that starts overloaded
backends = fresh()
backends[0].active_connections = 50  # A is busy
lc = LeastConnections(backends)
for _ in range(300):
    b = lc.pick()
    b.active_connections += 1
    b.total_handled += 1
print("\n=== Least-connections (A starts with 50 active) ===")
for b in backends:
    print(f"  {b.name:8} handled={b.total_handled:5}  final_active={b.active_connections}")

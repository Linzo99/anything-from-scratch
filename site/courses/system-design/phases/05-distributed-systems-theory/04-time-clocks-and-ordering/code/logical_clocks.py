# Run: python logical_clocks.py
# Lamport clocks (total order) and vector clocks (detect concurrency).


class LamportProcess:
    def __init__(self, pid):
        self.pid = pid
        self.clock = 0

    def local_event(self):
        self.clock += 1
        return self.clock

    def send(self):
        self.clock += 1
        return self.clock              # timestamp attached to message

    def receive(self, ts):
        self.clock = max(self.clock, ts) + 1
        return self.clock


def lamport_demo():
    p1, p2 = LamportProcess(1), LamportProcess(2)
    print("Lamport clocks:")
    a = p1.local_event()
    print(f"  P1 local event a -> L={a}")
    m = p1.send()
    print(f"  P1 sends m       -> L={m}")
    c = p2.receive(m)
    print(f"  P2 receives m    -> L={c} (max(0,{m})+1)")
    d = p2.local_event()
    print(f"  P2 local event d -> L={d}")
    print(f"  a→...→c holds: L(a)={a} < L(c)={c}  (causality respected)")


class VectorProcess:
    def __init__(self, pid, n):
        self.pid = pid
        self.vec = [0] * n

    def local_event(self):
        self.vec[self.pid] += 1
        return list(self.vec)

    def send(self):
        self.vec[self.pid] += 1
        return list(self.vec)

    def receive(self, other):
        self.vec = [max(a, b) for a, b in zip(self.vec, other)]
        self.vec[self.pid] += 1
        return list(self.vec)


def relation(v1, v2):
    le = all(a <= b for a, b in zip(v1, v2))
    ge = all(a >= b for a, b in zip(v1, v2))
    if le and not ge:
        return "a → b (a before b)"
    if ge and not le:
        return "b → a (b before a)"
    if le and ge:
        return "a == b"
    return "a ∥ b (CONCURRENT — conflict!)"


def vector_demo():
    print("\nVector clocks (3 processes):")
    p0, p1, p2 = VectorProcess(0, 3), VectorProcess(1, 3), VectorProcess(2, 3)
    a = p0.local_event()
    print(f"  P0 event a: {a}")
    msg = p0.send()
    print(f"  P0 sends:   {msg}")
    b = p1.receive(msg)
    print(f"  P1 recv->b: {b}  (knows of P0's event)")
    c = p2.local_event()
    print(f"  P2 event c: {c}  (independent)")
    print(f"\n  b vs c: {relation(b, c)}")
    print(f"  a vs b: {relation(a, b)}")


lamport_demo()
vector_demo()

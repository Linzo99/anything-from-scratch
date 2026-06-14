# Run: python idempotency.py
# At-least-once delivery causes duplicates; idempotent consumers absorb them.


class Account:
    def __init__(self, balance=0):
        self.balance = balance


def deliver_with_duplicates(messages):
    # Simulate at-least-once: messages marked dup are delivered twice.
    out = []
    for m in messages:
        out.append(m)
        if m.get("dup"):
            out.append(m)
    return out


def naive_consumer(messages):
    acct = Account(0)
    for m in deliver_with_duplicates(messages):
        acct.balance += m["amount"]          # NOT idempotent: adds every time
    return acct.balance


def idempotent_consumer(messages):
    acct = Account(0)
    seen = set()                             # durable/shared in production
    for m in deliver_with_duplicates(messages):
        key = m["id"]
        if key in seen:                      # already processed -> skip
            continue
        acct.balance += m["amount"]
        seen.add(key)
    return acct.balance


messages = [
    {"id": "tx1", "amount": 100},
    {"id": "tx2", "amount": 100, "dup": True},   # delivered twice
    {"id": "tx3", "amount": 100},
]

expected = 300
naive = naive_consumer(messages)
idem = idempotent_consumer(messages)

print("Three deposits of 100; tx2 is delivered twice (at-least-once).")
print(f"  Expected balance:            {expected}")
print(f"  Naive consumer (buggy):      {naive}   <- duplicate charge!")
print(f"  Idempotent consumer (dedup): {idem}   <- correct")

# Even if EVERY message is delivered 3x, the idempotent consumer is correct
heavy = []
for m in messages:
    heavy += [m, m, m]
acct = Account(0)
seen = set()
for m in heavy:
    if m["id"] in seen:
        continue
    acct.balance += m["amount"]
    seen.add(m["id"])
print(f"\nWith every message delivered 3x: idempotent balance = {acct.balance} (still 300)")

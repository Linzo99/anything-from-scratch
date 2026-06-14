<!-- Reference: the consistency spectrum and how to choose. -->

# Consistency Spectrum

## Strongest → weakest
```
Linearizability      acts like ONE copy; read sees latest completed write (real-time)
Sequential           one global order, not required to match real time
Causal               cause-before-effect everywhere; concurrent ops may differ
Read-your-writes }   client-centric: see your own writes;
Monotonic reads  }   never read backwards in time
Eventual             replicas converge eventually; reads may be stale
```
Down the list: less coordination, lower latency, more available — but more anomalies.

## Pick the WEAKEST model that keeps the app correct
| Data | Model |
|------|-------|
| Account balance, locks, leader | Linearizable (strong) |
| Comments where replies follow parent | Causal |
| Seeing your own new post | Read-your-writes |
| A live counter that shouldn't flicker down | Monotonic reads |
| View counts, presence, DNS | Eventual |

## Client-centric fixes (cheap)
- Read-your-writes → route your reads to a replica that has your write
- Monotonic reads → pin the client to one replica (or one ≥ as fresh)

## Eventual-consistency conflict resolution
- Last-write-wins (by timestamp) — simple, can lose data
- CRDTs — data types that merge concurrent updates with no conflict
- Application merge (e.g. union shopping carts)

## Gotchas
- Eventual ≠ wrong; it's temporarily divergent but GUARANTEED to converge.
- ACID "C" (constraints in a txn) ≠ distributed "C" (replicas agree).
- Don't default to strong "to be safe" — it costs latency + availability.

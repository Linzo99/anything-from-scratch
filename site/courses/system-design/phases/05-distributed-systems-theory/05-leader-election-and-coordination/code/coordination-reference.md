<!-- Reference: leader election, locks, and fencing with coordination services. -->

# Coordination Reference

## Why elect a leader?
One node "in charge" → single decision point → no conflicting actions / clean
ordering. Used by: single-leader replication, Raft, Kafka partitions, schedulers.
Failure mode to avoid: SPLIT-BRAIN (two leaders both acting).

## Coordination services (ZooKeeper / etcd)
Small, CP, consensus-backed stores. Use for FEW critical, low-volume facts:
- Leader election
- Distributed locks
- Cluster membership (who's alive)
- Consistent configuration / service discovery
NOT for: bulk data, high-volume writes, large blobs.

Primitives they give you:
- **Watches** — notify on key change
- **Ephemeral nodes** — auto-delete when the client session ends (liveness)
- **Atomic compare-and-set** — build locks/election

## Leader election (ephemeral sequenced nodes)
1. Each candidate creates /election/000N (ephemeral, sequenced)
2. Lowest sequence number = leader
3. Each node watches the one just ahead of it
4. Leader dies → its node vanishes → next-lowest is notified → becomes leader

## Distributed locks — and their danger
- Lock = atomically create a key; release = delete (or ephemeral vanishes)
- Use LEASES (expiring locks) so a crashed holder doesn't hold forever
- DANGER: a paused holder (GC) can overrun its lease → two holders

## Fencing token (the rigorous fix)
Each grant → monotonically increasing token. Resource records highest seen and
REJECTS lower tokens.
```
A gets token 33 → pauses (GC)
lease expires; B gets token 34, writes (resource records 34)
A wakes, writes with 33 → REJECTED (33 < 34)
```

## Gotchas
- Don't roll your own lock with a plain Redis key/DB row (misses fencing → split-brain).
- Don't store bulk data in ZK/etcd (every write needs a majority → bottleneck).
- Lease too short → false expiry; too long → slow failover. Tune deliberately.

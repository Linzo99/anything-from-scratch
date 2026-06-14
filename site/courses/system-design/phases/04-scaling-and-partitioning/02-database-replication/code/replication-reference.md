<!-- Reference: database replication models and pitfalls. -->

# Replication Reference

## Models
| Model | Writes to | Scales writes? | Conflicts? | Typical use |
|-------|-----------|----------------|------------|-------------|
| Single-leader | one leader | No | None | default relational |
| Multi-leader | many leaders | Yes | Yes (must reconcile) | multi-region, offline apps |
| Leaderless | any replica | Yes | Handled by quorum/versions | Cassandra, DynamoDB |

## Single-leader (the common case)
```
clients --writes--> LEADER --replication stream--> FOLLOWERS
clients --reads---------------------------------->  (any node)
```
- Scales READS (add followers). Does NOT scale WRITES (one leader).
- Write-heavy bottleneck? → shard (next lesson).

## Sync vs async
| | Sync | Async |
|---|------|-------|
| Leader waits for follower? | Yes | No |
| Write speed | Slow (slowest follower) | Fast |
| Data loss on leader crash | None | Possible (recent writes) |
| Causes lag? | No | Yes |
Most systems: async or semi-sync (wait for one follower).

## Read-after-write problem (the classic bug)
User writes → leader; immediate read → lagging follower → sees STALE value.
Fixes:
- Read your own recent writes from the LEADER
- Route read to a replica caught up to your write's version/timestamp
- Pin the user to the leader briefly after a write
Also: pin a user to ONE replica to get monotonic reads (no going backwards).

## Failover hazards
- Lost writes (async: writes not yet replicated vanish on promotion)
- Split-brain (two leaders) → prevent with quorum promotion + fencing
- False failure detection (slow ≠ dead) → don't fail over too eagerly

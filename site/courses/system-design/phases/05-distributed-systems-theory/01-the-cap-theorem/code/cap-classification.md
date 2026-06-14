<!-- Reference: applying CAP to real systems and decisions. -->

# CAP Cheat-Sheet

## The precise statement
> When a network partition occurs, a distributed system must choose between
> **Consistency** and **Availability**. Partition tolerance is mandatory.

When there's NO partition, you can have both C and A.

## The three properties
- **C** — every read returns the latest write or an error (linearizability)
- **A** — every request to a live node gets a non-error response
- **P** — keeps operating when nodes can't communicate (unavoidable → required)

## CP vs AP during a partition
| | CP | AP |
|---|---|---|
| Behavior | refuse/err to avoid stale data | answer with possibly-stale data |
| Sacrifices | availability | consistency |
| Examples | ZooKeeper, etcd, HBase, Spanner, MongoDB (default) | Cassandra, DynamoDB, Riak |

## Choose by data
| Data | Choice | Why |
|------|--------|-----|
| Account balance | CP | wrong value = real money lost |
| Cluster leader / locks | CP | two leaders = corruption (split-brain) |
| Likes / view counts | AP | brief staleness harmless |
| Shopping cart | AP | being down loses sales |
| Stock at checkout | CP-ish | oversell is costly |

## PACELC (the part CAP omits)
> if Partition: A or C; Else: Latency or Consistency.
Strong consistency costs coordination latency even with a healthy network.

## Gotchas
- "CA system" by dropping P is not real for a distributed system.
- Many systems are tunable PER OPERATION (e.g. Cassandra consistency levels),
  so the same DB can act CP for one query and AP for another.

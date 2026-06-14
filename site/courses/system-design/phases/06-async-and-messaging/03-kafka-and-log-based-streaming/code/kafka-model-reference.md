<!-- Reference: the log-based streaming model (Kafka). -->

# Kafka / Log-Streaming Reference

## The core idea
A topic is an APPEND-ONLY LOG. Records are immutable, ordered, and RETAINED
(not deleted on read). Consumers track their own OFFSET (read position).

```
offset:  0    1    2    3    4   <- producers append here
        [e]  [e]  [e]  [e]  [e]
consumer A reads up to offset 2; consumer B up to offset 4 — independent
```

## Queue vs Kafka log
| | Traditional queue | Kafka log |
|---|---|---|
| On consume | deleted/acked | retained |
| Replay history | no | yes (reset offset) |
| New late consumer | misses past | can read from 0 |
| Source of truth? | no (pipe) | yes (replayable record) |

## Partitions (sharding a stream)
- Topic split into N partitions, each an independent log on a broker.
- Throughput scales with partitions; partition = unit of parallelism.
- ORDER guaranteed only WITHIN a partition. Same key → same partition.
- Global order → 1 partition (loses parallelism).

## Consumer groups (queue + pub/sub in one)
- WITHIN a group: partitions split among consumers → queue (load-balanced).
- ACROSS groups: each group reads the full stream, own offsets → pub/sub (fan-out).

## What the retained log unlocks
- Replay (reprocess after a bug fix)
- Add consumers later (read from the beginning)
- Event sourcing (the log IS the source of truth; state = replay)
- Many materialized views (DB, search, cache) from one stream
- Time-decoupling (fast & slow consumers, same stream)

## When NOT to use Kafka
Simple "do this task async" → a regular queue is simpler and enough.
Kafka is operationally heavy; use it for retention, replay, high throughput,
or many independent consumers of one stream.

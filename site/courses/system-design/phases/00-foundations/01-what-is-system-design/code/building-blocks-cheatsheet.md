<!-- Reference: the standard building blocks of a large system. Keep this open while you design. -->

# Building Blocks Cheat-Sheet

| Box | Job | Add it when... | Covered in |
|-----|-----|----------------|------------|
| DNS | Resolve a name to an IP / load balancer | Always | Phase 1 |
| Load balancer | Spread requests across identical servers | You have >1 app server | Phase 1 |
| App server (stateless) | Run business logic | Always | Phase 4 |
| Cache | Serve hot reads without hitting the DB | Reads dominate; same data read often | Phase 3 |
| Database (replicated) | Source of truth | Always | Phases 2, 4 |
| Sharded database | Split data across nodes | One DB can't hold the writes/storage | Phase 4 |
| Message queue | Decouple slow work from the request | Work can be done async | Phase 6 |
| Object storage | Hold large blobs (images, video) | You store files, not rows | Phase 2 |
| CDN | Serve static content near users | Global users; static or cacheable assets | Phase 3 |

## The five dials (you cannot max all at once)

- **Scalability** — handle 10x load by adding machines
- **Availability** — fraction of time it's up (nines)
- **Latency** — speed of a single request (use p99, not average)
- **Consistency** — do all clients see the same data
- **Cost** — money + complexity; every choice above has a price

## The one question to always ask

> "What breaks at 100x the current load?"

Almost every technique in this course exists to answer that question.

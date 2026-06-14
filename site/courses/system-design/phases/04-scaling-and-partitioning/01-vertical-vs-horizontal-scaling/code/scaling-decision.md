<!-- Reference: choosing vertical vs horizontal scaling. -->

# Scaling Decision Guide

## The two directions
| | Vertical (scale UP) | Horizontal (scale OUT) |
|---|---|---|
| How | Bigger machine | More machines + load balancer |
| Code change | None | Must be designed for it |
| Ceiling | Yes (biggest box) | No (add boxes) |
| Cost curve | Non-linear (top-end pricey) | Roughly linear |
| Availability | SPOF (one machine) | Redundant (survives a failure) |
| Complexity | Low | High (distributed systems) |

## Decide by STATE
- **Stateless** (app/API tier) → scale OUT trivially. Add boxes behind the LB.
- **Stateful** (database) → hard to scale out. Needs replication (L2),
  sharding (L3), consistency tradeoffs (Phase 5). Scale UP first.

## Recommended sequence
1. One server (scale UP as needed) — handles most apps.
2. Split tiers; scale the stateless app tier OUT behind a load balancer.
3. Add DB read replicas (read scaling).
4. Shard the database (write scaling) — only when you must.
5. Multi-region (global scale + availability).

## Don't
- Don't go distributed prematurely (you buy consensus/replication/sharding pain).
- Don't scale up forever (you hit the ceiling AND have a SPOF).

## Availability intuition
- 1 server @ 99.9% → SPOF.
- 2 independent servers, either can serve → ~99.9999% (failures must coincide).
  Redundancy multiplies the downtime probabilities, so availability jumps.

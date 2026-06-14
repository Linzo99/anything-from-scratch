<!-- Reference: fault tolerance and the availability math. -->

# Fault Tolerance & Availability Math

## Principle
Assume EVERYTHING fails. Make each failure absorbed, not propagated.
No single failure should cause a user-visible outage.

## Eliminate SPOFs (single points of failure)
| SPOF | Fix |
|------|-----|
| one app server | many servers behind a load balancer |
| one load balancer | redundant LB pair (active/passive) |
| one database | replicas + failover |
| one data center | multi-AZ / multi-region |
| one network path | multiple links |
Trace every request path: "what one thing, if it died, kills this?"

## The math
**Series** (need ALL up) → multiply availabilities → LESS available:
```
0.999 × 0.999 × 0.999 ≈ 0.997   (three "three nines" → 99.7%)
```
Long dependency chains are fragile.

**Parallel** (need ONE of N) → multiply FAILURE probabilities → MORE available:
```
two @ 99%:  both down = 0.01 × 0.01 = 0.0001 → 99.99%
three @ 99%: 0.01^3 = 0.000001 → 99.9999%
```
Redundancy is cheap availability — IF failures are independent.

## Redundancy styles
- **Active-active**: all instances serve (no failover gap, no wasted capacity);
  needs stateless/coordinated instances. → app servers
- **Active-passive**: standby waits, promoted on failure (simpler, brief gap,
  idle capacity). → databases

## Failure domains (independence is everything)
rack < Availability Zone < Region. Spread copies across them.
- Same rack/AZ copies share power/network → correlated failure → little protection
- Blast radius = how much one failure takes down → keep it small (staged rollouts!)

## Gotcha
Backups ≠ fault tolerance. Backups prevent DATA LOSS; restoring takes hours.
Fault tolerance = LIVE redundancy that takes over in seconds.

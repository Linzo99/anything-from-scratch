<!-- Reference: where to keep session/state so the app tier stays stateless. -->

# Session & State Strategies

## The rule
> Keep the APP SERVER stateless. Any per-client state lives elsewhere.

Stateless = the load balancer can send any request to any server.

## Three session strategies
| | Sticky sessions | Shared store (Redis) | Stateless JWT |
|---|---|---|---|
| Where session lives | server memory | external store | in the client's token |
| App tier stateless? | ❌ No | ✅ Yes | ✅ Yes |
| Per-request lookup | none | yes (fast) | none (verify signature) |
| Instant revocation | easy | easy | ❌ hard (valid till expiry) |
| Extra infra | none | HA session store | signing key mgmt |
| Best for | small/legacy | most web apps | APIs, microservices |

## JWT revocation workarounds
- Short expiry + refresh tokens
- A denylist of revoked token IDs (reintroduces a small lookup)

## Move ALL local state off the box
| Local state | Put it in... |
|-------------|--------------|
| Session | shared store (Redis) or JWT |
| Uploaded files | object storage (S3) |
| Cached computation | distributed cache (Redis) |
| Long job state | database or queue |
| WebSocket connection | inherently on one server → use pub/sub to route (Phase 8) |

## Gotcha
- "Stateless" ≠ "no state anywhere." The system has state; the SERVER doesn't.
- If the session store (Redis) is down, users are logged out → run it HA.

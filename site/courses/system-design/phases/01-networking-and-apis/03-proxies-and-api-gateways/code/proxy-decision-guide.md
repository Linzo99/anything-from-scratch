<!-- Reference: where does each concern belong? -->

# Proxy / Gateway Decision Guide

## Forward vs reverse (one question)
> Who does the intermediary represent?
- Represents the **client** → forward proxy (egress filtering, anonymizing, client caching)
- Represents the **server** → reverse proxy (load balancing, TLS termination, edge caching)

## Where does each concern live?

| Concern | Backend service | Reverse proxy | API gateway |
|---|:--:|:--:|:--:|
| Business logic / validation | ✅ | | |
| Load balancing | | ✅ | ✅ |
| TLS termination | | ✅ | ✅ |
| Response caching | | ✅ | ✅ |
| Compression (gzip/br) | | ✅ | ✅ |
| Authentication / authorization | | | ✅ |
| Per-client rate limiting | | | ✅ |
| API versioning / routing by path | | (basic) | ✅ |
| Request aggregation (fan-out + merge) | | | ✅ |
| Protocol translation (REST↔gRPC) | | | ✅ |

## Do I need a gateway?
- **One service** → a reverse proxy (Nginx/HAProxy) is enough.
- **Many microservices sharing auth/rate-limit/logging** → add an API gateway.

## Typical request path
```
Client → DNS → API Gateway (auth, rate limit) → Load Balancer → Service instances → Data stores
```
Common reverse proxies: Nginx, HAProxy, Envoy.
Common gateways: Kong, Envoy/Ambassador, AWS API Gateway, managed cloud gateways.

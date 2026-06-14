<!-- Reference: the three pillars, golden signals, and alerting. -->

# Observability Reference

## Monitoring vs observability
- **Monitoring**: watch KNOWN failure modes (predefined metrics + alerts).
  "Is the thing I worried about happening?"
- **Observability**: investigate UNKNOWN problems from emitted telemetry.
  "Why is this weird thing I never imagined happening?"
Must instrument BEFORE the incident — can't add it mid-outage.

## The three pillars
| Pillar | What | Answers | Tools |
|--------|------|---------|-------|
| Metrics | numbers over time | "how much / how fast / how many?" (THAT it's wrong) | Prometheus, Grafana |
| Logs | discrete event records | "what exactly happened?" | ELK, Loki, structured logs |
| Traces | one request across services | "WHERE is it slow?" | Jaeger, Zipkin, OpenTelemetry |
They're complementary: metrics → traces → logs to drill down.

## Distributed tracing
Propagate a trace_id through every service call; each records a SPAN.
```
trace=abc:  gateway[2ms] → order[5ms] → inventory[1800ms] ← bottleneck visible
```

## Golden signals (measure these first)
| Signal | Example |
|--------|---------|
| Latency | p50, p99 (use PERCENTILES, not averages) |
| Traffic | requests/sec (QPS) |
| Errors | 5xx rate, error % |
| Saturation | CPU, memory, queue depth |

## Alerting (avoid fatigue)
- Alert on SYMPTOMS (user impact / SLO breach), not every cause
- Every alert must be ACTIONABLE (nothing to do → don't page)
- Tie alerts to error-budget burn (Lesson 05)
Noisy alerts → people ignore them → the real one is missed.

## Gotcha
Logs alone ≠ observable. Without metrics you can't see trends/alert;
without traces you can't follow a request across services.

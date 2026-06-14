<!-- Reference: stream processing concepts. -->

# Stream Processing Reference

## Batch vs stream
| | Batch | Stream |
|---|-------|--------|
| Data | bounded (fixed) | unbounded (endless) |
| Runs | once | continuously |
| Latency | high (wait for batch) | low (as events arrive) |
| Complexity | simple | windows, event time, late data |
| Tools | Spark, MapReduce | Flink, Kafka Streams, Spark Streaming |
| Use | nightly report, ETL | fraud, live dash, alerts, trending |

## Windows (make the infinite finite)
- **Tumbling**: fixed, non-overlapping. "count per minute"
- **Sliding/hopping**: overlapping. "5-min avg, updated every 30s"
- **Session**: gap-based bursts. "group a user's activity into a visit"

## Event time vs processing time
- **Event time** = when it happened (timestamp in the event) ← window by THIS
- **Processing time** = when you received it
- They differ (delays, retries, offline devices) → events arrive late & out of order
- Processing-time windows = non-reproducible, wrong; event-time = correct

## Watermark
Estimate "all events up to time T have arrived."
- Watermark passes window end → emit the window's result
- Late event after watermark → drop / side-output / correct
- Tradeoff: short wait = low latency but misses stragglers;
  long wait = complete but slow

## Choosing
- Hourly/daily freshness OK → BATCH (simpler, cheaper, easier to get right)
- Need seconds-fresh results → STREAM
- Many systems do both (Lambda/Kappa architectures)

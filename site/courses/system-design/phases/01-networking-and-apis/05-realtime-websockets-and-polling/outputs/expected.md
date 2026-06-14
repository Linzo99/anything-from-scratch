# Expected Output

Running `python realtime_overhead.py` should produce:

```
Window: 60s, 4 real updates to deliver

Technique             Requests  Overhead(B)  WorstLatency(s)
Short polling (5s)          12         8400                5
Long polling                 5         3500                0
SSE                          1          700                0
WebSockets                   1          716                0
```

What to notice:
- **Short polling** makes 12 requests to deliver just 4 updates — most are empty —
  and can be up to 5s late. Its overhead (8400 B) is the largest.
- **Long polling** cuts requests to 5 and latency to ~0, at the cost of holding
  requests open.
- **SSE and WebSockets** use a single connection (700-ish bytes of setup) and
  deliver instantly. WebSockets add a few bytes of per-message framing but are
  bidirectional.

The catch the script prints: SSE/WS each hold an **open socket per client**, so at
1,000,000 concurrent users that's 1,000,000 sockets to manage — a real scaling
problem addressed in the chat capstone.

Common issues:
- **Numbers differ:** they're deterministic. Short polling at 5s over 60s is
  exactly 12 requests; changing `interval` to 1 makes it 60.
- **Overhead is an approximation:** `HEADER_BYTES = 700` is a stand-in for real
  HTTP header size; the point is the relative comparison, not exact bytes.

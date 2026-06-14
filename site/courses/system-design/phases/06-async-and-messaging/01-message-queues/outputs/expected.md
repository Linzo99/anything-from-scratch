# Expected Output

Running `python message_queue.py` produces output like (exact times vary by machine):

```
Enqueued 1000 jobs in 0.7 ms (producer returns immediately)
Drained 1000 jobs with 8 workers in 1.51 s
Processed count: 1000

Throughput: ~663 jobs/sec with 8 workers
Producer latency stayed ~0; the slow work moved off the request path.
```

What to notice:
- **Enqueue is near-instant** (well under a millisecond for 1000 jobs). This is the
  user-facing latency: the producer drops the work and returns immediately.
- **Draining takes ~1-2 seconds** with 8 workers doing 10ms of "work" each. That's
  the slow part — but it happened in the background, not while the user waited.
- **Processed count is exactly 1000** — no work is lost; the queue buffered the
  whole burst and the workers drained it.
- **Throughput ≈ workers / task_time.** With 8 workers and 10ms tasks the ceiling is
  ~800/s; you'll see somewhat less due to threading overhead and Python's GIL.

The exact ms and jobs/sec depend on your CPU — don't expect identical numbers. The
*shape* is the point: instant enqueue, steady background drain, zero loss.

Common issues:
- **Processed count < 1000:** a race in `processed.append` — make sure it's under
  `processed_lock`.
- **Program hangs:** `work_queue.join()` blocks until every `task_done()` is called;
  ensure each `get()` is paired with exactly one `task_done()`.
- **More workers don't help past a point:** Python threads share the GIL, so
  CPU-bound work won't scale; this demo's `sleep` is I/O-like so it scales until
  overhead dominates (Exercise 2).

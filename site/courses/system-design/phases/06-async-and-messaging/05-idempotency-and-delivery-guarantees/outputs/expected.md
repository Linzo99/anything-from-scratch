# Expected Output

Running `python idempotency.py` should produce:

```
Three deposits of 100; tx2 is delivered twice (at-least-once).
  Expected balance:            300
  Naive consumer (buggy):      400   <- duplicate charge!
  Idempotent consumer (dedup): 300   <- correct

With every message delivered 3x: idempotent balance = 300 (still 300)
```

What to notice:
- **Naive consumer reports 400** instead of 300: because tx2 was delivered twice
  and `balance += amount` is not idempotent, the duplicate added another 100. In a
  real system that's a double charge.
- **Idempotent consumer reports 300**: it records each message's id in `seen` and
  skips any id it has already processed, so the duplicate tx2 is ignored.
- **Triple delivery still gives 300**: idempotency makes the consumer correct no
  matter how many times messages are redelivered — that's the whole point. You get
  the *effect* of exactly-once from at-least-once delivery + dedup.

Common issues:
- **Idempotent consumer also shows 400:** the dedup check isn't working — confirm
  you add `key` to `seen` after processing and `continue` when it's already present.
- **Real-world caveat:** the `seen` set here is in-memory and single-threaded. In
  production it must be durable and shared (Redis/DB), and the check-and-record must
  be atomic, or two concurrent duplicates can both slip through (Exercise 2).

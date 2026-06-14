# Expected Output

Running `python pubsub.py` should produce:

```
Publish user.signed_up (fans out to 3 services):
  [email]     welcome email for ada
  [billing]   created billing profile for ada
  [analytics] recorded event user.signed_up

Publish order.placed (fans out to 2 services):
  [inventory] reserved stock for order 1001
  [analytics] recorded event order.placed

Delivery counts:
  email     : 1 event(s)
  billing   : 1 event(s)
  analytics : 2 event(s)
  inventory : 1 event(s)

The publisher never named a single subscriber — adding a new one
means calling broker.subscribe(), with zero changes to the publisher.

After adding a 4th subscriber and publishing again:
  [email]     welcome email for grace
  [billing]   created billing profile for grace
  [analytics] recorded event user.signed_up
  [sales]     notified about grace
```

What to notice:
- **One `user.signed_up` event triggers three services** — fan-out. A plain queue
  would have delivered it to only one of them.
- **`analytics` gets 2 events** because it subscribes to *both* topics
  (`user.signed_up` and `order.placed`). Subscribers choose their topics independently.
- **Adding a 4th subscriber** (`[sales]`) and re-publishing shows it now reacts too —
  and the publishing code was never modified. That zero-change extensibility is the
  decoupling payoff of pub/sub.

Common issues:
- **Only one service reacts per event:** you've built a queue (point-to-point), not
  pub/sub. `publish` must loop over *all* subscribers of the topic.
- **A subscriber gets events from the wrong topic:** check that `subscribe` keys by
  topic and `publish` only delivers to that topic's list.

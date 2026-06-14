<!-- Reference design: chat system (design artifact, no runnable code). -->

# Chat System Design Summary

## Framework run
1. **Requirements**: 1:1 + group messaging, presence, delivery/read receipts,
   history, offline delivery. Out: voice/video, E2E crypto details.
   Low latency, reliable, ordered, millions of concurrent connections.
2. **Estimation**: ~50M concurrent WebSockets → ~5,000 gateways @10K conns each;
   ~25K msgs/sec; ~600 GB/day history.
3. **Protocol**: WebSocket (SEND / MESSAGE / RECEIPT) + REST for history.
4. **Data model**:
   - messages(msg_id PK time-sortable, conversation_id, sender_id, text, created, status)
   - conversations(conv_id, members[])
   - connections registry: user_id -> {gateway_server, conn_id, devices[]}
5. **Core**: route a message to the gateway holding the recipient's socket.
6. **Bottleneck**: millions of persistent connections + inter-gateway routing.

## Delivery flow
```
Alice (Gateway 3) ──SEND──> Gateway 3
  1. PERSIST message (durability first!)
  2. look up Bob in connection registry (Redis) -> Gateway 47
  3. publish message to Bob's channel on the pub/sub bus
Gateway 47 receives -> push down Bob's WebSocket -> Bob
  4. Gateway 47 sends 'delivered' receipt back to Alice
  5. Bob views -> 'read' receipt back to Alice
```
Offline Bob? No registry entry → message already stored → delivered on reconnect
(+ optional push notification).

## Key components
- **Chat gateways**: hold persistent WebSocket connections, push messages.
- **Connection registry** (Redis): user_id → gateway, for routing.
- **Pub/sub bus** (Phase 6): inter-gateway message routing.
- **Message store** (wide-column, e.g. Cassandra): partition by conversation_id,
  sort by time-sortable msg_id → per-conversation ordering (Phase 4/5).

## Hard parts
- Ordering: time-sortable ID + partition by conversation (no global order needed).
- Presence: registry + heartbeats; fan out changes to contacts (pub/sub).
- Group fan-out: 1 msg → all members; a 100K-member group ≈ celebrity problem (L3).
- Persist BEFORE deliver: never lose a message on crash / offline.

## Gotcha
Don't deliver by writing to a DB and hoping — connections live on different
servers; you MUST route via the registry + pub/sub to the recipient's gateway.

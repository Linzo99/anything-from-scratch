<!-- Reference: pick a data model from the access pattern. -->

# Data Model Decision Guide

## Step 1 — Write down your access patterns
- How do you READ? (by key / by range / with joins / by traversal / ad-hoc)
- How do you WRITE? (volume, by key, in transactions)
- Reads or writes dominant? Queries known up front or evolving?

## Step 2 — Match

| Access pattern | Model | Examples |
|---|---|---|
| Flexible, ad-hoc queries across related entities | Relational | PostgreSQL, MySQL |
| Get/put by a single key, very fast | Key-value | Redis, DynamoDB |
| Fetch a whole self-contained entity | Document | MongoDB, Couchbase |
| Huge write volume, query by key/range | Wide-column | Cassandra, Bigtable |
| Traverse relationships (friends-of-friends) | Graph | Neo4j, Neptune |

## Step 3 — Default
Start **relational** unless a pattern clearly demands otherwise.
You rarely regret the flexibility early; you often regret a premature
NoSQL choice when requirements evolve.

## What you trade for scale (NoSQL)
- Give up flexible JOINs → must denormalize (store read-shaped)
- Give up rigid schema → flexibility, but app enforces structure
- Sometimes give up strong consistency → eventual (see Phase 5)

## Polyglot persistence is normal
One system often uses several stores, e.g.:
- Postgres for orders/users (integrity, transactions)
- Redis for sessions/cache (speed)
- Cassandra for the event log (write scale)
- S3 for media blobs (size)

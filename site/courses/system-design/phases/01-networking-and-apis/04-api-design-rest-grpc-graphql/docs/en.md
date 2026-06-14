# API Design: REST, gRPC, GraphQL

> REST, gRPC, and GraphQL are three answers to the same question — how should a client ask a server for data? — and each optimizes for a different thing.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 1, Lesson 03 — Proxies & API Gateways
**Time:** ~50 minutes

## Learning Objectives

- Describe the model behind REST, gRPC, and GraphQL
- Compare them on payload size, coupling, performance, and tooling
- Recognize over-fetching and under-fetching and how GraphQL addresses them
- Choose the right style for a given client/service relationship
- Build a small example of each and compare their payloads

## The Problem

Every system needs a contract: how clients ask for data and actions, and how the server responds. Pick the wrong style and you pay for it forever. Use chatty REST between internal microservices and you waste latency and bandwidth on JSON parsing for millions of calls. Use rigid REST for a mobile app with a dozen screens and you either over-fetch (download fields you don't need) or make five round trips to assemble one screen. Use GraphQL where you didn't need its flexibility and you've taken on a complex query engine and caching headaches for nothing.

These three styles dominate modern APIs, and they aren't ranked — each wins in a different context. REST is the lingua franca of public web APIs. gRPC is the workhorse of internal service-to-service communication. GraphQL solves the client-driven data-fetching problem for rich front-ends. Knowing *why* each exists lets you pick deliberately instead of defaulting to whatever's familiar.

This lesson builds the same conceptual endpoint — fetch a user and their posts — in all three styles and compares the trade-offs concretely.

## The Concept

### REST: resources and verbs

REST models everything as **resources** addressed by URLs, manipulated with HTTP verbs:

```
GET    /users/42          → fetch user 42
GET    /users/42/posts    → fetch user 42's posts
POST   /users            → create a user
PUT    /users/42          → replace user 42
DELETE /users/42          → delete user 42
```

Strengths: simple, universally understood, cacheable via HTTP, great tooling (every language, every browser). Weaknesses: **over-fetching** (you get the whole user object even if you only wanted the name) and **under-fetching** (to show a profile screen you call `/users/42` *and* `/users/42/posts` *and* `/users/42/followers` — three round trips, the "N+1 round-trip" problem).

### gRPC: typed remote procedure calls

gRPC frames the interaction as **calling a function on a remote server**. You define the service and messages in a `.proto` schema, and gRPC generates client and server code:

```protobuf
service UserService {
  rpc GetUser(UserRequest) returns (User);
}
message UserRequest { int32 id = 1; }
message User { int32 id = 1; string name = 2; string email = 3; }
```

Messages are serialized with **Protocol Buffers** — a compact binary format, far smaller and faster to parse than JSON — and transported over HTTP/2 (multiplexed, supports streaming). Strengths: small payloads, high throughput, strong typing, bidirectional streaming. Weaknesses: not human-readable, not natively callable from a browser without a proxy, more setup. This is why gRPC dominates *internal* service-to-service traffic where both ends are yours and performance matters.

### GraphQL: the client specifies the shape

GraphQL exposes a single endpoint and a **query language** where the client declares exactly the fields it wants:

```graphql
query {
  user(id: 42) {
    name
    posts(last: 3) { title }
  }
}
```

The server returns exactly that shape — no more, no less — in one round trip. Strengths: eliminates over-fetching and under-fetching, one request assembles a whole screen, strongly typed schema with great tooling. Weaknesses: caching is harder (one URL, many query shapes), a malicious or naive client can request an expensive deep query, and the server needs a resolver layer. GraphQL shines for rich front-ends (especially mobile, where round trips are costly) talking to many backing data sources.

### Side-by-side

```
                 REST              gRPC               GraphQL
---------------  ----------------  -----------------  ----------------------
Model            resources + verbs remote procedures  client-shaped queries
Payload format   JSON (text)       Protobuf (binary)  JSON (text)
Transport        HTTP/1.1 or 2     HTTP/2             HTTP (usually POST)
Over-fetching    common            n/a (fixed msgs)   eliminated
Round trips      can be many       one per call       one per screen
Browser-native   yes               needs proxy        yes
Best for         public web APIs   internal services  rich front-ends
Streaming        limited           first-class        subscriptions
```

### A common misconception

Beginners think one of these is simply "better" and the others are legacy. They're not — they coexist in the same company. A typical large system uses **GraphQL or REST at the edge** for clients, and **gRPC internally** between microservices. The right question is never "which is best?" but "which fits *this* relationship?": public consumers you don't control (REST), your own high-volume services (gRPC), or a front-end that needs flexible, efficient data fetching (GraphQL).

## Build It

You'll model all three styles in plain Python (no servers needed) to compare their payloads. Create `api_styles.py`.

### Step 1 — A shared data source

```python
# Run: python api_styles.py
import json

DB = {
    42: {
        "id": 42, "name": "Ada", "email": "ada@example.com",
        "bio": "Mathematician", "created": "1815-12-10", "followers": 9999,
        "posts": [
            {"id": 1, "title": "On the Analytical Engine", "body": "..." * 50},
            {"id": 2, "title": "Note G", "body": "..." * 50},
            {"id": 3, "title": "Poetical Science", "body": "..." * 50},
        ],
    }
}
```

### Step 2 — REST: fixed responses, possible over/under-fetch

```python
def rest_get_user(uid):
    return DB[uid]                      # returns the WHOLE user (over-fetch)

def rest_get_posts(uid):
    return DB[uid]["posts"]             # a SECOND round trip (under-fetch)

# To render "name + last 3 post titles", a client needs BOTH calls:
rest_payload = json.dumps(rest_get_user(42)) + json.dumps(rest_get_posts(42))
```

### Step 3 — gRPC: compact, fixed message (simulated as a tight binary-ish form)

```python
def grpc_get_user(uid):
    u = DB[uid]
    # Protobuf would send only declared fields, binary-packed. Approximate the
    # *content* with just the fields the .proto declares (id, name, email).
    return {"id": u["id"], "name": u["name"], "email": u["email"]}

grpc_payload = json.dumps(grpc_get_user(42))   # stands in for compact binary
```

### Step 4 — GraphQL: client picks exactly the fields, one round trip

```python
def graphql_query(uid, fields, last_posts=0):
    u = DB[uid]
    out = {f: u[f] for f in fields if f in u}
    if last_posts:
        out["posts"] = [{"title": p["title"]} for p in u["posts"][-last_posts:]]
    return out

# Client asks for exactly: name + last 3 post titles — nothing else
graphql_payload = json.dumps(graphql_query(42, ["name"], last_posts=3))
```

### Step 5 — Compare payload sizes

```python
print("=== Payload size to render 'name + last 3 post titles' ===")
print(f"REST (user + posts, 2 round trips): {len(rest_payload):5} bytes")
print(f"gRPC GetUser (1 call, fixed msg):   {len(grpc_payload):5} bytes")
print(f"GraphQL (1 call, exact shape):      {len(graphql_payload):5} bytes")
print()
print("REST over-fetches (bio, email, followers, full post bodies) AND")
print("under-fetches (needs a 2nd call for posts).")
print("GraphQL returns exactly the requested shape in one round trip.")
```

### Step 6 — Run it

```bash
python api_styles.py
```

Observe how much smaller the GraphQL payload is for this specific screen, because it carries only the requested fields. Compare with `outputs/expected.md`.

## Exercises

1. **Run and read.** Confirm GraphQL's payload is far smaller than REST's for this screen. Which two REST problems does it solve at once?

2. **Add a field.** The client now also wants `followers`. Change the GraphQL query and re-run. Note that REST's payload doesn't change (it already sent everything).

3. **Make REST efficient.** Add a REST endpoint `/users/42?fields=name` that filters fields server-side. Does this fully solve over-fetching? What about under-fetching (posts)?

4. **Pick the style.** For each, choose REST, gRPC, or GraphQL and justify: (a) a public weather API, (b) the auth service called by 40 internal services, (c) a mobile app's home screen pulling from five sources.

5. **gRPC reasoning.** Real Protobuf would make the gRPC payload even smaller than the JSON stand-in. Explain why binary serialization beats JSON on both size and parse speed.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| REST | "Normal HTTP API" | An architecture modeling resources as URLs manipulated with HTTP verbs, returning JSON |
| gRPC | "Binary RPC" | A framework for typed remote procedure calls using Protobuf over HTTP/2; compact and fast |
| GraphQL | "Query language for APIs" | A single endpoint where clients specify exactly the fields they want, returned in one response |
| Protocol Buffers | "Protobuf" | A compact binary serialization format with a schema; smaller and faster to parse than JSON |
| Over-fetching | "Too much data" | Receiving fields you didn't need because the endpoint returns a fixed shape |
| Under-fetching | "Not enough in one call" | Needing multiple round trips to assemble what one screen requires |
| Round trip | "A request/response" | One client→server→client exchange; minimizing these is key for high-latency links |

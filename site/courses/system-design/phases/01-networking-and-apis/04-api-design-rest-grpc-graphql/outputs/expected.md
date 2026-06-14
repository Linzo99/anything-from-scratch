# Expected Output

Running `python api_styles.py` should produce:

```
=== Payload size to render 'name + last 3 post titles' ===
REST (user + posts, 2 round trips):  1340 bytes
gRPC GetUser (1 call, fixed msg):      53 bytes
GraphQL (1 call, exact shape):        117 bytes
```

What to notice:
- **REST** is by far the largest (~1340 bytes) and needs **two round trips**: it
  ships the entire user object (bio, email, followers, full post bodies you never
  asked for) and still needs a second call for posts.
- **GraphQL** (~117 bytes, one round trip) carries only `name` plus three post
  titles — exactly what the screen needs.
- **gRPC** looks smallest here (~53 bytes) because the JSON stand-in only contains
  the three declared fields; real Protobuf binary would be smaller still and
  faster to parse. (Note it returns a different shape — id/name/email — to
  illustrate gRPC's fixed-message model.)

Common issues:
- **Byte counts differ slightly:** the `"..." * 50` post bodies make REST large;
  if you edit the DB, REST's size moves. gRPC and GraphQL stay small because they
  never send the bodies.
- **Takeaway, not exact bytes:** the point is the *ratio* — fixed-shape, full-object
  REST vs client-shaped GraphQL vs compact gRPC.

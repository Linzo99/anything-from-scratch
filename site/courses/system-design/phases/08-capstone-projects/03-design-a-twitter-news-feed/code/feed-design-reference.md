<!-- Reference design: Twitter news feed (no runnable code; this is a design artifact). -->

# News Feed Design Summary

## Framework run
1. **Requirements**: post, follow, view reverse-chron home timeline. Out: search, ads, ranking.
   Read-heavy; fast timeline (p99<200ms); eventual consistency OK; huge fan-out skew.
2. **Estimation**: ~35K timeline reads/sec, ~5K posts/sec (~100:1). One celebrity
   post may fan out to 100M+ followers.
3. **API**: POST /tweet, POST /follow, GET /timeline?cursor=
4. **Data model**:
   - tweets(tweet_id PK, author_id, text, created)
   - follows(follower_id, followee_id)
   - timeline: user_id -> [tweet_ids]  (precomputed, in Redis)
5. **Core decision**: fan-out on WRITE vs READ
6. **Bottleneck**: celebrity fan-out → hybrid.

## Fan-out strategies
| | Push (on write) | Pull (on read) |
|---|---|---|
| Write cost | high (1 → N feeds) | very low (store once) |
| Read cost | very low (precomputed) | high (merge many followees) |
| Celebrity | BAD (100M inserts/post) | fine on write, slow read |

## The hybrid (production answer)
- **Normal users** → PUSH posts into followers' precomputed timelines.
- **Celebrities** → DON'T push; store once. At read time MERGE their recent
  posts into the reader's precomputed feed.
- timeline = precomputed(normal followees) ⊕ pulled(celebrity followees), sorted.
- Caps write fan-out AND keeps reads fast.

## Supporting choices
- Timelines in Redis, capped to recent N entries (Phase 3)
- Eventually consistent feed — a few seconds' lag is fine (Phase 5)
- Tweets stored once, cached/CDN'd for read-heavy load (Phase 2/3)
- Shard tweets & timelines by user_id (Phase 4)
- Cursor-based pagination for infinite scroll

## ASCII: a reader's timeline assembly (hybrid)
```
[ precomputed feed from normal followees ]  (pushed)
            +  merge/sort  +
[ recent posts pulled from my 3 celebs   ]  (pulled at read time)
            =  home timeline page
```

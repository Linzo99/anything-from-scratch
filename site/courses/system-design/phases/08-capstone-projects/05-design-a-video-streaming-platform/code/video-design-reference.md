<!-- Reference design: video streaming platform (design artifact, no runnable code). -->

# Video Streaming Platform Design Summary

## Framework run
1. **Requirements**: upload, transcode, adaptive smooth playback worldwide.
   Out: live streaming, DRM details, recommendations. VOD only.
   Massively read-heavy; no buffering (adapt quality); global; petabytes; bandwidth-bound.
2. **Estimation**: petabytes–exabytes of storage (object storage only);
   tens of Tbps egress at peak (CDN mandatory); huge transcoding compute.
3. **Flow**: presigned upload → async transcode → manifest → player pulls chunks from CDN.
4. **Data model**: metadata in DB (small); video bytes in OBJECT STORAGE behind CDN.
5. **Cores**: (a) async transcoding pipeline, (b) adaptive bitrate streaming.
6. **Bottlenecks**: bandwidth, storage, transcoding.

## Upload → transcoding pipeline (async, Phase 6)
```
client --presigned PUT--> Object Storage (raw)
        --> enqueue job --> Transcoding Queue
        --> worker fleet: produce renditions (240p..4K), chunk them
        --> write chunks + manifest to Object Storage
        --> CDN serves them; status flips processing -> ready
```

## Adaptive bitrate (ABR)
Manifest (HLS .m3u8 / DASH) lists the video at several qualities, time-aligned chunks:
```
240p:  [c0][c1][c2]...   720p: [c0][c1][c2]...   1080p: [c0][c1][c2]...
player picks per chunk: 720p,720p,[drop]480p,480p,[recover]720p  -> no stop, just quality
```
Degrades QUALITY instead of STOPPING → why streaming rarely buffers.

## Delivery
- Chunks are static & identical for all viewers → textbook CDN (Phase 3).
- Object storage = ORIGIN; CDN caches chunks at edges, offloads the Tbps egress.

## Bottlenecks → resolutions
| Bottleneck | Resolution |
|------------|------------|
| Bandwidth (Tbps egress, #1 cost) | CDN edge delivery |
| Storage (PB–EB of renditions) | object storage (S3), tiered |
| Transcoding (CPU-heavy) | async queue + worker fleet |

## The whole course in one system
presigned uploads + object storage (P2) · async queue + workers (P6) ·
CDN edge (P3) · metadata DB (P2) · sized by estimation (P0).

## Gotcha
Bandwidth is the dominant cost — the CDN is load-bearing, not optional.
Never put video bytes in a database; metadata DB + object storage + CDN.

<!-- Reference: the blob storage pattern and presigned upload/download flow. -->

# Object Storage Pattern Cheat-Sheet

## The split
- **Database**: small, structured, queryable data + a POINTER to the blob (its key/URL)
- **Object store (S3)**: the big blob bytes (media, backups, static assets)

## Upload flow (presigned PUT)
```
1. Client → App:  "I want to upload avatar.jpg"
2. App:           generate presigned PUT URL (scoped to one key, expires in minutes)
3. App → Client:  the URL
4. Client → S3:   PUT bytes DIRECTLY (never through your servers)
5. App → DB:      save object key, e.g. avatars/42.jpg, on the user row
```

## Download flow (CDN-backed)
```
1. Client → CDN:  GET avatars/42.jpg
2. CDN → S3:      (cache miss only) fetch from origin bucket
3. CDN → Client:  bytes, cached at the edge
   subsequent requests: served from edge, skipping S3 AND your app
```

## Object storage model
- Bucket = namespace; Key = object name; namespace is FLAT (prefixes ≈ folders)
- Operations: PUT, GET, DELETE, LIST. No in-place edits, no querying inside content.
- Durable (S3: 11 nines) and effectively unlimited; cheap per GB.

## Object vs block vs file
| Type | Unit | Use case |
|------|------|----------|
| Object | whole object by key (HTTP) | media, backups, static assets |
| Block | raw blocks (virtual disk) | the disk UNDER a database / VM |
| File | files + directories (NFS) | shared filesystems, legacy apps |

## Don't
- Don't store large blobs in DB rows.
- Don't proxy blob bytes through app servers (use presigned URLs).
- Don't treat S3 like a POSIX disk (no appends-per-write, no real dirs).

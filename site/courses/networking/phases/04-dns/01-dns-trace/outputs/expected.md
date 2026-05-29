# Expected Output

Running `bash dns_trace.sh github.com` should produce output similar to:

```
==============================
 DNS Resolution Trace for: github.com
==============================

─────────────────────────────────────────────────────────────────
STEP 1 — Full iterative trace (dig +trace)
─────────────────────────────────────────────────────────────────
  Each block shows one delegation step, ending with the server that answered.
  The resolver walks: local cache → root → TLD → authoritative nameserver

  ; <<>> DiG 9.16.1 <<>> +trace +additional github.com A

    .                       518400  IN      NS      a.root-servers.net.
    .                       518400  IN      NS      b.root-servers.net.
    ...
  *** 192.168.1.1  [ROOT → returns TLD nameservers]

    com.                    172800  IN      NS      a.gtld-servers.net.
    com.                    172800  IN      NS      b.gtld-servers.net.
    ...
  *** a.root-servers.net  [ROOT → returns TLD nameservers]

    github.com.             172800  IN      NS      ns-1707.awsdns-21.co.uk.
    github.com.             172800  IN      NS      ns-421.awsdns-52.com.
    ...
  *** a.gtld-servers.net  [TLD → returns authoritative NS]

    github.com.             60      IN      A       140.82.121.4
  *** ns-421.awsdns-52.com  [AUTHORITATIVE → returns final answer]

─────────────────────────────────────────────────────────────────
STEP 2 — Direct query to 8.8.8.8 (Google Public DNS)
─────────────────────────────────────────────────────────────────
  This bypasses your local cache and asks Google's recursive resolver.

  ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
  github.com.                                   60 IN A 140.82.121.4

─────────────────────────────────────────────────────────────────
STEP 3 — Who are the authoritative nameservers for github.com?
─────────────────────────────────────────────────────────────────

  NS: ns-1283.awsdns-32.org.
  NS: ns-1707.awsdns-21.co.uk.
  NS: ns-421.awsdns-52.com.
  NS: ns-520.awsdns-01.net.

─────────────────────────────────────────────────────────────────
STEP 4 — Query authoritative NS (ns-1283.awsdns-32.org.) directly
─────────────────────────────────────────────────────────────────
  Expect 'aa' (authoritative answer) flag in the response.

  ;; flags: qr aa rd; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1
  github.com.                                   60 IN A 140.82.121.4

==============================
 Trace complete for github.com
==============================
```

Key things to observe:
- Each `***` line shows which server answered that step and its role (ROOT / TLD / AUTHORITATIVE)
- The TTL in Step 1 trace shows: root NS records have ~518400s (6 days), domain A records may be as low as 60s
- Step 4 should show the `aa` (authoritative answer) flag, which is missing from Step 2

## Common issues

- **Issue**: `Error: 'dig' not found` → **Fix**: Install dnsutils: `sudo apt-get install -y dnsutils` (Ubuntu) or `brew install bind` (macOS with Homebrew).
- **Issue**: Step 1 trace shows only the final answer without delegation steps → **Fix**: Some DNS resolvers return the answer from cache and `dig +trace` skips the full walk. Try `dig +trace +nssearch github.com` or add `+norec` to force iterative mode.
- **Issue**: Step 4 shows no `aa` flag → **Fix**: The nameserver queried may be a secondary that does not set `aa`. Try a different NS from the Step 3 list.

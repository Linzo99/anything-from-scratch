# Expected Output

Running `bash dns_explore.sh example.com` produces output similar to (exact IPs
and TTLs vary over time and by resolver):

```
=== 1. Basic A record + TTL for example.com ===
example.com.		300	IN	A	93.184.216.34

=== 2. TTL counts down in the resolver cache (run twice) ===
example.com.		300	IN	A	93.184.216.34
example.com.		299	IN	A	93.184.216.34

=== 3. Record types ===
-- NS (authoritative name servers) --
a.iana-servers.net.
b.iana-servers.net.
-- MX (mail servers) --
0 .
-- AAAA (IPv6) --
2606:2800:220:1:248:1893:25c8:1946

=== 4. Query a specific public resolver (Google 8.8.8.8) ===
93.184.216.34

=== 5. Full hierarchy trace (root -> TLD -> authoritative) ===
.			518400	IN	NS	a.root-servers.net.
com.			172800	IN	NS	a.gtld-servers.net.
example.com.		172800	IN	NS	a.iana-servers.net.
```

The thing to notice: in section 2 the **second TTL is lower** (299 vs 300) — proof
the answer is being served from the resolver's cache and counting down.

Common issues:
- **`dig: command not found`:** install it — `sudo apt-get install dnsutils` (Debian/Ubuntu) or `brew install bind` (macOS).
- **`+trace` shows nothing useful:** some networks block direct root queries. The first three sections still work; the trace is a bonus.
- **Different IP than shown:** totally normal. Big sites use GeoDNS/CDNs, so your nearest answer differs from this example.

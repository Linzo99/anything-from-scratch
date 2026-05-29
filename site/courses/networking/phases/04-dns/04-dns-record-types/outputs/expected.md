# Expected Output

Running `bash dns_records.sh` should produce output similar to:

```
================================================================
  DNS Record Types — dig queries for real domains
================================================================

─────────────────────────────────────────────────────────
  A Record — Maps hostname to IPv4 address
─────────────────────────────────────────────────────────
  Purpose: The most common record type. Tells clients which IPv4
  address to connect to. Multiple A records = round-robin pool.

  >> example.com A (single address)
     93.184.216.34

  >> google.com A (multiple IPs, round-robin)
     172.217.14.206
     172.217.14.238
     (order may vary each query)

─────────────────────────────────────────────────────────
  AAAA Record — Maps hostname to IPv6 address
─────────────────────────────────────────────────────────
  >> google.com AAAA
     2607:f8b0:4004:c19::8b
     2607:f8b0:4004:c19::65

  >> cloudflare.com AAAA
     2606:4700::6810:84e5
     2606:4700::6810:85e5

  >> example.com AAAA (may be empty)
     2606:2800:220:1:248:1893:25c8:1946

─────────────────────────────────────────────────────────
  CNAME Record — Alias one name to another
─────────────────────────────────────────────────────────
  >> www.github.com CNAME (often aliased)
     github.com.

  >> www.github.com A (follow CNAME chain)
     140.82.121.3

─────────────────────────────────────────────────────────
  MX Record — Mail exchanger
─────────────────────────────────────────────────────────
  >> gmail.com MX (multiple priorities)
     5 gmail-smtp-in.l.google.com.
     10 alt1.gmail-smtp-in.l.google.com.
     20 alt2.gmail-smtp-in.l.google.com.
     30 alt3.gmail-smtp-in.l.google.com.
     40 alt4.gmail-smtp-in.l.google.com.

  >> Top-priority MX 'gmail-smtp-in.l.google.com.' resolves to:
     172.253.115.26

─────────────────────────────────────────────────────────
  TXT Record — Arbitrary text
─────────────────────────────────────────────────────────
  >> github.com TXT
     "MS=ms44452932"
     "v=spf1 ip4:192.30.252.0/22 include:_netblocks.google.com ..."

  >> _dmarc.gmail.com TXT
     "v=DMARC1; p=none; rua=mailto:mailauth-reports@google.com"

─────────────────────────────────────────────────────────
  NS Record — Authoritative nameservers
─────────────────────────────────────────────────────────
  >> example.com NS
     a.iana-servers.net.
     b.iana-servers.net.

  >> google.com NS
     ns1.google.com.
     ns2.google.com.
     ns3.google.com.
     ns4.google.com.

  >> Querying ns1.google.com directly (should show 'aa' flag):
     ;; flags: qr aa rd; QUERY: 1, ANSWER: 1, ...

─────────────────────────────────────────────────────────
  SOA Record — Start of Authority
─────────────────────────────────────────────────────────
  >> example.com SOA
     ns.icann.org. noc.dns.icann.org. 2024050601 7200 3600 1209600 3600

─────────────────────────────────────────────────────────
  Summary
─────────────────────────────────────────────────────────
  Record  Holds               Primary Use
  ──────────────────────────────────────────────────────────
  A       IPv4 address        Map hostname → IP
  AAAA    IPv6 address        Map hostname → IPv6
  CNAME   Domain name         Alias (cannot be at apex)
  MX      Priority + name     Email delivery routing
  TXT     Arbitrary text      SPF / DKIM / DMARC / verification
  NS      Domain name         Authoritative nameservers for zone
  SOA     Zone metadata       Serial, refresh, negative TTL
```

Exact IPs and TTL values will differ over time as records change.

## Common issues

- **Issue**: `Error: 'dig' not found` → **Fix**: `sudo apt-get install -y dnsutils` (Ubuntu) or `brew install bind` (macOS).
- **Issue**: AAAA query for example.com returns empty → **Fix**: This is expected on some networks that filter AAAA responses.  Try `dig +short example.com AAAA @8.8.8.8` to bypass your local resolver.
- **Issue**: `www.github.com CNAME` returns empty → **Fix**: GitHub may have changed their DNS configuration.  Try `dig www.github.com CNAME` manually and observe the response.  GitHub's www may now be a direct A record.

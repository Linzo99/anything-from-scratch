# Expected Output

**Lookup mode:**

```
$ python3 doh_resolver.py example.com
Resolving example.com A via DoH (https://1.1.1.1/dns-query)
──────────────────────────────────────────────────
Status: NOERROR
Answers (1):
  example.com                     TTL=86400  A       93.184.216.34

$ python3 doh_resolver.py google.com AAAA
Resolving google.com AAAA via DoH (https://1.1.1.1/dns-query)
──────────────────────────────────────────────────
Status: NOERROR
Answers (6):
  google.com                      TTL=300    AAAA    2607:f8b0:4004:c09::65
  google.com                      TTL=300    AAAA    2607:f8b0:4004:c09::71
  ...

$ python3 doh_resolver.py gmail.com MX
Resolving gmail.com MX via DoH (https://1.1.1.1/dns-query)
──────────────────────────────────────────────────
Status: NOERROR
Answers (5):
  gmail.com                       TTL=3600   MX      5 gmail-smtp-in.l.google.com
  gmail.com                       TTL=3600   MX      10 alt1.gmail-smtp-in.l.google.com
  ...
```

**Proxy mode:**
```
$ python3 doh_resolver.py --proxy
DoH proxy listening on UDP 127.0.0.1:5353
Forwarding to: https://1.1.1.1/dns-query
Test: dig @127.0.0.1 -p 5353 example.com A
Ctrl+C to stop

Query: example.com A from 127.0.0.1:52001
Query: google.com AAAA from 127.0.0.1:52002
```

Then from another terminal:
```
$ dig @127.0.0.1 -p 5353 example.com A
;; ANSWER SECTION:
example.com.    86400   IN  A   93.184.216.34
```

## Common issues

- **Issue**: `DoH network error: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]>` — **Fix**: On macOS, run `/Applications/Python 3.x/Install Certificates.command` to install root certificates. Alternatively use `--server https://8.8.8.8/dns-query`.
- **Issue**: `dig` returns `SERVFAIL` or times out — **Fix**: Ensure the proxy is running. Check that no other process is using UDP port 5353 (`ss -ulnp | grep 5353`). Use `--port 5454` if 5353 is taken.
- **Issue**: A record shows unexpected IP — **Fix**: Cloudflare may return different IPs based on your location. The resolved IP is correct; CDNs use anycast to serve from the nearest PoP.

# Expected Output

Running `python3 stub_resolver.py example.com` should produce:

```
Querying A record for example.com via 8.8.8.8:53 …

NAME                                TTL      TYPE     VALUE
----------------------------------------------------------------------
example.com                         86400    A        93.184.216.34

OS resolver:   ['93.184.216.34']
Stub resolver: ['93.184.216.34']
Match: True
```

Running `python3 stub_resolver.py gmail.com MX`:

```
Querying MX record for gmail.com via 8.8.8.8:53 …

NAME                                TTL      TYPE     VALUE
----------------------------------------------------------------------
gmail.com                           3600     MX       gmail-smtp-in.l.google.com (priority 5)
gmail.com                           3600     MX       alt1.gmail-smtp-in.l.google.com (priority 10)
gmail.com                           3600     MX       alt2.gmail-smtp-in.l.google.com (priority 20)
gmail.com                           3600     MX       alt3.gmail-smtp-in.l.google.com (priority 30)
gmail.com                           3600     MX       alt4.gmail-smtp-in.l.google.com (priority 40)
```

Running `python3 stub_resolver.py thisdoesnotexist99999.com`:

```
Querying A record for thisdoesnotexist99999.com via 8.8.8.8:53 …

DNS Error: DNS error for 'thisdoesnotexist99999.com': NXDOMAIN
```

## Common issues

- **Issue**: `DNS Error: All 3 attempts failed. Last: timeout on attempt 3` → **Fix**: UDP port 53 to 8.8.8.8 is blocked.  Try `python3 stub_resolver.py example.com A 1.1.1.1` (Cloudflare) or check your network/firewall settings.
- **Issue**: `Match: False` on the OS comparison → **Fix**: The OS may be using a different resolver that returns a different set of IPs (e.g., CDN-based geo-routing).  This is expected for some domains; it is not a bug in the stub resolver.
- **Issue**: `Transaction ID mismatch` error → **Fix**: A stray UDP datagram from a previous run arrived first.  The resolver will retry automatically; if it consistently fails, check for other DNS clients on the same port.

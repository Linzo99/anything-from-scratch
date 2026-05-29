# Expected Output

Running `python3 dns_parser.py` (queries example.com) should produce:

```
--- Parsing hardcoded hex example (offline) ---

=======================================================
  Hardcoded example.com A response
=======================================================
Transaction ID : 0x1234
Type           : Response
RCODE          : NOERROR
Authoritative  : False
Truncated      : False
Counts         : QD=1 AN=1 NS=0 AR=0

QUESTION SECTION:
  example.com                         IN  A

ANSWER SECTION:
  example.com                         86400    IN  A        93.184.216.34

  Raw bytes (43 total): 12348180000100010000000007657861...

--- Querying A record for: example.com ---

=======================================================
  Live response for example.com
=======================================================
Transaction ID : 0xabcd
Type           : Response
RCODE          : NOERROR
Authoritative  : False
Truncated      : False
Counts         : QD=1 AN=1 NS=0 AR=0

QUESTION SECTION:
  example.com                         IN  A

ANSWER SECTION:
  example.com                         86400    IN  A        93.184.216.34

  Raw bytes (56 total): abcd818000010001000000010765...
```

Running `python3 dns_parser.py github.com` shows github.com's A record(s):

```
ANSWER SECTION:
  github.com                          60       IN  A        140.82.121.4
```

Running `python3 dns_parser.py --offline` parses only the hardcoded example (works without network access).

## Common issues

- **Issue**: `Timeout — check your network connection` → **Fix**: The script needs UDP port 53 access to 8.8.8.8.  Use `--offline` to run without network.  On a restricted network, try `python3 dns_parser.py example.com 1.1.1.1` with a different resolver.
- **Issue**: `Error parsing hardcoded example: Packet too short` → **Fix**: The EXAMPLE_HEX constant in the source was accidentally truncated.  The hex string should be exactly 43 bytes (86 hex characters).
- **Issue**: RCODE shows `NXDOMAIN` instead of `NOERROR` → **Fix**: The domain queried does not exist.  Try a known-good domain like `example.com` or `google.com`.

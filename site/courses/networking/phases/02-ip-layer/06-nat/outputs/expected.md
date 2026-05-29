# Expected Output

Running `python3 nat_sim.py` should produce:

```
══════════════════════════════════════════════════════════════
  Basic NAT/PAT Scenario
══════════════════════════════════════════════════════════════
  Public IP: 203.0.113.5
  Private hosts: 192.168.1.10, 192.168.1.11, 192.168.1.12

  Outbound packets:

  [NAT] NEW entry:   192.168.1.10:54321 → MASQUERADE → 203.0.113.5:40000  (dest=93.184.216.34:80)
  [NAT] NEW entry:   192.168.1.11:54321 → MASQUERADE → 203.0.113.5:40001  (dest=93.184.216.34:80)
  [NAT] NEW entry:   192.168.1.12:33445 → MASQUERADE → 203.0.113.5:40002  (dest=8.8.8.8:53)
  [NAT] NEW entry:   192.168.1.10:54322 → MASQUERADE → 203.0.113.5:40003  (dest=93.184.216.34:443)

    192.168.1.10:54321 → 93.184.216.34:80   becomes   203.0.113.5:40000 → 93.184.216.34:80
    192.168.1.11:54321 → 93.184.216.34:80   becomes   203.0.113.5:40001 → 93.184.216.34:80
    192.168.1.12:33445 → 8.8.8.8:53         becomes   203.0.113.5:40002 → 8.8.8.8:53
    192.168.1.10:54322 → 93.184.216.34:443  becomes   203.0.113.5:40003 → 93.184.216.34:443

  NAT Translation Table (4 entries):
  Private source         Public source          Destination            Protocol   Out   In
  ──────────────────────────────────────────────────────────────────────────────────────────
  192.168.1.10:54321  ↔  203.0.113.5:40000  →  93.184.216.34:80      TCP        1     0
  192.168.1.11:54321  ↔  203.0.113.5:40001  →  93.184.216.34:80      TCP        1     0
  192.168.1.12:33445  ↔  203.0.113.5:40002  →  8.8.8.8:53            UDP        1     0
  192.168.1.10:54322  ↔  203.0.113.5:40003  →  93.184.216.34:443     TCP        1     0

  Packet rewrite example:
    Outbound (private → public):
      Before: src=192.168.1.10:54321  dst=93.184.216.34:80
      After:  src=203.0.113.5:40000   dst=93.184.216.34:80
    Inbound (public → private):
      Before: dst=203.0.113.5:40000   src=93.184.216.34:80
      After:  dst=192.168.1.10:54321  src=93.184.216.34:80
    NAT also recomputes TCP/UDP checksums (IP and port changed)

  Inbound reply packets:

    Reply 93.184.216.34:80 → 203.0.113.5:40000
    NAT rewrites dst → 192.168.1.10:54321  (delivered to correct host)

  Unsolicited inbound attempt (public → private, no NAT entry):

  [NAT] DROPPED inbound packet from 10.20.30.40:54000 to 203.0.113.5:12345 — no matching NAT entry

  Observation: both 192.168.1.10 and 192.168.1.11 used private port 54321
  NAT assigned them DIFFERENT public ports (key point of PAT/NAPT).
  The destination server at 93.184.216.34 only sees the public IP.
```

Key observations:
1. Both `192.168.1.10:54321` and `192.168.1.11:54321` share the same private port but get distinct public ports (40000 and 40001). This is NAPT.
2. The inbound reply for port 40000 is correctly translated back to `192.168.1.10:54321`.
3. An unsolicited connection attempt from outside is dropped — there is no NAT entry to translate it.

Run with `python3 nat_sim.py --demo` to see the port-reuse demo with 5 hosts.

## Common issues

- **Issue**: `RuntimeError: NAT port pool exhausted` → **Fix**: The simulator allocates ports starting at 40000. It would take ~25,000 connections to exhaust the pool. Real NAT gateways recycle entries after TCP connection close or UDP timeout.
- **Issue**: Output shows the same public port twice → **Fix**: This should not happen. The `_next_port` counter is never reset. Check that you are not creating a new `NATGateway()` object between connections.
- **Issue**: `[NAT] DROPPED` for a reply packet → **Fix**: The receive() lookup uses `(public_dst, src)` as the key. Make sure the `src` IP and port match the destination you used in `send()` exactly. Even a single different digit causes a miss.

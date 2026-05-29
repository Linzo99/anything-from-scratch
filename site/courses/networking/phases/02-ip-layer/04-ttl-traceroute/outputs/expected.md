# Expected Output

Running `bash ttl_trace.sh 8.8.8.8 10` (with internet access) should produce:

```
──────────────────────────────────────────────────────────
 TTL Expiry Demo — Step-by-step traceroute simulation
 Target: 8.8.8.8  |  Max hops: 10
──────────────────────────────────────────────────────────

 Theory:
   TTL = 1 → packet dies at first router → ICMP Time Exceeded from hop 1
   TTL = 2 → packet dies at second router → ICMP Time Exceeded from hop 2
   TTL = N → packet reaches destination → ICMP Echo Reply

Step 0: Resolving 8.8.8.8 ...
8.8.8.8.in-addr.arpa domain name pointer dns.google.

──────────────────────────────────────────────────────────
 Sending ICMP probes with increasing TTL values:
──────────────────────────────────────────────────────────

  TTL= 1  Time Exceeded from 192.168.1.1  (this router decremented TTL to 0)
  TTL= 2  Time Exceeded from 10.10.0.1  (this router decremented TTL to 0)
  TTL= 3  *  (no response — router blocked ICMP or rate-limited)
  TTL= 4  Time Exceeded from 209.85.168.174  (this router decremented TTL to 0)
  TTL= 5  REACHED destination (8.8.8.8)  RTT=14.23 ms

──────────────────────────────────────────────────────────
 Destination reached!
──────────────────────────────────────────────────────────

 For comparison, running system traceroute (if available):
──────────────────────────────────────────────────────────
traceroute to 8.8.8.8 (8.8.8.8), 10 hops max, 60 byte packets
 1  192.168.1.1  1.23 ms  1.10 ms  0.99 ms
 2  10.10.0.1  8.34 ms  7.91 ms  8.22 ms
 3  * * *
 4  209.85.168.174  14.12 ms  13.88 ms  14.01 ms
 5  8.8.8.8  14.23 ms  14.05 ms  13.99 ms

──────────────────────────────────────────────────────────
 Key takeaways:
   Each hop decrements TTL by 1
   TTL=0 triggers ICMP Time Exceeded → reveals the hop's IP
   traceroute sends TTL=1, 2, 3 ... to map every hop
   '*' means that hop doesn't respond to ICMP probes
──────────────────────────────────────────────────────────
```

Running `bash ttl_trace.sh 127.0.0.1 3` (loopback, no internet required):
```
Loopback target detected — packet never leaves the host.
TTL is not decremented on loopback, so it always reaches in 1 hop.

Sending ping with TTL=1 to 127.0.0.1:
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.044 ms
```

## Common issues

- **Issue**: All hops show `*  (no response)` → **Fix**: Your network or ISP may be blocking ICMP. Try `bash ttl_trace.sh 192.168.1.1 3` to trace only to your local gateway (which almost always responds).
- **Issue**: `ping: invalid option -- 't'` → **Fix**: Some minimal ping versions use `-m` for TTL (macOS) instead of `-t`. The script tries `-t` first. On strict POSIX systems you may need to install `iputils-ping` (`sudo apt-get install -y iputils-ping`).
- **Issue**: `traceroute: command not found` → **Fix**: Install with `sudo apt-get install -y traceroute`. The step-by-step TTL demo still works without it.

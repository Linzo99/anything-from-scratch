# Expected Output

Running `python3 port_scanner.py localhost 1 1024` should produce output similar to:

```
Scanning 127.0.0.1  ports 1–1024
Timeout: 0.5s per port   Threads: 100
Scan type: TCP connect scan (socket.connect_ex)

PORT       STATE        SERVICE
---------- ------------ --------------------
22         open         ssh
80         open         http
443        open         https

  47 port(s) filtered (no response within 0.5s timeout)

Scan complete: 1024 ports scanned in 3.21s
  Open: 3   Closed: 974   Filtered: 47
```

The exact open ports depend on which services are running on your machine. On a minimal system with only SSH:

```
PORT       STATE        SERVICE
---------- ------------ --------------------
22         open         ssh

Scan complete: 1024 ports scanned in 2.84s
  Open: 1   Closed: 1023   Filtered: 0
```

## Common issues

- **Issue**: Scan takes a very long time (>60s) — **Fix**: Reduce the port range or increase `--threads`. The default `--timeout 0.5` means each filtered port takes 0.5s, but with 100 threads they're checked in parallel. If many ports are filtered, total time ≈ (number_of_ports / threads) × timeout.
- **Issue**: All ports show "filtered" — **Fix**: A local firewall may be dropping connections. Try `sudo iptables -F` to flush rules (in a test VM), or scan `localhost` which usually bypasses firewall rules for loopback.

# Expected Output

Running `sudo python3 packet_analyzer.py lo` and then pinging localhost in another terminal should produce:

```
Capturing on interface: lo
Packet Analyzer — running (Ctrl+C to stop)
────────────────────────────────────────────────────────────────────────────────
       #  Timestamp  Summary
────────────────────────────────────────────────────────────────────────────────
  [     1] 14:45:22 IP 127.0.0.1 > 127.0.0.1  ICMP echo-request code=0 id=12345 seq=1 ttl=64
  [     2] 14:45:22 IP 127.0.0.1 > 127.0.0.1  ICMP echo-reply code=0 id=12345 seq=1 ttl=64
  [     3] 14:45:23 IP 127.0.0.1:54321 > 127.0.0.1:80(http)  TCP [SYN] seq=0 ack=0 len=0 ttl=64
  [     4] 14:45:23 IP 127.0.0.1:80(http) > 127.0.0.1:54321  TCP [SYN|ACK] seq=0 ack=1 len=0 ttl=64
  [     5] 14:45:23 IP 127.0.0.1:54321 > 127.0.0.1:80(http)  TCP [ACK] seq=1 ack=1 len=0 ttl=64
  [     6] 14:45:24 IP 127.0.0.1:52000 > 127.0.0.1:53(dns)  UDP len=36 ttl=64

^C

Capture stopped.
  Packets captured : 6
  Duration         : 2.3s
  Avg packet rate  : 2.6 pkt/s
```

To generate traffic for testing:
```bash
# Terminal 1: run the analyzer
sudo python3 packet_analyzer.py lo

# Terminal 2: generate traffic
ping -c3 127.0.0.1
curl -s http://127.0.0.1 >/dev/null   # if a web server is running locally
dig @127.0.0.1 localhost              # DNS over loopback
```

## Common issues

- **Issue**: `AF_PACKET is only available on Linux` — **Fix**: This script requires Linux. On macOS, use `sudo tcpdump -i lo0 -n` instead, or run the script inside a Linux VM or Docker container.
- **Issue**: `Permission denied. Run with sudo` — **Fix**: Raw socket capture requires root. Use `sudo python3 packet_analyzer.py`.
- **Issue**: No output despite network activity — **Fix**: Verify you're listening on the right interface. Use `ip link show` to list interfaces. The loopback interface is usually `lo`. For Ethernet, try `eth0` or `ens3`.

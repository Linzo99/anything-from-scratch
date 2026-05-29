# Expected Output

Running `bash osi_layers.sh` should produce:

```
────────────────────────────────────────────────────────────
  OSI Layer Demonstration
────────────────────────────────────────────────────────────

[ LAYER 1 — Physical ]
  Job: transmit raw bits on a medium
  Tool: ip link show  (state UP means carrier is detected)

lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP>
eth0             UP             aa:bb:cc:dd:ee:ff <BROADCAST,MULTICAST,UP,LOWER_UP>

  Note: 'UP' = administratively enabled; 'LOWER_UP' = physical link active
  Loopback (lo) shows UNKNOWN because there is no real wire.

────────────────────────────────────────────────────────────
[ LAYER 2 — Data Link ]
  Job: address frames on a single hop (MAC addresses, Ethernet)
  Tool: ip link show  (shows MAC addresses)

1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff

  MAC addresses identify individual NICs on a local segment.
  ff:ff:ff:ff:ff:ff would be the broadcast address.

────────────────────────────────────────────────────────────
[ LAYER 3 — Network ]
  Job: route packets between networks using IP addresses
  Tool: ip addr show  +  ping (ICMP — an L3 protocol)

  --- IP addresses ---
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.1.10/24 fe80::1/64

  --- ping 127.0.0.1 (ICMP, stays in L3) ---
PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.044 ms
64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.039 ms

--- 127.0.0.1 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss

────────────────────────────────────────────────────────────
[ LAYER 4 — Transport ]
  Job: reliable (TCP) or fast (UDP) delivery between ports
  Tool: ss -tn  (shows active TCP connections)

  --- Active TCP connections (ss -tn) ---
State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port
ESTAB   0       0       192.168.1.10:22     192.168.1.5:54321

  --- Listening TCP sockets (ss -tlnp) ---
State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port
LISTEN  0       128     0.0.0.0:22          0.0.0.0:*

[ LAYER 5 — Session ]
  ...
  Session: SYN -> SYN-ACK -> ACK -> data -> FIN (complete)

[ LAYER 6 — Presentation ]
  ...
  TLS is the most common L6 protocol...

[ LAYER 7 — Application ]
  --- HTTP response headers from example.com ---
HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
...
```

## Common issues

- **Issue**: `ping: connect: Network is unreachable` at Layer 3 → **Fix**: The loopback interface is down. Run `sudo ip link set lo up`.
- **Issue**: `ss` shows nothing at Layer 4 → **Fix**: This is normal on a freshly booted machine with no active connections. Start `ncat -l 9999` in another terminal to create a listening socket.
- **Issue**: Layer 7 (`curl`) shows `Could not resolve host` → **Fix**: No internet access is required for the core lesson. The script will print a skip message and continue.

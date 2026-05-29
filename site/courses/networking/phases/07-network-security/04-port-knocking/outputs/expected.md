# Expected Output

Run in two terminals:

**Terminal 1 (server):**
```
$ python3 port_knock.py server
[server] Port Knock Daemon
[server] Sequence : [7000, 8000, 9000]
[server] Window   : 10.0s
[server] Unlocks  : port 2200 for 30s
[server] Host     : 127.0.0.1
[server] Press Ctrl+C to stop

[server] Listening on knock port 7000
[server] Listening on knock port 8000
[server] Listening on knock port 9000
[server] Knock from 127.0.0.1 on port 7000
[server] 127.0.0.1: knock 1/3 ✓ (port 7000)
[server] Knock from 127.0.0.1 on port 8000
[server] 127.0.0.1: knock 2/3 ✓ (port 8000)
[server] Knock from 127.0.0.1 on port 9000
[server] 127.0.0.1: knock 3/3 ✓ (port 9000)

[server] *** PORT UNLOCKED for 127.0.0.1 ***
[server] Opening port 2200 for 30s


[server] *** PORT 2200 LOCKED — timer expired for 127.0.0.1 ***
```

**Terminal 2 (client):**
```
$ python3 port_knock.py client
[client] Port Knock Client
[client] Target  : 127.0.0.1
[client] Sequence: [7000, 8000, 9000]
[client] Sending knock sequence...

[client] Knocking port 7000... sent
[client] Knocking port 8000... sent
[client] Knocking port 9000... sent

[client] Knock sequence complete.
[client] Waiting 2s for server to open port 2200...
[client] Connecting to 127.0.0.1:2200...
[client] Connected! Server says: [PORT 2200] Access granted for 127.0.0.1. Port closes in 28s
[client] Echo reply: Echo: hello from client

[client] SUCCESS: Port 2200 was unlocked by knock sequence
```

## Common issues

- **Issue**: `Address already in use` on knock ports — **Fix**: Another process is using port 7000, 8000, or 9000. Change `KNOCK_SEQUENCE` at the top of the file to different ports (e.g., `[17000, 18000, 19000]`).
- **Issue**: Client reports "FAILED to connect" — **Fix**: Ensure the server is running before sending the knock sequence. The server needs 1-2 seconds to start listening. Also check that the port `OPEN_PORT` (2200) is not blocked by a local firewall.

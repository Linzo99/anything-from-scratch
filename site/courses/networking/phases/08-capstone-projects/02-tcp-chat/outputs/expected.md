# Expected Output

**Terminal 1 — Server:**
```
$ python3 tcp_chat_server.py 9000
14:50:00  Chat server listening on 0.0.0.0:9000
14:50:00  Connect clients with: python3 tcp_chat_client.py localhost 9000
14:50:00  Server running. Ctrl+C to stop.
14:50:05  + connected: client1 (127.0.0.1:52001)
14:50:08  + connected: client2 (127.0.0.1:52002)
14:50:12  [14:50:12] [client1] hello from client 1
14:50:15  [14:50:15] [client2] hi back!
14:50:20  - disconnected: client2 (connection closed)
```

**Terminal 2 — Client 1:**
```
$ python3 tcp_chat_client.py localhost 9000
Connected to localhost:9000
Type messages and press Enter to send.
Commands: /nick <name>  /users  /quit

Welcome, client1! (1 user(s) online)
Commands: /nick <name>  /users  /quit
> *** client2 joined ***
> hello from client 1
> [client2] hi back!
> *** client2 left ***
> /nick Alice
> *** client1 is now Alice ***
> /users
> Online: Alice
```

**Terminal 3 — Client 2:**
```
$ python3 tcp_chat_client.py localhost 9000
Connected to localhost:9000
...
Welcome, client2! (2 user(s) online)
> *** client1 joined ***   (actually already there)
> [client1] hello from client 1
> hi back!
> /quit
Disconnected.
```

## Common issues

- **Issue**: `Cannot connect to localhost:9000 — is the server running?` — **Fix**: Start the server first (`python3 tcp_chat_server.py 9000`), then launch clients.
- **Issue**: Messages from the server overwrite the input prompt — **Fix**: This is a known cosmetic issue with terminal line buffering. The `\r` in the client's print restores the prompt, but rapid messages may look jumbled. This is normal for a teaching implementation without a proper TUI library.

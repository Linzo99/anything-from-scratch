# Expected Output

## Server terminal

Running `python3 echo_server.py` should produce:

```
Echo server listening on 0.0.0.0:9999
Press Ctrl-C to stop

[+] Client connected: 127.0.0.1:52100
  recv: 'message 000: hello from echo_client'
  recv: 'message 001: hello from echo_client'
  recv: 'message 002: hello from echo_client'
  ...
  recv: 'message 009: hello from echo_client'
[-] Client disconnected: 127.0.0.1:52100
```

## Client terminal

Running `python3 echo_client.py localhost 9999` (with the server already running) should produce:

```
Connecting to localhost:9999 …
Connected.  Sending 10 messages.

  [000] OK      recv: '[ECHO] message 000: hello from echo_client'
  [001] OK      recv: '[ECHO] message 001: hello from echo_client'
  [002] OK      recv: '[ECHO] message 002: hello from echo_client'
  [003] OK      recv: '[ECHO] message 003: hello from echo_client'
  [004] OK      recv: '[ECHO] message 004: hello from echo_client'
  [005] OK      recv: '[ECHO] message 005: hello from echo_client'
  [006] OK      recv: '[ECHO] message 006: hello from echo_client'
  [007] OK      recv: '[ECHO] message 007: hello from echo_client'
  [008] OK      recv: '[ECHO] message 008: hello from echo_client'
  [009] OK      recv: '[ECHO] message 009: hello from echo_client'

Result: 10/10 correct, 0 failed
```

## Common issues

- **Issue**: `ConnectionRefusedError` when running the client → **Fix**: Make sure the server is running first (`python3 echo_server.py`) in a separate terminal.
- **Issue**: `OSError: [Errno 98] Address already in use` when starting the server → **Fix**: A previous server is still running; kill it with `kill $(lsof -ti:9999)` or wait ~60 seconds for TIME_WAIT to expire.  The server already sets `SO_REUSEADDR`, so this error only appears if another process holds the port.
- **Issue**: Client hangs waiting for a response → **Fix**: The server may have crashed; check the server terminal for a traceback.  The client has a 5-second `settimeout()` so it will eventually raise `socket.timeout`.

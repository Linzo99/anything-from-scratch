# Expected Output

Running `bash verify_lab.sh` should produce:

```
==============================
 Networking Lab Tool Checker  
==============================

iproute2      PASS  (ip utility, iproute2-6.x.x, libbpf 1.x.x)
tcpdump       PASS  (tcpdump version 4.x.x)
nmap          PASS  (Nmap version 7.xx ( https://nmap.org ))
ncat          PASS  (Ncat: Version 7.xx ( https://nmap.org/ncat ))

------------------------------
 Results: 4 PASS / 0 FAIL
------------------------------

All tools present. Your lab is ready.
```

Exit code is `0` when all tools pass, `1` when any tool is missing.

## Common issues

- **Issue**: `tcpdump: FAIL (not found)` → **Fix**: Run `sudo apt-get install -y tcpdump` then re-run the script.
- **Issue**: `nmap: FAIL (not found)` → **Fix**: Run `sudo apt-get install -y nmap` then re-run.
- **Issue**: `ncat: FAIL (not found)` → **Fix**: Run `sudo apt-get install -y ncat` (the Nmap project version); on older systems `nc` from `netcat-openbsd` is an acceptable substitute.
- **Issue**: Script exits with `command not found: bash` → **Fix**: Run `chmod +x verify_lab.sh` and then `./verify_lab.sh`, or invoke directly with `bash verify_lab.sh`.

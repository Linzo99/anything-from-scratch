# Expected Output

Running `sudo bash firewall_demo.sh` should produce:

```
[14:30:00]
[14:30:00] === iptables Firewall Demo ===

[14:30:00] Step 1: Initial iptables state (INPUT chain)
Chain INPUT (policy ACCEPT 0 packets, 0 bytes)
num  target     prot opt source               destination

[14:30:00] Step 2: Verify port 8888 is REACHABLE before adding DROP rule
[14:30:00]   PASS: connection to 127.0.0.1:8888 is open (expected: open)

[14:30:00] Step 3: Adding DROP rule for all inbound traffic on port 8888
[14:30:00]   Rule added: iptables -A INPUT -p tcp --dport 8888 -j DROP

[14:30:02] Step 4: Verify port 8888 is now BLOCKED
[14:30:04]   PASS: connection to 127.0.0.1:8888 is blocked (expected: blocked)

[14:30:04] Step 5: Adding ACCEPT rule for specific IP 127.0.0.2 on port 8888
[14:30:04]   (ACCEPT rule must be inserted BEFORE the DROP rule — use -I to insert at position 1)
[14:30:04]   Rule added: iptables -I INPUT 1 -s 127.0.0.2 -p tcp --dport 8888 -j ACCEPT

[14:30:04] Step 6: Current INPUT chain rules:
Chain INPUT (policy ACCEPT 0 packets, 0 bytes)
num  target     prot opt source               destination
1    ACCEPT     tcp  --  127.0.0.2            0.0.0.0/0            tcp dpt:8888
2    DROP       tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:8888

[14:30:04] Step 7: Verify port 8888 is BLOCKED from 127.0.0.1
[14:30:06]   PASS: connection to 127.0.0.1:8888 is blocked (expected: blocked)
[14:30:06]
[14:30:06]   Explanation: The ACCEPT rule is for source 127.0.0.2 specifically.

[14:30:06] Step 8: Cleaning up all demo rules
[14:30:06] Cleaning up iptables rules...
[14:30:06]   Removed: DROP tcp dport 8888
[14:30:06]   Removed: ACCEPT from 127.0.0.2 tcp dport 8888
[14:30:06] Cleanup complete. Rules restored to original state.

=== Demo complete ===
```

## Common issues

- **Issue**: `This script must be run as root` — **Fix**: Run with `sudo bash firewall_demo.sh`. iptables requires root privileges.
- **Issue**: `ncat: command not found` — **Fix**: Install ncat with `sudo apt install ncat` or `sudo apt install netcat-openbsd`. The script also accepts plain `nc`.
- **Issue**: Step 2 shows "blocked" before any rules are added — **Fix**: A pre-existing iptables rule may be blocking port 8888. Check `sudo iptables -L INPUT -n` before running and remove conflicting rules.

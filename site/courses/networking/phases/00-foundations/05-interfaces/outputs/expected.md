# Expected Output

Running `sudo bash lab_interface.sh` should produce:

```
======================================
 Lab Interface Test (dummy0)
======================================

Step 1: Load dummy kernel module
  modprobe dummy                              PASS

Step 2: Create dummy0 interface
  ip link add dummy0 type dummy               PASS
  Interface state after creation:
    3: dummy0: <BROADCAST,NOARP> mtu 1500 qdisc noop state DOWN mode DEFAULT group default qlen 1000
        link/ether 6a:7b:8c:9d:ae:bf brd ff:ff:ff:ff:ff:ff

Step 3: Assign 10.99.0.1/24
  ip addr add 10.99.0.1/24 dev dummy0         PASS

Step 4: Bring dummy0 UP
  ip link set dummy0 up                       PASS

  Interface state after up:
    3: dummy0: <BROADCAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc noqueue state UNKNOWN group default qlen 1000
        link/ether 6a:7b:8c:9d:ae:bf brd ff:ff:ff:ff:ff:ff
        inet 10.99.0.1/24 scope global dummy0
           valid_lft forever preferred_lft forever

Step 5: Ping 10.99.0.1 (loopback via dummy0)
  ping -c 2 10.99.0.1                         PASS

Step 6: Show auto-added route for 10.99.0.0/24
  Kernel automatically adds a connected route when an IP is assigned:

    10.99.0.0/24 dev dummy0 proto kernel scope link src 10.99.0.1

  Route for 10.99.0.0/24 exists                PASS

Step 7: Tear down (bring DOWN, delete interface)
  ip link set dummy0 down                      PASS
  ip link del dummy0                           PASS
  dummy0: does not exist (correct)
  Interface deleted                            PASS

======================================
  Results: 8 PASS / 0 FAIL
======================================
  All steps passed!
```

## Common issues

- **Issue**: `ERROR: Could not create dummy0. Are you running as root?` → **Fix**: Run with `sudo bash lab_interface.sh`.
- **Issue**: `ping -c 2 10.99.0.1: FAIL` → **Fix**: The dummy interface may not be fully UP. Check `ip link show dummy0` — the state should show `UP,LOWER_UP`. A dummy interface automatically shows `LOWER_UP` when brought up because there is no real cable to wait for.
- **Issue**: Route not found in Step 6 → **Fix**: Confirm the IP was assigned with `ip addr show dummy0`. The route is only added automatically when the interface has an IP and is UP simultaneously.
- **Issue**: `modprobe dummy: FAIL` → **Fix**: The dummy module may already be loaded (not an error), or your kernel may not have the module. Check with `lsmod | grep dummy`. If missing, your kernel was built without dummy support (uncommon).

# Expected Output

Running `sudo bash routing_table.sh` should produce:

```
════════════════════════════════════════════════════════
 Step 1: Current host routing table
════════════════════════════════════════════════════════
default via 192.168.1.1 dev eth0 proto dhcp src 192.168.1.10 metric 100
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.10

 Explanation:
   'default via X.X.X.X dev ethN' = packets with no specific route go here
   'X.X.X.X/N dev ethN proto kernel' = directly connected subnet

════════════════════════════════════════════════════════
 Step 2: Building topology in network namespaces
════════════════════════════════════════════════════════
 Topology:
   10.0.1.2/24  [hostA] ---veth--- [router] 10.0.1.1/24 | 10.0.2.1/24 ---veth--- [hostB] 10.0.2.2/24

 Created namespaces: lab-hostA, lab-router, lab-hostB
 Created veth pairs and moved into namespaces

════════════════════════════════════════════════════════
 Step 3: Configuring IP addresses and static routes
════════════════════════════════════════════════════════
 hostA: 10.0.1.2/24, default via 10.0.1.1
 router: 10.0.1.1/24 (A side), 10.0.2.1/24 (B side), forwarding=ON
 hostB: 10.0.2.2/24, default via 10.0.2.1

════════════════════════════════════════════════════════
 Step 4: Routing tables in each namespace
════════════════════════════════════════════════════════
 hostA routing table:
   10.0.1.0/24 dev veth-la proto kernel scope link src 10.0.1.2
   default via 10.0.1.1 dev veth-la
 router routing table:
   10.0.1.0/24 dev veth-lr1 proto kernel scope link src 10.0.1.1
   10.0.2.0/24 dev veth-lr2 proto kernel scope link src 10.0.2.1
 hostB routing table:
   10.0.2.0/24 dev veth-lb proto kernel scope link src 10.0.2.2
   default via 10.0.2.1 dev veth-lb

════════════════════════════════════════════════════════
 Step 5: Connectivity tests
════════════════════════════════════════════════════════
  hostA → router (10.0.1.1)                              PASS
  hostB → router (10.0.2.1)                              PASS
  hostA → hostB (10.0.2.2) via router                    PASS
  hostB → hostA (10.0.1.2) via router                    PASS

════════════════════════════════════════════════════════
 Step 6: Route lookup (ip route get)
════════════════════════════════════════════════════════
 hostA route to 10.0.2.2:
   10.0.2.2 via 10.0.1.1 dev veth-la src 10.0.1.2 uid 0
 hostB route to 10.0.1.2:
   10.0.1.2 via 10.0.2.1 dev veth-lb src 10.0.2.2 uid 0

════════════════════════════════════════════════════════
 Step 7: Demonstrate IP forwarding requirement
════════════════════════════════════════════════════════
 Disabling IP forwarding in router namespace ...
 hostA → hostB now (should FAIL):
   FAILED — as expected (forwarding=0 drops cross-subnet packets)

 Re-enabling IP forwarding ...
  hostA → hostB after re-enabling forwarding                PASS

════════════════════════════════════════════════════════
 Results: 5 PASS / 0 FAIL
════════════════════════════════════════════════════════
 All tests passed. Static routing is working correctly.
```

## Common issues

- **Issue**: `ip netns: Operation not permitted` → **Fix**: Run with `sudo bash routing_table.sh`. Network namespace creation requires `CAP_SYS_ADMIN`.
- **Issue**: `hostA → hostB: FAIL` in Step 5 → **Fix**: Check that `net.ipv4.ip_forward=1` was set in the router namespace. The most common mistake is forgetting to enable forwarding. Verify with `sudo ip netns exec lab-router sysctl net.ipv4.ip_forward`.
- **Issue**: `Cannot find device 'veth-la'` on second run → **Fix**: The previous run's cleanup may have been incomplete. The script calls `cleanup` on exit automatically. If it still fails, manually run: `sudo ip netns del lab-hostA; sudo ip netns del lab-router; sudo ip netns del lab-hostB`.
- **Issue**: `Cannot find device` errors → **Fix**: The veth pair was already moved into a namespace and does not exist in the root namespace. This is expected — use `sudo ip netns exec <ns> ip link show` to inspect interfaces inside a namespace.

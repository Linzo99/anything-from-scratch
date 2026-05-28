# Explore BGP Path Selection

> BGP connects the entire Internet — and it does not pick the shortest path. It picks the path you told it to prefer.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 6, Lesson 01 — Configure OSPF with FRRouting
**Time:** ~50 minutes

## Learning Objectives
- Explain the difference between an Interior Gateway Protocol (IGP) and an Exterior Gateway Protocol (EGP)
- Set up a two-AS FRRouting lab with eBGP peering across a shared link
- Advertise a prefix from one AS and verify it is received in the other
- Manipulate LOCAL_PREF to prefer one path over another within an AS
- Manipulate AS_PATH prepending to influence inbound path selection from a remote AS

## The Problem

OSPF works great inside one organisation's network. But what about connecting your network to your ISP? Or connecting two ISPs together? OSPF floods topology details — you cannot flood your internal routing table to the entire Internet. The Internet has roughly 900,000 prefixes. You cannot run one big OSPF domain.

BGP (Border Gateway Protocol) solves this. It is a policy-driven routing protocol used between Autonomous Systems (AS). An AS is a network under single administrative control (typically one organisation or one ISP). BGP lets each AS advertise which IP prefixes it can reach, and crucially, lets operators apply policy to influence which paths are used.

OSPF picks the shortest path (by metric). BGP picks the path that survives a complex decision process involving up to 13 attributes, in order. Understanding the top three — LOCAL_PREF, AS_PATH, and MED — covers 90% of real-world BGP behaviour.

## The Concept

### Autonomous Systems

Every organisation that participates in BGP has an Autonomous System Number (ASN). These are either 16-bit (1–65535) or 32-bit. ASNs 64512–65534 are reserved for private use (like RFC 1918 addresses for IP). We will use AS 65001 and AS 65002.

```
           AS 65001                          AS 65002
  ┌─────────────────────┐          ┌─────────────────────┐
  │  R1 ─── R2 (OSPF)   │          │  R3                 │
  │         │            │  eBGP   │  │                  │
  │         └────────────┼─────────┼──┘                  │
  │                      │         │                      │
  │  prefix: 10.1.0.0/24 │         │  prefix: 10.2.0.0/24│
  └─────────────────────┘          └─────────────────────┘

eBGP = external BGP (between ASes)
iBGP = internal BGP (within same AS, not used in this lab)
```

### eBGP vs iBGP

**eBGP** (external BGP): BGP session between routers in different ASes. The AS_PATH attribute is updated at each AS boundary. eBGP neighbors are almost always directly connected.

**iBGP** (internal BGP): BGP session between routers in the same AS. Used to distribute BGP routes internally. iBGP does NOT add to AS_PATH. iBGP requires either full mesh or route reflectors. We focus on eBGP today.

### The BGP Decision Process (simplified)

When BGP receives multiple paths to the same prefix, it selects the best one using these attributes in order:

```
1. Highest WEIGHT (Cisco-proprietary, local to the router)
2. Highest LOCAL_PREF (preferred within one AS, default 100)
3. Locally originated routes preferred
4. Shortest AS_PATH (fewest AS hops)
5. Lowest ORIGIN type (IGP < EGP < incomplete)
6. Lowest MED (Multi-Exit Discriminator — hint to neighbors)
7. eBGP preferred over iBGP
8. Lowest IGP metric to BGP next-hop
9. Oldest eBGP route (stability)
10. Lowest Router ID
```

We will demonstrate steps 2 and 4.

### LOCAL_PREF: Influencing Outbound Traffic

LOCAL_PREF is set on routes received from eBGP peers. It is shared with all iBGP peers inside your AS. Routers in your AS prefer the exit point with the highest LOCAL_PREF.

```
AS 65001 has two exits to AS 65002:
  Exit A: LOCAL_PREF 200  ← preferred (higher wins)
  Exit B: LOCAL_PREF 100  ← backup

Traffic from AS 65001 to AS 65002's prefixes exits via A.
If A fails, traffic switches to B.
```

Use case: you have two ISP connections and want all outbound traffic to use the faster ISP.

### AS_PATH Prepending: Influencing Inbound Traffic

AS_PATH is a list of ASNs a route has traversed. Shorter is better. If you want inbound traffic to prefer one of your links, make the AS_PATH on the other link look longer by repeating your own ASN:

```
Link A advertises: 10.1.0.0/24   AS_PATH: 65001
Link B advertises: 10.1.0.0/24   AS_PATH: 65001 65001 65001

Remote ASes prefer Link A (shorter path).
```

Use case: multihomed customer wants most inbound traffic on their primary link.

## Build It

### Step 1: Create the Two-AS Topology

Save as `setup-bgp-lab.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Clean up
for ns in r1 r2 r3; do
  ip netns del "$ns" 2>/dev/null || true
done

# Create namespaces
ip netns add r1   # AS 65001
ip netns add r2   # AS 65001 (border router)
ip netns add r3   # AS 65002 (border router)

# R1-R2 internal link (AS 65001)
ip link add veth12 type veth peer name veth21
ip link set veth12 netns r1
ip link set veth21 netns r2

# R2-R3 eBGP peering link
ip link add veth23 type veth peer name veth32
ip link set veth23 netns r2
ip link set veth32 netns r3

# Loopbacks up
for ns in r1 r2 r3; do
  ip netns exec $ns ip link set lo up
done

# R1 (AS 65001 internal)
ip netns exec r1 ip addr add 192.168.1.1/32 dev lo
ip netns exec r1 ip addr add 10.0.12.1/30   dev veth12
ip netns exec r1 ip link set veth12 up
ip netns exec r1 sysctl -qw net.ipv4.ip_forward=1

# R2 (AS 65001 border)
ip netns exec r2 ip addr add 192.168.2.2/32 dev lo
ip netns exec r2 ip addr add 10.0.12.2/30   dev veth21
ip netns exec r2 ip addr add 10.0.23.1/30   dev veth23
ip netns exec r2 ip link set veth21 up
ip netns exec r2 ip link set veth23 up
ip netns exec r2 sysctl -qw net.ipv4.ip_forward=1

# R3 (AS 65002 border)
ip netns exec r3 ip addr add 192.168.3.3/32 dev lo
ip netns exec r3 ip addr add 10.0.23.2/30   dev veth32
ip netns exec r3 ip link set veth32 up
ip netns exec r3 sysctl -qw net.ipv4.ip_forward=1

# Add "customer" prefixes as dummy routes to advertise
ip netns exec r2 ip route add 10.1.0.0/24 dev lo   # AS 65001's prefix
ip netns exec r3 ip route add 10.2.0.0/24 dev lo   # AS 65002's prefix

echo "Topology ready."
```

```bash
sudo bash setup-bgp-lab.sh
```

### Step 2: Write FRR BGP Configurations

**`/tmp/frr-bgp-r2.conf`** (AS 65001 border router):

```
frr version 8.5
frr defaults traditional
hostname r2
!
interface veth21
!
interface veth23
!
router bgp 65001
 bgp router-id 192.168.2.2
 !
 neighbor 10.0.23.2 remote-as 65002
 neighbor 10.0.23.2 description "eBGP peer R3"
 !
 address-family ipv4 unicast
  network 10.1.0.0/24
  neighbor 10.0.23.2 activate
 exit-address-family
!
```

**`/tmp/frr-bgp-r3.conf`** (AS 65002 border router):

```
frr version 8.5
frr defaults traditional
hostname r3
!
interface veth32
!
router bgp 65002
 bgp router-id 192.168.3.3
 !
 neighbor 10.0.23.1 remote-as 65001
 neighbor 10.0.23.1 description "eBGP peer R2"
 !
 address-family ipv4 unicast
  network 10.2.0.0/24
  neighbor 10.0.23.1 activate
 exit-address-family
!
```

### Step 3: Start FRR BGP Daemons

```bash
#!/usr/bin/env bash
# start-bgp-lab.sh

for ns in r2 r3; do
  mkdir -p /var/run/frr-${ns} /var/log/frr-${ns}

  ip netns exec "$ns" /usr/lib/frr/zebra \
    --config_file /tmp/frr-bgp-${ns}.conf \
    --pid_file /var/run/frr-${ns}/zebra.pid \
    --log file:/var/log/frr-${ns}/zebra.log \
    --vty_socket /var/run/frr-${ns}/zebra.vty \
    --daemon

  sleep 1

  ip netns exec "$ns" /usr/lib/frr/bgpd \
    --config_file /tmp/frr-bgp-${ns}.conf \
    --pid_file /var/run/frr-${ns}/bgpd.pid \
    --log file:/var/log/frr-${ns}/bgpd.log \
    --vty_socket /var/run/frr-${ns}/bgpd.vty \
    --daemon
done

echo "Waiting 20s for BGP to establish..."
sleep 20
echo "Done."
```

```bash
sudo bash start-bgp-lab.sh
```

### Step 4: Verify BGP Peering and Route Exchange

```bash
# Check BGP summary on R2
sudo ip netns exec r2 vtysh \
  --vty_socket /var/run/frr-r2/bgpd.vty \
  -c "show bgp summary"
```

Look for `Established` in the state column. If you see `Active`, the TCP session hasn't come up yet — wait another 15 seconds.

```bash
# Check BGP table on R2 — should see 10.2.0.0/24 from R3
sudo ip netns exec r2 vtysh \
  --vty_socket /var/run/frr-r2/bgpd.vty \
  -c "show bgp ipv4 unicast"
```

```bash
# Check BGP table on R3 — should see 10.1.0.0/24 from R2
sudo ip netns exec r3 vtysh \
  --vty_socket /var/run/frr-r3/bgpd.vty \
  -c "show bgp ipv4 unicast"
```

Look at the AS_PATH column. The route 10.1.0.0/24 on R3 should show AS_PATH `65001`. The route 10.2.0.0/24 on R2 should show AS_PATH `65002`.

### Step 5: Demonstrate LOCAL_PREF

Add a route-map to R2 that sets LOCAL_PREF=200 on routes received from R3:

Connect to R2's vtysh and enter configuration mode:

```bash
sudo ip netns exec r2 vtysh --vty_socket /var/run/frr-r2/bgpd.vty
```

Then type:

```
configure terminal
!
route-map SET-LOCALPREF permit 10
 set local-preference 200
!
router bgp 65001
 address-family ipv4 unicast
  neighbor 10.0.23.2 route-map SET-LOCALPREF in
 exit-address-family
!
end
clear bgp 10.0.23.2 soft in
show bgp ipv4 unicast 10.2.0.0/24
```

You should now see `LocPrf 200` on the route from R3. In a real dual-homed scenario, this would make R2 the preferred exit for all traffic to AS 65002.

### Step 6: Demonstrate AS_PATH Prepending

Add prepending on R3 to make its advertisement of 10.2.0.0/24 look longer:

```bash
sudo ip netns exec r3 vtysh --vty_socket /var/run/frr-r3/bgpd.vty
```

```
configure terminal
!
route-map PREPEND permit 10
 set as-path prepend 65002 65002
!
router bgp 65002
 address-family ipv4 unicast
  neighbor 10.0.23.1 route-map PREPEND out
 exit-address-family
!
end
clear bgp 10.0.23.1 soft out
```

Back on R2:

```bash
sudo ip netns exec r2 vtysh \
  --vty_socket /var/run/frr-r2/bgpd.vty \
  -c "show bgp ipv4 unicast 10.2.0.0/24"
```

The AS_PATH should now read `65002 65002 65002`. If R2 had an alternate path with just `65002`, it would prefer that shorter path. That is the mechanism ISPs use to steer inbound traffic.

## Exercises

1. **Add a second eBGP link** between R2 and R3 via a new veth pair. Advertise 10.2.0.0/24 via both links. Without any policy, which link does R2 prefer and why?

2. **Use LOCAL_PREF to choose the backup path**: Set LOCAL_PREF=50 on routes from one eBGP peer. Verify R2 prefers the other path. Take down the primary path and verify traffic switches to the backup.

3. **Read a real BGP table**: Use the RIPE NCC BGP looking glass at `https://stat.ripe.net/widget/bgp-updates` to look up your university or ISP's AS number. How many prefixes do they advertise? What is the typical AS_PATH length to reach them from a European vantage point?

4. **Implement a prefix filter**: Add a route-map that rejects any prefix longer than /24 from R3 (`ip prefix-list` + `match ip address prefix-list`). This is a real security practice to prevent "route leaks."

5. **Measure BGP convergence**: Send continuous pings from R2 to R3's prefix 10.2.0.0 and take down the BGP session by killing bgpd on R3. How long before R2 withdraws the route? The default BGP hold timer is 90 seconds — negotiate it lower.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| AS | "Autonomous System" | A network under single administrative control, identified by a 32-bit ASN, that runs a consistent routing policy |
| eBGP | "external BGP" | A BGP session between routers in different Autonomous Systems |
| iBGP | "internal BGP" | A BGP session between routers in the same AS; does not increment AS_PATH |
| LOCAL_PREF | "local preference" | A BGP attribute that controls which exit point routers in an AS prefer for outbound traffic; higher wins |
| AS_PATH | "AS path" | The ordered list of ASNs a BGP route has passed through; shorter is preferred; used to prevent loops |
| Prepending | "AS path prepending" | Artificially lengthening AS_PATH by repeating your own ASN to make a path look less preferred |
| Route-map | "policy" | An ordered list of match-and-set rules applied to BGP routes on import or export |
| BGP hold timer | "hold time" | How long a router waits without a BGP Keepalive before declaring the session dead (default 90s) |

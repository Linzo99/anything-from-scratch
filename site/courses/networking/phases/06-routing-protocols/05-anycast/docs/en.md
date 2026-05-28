# Understand Anycast Routing

> One IP address, two servers, traffic goes to the closer one — that is how DNS and CDNs serve the world at scale.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 6, Lesson 03 — Explore BGP Path Selection
**Time:** ~30 minutes

## Learning Objectives
- Define anycast and distinguish it from unicast, multicast, and broadcast
- Announce the same prefix from two BGP locations in a FRRouting lab
- Verify that traffic from each vantage point lands on the topologically closest node
- Explain how DNS anycast works for root nameservers and public resolvers
- Describe failure handling when an anycast node goes offline

## The Problem

The DNS root nameservers collectively receive tens of billions of queries per day from every corner of the world. There are only 13 root server identities (A through M). If each identity were a single physical machine in one location, every query from Australia would travel to, say, Virginia. Latency would be terrible and a single DDoS attack could take out a letter.

The solution is anycast. Each of the 13 root server identities is actually dozens or hundreds of physical machines, spread across every continent. They all announce the same IP address via BGP. A resolver in Tokyo sends its query to the nearest machine announcing that address. A resolver in Frankfurt sends to a different machine. Same destination address, different physical endpoints.

This lesson builds a tiny anycast demonstration in Linux namespaces and BGP, making the concept concrete.

## The Concept

### The Four Addressing Modes

```
Unicast:    One sender → One specific receiver
            (normal TCP connection, ping to a single host)

Broadcast:  One sender → All receivers on a segment
            (ARP request to 255.255.255.255)

Multicast:  One sender → A group of subscribed receivers
            (video streaming, OSPF Hello packets to 224.0.0.5)

Anycast:    One sender → The nearest receiver from a set
            (DNS query to 8.8.8.8 goes to Google's nearest PoP)
```

The key insight: anycast is not a special protocol feature. It is just BGP routing behaviour. Multiple nodes announce the same prefix. Routing converges normally. Traffic naturally flows to the topologically closest announcement based on BGP path selection (AS_PATH length, LOCAL_PREF, etc.).

### How Anycast Works at the Network Level

```
         AS 100 (source)
             │
     ┌───────┴────────┐
     │                │
  AS 200           AS 300
  Node X           Node Y
  announces        announces
  10.9.9.0/24      10.9.9.0/24

Traffic from AS 100 reaches a BGP border router.
That router sees two paths to 10.9.9.0/24:
  Path 1: via AS 200 (1 hop)
  Path 2: via AS 300 (1 hop, but higher IGP cost)

BGP path selection picks the topologically closest path.
Packets to 10.9.9.1 land at Node X.
```

If Node X fails (its BGP process dies, or the operator withdraws the announcement), BGP reconverges and all traffic switches to Node Y. This is automatic — no application change, no DNS change, no operator intervention.

### Anycast vs. Load Balancing

Anycast is not load balancing in the traditional sense. You cannot guarantee even distribution. Traffic goes to the closest node by routing topology, not by server load. An overloaded anycast node will keep receiving traffic unless operators withdraw its BGP announcement.

Real CDNs combine anycast (for latency) with health checks that withdraw the BGP route if the server is unhealthy.

### Real-World Uses

- **DNS root servers**: All 13 root identities are anycast. A/K/L/etc. are distributed globally.
- **Google Public DNS**: 8.8.8.8 is anycast — your query goes to Google's nearest data centre.
- **Cloudflare**: 1.1.1.1 is anycast. Hundreds of PoPs worldwide.
- **DDoS scrubbing**: Route victim's IP via anycast to scrubbing centres worldwide.
- **Content Delivery Networks**: anycast edge nodes absorb traffic close to users.

## Build It

### Step 1: Topology

```
  [Client] ──── [R1, AS 65001] ──── [AnyA, AS 65010]  <- announces 10.9.9.0/24
       \
        ──── [R2, AS 65002] ──── [AnyB, AS 65010]  <- also announces 10.9.9.0/24

Client can reach 10.9.9.0/24 via R1 (1 hop to AnyA) or via R2 (1 hop to AnyB).
We will make the Client prefer R1 via LOCAL_PREF.
```

Set up the namespaces:

```bash
#!/usr/bin/env bash
set -euo pipefail

for ns in client r1 r2 anya anyb; do
  ip netns del "$ns" 2>/dev/null || true
  ip netns add "$ns"
  ip netns exec "$ns" ip link set lo up
  ip netns exec "$ns" sysctl -qw net.ipv4.ip_forward=1
done

# Client ─── R1
ip link add veth-c1 type veth peer name veth-1c
ip link set veth-c1 netns client && ip link set veth-1c netns r1

# Client ─── R2
ip link add veth-c2 type veth peer name veth-2c
ip link set veth-c2 netns client && ip link set veth-2c netns r2

# R1 ─── AnyA
ip link add veth-1a type veth peer name veth-a1
ip link set veth-1a netns r1 && ip link set veth-a1 netns anya

# R2 ─── AnyB
ip link add veth-2b type veth peer name veth-b2
ip link set veth-2b netns r2 && ip link set veth-b2 netns anyb

# Assign addresses
ip netns exec client ip addr add 10.0.0.1/30  dev veth-c1 && ip netns exec client ip link set veth-c1 up
ip netns exec client ip addr add 10.0.0.5/30  dev veth-c2 && ip netns exec client ip link set veth-c2 up
ip netns exec r1     ip addr add 10.0.0.2/30  dev veth-1c && ip netns exec r1     ip link set veth-1c up
ip netns exec r1     ip addr add 10.0.1.1/30  dev veth-1a && ip netns exec r1     ip link set veth-1a up
ip netns exec r2     ip addr add 10.0.0.6/30  dev veth-2c && ip netns exec r2     ip link set veth-2c up
ip netns exec r2     ip addr add 10.0.2.1/30  dev veth-2b && ip netns exec r2     ip link set veth-2b up
ip netns exec anya   ip addr add 10.0.1.2/30  dev veth-a1 && ip netns exec anya   ip link set veth-a1 up
ip netns exec anyb   ip addr add 10.0.2.2/30  dev veth-b2 && ip netns exec anyb   ip link set veth-b2 up

# Anycast address on loopback of both nodes
ip netns exec anya  ip addr add 10.9.9.1/32   dev lo
ip netns exec anyb  ip addr add 10.9.9.1/32   dev lo   # SAME IP — that's anycast!

echo "Topology ready."
```

```bash
sudo bash setup-anycast.sh
```

### Step 2: FRR BGP Configurations

**`/tmp/frr-anycast-client.conf`** (AS 65000 — the source of traffic):

```
frr version 8.5
hostname client
!
router bgp 65000
 bgp router-id 10.0.0.1
 neighbor 10.0.0.2 remote-as 65001
 neighbor 10.0.0.6 remote-as 65002
 !
 address-family ipv4 unicast
  neighbor 10.0.0.2 activate
  neighbor 10.0.0.6 activate
  ! Prefer R1 path with higher LOCAL_PREF
  neighbor 10.0.0.2 route-map PREFER-R1 in
 exit-address-family
!
route-map PREFER-R1 permit 10
 set local-preference 200
!
```

**`/tmp/frr-anycast-r1.conf`** (AS 65001):

```
frr version 8.5
hostname r1
!
router bgp 65001
 bgp router-id 10.0.0.2
 neighbor 10.0.0.1 remote-as 65000
 neighbor 10.0.1.2 remote-as 65010
 !
 address-family ipv4 unicast
  neighbor 10.0.0.1 activate
  neighbor 10.0.1.2 activate
 exit-address-family
!
```

**`/tmp/frr-anycast-r2.conf`** (AS 65002):

```
frr version 8.5
hostname r2
!
router bgp 65002
 bgp router-id 10.0.0.6
 neighbor 10.0.0.5 remote-as 65000
 neighbor 10.0.2.2 remote-as 65010
 !
 address-family ipv4 unicast
  neighbor 10.0.0.5 activate
  neighbor 10.0.2.2 activate
 exit-address-family
!
```

**`/tmp/frr-anycast-anya.conf`** (AS 65010 — Node A announces anycast prefix):

```
frr version 8.5
hostname anya
!
router bgp 65010
 bgp router-id 10.0.1.2
 neighbor 10.0.1.1 remote-as 65001
 !
 address-family ipv4 unicast
  network 10.9.9.0/24
  neighbor 10.0.1.1 activate
 exit-address-family
!
```

**`/tmp/frr-anycast-anyb.conf`** (AS 65010 — Node B also announces same prefix):

```
frr version 8.5
hostname anyb
!
router bgp 65010
 bgp router-id 10.0.2.2
 neighbor 10.0.2.1 remote-as 65002
 !
 address-family ipv4 unicast
  network 10.9.9.0/24
  neighbor 10.0.2.1 activate
 exit-address-family
!
```

### Step 3: Start All BGP Daemons

```bash
for ns in client r1 r2 anya anyb; do
  mkdir -p /var/run/frr-$ns /var/log/frr-$ns
  ip netns exec "$ns" /usr/lib/frr/zebra \
    --config_file /tmp/frr-anycast-${ns}.conf \
    --pid_file /var/run/frr-${ns}/zebra.pid \
    --log file:/var/log/frr-${ns}/zebra.log \
    --vty_socket /var/run/frr-${ns}/zebra.vty \
    --daemon
  sleep 1
  ip netns exec "$ns" /usr/lib/frr/bgpd \
    --config_file /tmp/frr-anycast-${ns}.conf \
    --pid_file /var/run/frr-${ns}/bgpd.pid \
    --log file:/var/log/frr-${ns}/bgpd.log \
    --vty_socket /var/run/frr-${ns}/bgpd.vty \
    --daemon
done
sleep 25
echo "BGP should be up."
```

### Step 4: Verify Anycast Behaviour

Check the client's BGP table:

```bash
sudo ip netns exec client vtysh \
  --vty_socket /var/run/frr-client/bgpd.vty \
  -c "show bgp ipv4 unicast 10.9.9.0/24"
```

You should see two paths: one via R1 (LOCAL_PREF 200) and one via R2 (LOCAL_PREF 100). The `>` marker shows the selected best path — it should be via R1.

Ping the anycast address from the client:

```bash
sudo ip netns exec client ping -c3 10.9.9.1
```

Now simulate Node A going offline by withdrawing its BGP announcement:

```bash
sudo kill $(sudo ip netns exec anya cat /var/run/frr-anya/bgpd.pid)
sleep 5   # wait for BGP hold timer
```

Check the client's BGP table again. The R1 path should be gone. Ping again — traffic should still reach 10.9.9.1, now via Node B through R2:

```bash
sudo ip netns exec client ping -c3 10.9.9.1
# Should still succeed — anycast failover worked
```

## Exercises

1. **Measure failover time**: Run a continuous ping while killing AnyA's bgpd. Count the lost packets. How does the outage duration compare to what you expect based on the BGP hold timer?

2. **Equal-cost anycast**: Remove the PREFER-R1 route-map. Now both paths have the same LOCAL_PREF. Run many pings. Does traffic consistently prefer one path? Run `traceroute 10.9.9.1` from the client and examine the path.

3. **DNS anycast in practice**: Use `dig +short txt chaos version.bind @a.root-servers.net` and then `@b.root-servers.net`. These queries go to different anycast nodes. Try using `dig` with `+time=1` to measure round-trip latency to several root servers from your location.

4. **Health-check-driven withdrawal**: Write a short Bash script that pings 10.9.9.1 from inside AnyA's namespace, and if the ping fails, kills AnyA's bgpd (simulating an automatic withdrawal on health failure).

5. **Research Cloudflare's anycast implementation**: Cloudflare's blog has detailed posts on how they use anycast. Find and read one. What additional mechanisms do they use beyond basic BGP anycast to handle load distribution across anycast nodes in the same PoP?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Anycast | "routing to the nearest" | One IP address announced by multiple nodes; BGP routing causes traffic to land at the topologically closest node |
| PoP | "Point of Presence" | A physical data centre location where a network operator has equipment connected to the Internet |
| BGP withdrawal | "route withdrawal" | A BGP UPDATE message advertising that a previously announced prefix is no longer reachable |
| Failover | "traffic shift" | When one anycast node's BGP announcement disappears, other nodes absorb the traffic automatically |
| CDN | "Content Delivery Network" | Infrastructure that serves content from nodes close to users; anycast is a key enabling mechanism |
| DNS anycast | "anycast DNS" | Using anycast to serve DNS queries — the same resolver IP is hosted at dozens of locations globally |

# Observe VLANs with 802.1Q Tags

> A VLAN cuts one physical switch into multiple isolated virtual switches — traffic on VLAN 10 literally cannot reach VLAN 20 without passing through a router, even if both VLANs share the same physical hardware.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 1, Lesson 04 — Build a Layer-2 Switch Simulation
**Time:** ~40 minutes

## Learning Objectives
- Explain what a VLAN is and why network segmentation matters
- Create Linux VLAN subinterfaces using `ip link add link ... type vlan id N`
- Create a Linux bridge and attach VLAN interfaces to it
- Verify that hosts on different VLANs cannot reach each other without a router
- Explain how 802.1Q tags work at the byte level

## The Problem

Imagine a company with 200 employees on one floor. Sales, Engineering, and Finance all connect to the same physical switches. Without VLANs:
- An employee in Sales can reach any server in Finance — a security risk
- A broadcast storm in the Sales network affects Engineering's machines
- The network admin cannot apply different policies to different departments

The naive solution is to buy three separate sets of switches — one per department. But this is expensive, wastes hardware, and makes reconfiguration slow (moving a user between departments requires physically replugging cables).

VLANs (Virtual Local Area Networks) solve this at the software level. You tag each frame with a VLAN ID (1–4094). The switch checks the VLAN tag before forwarding — it only forwards frames to ports in the same VLAN. No frame ever crosses VLAN boundaries without passing through a router (which you can then filter with access control lists).

This is not just a corporate network concept. VLANs appear everywhere:
- Cloud providers use VLANs to isolate customer traffic on shared hardware
- Docker uses network namespaces + bridges (similar concept) to isolate containers
- Home routers often put IoT devices on a separate VLAN from laptops
- Internet exchange points use VLANs to separate customer peering sessions

## The Concept

### The 802.1Q VLAN Tag

The 802.1Q standard defines how to add a VLAN identifier to an Ethernet frame. It inserts a 4-byte tag between the Source MAC and the EtherType fields:

```
Standard Ethernet II frame (no VLAN):
+--dst MAC--+--src MAC--+--EtherType--+--Payload--+
| 6 bytes   | 6 bytes   | 2 bytes     | 46-1500 B |

802.1Q tagged frame:
+--dst MAC--+--src MAC--+--802.1Q Tag--+--EtherType--+--Payload--+
| 6 bytes   | 6 bytes   | 4 bytes      | 2 bytes     | 46-1500 B |
                          ^
                          Inserted here
```

The 4-byte 802.1Q tag structure:

```
Byte  Field                       Bits    Notes
----  --------------------------  ------  ------------------------------------
0-1   TPID (Tag Protocol ID)      16      Always 0x8100 for 802.1Q
        ↳ This is also the EtherType field when the switch reads bytes 12-13
2     PCP (Priority Code Point)   3       QoS priority (0-7)
      DEI (Drop Eligible Ind.)    1       Whether frame can be dropped if congested
3     VID (VLAN Identifier)       12      VLAN ID: 0 = no VLAN, 1-4094 = VLAN, 4095 = reserved
```

When a switch receives a frame:
- If bytes 12–13 are `0x8100`: it is a tagged frame → read the VLAN ID from the tag
- Otherwise: it is an untagged frame → assign to the port's default VLAN (access port)

### Access Ports vs. Trunk Ports

```
Access Port:
  - Belongs to exactly one VLAN
  - Frames going OUT are untagged (tag stripped before delivery to the host)
  - Frames coming IN are untagged (switch adds the port's VLAN tag internally)
  - End hosts do not know or care about VLANs

Trunk Port:
  - Carries multiple VLANs
  - Frames going OUT carry 802.1Q tags (host must understand 802.1Q)
  - Frames coming IN may be tagged or untagged (native VLAN)
  - Used between switches and between switches and routers
```

```
                    +-------------------+
  VLAN 10 hosts     |      Switch       |    Trunk to router
  access port 1 ----|port1  port2  port3|----port3 carries all VLANs
  VLAN 10 host -----| VLAN10           |
                    |                   |
  VLAN 20 hosts     |                   |
  access port 4 ----|port4  port5       |
  VLAN 20 host -----| VLAN20           |
                    +-------------------+
                           |
              VLAN 10 and VLAN 20 cannot communicate
              without going through port3 (router)
```

### Inter-VLAN Routing: Why VLANs Need a Router

A VLAN is, by definition, an isolated Layer 2 domain. A broadcast sent on VLAN 10 stays on VLAN 10. An ARP request on VLAN 10 cannot reach VLAN 20.

For hosts on different VLANs to communicate, a packet must go UP to Layer 3 (IP routing) and then come back down. This is "inter-VLAN routing," and it requires either:
1. A separate physical router with one interface per VLAN, OR
2. A "Router on a Stick" — one router port configured as a trunk, with subinterfaces per VLAN, OR
3. A Layer 3 switch — a switch with built-in IP routing

In this lesson, we simulate VLANs on Linux using bridge + VLAN subinterfaces. You will verify isolation by showing that hosts on VLAN 10 cannot ping hosts on VLAN 20.

### Linux VLAN Implementation

Linux implements VLANs as subinterfaces. A VLAN subinterface sits on top of a physical interface and handles VLAN tagging transparently:

```
eth0 (physical interface, receives all frames)
  ├── eth0.10 (VLAN 10 subinterface — sees only VLAN 10 frames)
  └── eth0.20 (VLAN 20 subinterface — sees only VLAN 20 frames)
```

When you assign an IP to `eth0.10`, the kernel automatically tags outgoing frames with VLAN ID 10 and strips the tag from incoming VLAN-10 frames before delivering them to the socket.

## Build It

### Step 1 — Load the 8021q kernel module

```bash
sudo modprobe 8021q
lsmod | grep 8021q
# Expected: 8021q    36864  0
```

### Step 2 — Create the bridge interface

A Linux bridge acts like a virtual switch. We will connect our VLAN subinterfaces to it:

```bash
# Create a bridge named br0
sudo ip link add name br0 type bridge

# Bring the bridge up
sudo ip link set br0 up

# Verify
ip link show br0
```

### Step 3 — Create dummy interfaces as "hosts"

Each dummy interface represents a host connected to the bridge:

```bash
sudo modprobe dummy

# Host A: will be on VLAN 10
sudo ip link add dev host-a type dummy
sudo ip link set host-a up

# Host B: will be on VLAN 10 (same VLAN as A)
sudo ip link add dev host-b type dummy
sudo ip link set host-b up

# Host C: will be on VLAN 20 (different VLAN)
sudo ip link add dev host-c type dummy
sudo ip link set host-c up
```

### Step 4 — Create VLAN subinterfaces

```bash
# VLAN 10 subinterface on host-a
sudo ip link add link host-a name host-a.10 type vlan id 10
sudo ip link set host-a.10 up

# VLAN 10 subinterface on host-b
sudo ip link add link host-b name host-b.10 type vlan id 10
sudo ip link set host-b.10 up

# VLAN 20 subinterface on host-c
sudo ip link add link host-c name host-c.20 type vlan id 20
sudo ip link set host-c.20 up

# Verify all VLAN interfaces exist
ip link show type vlan
```

Expected output shows each VLAN interface with its parent:
```
host-a.10@host-a: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ... VLAN: id 10
host-b.10@host-b: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ... VLAN: id 10
host-c.20@host-c: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ... VLAN: id 20
```

### Step 5 — Assign IP addresses

```bash
# VLAN 10 subnet: 10.10.0.0/24
sudo ip addr add 10.10.0.1/24 dev host-a.10
sudo ip addr add 10.10.0.2/24 dev host-b.10

# VLAN 20 subnet: 10.20.0.0/24
sudo ip addr add 10.20.0.1/24 dev host-c.20

# Verify addresses
ip addr show host-a.10
ip addr show host-b.10
ip addr show host-c.20
```

### Step 6 — Test Layer 2 isolation

Add subinterfaces to the bridge and test connectivity:

```bash
# Add interfaces to the bridge (simplified — in a real VLAN setup
# you would configure bridge VLAN filtering)
sudo ip link set host-a.10 master br0
sudo ip link set host-b.10 master br0
sudo ip link set host-c.20 master br0
```

Test that host-a and host-b (same VLAN 10) can communicate at Layer 3:

```bash
# host-a.10 (10.10.0.1) → host-b.10 (10.10.0.2)
ping -c 2 -I host-a.10 10.10.0.2
```

Test that host-a (VLAN 10) cannot reach host-c (VLAN 20) directly:

```bash
# host-a.10 (10.10.0.1) → host-c.20 (10.20.0.1)
# This should fail — different subnets, no router configured
ping -c 2 -I host-a.10 10.20.0.1
# Expected: "Network is unreachable" or all packets lost
```

### Step 7 — Verify the VLAN tag in a capture

Capture frames on the parent interface to see the raw 802.1Q tag:

```bash
# Capture on host-a (parent interface, sees tagged frames)
sudo tcpdump -i host-a -n -e -c 4 &

# Generate traffic from host-a.10
ping -c 2 -I host-a.10 10.10.0.2

wait
```

In the tcpdump output, look for `ethertype 802.1Q (0x8100)` and the `vlan N` annotation — confirming the VLAN tag is present on the wire.

### Step 8 — Clean up

```bash
# Remove IP addresses and VLAN subinterfaces
sudo ip link set br0 down
sudo ip link delete br0

sudo ip link set host-a.10 down && sudo ip link delete host-a.10
sudo ip link set host-b.10 down && sudo ip link delete host-b.10
sudo ip link set host-c.20 down && sudo ip link delete host-c.20

sudo ip link delete host-a
sudo ip link delete host-b
sudo ip link delete host-c

echo "Cleanup complete"
ip link show type vlan  # Should show nothing
ip link show type dummy # Should show nothing
```

## Exercises

1. **VLAN tag byte decode** — Capture a frame from Step 7 and find the 4 bytes of the 802.1Q tag in the hex dump. Decode the TPID (0x8100), PCP (should be 0), DEI (should be 0), and VID (should be 10). Confirm the values match your configuration.

2. **Inter-VLAN routing** — Add a `router0` interface with two IPs: `10.10.0.254/24` (as default gateway for VLAN 10) and `10.20.0.254/24` (for VLAN 20). Enable IP forwarding with `sysctl -w net.ipv4.ip_forward=1`. Now can host-a reach host-c through the router? Trace the packets.

3. **VLAN storm test** — What happens if you put hosts from the same VLAN (10.10.0.1 and 10.10.0.2) in different subnets — say assign 10.10.0.1/24 to one and 192.168.5.1/24 to another? They are on the same VLAN but have different IP subnets. Do ARP and ping work?

4. **802.1Q double tagging** — Research "Q-in-Q" (802.1ad) double tagging, used by ISPs to carry customer VLANs inside provider VLANs. What is the structure of a double-tagged frame? What is the TPID used by the outer tag?

5. **PVID and native VLAN** — Research what the "native VLAN" on a trunk port means. What happens to untagged frames arriving on a trunk port? Why is it a security risk to leave the native VLAN as VLAN 1 on production networks?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| VLAN | "virtual LAN" | A logically isolated Layer 2 broadcast domain within a switch. Hosts on different VLANs cannot communicate directly — traffic must go through a router. Defined by IEEE 802.1Q. |
| 802.1Q | "dot1q", "VLAN tagging" | The IEEE standard that defines how to add a 4-byte VLAN tag between the source MAC and EtherType fields of an Ethernet frame. TPID=0x8100 identifies a tagged frame. |
| trunk port | "tagged port" | A switch port that carries frames for multiple VLANs, distinguished by 802.1Q tags. Used between switches, between switches and routers, and in hypervisors where one physical NIC carries many VMs' traffic. |
| access port | "untagged port" | A switch port that belongs to exactly one VLAN. The switch strips VLAN tags before delivering frames to the host (the host sees normal untagged Ethernet). Used for end hosts. |
| inter-VLAN routing | "VLAN routing" | The process of moving traffic between VLANs by routing at Layer 3. Requires a router (physical, virtual, or built into a Layer 3 switch). VLAN isolation means you can apply firewall rules at VLAN boundaries. |
| PVID | "port VLAN ID" | The default VLAN ID assigned to untagged frames arriving on a port. On a trunk port, this is the "native VLAN" — untagged frames are assumed to belong to this VLAN. |

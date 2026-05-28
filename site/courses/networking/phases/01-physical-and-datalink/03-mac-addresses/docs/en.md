# Understand MAC Addresses

> A MAC address is not just a number — it encodes the manufacturer, tells you whether the frame is for one host or many, and disappears at every router hop while an IP address travels end-to-end.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 1, Lesson 02 — Dissect an Ethernet Frame
**Time:** ~30 minutes

## Learning Objectives
- Explain the structure of a MAC address (OUI + NIC-specific portion)
- Distinguish unicast, multicast, and broadcast MAC addresses by inspecting the first byte
- Use the `ip neigh` command to observe the ARP table
- Watch ARP resolve a MAC address in real time with tcpdump
- Explain why MAC addresses are only relevant on a single network segment

## The Problem

When your computer sends a packet to `192.168.1.5`, the IP address identifies *which host* should receive it. But IP addresses are abstract — they say nothing about *which wire* to use, or *which NIC on that wire* should pick up the frame.

On an Ethernet network, every frame must carry a destination MAC address. The switch uses this MAC address to decide which physical port to forward the frame to. If you get the destination MAC wrong — or if it is missing entirely — the frame will never reach the right host.

This is the job of ARP (Address Resolution Protocol): given an IP address that you want to talk to, find out what MAC address it uses. ARP is invisible most of the time, but when it breaks — wrong entry in the ARP cache, ARP spoofing attack, stale ARP entry — the network silently fails.

Understanding MAC addresses also corrects a common misconception: many people think MAC addresses "travel with packets across the internet." They do not. MAC addresses only exist on one network segment. When a packet crosses a router, the router strips the old Ethernet frame and creates a brand new one with new source and destination MAC addresses for the next hop.

## The Concept

### MAC Address Structure

A MAC address is 6 bytes (48 bits) long. Written in human-readable form, each byte is shown as two hex digits separated by colons:

```
aa:bb:cc:dd:ee:ff
^       ^
|       |
OUI     NIC-specific
(first  (last 3 bytes)
3 bytes)
```

The first 3 bytes are the **OUI (Organizationally Unique Identifier)**, assigned by the IEEE to each manufacturer. Examples:
```
00:50:56    VMware (virtual machines)
00:1a:2b    Apple
fc:aa:14    Apple (another range)
00:15:5d    Microsoft (Hyper-V)
08:00:27    Oracle (VirtualBox)
dc:a6:32    Raspberry Pi Foundation
```

The last 3 bytes are the manufacturer's responsibility — they just need to be unique within their OUI space.

### The Two Special Bits in the First Byte

The first byte of a MAC address contains two special bits:

```
First byte: aa = 1010 1010
                      ^ ^
                      | └── Bit 0 (least significant): I/G bit
                      └──── Bit 1: U/L bit

I/G bit (bit 0):
  0 = Individual (unicast) — sent to exactly one NIC
  1 = Group (multicast or broadcast) — sent to multiple NICs

U/L bit (bit 1):
  0 = Universally administered (OUI-assigned by IEEE)
  1 = Locally administered (manually set or generated)
```

This means you can tell the type of a frame just by looking at the first byte:

```
Destination MAC     Binary first byte   Type
------------------  ------------------  ----------------
00:1a:2b:cc:dd:ee   00000000            Unicast (OUI-based)
ff:ff:ff:ff:ff:ff   11111111            Broadcast (all I/G and U/L bits set)
01:00:5e:xx:xx:xx   00000001            IPv4 multicast
33:33:xx:xx:xx:xx   00110011            IPv6 multicast
02:42:xx:xx:xx:xx   00000010            Locally administered (common in Docker)
```

### Unicast vs. Multicast vs. Broadcast

```
Type        First byte I/G bit    Destination       Who receives it?
----------  --------------------  ----------------  ---------------------------
Unicast     0                     One specific MAC  Only the NIC with that MAC
Multicast   1 (not all 1s)        Group address     NICs subscribed to the group
Broadcast   1 (all bytes 0xFF)    ff:ff:ff:ff:ff:ff Every NIC on the segment
```

Switches handle these differently:
- **Unicast**: forwarded to the specific port that learned this MAC address
- **Broadcast**: flooded out all ports (except the incoming port)
- **Multicast**: flooded (unless the switch does IGMP snooping to be smarter)

### ARP: The Bridge Between IP and MAC

When your computer wants to send a packet to `192.168.1.5`:
1. It checks its ARP cache: "Do I already know the MAC for 192.168.1.5?"
2. If yes: use the cached MAC, proceed immediately
3. If no: send an ARP request

An ARP request is an Ethernet broadcast frame containing:
- "I am 192.168.1.1 with MAC aa:bb:cc:11:22:33"
- "Who has 192.168.1.5? Please reply with your MAC"

The host at 192.168.1.5 sees the broadcast, recognizes its own IP, and sends a unicast ARP reply:
- "I am 192.168.1.5 with MAC dd:ee:ff:44:55:66"

Your computer caches this MAC-to-IP mapping and uses it for future frames. The cache entry typically expires after a few minutes.

```
Your PC (192.168.1.1)                    Target (192.168.1.5)
         |                                        |
         | ARP Request (broadcast)                |
         | Dst: ff:ff:ff:ff:ff:ff                |
         | "Who has 192.168.1.5?"                 |
         |--------------------------------------> |
         |                                        |
         |          ARP Reply (unicast)            |
         |          Src: dd:ee:ff:44:55:66        |
         |          "192.168.1.5 is at dd:ee:ff:44:55:66"
         | <--------------------------------------|
         |                                        |
         | [Now caches: 192.168.1.5 = dd:ee:ff:44:55:66]
         | [Sends the original IP packet directly]
```

### MAC Addresses Hop by Hop

This is the most important misconception to correct. When a packet crosses a router:

```
Before router:
  Ethernet frame:
    Src MAC: your-NIC-MAC
    Dst MAC: router-eth0-MAC
    [IP packet inside: Src IP=your-IP, Dst IP=remote-server-IP]

After router (new frame on next network segment):
  Ethernet frame:
    Src MAC: router-eth1-MAC   ← Router's MAC on outgoing interface
    Dst MAC: next-hop-MAC      ← Could be another router or the server
    [IP packet inside: Src IP=your-IP, Dst IP=remote-server-IP]  ← IP unchanged!
```

The IP addresses stay the same end-to-end. The MAC addresses change at every router hop. MAC addresses are a per-segment addressing mechanism.

## Build It

### Step 1 — Examine your ARP cache

```bash
ip neigh show
```

Expected output format:
```
192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
192.168.1.5 dev eth0 lladdr 11:22:33:44:55:66 STALE
```

Fields explained:
- `192.168.1.1` — the IP address
- `dev eth0` — which interface this entry was learned on
- `lladdr aa:bb:cc:dd:ee:ff` — the MAC address (link-layer address)
- `REACHABLE` — recently confirmed reachable
- `STALE` — not confirmed recently, but still in cache; will be rechecked on next use

### Step 2 — Look up an OUI

Look up the manufacturer of your default gateway's MAC address:

```bash
# Get your default gateway IP
GATEWAY=$(ip route show default | awk '/default via/ {print $3}' | head -1)
echo "Default gateway: $GATEWAY"

# Get the gateway's MAC from ARP cache
GW_MAC=$(ip neigh show "$GATEWAY" | awk '{print $5}' | head -1)
echo "Gateway MAC: $GW_MAC"

# Extract the OUI (first 3 bytes)
OUI=$(echo "$GW_MAC" | tr ':' '-' | cut -c1-8 | tr 'a-z' 'A-Z')
echo "OUI: $OUI"
```

To look up the OUI, you can use the `oui-database` package or query online:
```bash
# Install oui lookup tool (Debian/Ubuntu)
sudo apt-get install -y ieee-data

# Search for the OUI
grep -i "${OUI//-/:}" /usr/share/ieee-data/iab.txt 2>/dev/null || \
grep -i "$OUI" /usr/share/misc/oui.txt 2>/dev/null || \
echo "OUI database not found — search https://maclookup.app for $OUI"
```

### Step 3 — Watch ARP in real time

Clear the ARP cache for a specific entry to force ARP to run:

```bash
# First, ping something to populate the ARP cache
ping -c 1 192.168.1.1 2>/dev/null

# Show the current ARP table
ip neigh show

# Delete the gateway entry from cache (forces a fresh ARP request next time)
GATEWAY=$(ip route show default | awk '/default via/ {print $3}' | head -1)
sudo ip neigh del "$GATEWAY" dev "$(ip route show default | awk '{print $5}' | head -1)" 2>/dev/null || true
```

Now capture the ARP exchange:

```bash
# Get interface name
IFACE=$(ip route show default | awk '{print $5}' | head -1)

# Start capture (filter for ARP frames only)
sudo tcpdump -i "$IFACE" -n arp -c 4 &

# Trigger an ARP request by pinging the gateway
ping -c 1 "$GATEWAY"

wait
```

You should see:
```
ARP, Request who-has 192.168.1.1 tell 192.168.1.10, length 28
ARP, Reply 192.168.1.1 is-at aa:bb:cc:dd:ee:ff, length 28
```

The first line is your ARP request (broadcast). The second line is the reply (unicast back to you).

### Step 4 — Identify frame types by MAC

Write a one-liner to check if a MAC address is unicast, multicast, or broadcast:

```bash
# Check a specific MAC address
check_mac_type() {
    local mac="$1"
    # Extract the first byte (before the first colon)
    local first_byte_hex="${mac%%:*}"
    # Convert to decimal using bash arithmetic
    local first_byte=$((16#$first_byte_hex))
    # Check the least significant bit (I/G bit)
    local ig_bit=$((first_byte & 1))

    if [ "$mac" = "ff:ff:ff:ff:ff:ff" ]; then
        echo "$mac → BROADCAST"
    elif [ "$ig_bit" -eq 1 ]; then
        echo "$mac → MULTICAST"
    else
        echo "$mac → UNICAST"
    fi
}

# Test with different MAC addresses
check_mac_type "00:1a:2b:cc:dd:ee"   # Unicast
check_mac_type "ff:ff:ff:ff:ff:ff"   # Broadcast
check_mac_type "01:00:5e:01:02:03"   # IPv4 multicast
check_mac_type "33:33:00:00:00:01"   # IPv6 multicast
check_mac_type "02:42:ac:11:00:02"   # Docker locally-administered
```

### Step 5 — Verify MAC address locally administered bit

```bash
# Check your loopback MAC
ip link show lo | grep "link/ether"

# Check your main interface MAC
ip link show | grep -A1 "state UP" | grep "link/ether"

# Create a dummy interface with a locally-administered MAC
sudo modprobe dummy
sudo ip link add dev testmac0 type dummy
sudo ip link set testmac0 address 02:00:00:aa:bb:cc  # 02 = locally administered
ip link show testmac0 | grep "link/ether"
# The U/L bit (bit 1 of first byte) = 1 in 0x02 = 00000010

sudo ip link delete testmac0
```

## Exercises

1. **OUI census** — Run `ip neigh show` and for each MAC address in your ARP table, look up its manufacturer. If you are on a VM, most MACs will belong to VMware, VirtualBox, or QEMU/KVM.

2. **ARP spoofing awareness** — ARP has no authentication: any host can send a fake ARP reply claiming to be the gateway. Research how ARP cache poisoning works. What does an attacker gain by sending `192.168.1.1 is-at attacker-MAC`?

3. **Gratuitous ARP** — A "gratuitous ARP" is an ARP reply sent without a corresponding request. When and why is it used? (Hint: think about network failover and VM migration.)

4. **IPv6 NDP** — IPv6 replaces ARP with NDP (Neighbor Discovery Protocol), which uses ICMPv6 multicast instead of Ethernet broadcast. Run `ip -6 neigh show` to see your IPv6 neighbor table. What multicast MAC addresses do you see?

5. **Docker MAC investigation** — If Docker is installed, run `docker run -d nginx` (or any container). Run `docker inspect <container-id> | grep MacAddress`. The Docker-assigned MAC starts with `02:42`. Why? (Answer: 02 in hex = 00000010 in binary; bit 1 is the U/L bit = locally administered.)

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| OUI | "vendor prefix" | Organizationally Unique Identifier. The first 3 bytes of a MAC address, assigned by the IEEE to a specific manufacturer. Allows you to identify which company made a NIC. |
| I/G bit | "unicast or multicast bit" | Bit 0 (least significant) of the first MAC address byte. 0 = Individual (unicast), 1 = Group (multicast or broadcast). You can check this bit to determine frame type without looking at the full address. |
| U/L bit | "universal or local bit" | Bit 1 of the first MAC address byte. 0 = Universally administered (assigned by IEEE to manufacturer), 1 = Locally administered (set manually or generated randomly). Docker and VMs use locally-administered MACs. |
| ARP cache | "ARP table" | A kernel-maintained table mapping IP addresses to MAC addresses, populated by ARP request/reply exchanges. Entries expire after a few minutes (typically 30–60s on Linux). View with `ip neigh show`. |
| gratuitous ARP | "unsolicited ARP" | An ARP reply sent without a request, used to announce or update an IP-to-MAC mapping. Used by systems after getting a new IP address, by VMs after migration, and by network failover systems. |

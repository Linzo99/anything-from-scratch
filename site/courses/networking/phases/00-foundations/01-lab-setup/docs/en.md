# Set Up a Linux Networking Lab

> You cannot learn networking by reading alone — you need a machine that lets you capture real packets, forge custom frames, and watch the kernel's routing table update in real time.

**Type:** Build
**Languages:** Bash
**Prerequisites:** None
**Time:** ~45 minutes

## Learning Objectives
- Install and verify four essential networking tools: Wireshark, netcat, nmap, and iproute2
- Confirm that Wireshark can capture live traffic on the loopback interface
- Understand what each tool is for and when to reach for it
- Run a first capture and see raw packet data on the terminal
- Set your shell environment up so these tools are always available

## The Problem

Every networking concept in this course is grounded in observable behavior. When someone says "TCP does a three-way handshake," that is only a useful claim if you can *see* the three SYN, SYN-ACK, and ACK packets traveling across a wire. If you take it on faith, you will hit a wall the moment things break in production.

The standard Linux desktop or server installation omits most packet-level tools by default. A fresh Ubuntu 24.04 machine, for example, ships without `tcpdump`, without `nmap`, and without `Wireshark`. The `ip` command (from the `iproute2` package) may be present, but older systems still default to the deprecated `ifconfig` from `net-tools`.

More importantly, capturing packets requires elevated privileges. On Linux, the kernel restricts raw socket access to the root user unless you explicitly grant the capture capability to a user-space program. Part of setting up this lab is understanding *why* that restriction exists and how to work within it safely.

By the end of this lesson your machine will be a fully equipped networking workbench. Every subsequent lesson assumes this setup is complete.

## The Concept

### The Four Tools and What They Do

Think of these four tools as four different lenses you can hold up to a network:

```
Tool        Layer focus     What it does
----------  --------------  -----------------------------------------------
iproute2    L2 / L3         Reads and writes the kernel's networking state:
                            interfaces, addresses, routes, ARP table, etc.
                            Commands: ip addr, ip link, ip route, ss

tcpdump     L2–L7           Captures live packets from any interface and
                            prints them as text. The network microscope.

nmap        L3–L7           Probes remote hosts: discovers open ports,
                            guesses OS, maps network topology.

netcat      L3–L4           Opens raw TCP or UDP connections from the
(nc)                        command line. The networking Swiss Army knife.
```

These tools operate at different layers of the protocol stack. You will hear about the OSI model in Lesson 03; for now, "layer" just means how close to the hardware vs. the application you are working.

### The Loopback Interface

Every Linux machine has a special network interface called `lo` (loopback). Any packet you send to `127.0.0.1` (IPv4) or `::1` (IPv6) goes into the kernel and comes right back out — it never touches a physical wire.

```
Your process
    |
    | write() to socket bound to 127.0.0.1
    v
Linux TCP/IP stack
    |
    | "destination is 127.0.0.1 — route to loopback"
    v
lo interface (software only — no hardware)
    |
    | packet loops back
    v
Linux TCP/IP stack (receiving side)
    |
    v
Your process (or another process listening on that port)
```

The loopback interface is perfect for a lab because:
1. You do not need a network cable or a second machine.
2. Traffic never leaves the host, so you can experiment freely.
3. Capture permissions are easier to set up (no promiscuous mode needed).

### Capture Permissions: Why Root?

Raw sockets let a program read *every* packet on a wire, not just the ones addressed to it. That is a serious privacy risk on a shared network — you could read other users' unencrypted traffic. Linux therefore requires `CAP_NET_RAW` capability or root privilege to open a raw socket.

Two safe approaches:
- **Run as root (simple, lab-only):** `sudo tcpdump`. Fine for a personal lab VM.
- **Add your user to the `wireshark` group (preferred):** The Wireshark installer creates a `dumpcap` binary that is setuid to a special group. Members of that group can capture without full root.

## Build It

### Step 1 — Update package lists

Always update before installing to avoid installing stale package versions:

```bash
sudo apt-get update
```

If you are on a Red Hat / Fedora / CentOS system, replace `apt-get` with `dnf` throughout this lesson.

### Step 2 — Install iproute2

On modern Ubuntu, `iproute2` is usually already installed. Verify:

```bash
ip --version
```

Expected output looks like:
```
ip utility, iproute2-6.x.x, libbpf 1.x.x
```

If the command is not found:
```bash
sudo apt-get install -y iproute2
```

Verify the install worked:
```bash
ip addr show lo
```

You should see the loopback interface listed with address `127.0.0.1/8` and `::1/128`.

### Step 3 — Install tcpdump

```bash
sudo apt-get install -y tcpdump
```

Verify:
```bash
tcpdump --version
```

Expected output:
```
tcpdump version 4.x.x
libpcap version 1.x.x (with TPACKET_V3)
```

### Step 4 — Install Wireshark

```bash
sudo apt-get install -y wireshark
```

During installation, a dialog will ask:
> "Should non-superusers be able to capture packets?"

Select **Yes**. This configures `dumpcap` with the correct group permissions.

After installation, add your user to the `wireshark` group:
```bash
sudo usermod -aG wireshark $USER
```

**Important:** Log out and log back in for group membership to take effect. Verify your groups with:
```bash
groups
# Should include: wireshark
```

### Step 5 — Install nmap

```bash
sudo apt-get install -y nmap
```

Verify:
```bash
nmap --version
```

Expected output starts with:
```
Nmap version 7.x ( https://nmap.org )
```

### Step 6 — Install netcat

On Debian/Ubuntu there are two versions of netcat. Install `ncat` (the nmap project's version — more feature-complete):

```bash
sudo apt-get install -y ncat
```

Verify:
```bash
ncat --version
```

If you need the classic BSD version for compatibility:
```bash
sudo apt-get install -y netcat-openbsd
# Binary is nc
nc -h
```

### Step 7 — Verify: capture live loopback traffic

This is the critical check. Open two terminal windows.

**Terminal 1 — start capturing:**
```bash
sudo tcpdump -i lo -n -c 10
```

Flag breakdown:
- `-i lo` — listen on the loopback interface
- `-n` — do not resolve IP addresses to hostnames (faster, clearer)
- `-c 10` — stop after capturing 10 packets

**Terminal 2 — generate some traffic:**
```bash
ping -c 4 127.0.0.1
```

Back in Terminal 1, you should see output like:
```
tcpdump: verbose output suppressed, use -v or -vv for full protocol decode
listening on lo, link-type EN10MB (Ethernet), snapshot length 262144 bytes
14:23:01.123456 IP 127.0.0.1 > 127.0.0.1: ICMP echo request, id 3, seq 1, length 64
14:23:01.123478 IP 127.0.0.1 > 127.0.0.1: ICMP echo reply, id 3, seq 1, length 64
...
10 packets captured
10 packets received by filter
0 packets dropped by kernel
```

If you see those ICMP lines, your lab is working correctly.

### Step 8 — Verify: nmap localhost scan

```bash
nmap -sT 127.0.0.1
```

This performs a TCP connect scan on the loopback address. You will see a list of open ports (SSH on 22 if it is running, etc.). The exact ports depend on what services your machine runs.

### Step 9 — Verify: netcat echo test

Open two terminals again.

**Terminal 1 — start a listener on port 9999:**
```bash
ncat -l 9999
```

**Terminal 2 — connect and send a message:**
```bash
echo "hello networking lab" | ncat 127.0.0.1 9999
```

You should see `hello networking lab` appear in Terminal 1. This confirms netcat can open TCP connections and move data.

### Step 10 — (Optional) Create a lab alias file

Add these shortcuts to your `~/.bashrc` or `~/.zshrc`:

```bash
# Networking lab aliases
alias capture-lo='sudo tcpdump -i lo -n -vv'
alias myip='ip addr show | grep "inet " | grep -v 127'
alias ports='ss -tlnp'
alias scan-local='nmap -sn 192.168.1.0/24'
```

Reload your shell:
```bash
source ~/.bashrc
```

## Exercises

1. **Verify all four tools** — Run the version check commands for each tool and paste the output into a text file. This is your baseline snapshot.

2. **Capture an HTTP request** — If your machine has curl installed, run `sudo tcpdump -i lo -n -A port 8080` in one terminal and in another terminal start `python3 -m http.server 8080`, then `curl http://127.0.0.1:8080`. Find the HTTP GET request in the tcpdump output.

3. **Explore iproute2** — Run `ip route show`. Identify: the default gateway, and which interface handles local traffic. Add a comment explaining what each line means.

4. **Non-root capture** — If you added yourself to the `wireshark` group, try running `tcpdump -i lo -n -c 5` without `sudo`. Does it work? If not, investigate why (hint: log out and back in).

5. **nmap host discovery** — Run `nmap -sn 127.0.0.0/8`. What does the `-sn` flag do? Why does it only find one host?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| loopback | "localhost" | A virtual network interface (`lo`) that routes packets back to the same host without touching physical hardware |
| raw socket | "packet capture" | A socket type that bypasses the normal transport layer and receives every packet on an interface, not just those addressed to the process |
| iproute2 | "the ip command" | A suite of Linux utilities (`ip`, `ss`, `tc`) that replace the older `ifconfig`/`route`/`netstat` tools from net-tools |
| tcpdump | "packet sniffer" | A command-line program that reads a copy of every packet the kernel processes on a given interface |
| promiscuous mode | "sniffing mode" | NIC setting that accepts all frames on the wire, not just those with a matching destination MAC address |
| CAP_NET_RAW | "root for networking" | A Linux capability that grants raw socket access without full superuser privileges |

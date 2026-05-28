# Scan a Network with nmap

> nmap turns invisible network hosts into a readable report in seconds — understanding what it does makes you a better defender.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 3, Lesson 01 — TCP Three-Way Handshake
**Time:** ~30 minutes

## Learning Objectives
- Explain what a SYN scan is and why it is called "half-open"
- Run a targeted nmap SYN scan and service-version probe against a local lab host
- Interpret nmap's port states: open, closed, filtered
- Understand what information OS fingerprinting reveals and how it works
- Describe the difference between what nmap can find and what it cannot

## The Problem

Before an attacker targets a system, they enumerate it: What ports are open? What software is running? What OS? This phase is called reconnaissance. Without it, attackers are blind. But so are defenders who don't periodically scan their own infrastructure.

Most organisations do not know exactly which ports are open on which machines. They install a service, open a port, and forget. Years later there is an old Node.js app on port 3001 that nobody maintained. A regular nmap scan of your own network reveals:
- Services you forgot you left running
- Services exposed on unexpected interfaces
- Outdated software versions with known CVEs
- Machines that should not be internet-accessible

This lesson teaches you to run nmap intelligently and, more importantly, to understand what each scan type actually does so you can interpret results correctly.

## The Concept

### How Port Scanning Works

A port scanner needs to determine, for each port, whether anything is listening. There are several ways to do this:

**TCP Connect scan (`-sT`)**: The scanner performs a complete three-way handshake. Easy to detect (shows up in server logs as a connection). Available without root.

**SYN scan (`-sS`)**: The scanner sends a SYN packet. If it gets a SYN-ACK back, the port is open. The scanner immediately sends RST (never completes the handshake). It is called "half-open" or "stealth" because the connection is never completed. Requires raw socket access (root).

```
SYN Scan — Port OPEN:
  Scanner ──[SYN]──────────► Target
  Scanner ◄──[SYN-ACK]────── Target   ← port is open
  Scanner ──[RST]──────────► Target   ← kill it before completing

SYN Scan — Port CLOSED:
  Scanner ──[SYN]──────────► Target
  Scanner ◄──[RST-ACK]────── Target   ← port is closed

SYN Scan — Port FILTERED:
  Scanner ──[SYN]──────────► Target
  [no response]                        ← firewall dropped the packet
```

**UDP scan (`-sU`)**: Sends a UDP packet. If a UDP port is closed, the target usually replies with ICMP "Port Unreachable." If open, the service may reply or not. UDP scanning is slow because of ICMP rate limits and the unreliable nature of no-response meaning "open or filtered."

### Port States

| State | Meaning |
|-------|---------|
| `open` | A service is actively listening and accepted the probe |
| `closed` | Nothing is listening; the OS sent back a RST or ICMP unreachable |
| `filtered` | A firewall or filter dropped the probe; no response (nmap times out) |
| `open\|filtered` | UDP probe got no response — could be open or filtered |
| `unfiltered` | Port responds to ACK probes but open/closed unknown |

### Service Version Detection (`-sV`)

After finding open ports, nmap can probe each port with protocol-specific probes to identify the service and its version. It sends various banner-triggering payloads and compares responses against its database (`nmap-service-probes`).

```
Port 22 open → nmap sends a probe
Target replies: "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6"
nmap reports: 22/tcp open  ssh  OpenSSH 8.9p1 Ubuntu
```

This tells you exact software versions, which you can cross-reference with CVE databases.

### OS Fingerprinting (`-O`)

Different OS implementations of the TCP/IP stack respond slightly differently to unusual probes:
- Initial window size in SYN-ACK
- TCP options ordering (MSS, SACK, Timestamps, Window Scale)
- Response to TCP packets with unusual flag combinations
- IP ID values and TTL

nmap collects these "fingerprints" and matches them against its OS database. Results are probabilistic — nmap reports confidence percentages.

### What nmap CANNOT Find

- Services behind application-layer firewalls that inspect payload
- Services using non-standard protocols on non-standard ports (without `-sV`)
- Active sessions (nmap shows open ports, not current connections — use `ss -tnp` for that)
- Anything behind NAT that does not forward the port

## Build It

### Lab Setup: Target Host

For safe practice, run nmap against a local target. The simplest approach: scan your own machine, or start a few services in a Docker container or VM.

```bash
# Start a simple target with a few services (requires Docker)
docker run -d --name nmap-target \
  -p 2222:22 -p 8080:80 -p 8443:443 \
  linuxserver/openssh-server

# Get the target's IP
docker inspect nmap-target | grep IPAddress
```

Or simply scan localhost (`127.0.0.1`) if you have services running.

**IMPORTANT**: Only scan machines you own or have explicit written permission to scan. Scanning others' machines without permission is illegal in many jurisdictions.

### Step 1: Basic SYN Scan

```bash
# Scan the 1000 most common ports (requires root for SYN scan)
sudo nmap -sS 127.0.0.1

# Sample output:
# Starting Nmap 7.93 ( https://nmap.org )
# Nmap scan report for localhost (127.0.0.1)
# Host is up (0.000085s latency).
# Not shown: 994 closed tcp ports (reset)
# PORT     STATE SERVICE
# 22/tcp   open  ssh
# 80/tcp   open  http
# 443/tcp  open  https
# 5432/tcp open  postgresql
```

### Step 2: Service Version Detection

```bash
# Add -sV to detect service versions
sudo nmap -sS -sV 127.0.0.1 -p 22,80,443,5432

# Sample output:
# PORT     STATE SERVICE    VERSION
# 22/tcp   open  ssh        OpenSSH 8.9p1 Ubuntu 3ubuntu0.6
# 80/tcp   open  http       nginx 1.24.0
# 443/tcp  open  ssl/https  nginx 1.24.0
# 5432/tcp open  postgresql PostgreSQL DB 9.6.0 or later
```

### Step 3: OS Fingerprinting

```bash
# Add -O for OS detection
sudo nmap -sS -O 127.0.0.1

# Sample output (when scanning a remote host):
# Running: Linux 5.X|6.X
# OS CPE: cpe:/o:linux:linux_kernel:5
# OS details: Linux 5.10 - 6.4
# Network Distance: 0 hops
```

OS fingerprinting works best against remote hosts. On localhost (127.0.0.1) nmap will report a low-confidence result.

### Step 4: Scan a Subnet

```bash
# Discover all hosts on your LAN and scan them
# -sn = ping scan only (host discovery, no port scan)
sudo nmap -sn 192.168.1.0/24

# Then scan all discovered hosts for top 100 ports
sudo nmap -sS --top-ports 100 192.168.1.0/24
```

### Step 5: Scan for Specific CVE-Relevant Ports

```bash
# Scan for commonly exploited services:
# 21=FTP, 23=Telnet, 3389=RDP, 5900=VNC, 27017=MongoDB
sudo nmap -sS -sV -p 21,23,3389,5900,27017 192.168.1.0/24

# Any of these showing as "open" in an unexpected place is a finding.
```

### Step 6: Understand Timing Templates

nmap has six timing levels (`-T0` to `-T5`):

```
-T0 (paranoid):    Very slow, avoids IDS detection
-T1 (sneaky):      Slow, low bandwidth
-T2 (polite):      Reduces interference with target
-T3 (normal):      Default
-T4 (aggressive):  Assumes fast reliable network
-T5 (insane):      Very fast, may miss open ports on slow targets
```

```bash
# Aggressive scan (fast, for lab use)
sudo nmap -sS -T4 -sV 127.0.0.1

# Stealthy scan (for authorised red-team exercises)
sudo nmap -sS -T1 192.168.1.1
```

### Step 7: Output Formats

```bash
# Save results in multiple formats at once
sudo nmap -sS -sV -oA scan-results 192.168.1.1
# Creates: scan-results.nmap (human), scan-results.xml, scan-results.gnmap (grepable)

# Grep the grepable format to find all hosts with port 22 open:
grep "22/open" scan-results.gnmap | awk '{print $2}'
```

## Exercises

1. **Fingerprint a service manually**: Run `nc 127.0.0.1 22`. SSH servers send a banner immediately. Note the exact version string. Compare it to what nmap reports with `-sV`. Are they identical?

2. **Compare SYN scan vs connect scan**: Run `sudo nmap -sS 127.0.0.1` and `nmap -sT 127.0.0.1` (no sudo). Compare the results and timing. Check `/var/log/auth.log` — does the connect scan leave log entries that the SYN scan doesn't?

3. **Scan filtered ports**: Add an iptables rule to block port 9999: `sudo iptables -A INPUT -p tcp --dport 9999 -j DROP`. Start a listener: `nc -l 9999 &`. Scan it with nmap. Is the port reported as `filtered` or `closed`? Remove the DROP rule, re-scan. What changes?

4. **Interpret the XML output**: Run `nmap -sV -oX output.xml 127.0.0.1`. Open `output.xml`. Write a Python script that parses it with `xml.etree.ElementTree` and prints a table of host, port, protocol, state, and service.

5. **Set up an IDS and detect a scan**: Install `snort` or `suricata` in a VM, run an nmap scan against it, and check whether the IDS alerts fire. Try different timing templates (`-T1`, `-T4`) and compare detection rates.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| SYN scan | "half-open scan" | Send SYN, receive SYN-ACK (port open) or RST (closed), then send RST — never completes the handshake |
| Filtered | "port filtered" | nmap sent a probe but received no response; a firewall is likely dropping packets silently |
| Service detection | "-sV" | nmap probes open ports with service-specific payloads to identify software and version |
| OS fingerprinting | "-O" | Comparing TCP/IP stack behaviour against a database of known OS signatures to guess the operating system |
| -T4 | "aggressive timing" | nmap timing template that reduces timeouts for fast local networks; may produce false results on slow links |
| Nmap NSE | "nmap scripts" | The Nmap Scripting Engine — Lua scripts bundled with nmap for vulnerability detection, brute force, service enumeration |

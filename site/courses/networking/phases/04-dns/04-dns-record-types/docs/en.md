# Explore DNS Record Types

> A domain is not just an IP address — it's a bundle of structured facts, and each record type tells a different story.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 4, Lesson 01 — Trace a DNS Resolution
**Time:** ~30 minutes

## Learning Objectives
- Query A, AAAA, MX, TXT, CNAME, and NS records with `dig`
- Explain what each record type means and when it is used
- Distinguish between records that hold IP addresses vs. domain names vs. arbitrary text
- Understand why CNAME records cannot coexist with other record types at the same name
- Read a full `dig` output including the authority and additional sections

## The Problem

Most developers know that "DNS points a domain to an IP address." That's A records. But a domain's DNS zone contains much more:

- Where to deliver email for this domain
- What IPv6 addresses this domain has
- That `www.example.com` is an alias for `example.com`
- That this domain is owned and authorized to send email (SPF, DKIM, DMARC)
- Which nameservers are authoritative for this zone

Misconfigured DNS records cause real incidents: emails bouncing because MX records are wrong, SPF failures silently sending emails to spam, HTTPS broken because CNAME and apex domain rules are misunderstood. This lesson maps each record type to its purpose.

## The Concept

### Record Type Overview

```
Record Type  Stores            Primary Use
───────────────────────────────────────────────────────────────
A            IPv4 address      Map hostname → IP (most common)
AAAA         IPv6 address      Map hostname → IPv6 address
CNAME        Domain name       Alias one name to another
MX           Priority + name   Email delivery routing
NS           Domain name       Identify authoritative nameservers
TXT          Arbitrary text    Email auth (SPF/DKIM), verification
SOA          Zone metadata     Start of Authority; serial number, refresh
PTR          Domain name       Reverse DNS: IP → hostname
SRV          Priority/host     Service discovery (SIP, XMPP, etc.)
CAA          CA restriction    Which CAs may issue TLS certs
```

### A and AAAA Records

An A record maps a hostname to an IPv4 address. Multiple A records on the same name create a round-robin set — clients receive one or more addresses and pick one.

```
hostname.example.com.  300  IN  A  93.184.216.34
hostname.example.com.  300  IN  A  93.184.216.35
```

An AAAA record is identical in function but holds an IPv6 address (128 bits, 16 bytes).

### CNAME Records

A CNAME (Canonical Name) record makes one name an alias for another. The client follows the CNAME and resolves the target name.

```
www.example.com.  300  IN  CNAME  example.com.
example.com.      300  IN  A      93.184.216.34
```

A query for `www.example.com` A record returns the CNAME first, then the A record for `example.com`.

**Critical rule**: A CNAME cannot coexist with any other record type at the same name. You cannot have `www.example.com CNAME ...` and `www.example.com MX ...` at the same time. This is why you cannot CNAME the apex (root) domain — the apex must have NS and SOA records.

### MX Records

An MX (Mail Exchanger) record specifies the mail server for a domain. It has two fields: priority (lower = preferred) and the mail server hostname.

```
example.com.  3600  IN  MX  10  mail1.example.com.
example.com.  3600  IN  MX  20  mail2.example.com.
```

When someone sends email to `user@example.com`, their mail server queries the MX records for `example.com` and delivers to the mail server with the lowest priority number.

**Important**: MX records point to hostnames, not IP addresses. The sending server must then resolve those hostnames to IPs.

### TXT Records

TXT records hold arbitrary text strings. Modern DNS uses them for:

- **SPF**: `"v=spf1 include:_spf.google.com ~all"` — authorizes which servers may send email claiming to be from this domain
- **DKIM**: public key used to verify email signatures
- **DMARC**: policy for what to do with email that fails SPF/DKIM
- **Domain verification**: `"google-site-verification=abcdef123"` — proves domain ownership to Google

### NS Records

NS (Name Server) records list the authoritative nameservers for a zone. When you register a domain, you configure NS records at your registrar. These tell the TLD (e.g., `.com`) which servers are authoritative for your domain.

```
example.com.  172800  IN  NS  a.iana-servers.net.
example.com.  172800  IN  NS  b.iana-servers.net.
```

Every domain must have at least two NS records (for redundancy).

## Build It

### Step 1: Query A Records

```bash
# Basic A record query
dig example.com A

# Short output (just the answer section)
dig +short example.com A

# Multiple A records (round-robin)
dig +short google.com A
```

Notice google.com returns multiple IPs. Run it a few times — the order may change (DNS-level load balancing).

### Step 2: Query AAAA Records

```bash
# IPv6 address
dig +short google.com AAAA
dig +short cloudflare.com AAAA

# See if example.com has IPv6
dig +short example.com AAAA
```

Not all domains have AAAA records. If the output is empty, the domain either doesn't have IPv6 or the A record is handling all traffic.

### Step 3: Query CNAME Records

```bash
# www often aliases the apex
dig www.example.com CNAME

# GitHub's www is often a CNAME
dig www.github.com CNAME

# Follow the full chain (default behavior for A queries)
dig www.github.com A
```

When you query for an A record on a CNAME, `dig` follows the chain and shows all records. The output shows the CNAME first, then the A record of the final target.

### Step 4: Query MX Records

```bash
# Who accepts email for gmail.com?
dig gmail.com MX

# Short format shows priority + hostname
dig +short gmail.com MX

# Real company examples
dig +short github.com MX
dig +short cloudflare.com MX
```

The output looks like:
```
5 gmail-smtp-in.l.google.com.
10 alt1.gmail-smtp-in.l.google.com.
20 alt2.gmail-smtp-in.l.google.com.
30 alt3.gmail-smtp-in.l.google.com.
40 alt4.gmail-smtp-in.l.google.com.
```

Lowest number = highest priority. gmail.com has 5 mail servers with different priorities for failover.

### Step 5: Query TXT Records

```bash
# SPF record for gmail.com
dig gmail.com TXT

# Look for SPF specifically
dig gmail.com TXT | grep spf

# Domain verification records for github.com
dig github.com TXT

# DMARC is stored at _dmarc subdomain
dig _dmarc.gmail.com TXT
```

The TXT section can contain multiple records. Each serves a different purpose (SPF, DKIM, verification).

### Step 6: Query NS Records

```bash
# Authoritative nameservers for example.com
dig example.com NS

# Google's nameservers
dig google.com NS

# Short format
dig +short google.com NS
```

You can then query those nameservers directly to confirm they're authoritative:

```bash
# Ask Google's own nameserver for www.google.com
dig @ns1.google.com www.google.com A
```

The response should have the `aa` (authoritative answer) flag set.

### Step 7: Read the Full dig Output

```bash
# Full output with all sections
dig google.com ANY
```

The `ANY` type requests all record types. Study the four sections:

```
;; QUESTION SECTION:     ← what you asked
;; ANSWER SECTION:       ← direct answers
;; AUTHORITY SECTION:    ← which nameservers are authoritative
;; ADDITIONAL SECTION:   ← extra helpful records (glue records)
```

The **additional section** often contains A records for the nameservers listed in the authority section — these are called **glue records**. Without them, resolving the nameserver's hostname would require another DNS lookup, creating a circular dependency.

### Step 8: Verify Record Relationships

```bash
# Trace MX to final IP
MX_HOST=$(dig +short gmail.com MX | sort -n | head -1 | awk '{print $2}')
echo "Top MX: $MX_HOST"
dig +short "$MX_HOST" A
```

This shows the full chain: `gmail.com → MX record → mail server hostname → IP address`.

## Exercises

1. **Map a full domain**: For `github.com`, query and record: all A records, AAAA records, MX records, NS records, and TXT records. Draw a diagram showing all the relationships.

2. **CNAME restriction test**: Try to understand why `example.com` cannot have a CNAME at the apex. Check what records exist at `example.com` directly — what would conflict?

3. **Email routing trace**: For `google.com`, find all MX records sorted by priority. Then resolve each MX hostname to its IP address. Which MX server would receive email first?

4. **SPF analysis**: Query TXT records for a domain you own or a company you know. Find the SPF record. List which mail servers or services it authorizes. What does `~all` vs `-all` vs `+all` mean at the end?

5. **TTL comparison**: Query `example.com A` and `gmail.com MX` and compare their TTLs. Which is longer? Why would a mail operator choose a shorter TTL for MX records compared to A records?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| A record | "DNS record" | Maps a hostname to an IPv4 address; multiple A records on one name create a round-robin pool |
| AAAA record | "IPv6 DNS record" | Maps a hostname to an IPv6 address; the four A's stand for "quad A" |
| CNAME | "DNS alias" | Maps one name to another (canonical) name; the client resolves the target name recursively; cannot coexist with other record types at the same label |
| MX record | "email DNS" | Specifies the mail server hostname and priority for a domain; the priority number is inverse — lower number = higher priority |
| TXT record | "DNS text" | Stores arbitrary text; used for SPF (email authorization), DKIM keys, DMARC policies, and third-party domain verification |
| NS record | "nameserver" | Names the authoritative nameservers for a zone; configured at the registrar and replicated into the parent TLD zone |
| Glue record | "extra DNS data" | An A record in the additional section that provides the IP for a nameserver whose hostname is within the same zone — breaks the circular dependency |
| Apex domain | "root domain" or "naked domain" | The domain itself without any subdomain (e.g., `example.com` vs `www.example.com`); cannot use CNAME because it must have NS and SOA records |

# Trace a DNS Resolution

> Every URL you type triggers a multi-step conversation with servers around the world — most developers have no idea it's happening.

**Type:** Learn
**Languages:** Bash
**Prerequisites:** Phase 2, Lesson 01 — IP Addresses and Subnets
**Time:** ~30 minutes

## Learning Objectives
- Explain the roles of root servers, TLD nameservers, and authoritative nameservers in a DNS resolution chain
- Use `dig +trace` to walk every delegation step from `.` (root) to the final answer
- Identify the difference between recursive and iterative DNS resolution
- Read a `dig` output and extract the answer section, TTL, and nameserver chain
- Describe what a referral is and why it exists

## The Problem

You type `https://example.com` in your browser. Within 50 milliseconds, your computer knows the IP address. How?

Most developers treat DNS as magic — it just works. That's fine until it doesn't. When a deployment fails because a new IP isn't propagating, when you're debugging a split-horizon DNS issue, or when you're hardening a system against DNS hijacking, you need to know what actually happens at each step.

The fundamental question DNS answers is: "given a human-readable name like `api.mycompany.com`, what numeric IP address does it correspond to?" No single server knows every name-to-IP mapping in the world — there are hundreds of millions of domain names. So DNS is designed as a distributed, hierarchical, delegated database. The key word is *delegated*: no central authority holds all the answers. Instead, each level of the hierarchy says "I don't know the final answer, but here's who you should ask next."

If you don't understand this chain, you will misdiagnose DNS propagation delays, misread `dig` output, and be confused every time something silently fails because a nameserver returned a wrong referral.

## The Concept

### The Hierarchy

DNS is organized as an inverted tree. The root is at the top (represented by `.`), TLDs branch off from it, then registered domains, then subdomains.

```
                         . (root)
                   /     |     \
                .com    .org    .net
               /    \
          google    example
         /      \
       www       mail
```

When your computer needs to resolve `www.example.com`, it reads the name right-to-left:

1. Start at `.` (root) — ask: who manages `.com`?
2. Go to the `.com` TLD nameserver — ask: who manages `example.com`?
3. Go to `example.com`'s authoritative nameserver — ask: what is `www.example.com`?
4. Get the final IP address.

### The Players

**Your stub resolver** — the tiny DNS client built into your OS. It knows only one thing: the IP address of a recursive resolver to ask.

**The recursive resolver** (also called a full-service resolver) — usually run by your ISP or by Google (8.8.8.8) or Cloudflare (1.1.1.1). This is the server that does the actual work of walking the hierarchy for you. It caches results.

**Root servers** — 13 logical root server addresses (though hundreds of physical machines via anycast). They hold the list of TLD nameservers. They do NOT know your domain — they only know who manages `.com`, `.org`, `.io`, etc.

**TLD nameservers** — run by registries like Verisign (.com/.net) or ICANN (.org). They hold the list of authoritative nameservers for every domain registered under that TLD.

**Authoritative nameserver** — the server that actually holds the zone file for your domain. This is where `A`, `MX`, `CNAME`, and other records live. When you register a domain and set nameservers in your registrar panel, you're pointing to this server.

### Iterative vs Recursive Resolution

```
RECURSIVE (what your stub resolver does):
  Your computer ──ask──▶ Recursive Resolver
                             │
                     ┌───────▼─────────┐
                     │ walks the chain │
                     │ itself          │
                     └───────┬─────────┘
  Your computer ◀──answer── Recursive Resolver


ITERATIVE (what the recursive resolver does internally):
  Recursive ──ask root──▶ Root Server
  Resolver  ◀──referral─ "ask .com servers at X.X.X.X"

  Recursive ──ask .com──▶ TLD Server
  Resolver  ◀──referral─ "ask ns1.example.com at Y.Y.Y.Y"

  Recursive ──ask auth──▶ Authoritative Server
  Resolver  ◀──answer──  "www.example.com = 93.184.216.34"
```

Your stub resolver asks one question recursively and gets one answer back. The recursive resolver does the iterative heavy lifting — asking each server in turn, following referrals.

### What a Referral Looks Like

When the root server responds to a query for `www.example.com`, it does NOT say "I don't know." It says "I'm not authoritative for this, but here are the nameservers for `.com`, and here are their IP addresses." That response is called a **referral** (or delegation). The recursive resolver then contacts those servers and repeats the process.

This continues until a server responds with an **authoritative answer** — the actual record with no further referrals.

## Build It

### Step 1: Install dig

On macOS, `dig` is included with the system. On Ubuntu/Debian:

```bash
sudo apt-get install -y dnsutils
```

Verify:

```bash
dig -v
```

### Step 2: A Basic Query

First, see what a normal query looks like:

```bash
dig example.com
```

You'll see output like this:

```
; <<>> DiG 9.16.1-Ubuntu <<>> example.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; QUESTION SECTION:
;example.com.                   IN      A

;; ANSWER SECTION:
example.com.            86400   IN      A       93.184.216.34

;; Query time: 18 msec
;; SERVER: 192.168.1.1#53(192.168.1.1)
;; WHEN: Wed May 28 10:00:00 UTC 2026
;; MSG SIZE  rcvd: 56
```

The `SERVER` line shows your recursive resolver (your router or ISP). The `ra` flag in the header means "recursion available" — this resolver will do the work for you. The `rd` flag means you asked for "recursion desired."

### Step 3: Trace the Full Chain

Now add `+trace` to see every step:

```bash
dig +trace example.com
```

The output is long. Here's an annotated version of what you'll see:

```
; <<>> DiG 9.16.1 <<>> +trace example.com
;; global options: +cmd
.                       518400  IN      NS      a.root-servers.net.
.                       518400  IN      NS      b.root-servers.net.
...
;; Received 811 bytes from 192.168.1.1#53(192.168.1.1) in 5 ms
```

This first block shows `dig` querying your local resolver for the root servers (the `.` zone). The `518400` is the TTL in seconds (~6 days). `NS` means nameserver record. Your resolver returned 13 root server names.

```
com.                    172800  IN      NS      a.gtld-servers.net.
com.                    172800  IN      NS      b.gtld-servers.net.
...
;; Received 1173 bytes from 198.41.0.4#53(a.root-servers.net) in 22 ms
```

`dig` contacted `a.root-servers.net` (198.41.0.4) and asked about `example.com`. The root server replied with a referral: "I don't know `example.com`, but here are the `.com` TLD nameservers."

```
example.com.            172800  IN      NS      a.iana-servers.net.
example.com.            172800  IN      NS      b.iana-servers.net.
;; Received 506 bytes from 192.5.6.30#53(a.gtld-servers.net) in 18 ms
```

`dig` contacted a `.com` TLD server and asked about `example.com`. Another referral: "Here are `example.com`'s authoritative nameservers."

```
example.com.            86400   IN      A       93.184.216.34
;; Received 56 bytes from 199.43.135.53#53(a.iana-servers.net) in 11 ms
```

Finally, `dig` contacted `a.iana-servers.net` — the authoritative nameserver for `example.com` — and got the real answer: `93.184.216.34`.

### Step 4: Trace a Subdomain

Try a subdomain to see an extra delegation level:

```bash
dig +trace www.google.com
```

You'll see: root → `.com` TLD → `google.com` nameservers → final `A` record.

### Step 5: Query a Specific Server Directly

Skip the recursive resolver and query a root server directly:

```bash
# Ask a root server about .com
dig @a.root-servers.net com NS

# Ask a .com TLD server about google.com
dig @a.gtld-servers.net google.com NS

# Ask Google's authoritative server directly
dig @ns1.google.com www.google.com A
```

The `@server` syntax directs `dig` to send the query to that specific server. Notice that when you query the root server, the response has no `aa` (authoritative answer) flag — it's a referral. When you query the authoritative server, you get the `aa` flag set.

### Step 6: Check the Flags

```bash
dig +trace +additional example.com
```

Look at the header flags:
- `qr` — this is a query response (not a question)
- `aa` — authoritative answer (only set by the authoritative nameserver)
- `tc` — truncated (response was too big for UDP, use TCP)
- `rd` — recursion desired (you asked for it)
- `ra` — recursion available (server supports it)

## Exercises

1. **Verify the chain yourself**: Run `dig +trace github.com` and write down every server contacted. How many hops were there? Which IP answered the final A record query?

2. **Find a multi-level subdomain**: Run `dig +trace status.github.com`. Does `github.com`'s nameserver answer directly, or is there another delegation for `status.github.com`?

3. **Compare TTLs**: Run `dig example.com` twice, 30 seconds apart. Does the TTL in the ANSWER section decrease? What does that tell you about your recursive resolver's cache?

4. **No recursion**: Run `dig +norecurse example.com @8.8.8.8`. The `+norecurse` flag tells the server not to recurse. What do you get back? Why?

5. **Negative result**: Run `dig +trace thisdomaindoesnotexist12345678.com`. At which step does the chain break? What status code appears in the header?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| DNS resolution | "looking up a domain" | A multi-step iterative process of following delegation chains from root servers to an authoritative answer |
| Root server | "the main DNS server" | One of 13 logical servers that hold only the list of TLD nameservers; they know nothing about individual domains |
| Authoritative nameserver | "the DNS server for your domain" | The server that holds the actual zone file with A, MX, CNAME records; its answers carry the `aa` flag |
| Recursive resolver | "your DNS server" | A full-service resolver that performs the entire iterative walk on your behalf and caches results |
| Referral | "DNS delegation" | A response that says "I don't know the answer, but contact these servers next" — not an error, it's how DNS works |
| TTL | "how long DNS is cached" | Time-to-live in seconds; set by the zone owner to control how long resolvers cache an answer before re-asking |
| Stub resolver | "the DNS client" | The minimal OS component that just forwards your query to a configured recursive resolver |

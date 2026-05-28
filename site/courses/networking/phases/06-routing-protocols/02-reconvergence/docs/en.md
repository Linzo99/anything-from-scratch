# Simulate Link Failure and Reconvergence

> How long does OSPF take to recover when a link dies? We will measure it to the millisecond.

**Type:** Build
**Languages:** Bash
**Prerequisites:** Phase 6, Lesson 01 — Configure OSPF with FRRouting
**Time:** ~40 minutes

## Learning Objectives
- Trigger a link failure in a running OSPF topology using `ip link set down`
- Measure end-to-end reconvergence time using timestamped ping output
- Explain the sequence of OSPF events that happen after a link failure
- Tune the Hello and Dead intervals and observe the effect on recovery time
- Interpret SPF delay and throttle timers in FRR output

## The Problem

A routing protocol that can't recover from failures is worse than useless — it gives you false confidence. You deploy OSPF, think you have redundancy, and then a link dies. Traffic drops. How long does the outage last? 40 seconds? 5 seconds? 500 milliseconds?

The answer depends on how OSPF is tuned, and many operators don't know what their default convergence time actually is. They assume it's "fast" without ever measuring it.

This lesson puts a number on it. You will take down a link in the lab from the previous lesson, run a continuous ping, and watch the timestamps to see exactly how many packets are lost and for how long. Then you will tune the timers to make recovery faster.

## The Concept

### What Happens When a Link Dies

When you run `ip link set veth12 down` inside a namespace, the interface loses carrier. Here is the full sequence of events OSPF goes through:

```
t=0    Link goes down (carrier lost)
       │
t=0    ospfd detects interface DOWN event immediately
       │  (interface events are instant — no waiting)
       │
t=0    ospfd marks the link as down in its local LSDB
       │
t=0    ospfd originates a new Router LSA for itself
       │  (updated: this link no longer exists)
       │
t≈0    Router LSA is flooded to all reachable neighbors
       │  (R2 → R3 path still works)
       │
t≈1s   All routers receive the updated LSA
       │
t≈1s   Each router re-runs SPF (Dijkstra) with the new topology
       │
t≈1s   New routes installed in kernel (via zebra → netlink)
       │
t≈1s   Traffic now flows on the surviving path
```

The good news: a direct interface-down event is detected instantly. The bad news: if the interface stays up but the remote end dies (e.g., a fibre cut that doesn't change local carrier), OSPF must wait for the **Dead Interval** (default 40 seconds) before declaring the neighbor down. That is the worst case.

### SPF Throttle Timers

OSPF does not re-run Dijkstra the instant an LSA arrives. That would cause a CPU spike if many LSAs arrive at once (as happens during large-scale failures). Instead, FRR uses SPF throttle timers:

```
ospf timers throttle spf <delay> <initial-hold> <max-hold>
```

- **delay**: milliseconds to wait after receiving a trigger before running SPF (default 0ms in FRR)
- **initial-hold**: after running SPF, how long to wait before running it again (default 50ms)
- **max-hold**: cap on the hold time, which doubles each run (default 5000ms)

For lab purposes (and fast convergence in production), you can set these very low:

```
ospf timers throttle spf 0 10 100
```

### Dead Interval and Hello Interval

| Timer | Default | What it controls |
|-------|---------|-----------------|
| Hello interval | 10 s | How often Hello packets are sent to maintain neighbor relationships |
| Dead interval | 40 s | How long to wait for a Hello before declaring the neighbor dead |

The relationship: Dead interval is typically 4× Hello interval. You can lower both:

```
interface veth12
 ip ospf hello-interval 1
 ip ospf dead-interval 4
```

With these settings, a non-carrier failure is detected in at most 4 seconds instead of 40.

### Measuring Reconvergence with Ping

The standard technique: run `ping -i 0.2 <destination>` (one ping every 200ms) while triggering a failure. Count the "Request timeout" lines. Each represents 200ms of outage. Multiply by 0.2 to get seconds.

Modern `ping` prints timestamps if you pass the `-D` flag (Linux):

```bash
ping -D -i 0.2 192.168.3.3
# [1748000.123456] 64 bytes from 192.168.3.3: icmp_seq=1 ttl=64 time=0.5 ms
# [1748000.323456] Request timeout for icmp_seq 2
# [1748000.523456] Request timeout for icmp_seq 3
# [1748001.123456] 64 bytes from 192.168.3.3: icmp_seq=8 ttl=64 time=1.2 ms
```

Subtract the last success timestamp before the failure from the first success after recovery. That is your reconvergence window.

## Build It

### Step 1: Start the Three-Router Lab

Reuse the setup from Lesson 01. Run both scripts:

```bash
sudo bash setup-ospf-lab.sh
sudo bash start-frr-lab.sh
```

Confirm everything is up before proceeding:

```bash
sudo ip netns exec r1 ip route show | grep ospf
# Should show routes to 192.168.2.2, 192.168.3.3, 10.0.23.0/30
```

### Step 2: Launch a Continuous Ping from R1 to R3

Open a second terminal. Start a timestamped ping from R1 to R3's loopback:

```bash
sudo ip netns exec r1 ping -D -i 0.2 192.168.3.3
```

Leave this running. You should see replies every 200ms.

### Step 3: Kill the R1-R2 Link

In your first terminal, take down the link between R1 and R2:

```bash
# Bring down veth12 inside R1's namespace
sudo ip netns exec r1 ip link set veth12 down
```

In the ping terminal, you will immediately see timeouts. Note the timestamp of the last success. Wait for replies to resume. Note the timestamp of the first success after recovery.

With default timers (Hello=10s, Dead=40s) and a direct carrier-down event on R1's side, you should see only 1-3 seconds of outage because the interface-down event triggers immediate LSA origination. The neighbor on R2 side will still be up (R2 still has its veth21 up), so R2 will eventually notice through the Dead timer or through receiving R1's updated LSA with the link removed.

Record your measurement:

```
Last success before failure:  [timestamp]
First success after recovery: [timestamp]
Outage duration:              [difference] seconds
Packets lost:                 [count]
```

### Step 4: Restore the Link

```bash
sudo ip netns exec r1 ip link set veth12 up
```

Watch OSPF reconverge and routes reappear.

### Step 5: Tune Timers for Faster Convergence

Now edit the FRR configs to use aggressive timers. Add these lines to each router's config under `router ospf`:

```
  timers throttle spf 0 10 1000
```

And on each interface:

```
  ip ospf hello-interval 1
  ip ospf dead-interval 4
```

Restart ospfd in each namespace:

```bash
for ns in r1 r2 r3; do
  # Find and kill ospfd in each namespace
  pid=$(sudo ip netns exec $ns cat /var/run/frr-${ns}/ospfd.pid 2>/dev/null)
  [ -n "$pid" ] && sudo kill "$pid"
  sleep 1
  sudo ip netns exec "$ns" /usr/lib/frr/ospfd \
    --config_file /tmp/frr-${ns}.conf \
    --pid_file /var/run/frr-${ns}/ospfd.pid \
    --log file:/var/log/frr-${ns}/ospfd.log \
    --vty_socket /var/run/frr-${ns}/ospfd.vty \
    --daemon
done
sleep 10   # wait for re-adjacency
```

Repeat the failure test. With Hello=1s / Dead=4s, a failure not detected by carrier loss will now take at most 4 seconds rather than 40. You should see a noticeably shorter outage.

### Step 6: Simulate a "Silent" Failure

A carrier-loss failure is easy for OSPF. A tougher test: the remote router dies but the local interface stays up (common with optical transceivers and some switches). Simulate this by killing ospfd on R2 while keeping the interface up:

```bash
# Kill ospfd on R2 — the interface stays up but OSPF stops
sudo kill $(sudo ip netns exec r2 cat /var/run/frr-r2/ospfd.pid)
```

Now R1 has an interface up to R2 but no OSPF process responding. OSPF on R1 must wait for the Dead Interval before declaring R2 down. With default timers that is 40 seconds. With tuned timers (Dead=4s) it is 4 seconds.

Watch the ping output. Count the outage. Compare with your tuned timers.

```bash
# After measuring, restart R2's ospfd to restore the lab
sudo ip netns exec r2 /usr/lib/frr/ospfd \
  --config_file /tmp/frr-r2.conf \
  --pid_file /var/run/frr-r2/ospfd.pid \
  --log file:/var/log/frr-r2/ospfd.log \
  --vty_socket /var/run/frr-r2/ospfd.vty \
  --daemon
```

## Exercises

1. **Build a measurement script** that automatically runs the failure test, captures ping output to a file, and parses it to print the outage start time, end time, and duration. Use `awk` or Python to parse the `-D` timestamps.

2. **Compare Hello intervals**: Test with Hello=10s/Dead=40s, Hello=2s/Dead=8s, and Hello=1s/Dead=4s. Build a table of measured reconvergence times for carrier-loss vs. silent failure.

3. **Add a third path**: Add a direct R1-R3 link so there are two paths to R3. Verify that when R2 dies, traffic immediately switches to the direct link (no Dead Interval wait needed because the alternate path is always present in the LSDB).

4. **Watch the LSA flood**: Run `tcpdump -i veth12 proto ospf -n` on R1's interface during a failure. Capture the LSU (Link State Update) that carries the updated Router LSA. Decode its sequence number — it should be higher than before the failure.

5. **Research BFD**: Bidirectional Forwarding Detection (BFD) is a separate protocol that detects link failures in milliseconds and notifies OSPF. Look up how to enable FRR's BFD daemon and configure it on the R1-R2 link. What outage time do you measure with BFD enabled?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Reconvergence | "convergence time" | The time from a topology change until all routers have computed and installed correct new routes |
| Dead Interval | "OSPF dead timer" | How long a router waits without receiving a Hello before declaring a neighbor unreachable (default 40s) |
| Hello Interval | "hello timer" | How often OSPF sends Hello packets to maintain neighbor adjacencies (default 10s) |
| SPF throttle | "SPF delay" | A timer that batches multiple LSA arrivals before running Dijkstra, preventing CPU spikes during storms |
| Carrier loss | "link down" | The physical layer signal that an interface has lost its connection — detected instantly by the OS |
| Silent failure | "black hole" | A failure where the interface stays up but the remote end is unreachable — only detectable by Hello timeouts |
| LSU | "Link State Update" | An OSPF packet that carries one or more LSAs to neighbors during flooding |

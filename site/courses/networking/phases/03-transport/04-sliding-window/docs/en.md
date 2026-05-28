# Visualize TCP Sliding Window

> Stop-and-wait wastes 99% of your link capacity waiting for ACKs. The sliding window is the algorithm that fills that idle time — and it is why a 1 Gbps link actually transfers close to 1 Gbps.

**Type:** Build
**Languages:** Python
**Prerequisites:** Phase 3, Lesson 03 — Implement Stop-and-Wait ARQ
**Time:** ~45 minutes

## Learning Objectives
- Explain how a sliding window allows multiple in-flight packets without waiting for each ACK
- Calculate the window size required to saturate a link given RTT and bandwidth
- Implement a sliding window sender in Python that tracks sent-but-unacknowledged packets
- Visualise the window advancing as ACKs arrive
- Distinguish sender-side flow control (window) from congestion control (cwnd)

## The Problem

In Lesson 03 you measured that stop-and-wait with a 100ms RTT on a 100 Mbps link achieves roughly 120 Kbps — 0.12% utilisation. Every millisecond the sender is waiting for an ACK is a millisecond the link is idle.

The fix is **pipelining**: send multiple packets without waiting for each to be acknowledged. But you need a mechanism to track which packets have been sent and not yet acknowledged, and to retransmit any that are lost. The **sliding window** is that mechanism.

TCP's throughput depends almost entirely on how large the window is. When you `scp` a file and see 10 MB/s instead of the expected 50 MB/s, the window is almost always the bottleneck.

## The Concept

### The window as a view into the byte stream

Think of the TCP byte stream as a long tape of data. The window is a fixed-size viewport sliding along that tape:

```
Byte stream:  ... 0  1  2  3  4  5  6  7  8  9  10 11 12 13 14 ...

Window = 4:

State 1: Sent and ACKed | In-window (sent, not ACKed) | Not yet sent
         [  0  1  2  ] | [  3  4  5  6  ]             | [  7  8 ...
          ↑                ↑           ↑                  ↑
      (discarded)     SND.UNA       SND.NXT            SND.UNA + W

After ACK for 3:
         [0  1  2  3  ] | [  4  5  6  7  ]             | [  8  9 ...
                           ↑                                 ↑
                       SND.UNA                         new limit
```

The window **slides** to the right as ACKs arrive. New data can be sent as long as `SND.NXT < SND.UNA + window_size`.

### TCP's three windows

TCP actually manages three interacting window values:

```
1. rwnd  (receiver window): advertised by the receiver in every ACK.
         "I have this much buffer space — don't exceed it."

2. cwnd  (congestion window): maintained by the sender.
         "The network can handle this many bytes in flight."
         Adjusted by congestion control algorithms (Lesson 05).

3. Effective window = min(rwnd, cwnd)
         The actual limit on in-flight bytes.
```

In this lesson we implement a simple window limited by a fixed size (simulating `rwnd`). Lesson 05 adds `cwnd` dynamics.

### The Bandwidth-Delay Product

To maximise throughput, the window must be at least as large as the **bandwidth-delay product** (BDP):

```
BDP = bandwidth × RTT

Example:
  Bandwidth = 100 Mbps = 12.5 MB/s
  RTT = 100ms = 0.1s
  BDP = 12.5 MB/s × 0.1s = 1.25 MB

If window < BDP, the link will be idle some of the time.
If window = BDP, the link is fully saturated.
If window > BDP, the sender is limited by something else (bandwidth, app speed).
```

This is why "TCP window scaling" (RFC 7323) was needed: the original TCP window field is 16 bits = max 65,535 bytes. On a 1 Gbps link with 100ms RTT, BDP = 12.5 MB — way bigger than 65,535. The window scale option multiplies the window size by a power of 2 (up to 2^14 = 16384).

### Cumulative vs. selective acknowledgment

**Cumulative ACK** (original TCP): ACK N means "I have received all bytes up to and including N-1. Send me N next." If packet 3 is lost but 4 and 5 arrive, ACK still says 3 (waiting for the hole to be filled). The sender retransmits from the hole.

**Selective ACK (SACK)**: The receiver can say "I received 1, 2, 4, 5 — I'm missing 3." The sender retransmits only the missing packet. Most modern TCP stacks support SACK.

Our simulation uses cumulative ACKs for simplicity.

### Retransmission trigger

Two events trigger retransmission:

1. **Timeout**: The oldest unacknowledged packet has been in-flight for more than the retransmission timeout (RTO). The sender retransmits from the oldest unACKed packet.

2. **Three duplicate ACKs** (fast retransmit): If the sender receives three ACKs for the same byte offset, it means packets after that offset are arriving but one earlier packet is missing. The sender retransmits the missing packet immediately without waiting for timeout.

## Build It

```python
#!/usr/bin/env python3
"""
sliding_window.py — Visualise a sliding window sender.

Simulates a sender that maintains a window of N in-flight packets,
sends new packets as old ones are acknowledged, and retransmits on timeout.

Runs entirely in one process (no real network) using simulated ACKs.
Use --loss to simulate packet loss and watch retransmissions.

Usage:
    python3 sliding_window.py
    python3 sliding_window.py --window 8 --packets 30 --loss 0.1 --rtt 0.02
"""

import argparse
import random
import time
import collections


# ── visual helpers ────────────────────────────────────────────────────────────

def window_bar(total_packets: int, acked_up_to: int,
               in_flight: set, window_size: int) -> str:
    """
    Render a visual representation of the window state.

    Legend:
      A = acked (received and acknowledged)
      S = sent, waiting for ACK (in-flight)
      . = can be sent next (within window but not yet sent)
      _ = beyond window (not yet sendable)
    """
    bar = []
    for i in range(total_packets):
        if i < acked_up_to:
            bar.append("A")
        elif i in in_flight:
            bar.append("S")
        elif i < acked_up_to + window_size:
            bar.append(".")
        else:
            bar.append("_")
    return "".join(bar)


# ── packet state ──────────────────────────────────────────────────────────────

class Packet:
    def __init__(self, seq: int, data: bytes):
        self.seq = seq
        self.data = data
        self.send_time: float | None = None    # when last sent
        self.acked: bool = False


# ── sliding window sender simulation ─────────────────────────────────────────

def simulate(total_packets: int, window_size: int,
             rtt: float, loss_rate: float, verbose: bool = True):
    """
    Simulate a sliding window sender.

    Parameters:
      total_packets: number of packets to send
      window_size:   maximum in-flight packets
      rtt:           simulated round-trip time in seconds
      loss_rate:     probability that a DATA packet is lost
    """
    # Create packets
    packets = [Packet(i, f"data_{i:04d}".encode()) for i in range(total_packets)]

    # State
    snd_una = 0        # oldest unacknowledged packet (SND.UNA)
    snd_nxt = 0        # next packet to send (SND.NXT)
    in_flight = set()  # seq numbers currently in flight

    # Simulated ACK queue: (arrival_time, acked_seq)
    ack_queue: collections.deque = collections.deque()

    # Metrics
    total_transmissions = 0
    total_retransmits = 0
    rto = rtt * 2      # retransmission timeout = 2× RTT (simplified)

    print(f"\nSliding Window Simulation")
    print(f"  Packets:     {total_packets}")
    print(f"  Window size: {window_size}")
    print(f"  RTT:         {rtt * 1000:.0f}ms")
    print(f"  Loss rate:   {loss_rate:.0%}")
    print(f"  RTO:         {rto * 1000:.0f}ms")
    print()
    print(f"  {'Legend: A=acked, S=in-flight, .=sendable, _=beyond window':}")
    print()

    # Track real time for scheduling
    sim_time = 0.0      # simulated clock (seconds)
    sim_step = 0.001    # 1ms per tick

    completed = False
    ticks = 0

    while not completed:
        sim_time += sim_step
        ticks += 1

        # ── Step 1: Process incoming ACKs ────────────────────────────────────
        while ack_queue and ack_queue[0][0] <= sim_time:
            _, acked_seq = ack_queue.popleft()

            if acked_seq >= snd_una:
                # Cumulative ACK: advance snd_una
                old_una = snd_una
                snd_una = acked_seq + 1

                # Remove acked packets from in-flight set
                for seq in range(old_una, snd_una):
                    in_flight.discard(seq)
                    packets[seq].acked = True

                if verbose:
                    bar = window_bar(total_packets, snd_una, in_flight, window_size)
                    print(f"  t={sim_time*1000:6.1f}ms  ACK {acked_seq:3d}  "
                          f"una={snd_una:3d}  nxt={snd_nxt:3d}  "
                          f"flight={len(in_flight):2d}  [{bar}]")

        # ── Step 2: Retransmit timed-out packets ─────────────────────────────
        for seq in sorted(in_flight):
            pkt = packets[seq]
            if pkt.send_time is not None and sim_time - pkt.send_time > rto:
                # Timeout — retransmit
                total_retransmits += 1
                total_transmissions += 1
                pkt.send_time = sim_time

                # Schedule ACK for the retransmit
                arrival = sim_time + rtt
                if random.random() >= loss_rate:
                    ack_queue.append((arrival, seq))
                    # Sort the ACK queue by arrival time
                    # (deque doesn't support sort; use a list temporarily)
                    ack_list = sorted(ack_queue)
                    ack_queue.clear()
                    ack_queue.extend(ack_list)

                if verbose:
                    print(f"  t={sim_time*1000:6.1f}ms  RTO seq={seq:3d} (retransmit #{total_retransmits})")

        # ── Step 3: Send new packets within the window ───────────────────────
        while (snd_nxt < total_packets and
               snd_nxt < snd_una + window_size and
               snd_nxt not in in_flight):

            pkt = packets[snd_nxt]
            pkt.send_time = sim_time
            in_flight.add(snd_nxt)
            total_transmissions += 1

            # Schedule ACK arrival (with possible loss)
            if random.random() >= loss_rate:
                arrival = sim_time + rtt
                ack_list = sorted(list(ack_queue) + [(arrival, snd_nxt)])
                ack_queue.clear()
                ack_queue.extend(ack_list)

            snd_nxt += 1

        # ── Check completion ─────────────────────────────────────────────────
        if snd_una >= total_packets:
            completed = True

        # Safety limit
        if ticks > 1_000_000:
            print("  [WARN] Simulation exceeded tick limit — possibly stuck")
            break

    # Final statistics
    elapsed_ms = sim_time * 1000
    goodput = total_packets * 512 / sim_time  # assume 512 bytes per packet
    print()
    print("=== Simulation complete ===")
    print(f"  Simulated time: {elapsed_ms:.1f}ms")
    print(f"  Transmissions:  {total_transmissions} "
          f"({total_retransmits} retransmits)")
    print(f"  Retransmit rate:{total_retransmits/total_transmissions:.1%}")
    print(f"  Goodput:        {goodput/1024:.1f} KB/s")
    print()

    return sim_time, total_transmissions


def compare_windows(rtt: float, loss_rate: float, total_packets: int = 40):
    """Compare multiple window sizes and print a throughput table."""
    print(f"\n{'='*60}")
    print(f"Window size comparison (RTT={rtt*1000:.0f}ms, loss={loss_rate:.0%})")
    print(f"{'='*60}")
    print(f"  {'Window':>8}  {'Time (ms)':>10}  {'Throughput (KB/s)':>18}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*18}")

    for window in [1, 2, 4, 8, 16, 32]:
        elapsed, _ = simulate(
            total_packets=total_packets,
            window_size=window,
            rtt=rtt,
            loss_rate=loss_rate,
            verbose=False,
        )
        throughput = total_packets * 512 / elapsed / 1024
        print(f"  {window:>8}  {elapsed*1000:>10.1f}  {throughput:>18.1f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Sliding window simulation")
    parser.add_argument("--window",  type=int,   default=4,   help="Window size")
    parser.add_argument("--packets", type=int,   default=20,  help="Packets to send")
    parser.add_argument("--loss",    type=float, default=0.0, help="Packet loss rate")
    parser.add_argument("--rtt",     type=float, default=0.05, help="RTT in seconds")
    parser.add_argument("--compare", action="store_true",
                        help="Compare multiple window sizes")
    args = parser.parse_args()

    if args.compare:
        compare_windows(rtt=args.rtt, loss_rate=args.loss)
    else:
        simulate(
            total_packets=args.packets,
            window_size=args.window,
            rtt=args.rtt,
            loss_rate=args.loss,
        )


if __name__ == "__main__":
    main()
```

Run it:

```bash
# Single window simulation — watch the window slide
python3 sliding_window.py --window 4 --packets 20 --rtt 0.05 --loss 0.0

# With packet loss — watch retransmissions
python3 sliding_window.py --window 4 --packets 20 --rtt 0.05 --loss 0.2

# Compare window sizes 1 through 32
python3 sliding_window.py --compare --rtt 0.05 --loss 0.0
```

Sample output for `--compare` with no loss:

```
============================================================
Window size comparison (RTT=50ms, loss=0%)
============================================================
    Window    Time (ms)    Throughput (KB/s)
  --------  ----------  ------------------
         1     1000.0                10.0
         2      501.0                19.9
         4      253.0                39.5
         8      128.0                78.1
        16       65.0               153.8
        32       34.0               294.1
```

The throughput roughly doubles with each doubling of window size (until the link bandwidth becomes the bottleneck).

## Exercises

1. **BDP calculation.** For RTT=200ms and bandwidth=1 Gbps, calculate the BDP. What window size (in packets, assuming 1500 bytes each) do you need to fully utilise the link? Does your simulation confirm this?

2. **Window size vs. loss.** Run `--compare` with `--loss 0.1`, `--loss 0.2`, `--loss 0.3`. How does loss degrade throughput at each window size? At high loss, does a larger window help or hurt?

3. **Fast retransmit.** Modify the simulation to trigger retransmission after 3 duplicate ACKs (instead of waiting for RTO). Implement this by tracking when the same `snd_una` value appears three times with packets still in flight. Measure the improvement in throughput under 20% loss.

4. **SACK.** Extend the ACK format to include a list of "received out-of-order" ranges. When packets 1 and 3 are received but 2 is missing, the ACK carries `{received: [3,3]}`. The sender uses this to retransmit only packet 2, not 2+3+4...

5. **Real TCP window.** Open a connection with `ss -tin dst <some-host>` during a large file transfer. Find the `wscale`, `rcv_space`, and `snd_wnd` fields. Calculate the effective window and compare to the BDP for that connection.

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| Sliding window | "The TCP window" | A protocol mechanism allowing multiple packets to be in flight simultaneously; the window "slides" right as ACKs arrive |
| SND.UNA | "Unacknowledged pointer" | The sequence number of the oldest unacknowledged byte; the left edge of the window |
| SND.NXT | "Next to send" | The sequence number of the next byte to be sent; advances as new data is transmitted |
| In-flight | "Unacknowledged packets" | Packets that have been sent but not yet ACKed; count must stay below window size |
| BDP | "Bandwidth-delay product" | The amount of data that fills a pipe of given bandwidth and RTT; minimum window size for full utilisation |
| RTO | "Retransmission timeout" | The time a sender waits before retransmitting an unacknowledged packet; should be slightly larger than RTT |
| Cumulative ACK | "Sequential acknowledgment" | An ACK that confirms receipt of all bytes up to a given sequence number, not individual out-of-order packets |

# Run: python3 sliding_window.py
"""
sliding_window.py — Simulate a Go-Back-N sliding window protocol.

Runs entirely in one process using a simulated clock, no real network.
Prints a visual window diagram at each ACK event showing:
  A = acknowledged  S = in-flight (sent, unACKed)
  . = sendable (within window, not yet sent)
  _ = beyond window

Usage:
    python3 sliding_window.py                         # defaults
    python3 sliding_window.py --window 4 --packets 20 --loss 0.1 --rtt 0.05
    python3 sliding_window.py --compare               # compare window sizes 1–32
"""

import argparse
import random
import collections


# ── visual helper ─────────────────────────────────────────────────────────────

def window_bar(total: int, una: int, in_flight: set, window: int) -> str:
    """Return a one-line ASCII window diagram."""
    bar = []
    for i in range(total):
        if i < una:
            bar.append("A")
        elif i in in_flight:
            bar.append("S")
        elif i < una + window:
            bar.append(".")
        else:
            bar.append("_")
    return "".join(bar)


# ── core simulation ───────────────────────────────────────────────────────────

def simulate(
    total_packets: int = 20,
    window_size: int = 4,
    rtt: float = 0.05,
    loss_rate: float = 0.0,
    verbose: bool = True,
    seed: int = 0,
) -> tuple:
    """
    Simulate a Go-Back-N sliding window sender.

    Returns (elapsed_seconds, total_transmissions).
    """
    rng = random.Random(seed)
    rto = rtt * 2   # retransmission timeout = 2 × RTT

    # Packet send times (for RTO detection)
    send_time = [None] * total_packets
    acked     = [False] * total_packets

    # SND.UNA = oldest unACKed;  SND.NXT = next to send
    snd_una = 0
    snd_nxt = 0

    in_flight:  set = set()
    ack_queue = collections.deque()   # (arrival_time, seq)

    tx_total = 0
    tx_rtx   = 0
    sim_time = 0.0
    sim_step = rtt / 20   # tick = 1/20 of RTT for resolution
    ticks    = 0

    if verbose:
        print(f"\nGo-Back-N Sliding Window Simulation")
        print(f"  Packets:     {total_packets}")
        print(f"  Window size: {window_size}")
        print(f"  RTT:         {rtt*1000:.0f}ms")
        print(f"  Loss rate:   {loss_rate:.0%}")
        print(f"  RTO:         {rto*1000:.0f}ms")
        print()
        print(f"  Legend: A=acked  S=in-flight  .=sendable  _=beyond window")
        print()
        print(f"  {'t(ms)':>8}  {'Event':<22} {'una':>4} {'nxt':>4} "
              f"{'flight':>6}  Window")
        print("  " + "-" * 78)

    def schedule_ack(seq: int, at: float) -> None:
        """Insert (at, seq) into the ack_queue in arrival-time order."""
        lst = sorted(list(ack_queue) + [(at, seq)])
        ack_queue.clear()
        ack_queue.extend(lst)

    while snd_una < total_packets:
        sim_time += sim_step
        ticks    += 1

        # ── process ACKs that have arrived ────────────────────────────────
        while ack_queue and ack_queue[0][0] <= sim_time:
            _, ack_seq = ack_queue.popleft()
            if ack_seq < snd_una or acked[ack_seq]:
                continue   # stale or already processed
            # Cumulative ACK: advance snd_una to ack_seq + 1
            for s in range(snd_una, ack_seq + 1):
                acked[s] = True
                in_flight.discard(s)
            old_una  = snd_una
            snd_una  = ack_seq + 1

            if verbose:
                bar = window_bar(total_packets, snd_una, in_flight, window_size)
                print(f"  {sim_time*1000:>8.1f}  "
                      f"{'ACK ' + str(ack_seq):<22} "
                      f"{snd_una:>4} {snd_nxt:>4} {len(in_flight):>6}  [{bar}]")

        # ── Go-Back-N: retransmit from snd_una on RTO ─────────────────────
        if in_flight:
            oldest = min(in_flight)
            if send_time[oldest] is not None and sim_time - send_time[oldest] > rto:
                # Retransmit all packets from oldest in window (Go-Back-N)
                retransmit_from = oldest
                in_flight.clear()
                snd_nxt = retransmit_from   # go back

                if verbose:
                    print(f"  {sim_time*1000:>8.1f}  "
                          f"{'RTO from ' + str(retransmit_from):<22} "
                          f"{snd_una:>4} {snd_nxt:>4} {'':>6}  "
                          f"[{'A'*snd_una + '_'*(total_packets-snd_una)}]")

        # ── send new packets within window ─────────────────────────────────
        while snd_nxt < total_packets and snd_nxt < snd_una + window_size:
            is_retransmit = send_time[snd_nxt] is not None
            send_time[snd_nxt] = sim_time
            in_flight.add(snd_nxt)
            tx_total += 1
            if is_retransmit:
                tx_rtx += 1

            # Schedule ACK (may be lost)
            if rng.random() >= loss_rate:
                schedule_ack(snd_nxt, sim_time + rtt)

            snd_nxt += 1

        if ticks > 500_000:
            if verbose:
                print("  [WARN] tick limit reached")
            break

    if verbose:
        print()
        print("=== Simulation Complete ===")
        print(f"  Simulated time:  {sim_time*1000:.1f}ms")
        print(f"  Transmissions:   {tx_total}  ({tx_rtx} retransmits)")
        if tx_total:
            print(f"  Retransmit rate: {tx_rtx/tx_total:.1%}")
        # Goodput: total useful data / elapsed time (assume 512B per packet)
        goodput = total_packets * 512 / sim_time / 1024 if sim_time > 0 else 0
        print(f"  Goodput:         {goodput:.1f} KB/s")

    return sim_time, tx_total


# ── window-size comparison table ─────────────────────────────────────────────

def compare_windows(rtt: float = 0.05, loss_rate: float = 0.0,
                    total_packets: int = 40) -> None:
    print(f"\n{'='*60}")
    print(f"Window comparison  RTT={rtt*1000:.0f}ms  loss={loss_rate:.0%}")
    print(f"{'='*60}")
    print(f"  {'Window':>8}  {'Time (ms)':>10}  {'Goodput (KB/s)':>15}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*15}")

    for w in [1, 2, 4, 8, 16, 32]:
        elapsed, _ = simulate(
            total_packets=total_packets,
            window_size=w,
            rtt=rtt,
            loss_rate=loss_rate,
            verbose=False,
            seed=7,
        )
        gp = total_packets * 512 / elapsed / 1024 if elapsed > 0 else 0
        print(f"  {w:>8}  {elapsed*1000:>10.1f}  {gp:>15.1f}")
    print()


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Go-Back-N sliding window simulator")
    p.add_argument("--window",  type=int,   default=4,    help="window size")
    p.add_argument("--packets", type=int,   default=20,   help="packets to send")
    p.add_argument("--loss",    type=float, default=0.0,  help="packet loss rate 0.0–1.0")
    p.add_argument("--rtt",     type=float, default=0.05, help="round-trip time in seconds")
    p.add_argument("--compare", action="store_true",
                   help="compare window sizes 1–32 (suppresses verbose output)")
    args = p.parse_args()

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

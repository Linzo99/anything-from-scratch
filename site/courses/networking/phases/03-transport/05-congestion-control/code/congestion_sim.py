# Run: python3 congestion_sim.py
"""
congestion_sim.py — Simulate TCP slow start and congestion avoidance (AIMD).

Models TCP Reno congestion control:
  1. Slow Start:        cwnd doubles every RTT until ssthresh
  2. Congestion Avoid.: cwnd += 1 MSS per RTT (additive increase)
  3. Loss via 3 dupACK: ssthresh = cwnd/2, cwnd = ssthresh (fast retransmit)
  4. Loss via timeout:  ssthresh = cwnd/2, cwnd = 1 (slow start restart)

Prints an ASCII graph of CWND over time and labels each phase.

Usage:
    python3 congestion_sim.py
    python3 congestion_sim.py --rtts 60 --loss-prob 0.08 --init-ssthresh 32
"""

import argparse
import random


MSS = 1          # work in MSS units for clarity


def simulate_tcp_reno(
    num_rtts: int = 50,
    initial_ssthresh: int = 32,
    loss_prob: float = 0.05,
    seed: int = 42,
) -> list:
    """
    Simulate TCP Reno congestion control over `num_rtts` rounds.

    Returns a list of (rtt_number, cwnd, ssthresh, event) tuples.
    """
    rng = random.Random(seed)

    cwnd    = 1          # start in slow start
    ssthresh = initial_ssthresh

    history = []

    for rtt in range(num_rtts):
        event = ""

        # ── congestion event check ────────────────────────────────────────
        # Simulate triple-dupACK with probability proportional to cwnd
        # (more in-flight packets → higher chance of loss)
        effective_loss = 1 - (1 - loss_prob) ** cwnd
        lost = rng.random() < effective_loss

        if lost:
            if rng.random() < 0.7:
                # 70% of losses detected as triple dupACK (fast retransmit)
                event = "LOSS(3dupACK)"
                ssthresh = max(cwnd // 2, 2)
                cwnd     = ssthresh
            else:
                # 30%: timeout — more severe
                event = "LOSS(timeout)"
                ssthresh = max(cwnd // 2, 2)
                cwnd     = 1

        history.append((rtt, cwnd, ssthresh, event))

        # ── advance cwnd for next RTT ─────────────────────────────────────
        if cwnd < ssthresh:
            # Slow start: exponential growth
            cwnd = min(cwnd * 2, ssthresh)
        else:
            # Congestion avoidance: additive increase (+1 per RTT)
            cwnd += 1

    return history


def ascii_graph(history: list, width: int = 60) -> None:
    """Print a horizontal bar chart of CWND over time."""
    max_cwnd = max(row[1] for row in history) or 1

    print(f"\n  CWND over {len(history)} RTTs  (max={max_cwnd} MSS)")
    print(f"  {'RTT':>4}  {'cwnd':>5}  {'ssth':>5}  Phase              Graph")
    print("  " + "-" * (width + 40))

    for rtt, cwnd, ssthresh, event in history:
        phase = "Slow Start " if cwnd <= ssthresh else "Cong.Avoid."
        bar_len = max(1, int(cwnd / max_cwnd * width))
        bar = "#" * bar_len

        note = ""
        if event:
            note = f"  ← {event}"
            bar = "!" * bar_len   # mark loss events differently

        print(f"  {rtt:>4}  {cwnd:>5}  {ssthresh:>5}  {phase:<18} {bar}{note}")


def print_summary(history: list) -> None:
    cwnds  = [r[1] for r in history]
    events = [r[3] for r in history if r[3]]

    dupacks  = sum(1 for e in events if "3dupACK" in e)
    timeouts = sum(1 for e in events if "timeout" in e)

    print()
    print("=== TCP Reno Congestion Control Summary ===")
    print(f"  RTTs simulated:       {len(history)}")
    print(f"  Peak CWND:            {max(cwnds)} MSS")
    print(f"  Average CWND:         {sum(cwnds)/len(cwnds):.1f} MSS")
    print(f"  Loss events:          {len(events)}")
    print(f"    via 3 dupACK:       {dupacks}")
    print(f"    via timeout:        {timeouts}")
    print()

    # Explain the phases
    print("  Phase progression:")
    prev_phase = None
    for rtt, cwnd, ssthresh, event in history[:20]:
        phase = "slow_start" if cwnd < ssthresh else "cong_avoid"
        if phase != prev_phase:
            label = "Slow Start (exponential)" if phase == "slow_start" \
                    else "Congestion Avoidance (AIMD +1/RTT)"
            print(f"    RTT {rtt:>3}: entering {label}  (cwnd={cwnd}, ssthresh={ssthresh})")
            prev_phase = phase
        if event:
            print(f"    RTT {rtt:>3}: {event}  cwnd {cwnd} → {max(cwnd//2, 2)}  "
                  f"ssthresh → {max(cwnd//2, 2)}")


def main() -> None:
    p = argparse.ArgumentParser(description="TCP Reno congestion control simulator")
    p.add_argument("--rtts",          type=int,   default=50,   help="number of RTTs to simulate")
    p.add_argument("--loss-prob",     type=float, default=0.05, help="per-packet loss probability")
    p.add_argument("--init-ssthresh", type=int,   default=32,   help="initial slow-start threshold")
    p.add_argument("--seed",          type=int,   default=42,   help="random seed")
    p.add_argument("--width",         type=int,   default=50,   help="graph bar width")
    args = p.parse_args()

    history = simulate_tcp_reno(
        num_rtts=args.rtts,
        initial_ssthresh=args.init_ssthresh,
        loss_prob=args.loss_prob,
        seed=args.seed,
    )

    ascii_graph(history, width=args.width)
    print_summary(history)


if __name__ == "__main__":
    main()

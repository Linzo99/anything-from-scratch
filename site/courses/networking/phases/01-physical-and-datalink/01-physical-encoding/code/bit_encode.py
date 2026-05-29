# Run: python3 bit_encode.py
#!/usr/bin/env python3
"""
bit_encode.py — Simulate NRZ and Manchester encoding for a byte string.

Implements:
  - NRZ encoding: 1 → high (+1.0), 0 → low (0.0)
  - Manchester encoding (IEEE 802.3): 1 → high-to-low, 0 → low-to-high
  - ASCII art waveform display
  - Baud-rate analysis (transitions per bit)
  - Clock-drift demonstration showing why NRZ fails on long runs

Usage:
    python3 bit_encode.py                  # uses default 'Hi' example
    python3 bit_encode.py --text "AB"      # encode arbitrary ASCII text
    python3 bit_encode.py --bits 10110010  # encode a raw bit string
"""

import argparse
import sys


# ── encoding functions ────────────────────────────────────────────────────────

def nrz_encode(bits: list[int]) -> list[float]:
    """
    NRZ (Non-Return-to-Zero) encoding.
    Bit 1 → high voltage (+1.0) for the entire bit period.
    Bit 0 → low voltage (0.0)  for the entire bit period.
    Returns 2 voltage samples per bit (beginning and end of period).
    """
    samples: list[float] = []
    for bit in bits:
        v = 1.0 if bit == 1 else 0.0
        samples.append(v)   # first half of bit period
        samples.append(v)   # second half of bit period
    return samples


def manchester_encode(bits: list[int]) -> list[float]:
    """
    Manchester encoding (IEEE 802.3 convention):
      Bit 1: high first half → low second half  (high-to-low transition)
      Bit 0: low first half  → high second half (low-to-high transition)

    Every bit period contains exactly one guaranteed mid-bit transition,
    which lets the receiver recover its clock continuously.
    Returns 2 voltage samples per bit.
    """
    samples: list[float] = []
    for bit in bits:
        if bit == 1:
            samples.append(1.0)  # high first half
            samples.append(0.0)  # low  second half
        else:
            samples.append(0.0)  # low  first half
            samples.append(1.0)  # high second half
    return samples


# ── waveform display ──────────────────────────────────────────────────────────

def render_waveform(label: str, samples: list[float], bits: list[int]) -> str:
    """
    Build an ASCII-art timing diagram.
    High samples draw on the top line, low samples on the bottom line.
    Vertical transitions are shown where voltage changes between samples.
    """
    n = len(samples)
    high_row = ""
    low_row  = ""

    for i, v in enumerate(samples):
        # Current sample segment (2 chars wide)
        if v == 1.0:
            high_row += "──"
            low_row  += "  "
        else:
            high_row += "  "
            low_row  += "──"

        # Transition between this sample and the next
        if i < n - 1:
            nv = samples[i + 1]
            if v != nv:
                # Voltage changes: draw vertical connector
                if v == 1.0:   # falling edge
                    high_row += "╮"
                    low_row  += "╰"
                else:           # rising edge
                    high_row += "╯"
                    low_row  += "╭"
            else:
                # No change: continue the horizontal line
                if v == 1.0:
                    high_row += "─"
                    low_row  += " "
                else:
                    high_row += " "
                    low_row  += "─"

    # Bit boundary markers ("|" every 5 chars = 2 samples + 1 separator)
    bit_row = "     "
    for bit in bits:
        bit_row += f" {bit}    "

    lines = [
        f"\n{label}",
        f"Hi  │{high_row}",
        f"Lo  │{low_row}",
        f"Bit │{bit_row}",
    ]
    return "\n".join(lines)


# ── analysis ──────────────────────────────────────────────────────────────────

def count_transitions(samples: list[float]) -> int:
    return sum(1 for i in range(len(samples) - 1)
               if samples[i] != samples[i + 1])


def print_analysis(name: str, bits: list[int], samples: list[float]) -> None:
    n_bits = len(bits)
    n_trans = count_transitions(samples)
    trans_per_bit = n_trans / n_bits if n_bits else 0
    print(f"  {name}:")
    print(f"    Bits:          {n_bits}")
    print(f"    Transitions:   {n_trans}")
    print(f"    Trans/bit:     {trans_per_bit:.2f}  "
          f"(NRZ ideal=1.00 worst=0.00; Manchester always≥1.00)")


# ── clock drift simulation ────────────────────────────────────────────────────

def nrz_decode_with_drift(samples: list[float], drift_ppm: float) -> list[int]:
    """
    Decode NRZ samples with a simulated clock drift.
    drift_ppm > 0 means the receiver clock is slightly faster than the sender.
    With enough drift the receiver samples at the wrong point and miscounts bits.
    """
    decoded: list[int] = []
    samples_per_bit = 2.0
    # Receiver perceives a slightly different sample rate
    effective_period = samples_per_bit / (1 + drift_ppm / 1_000_000)

    pos = 0.5  # start sampling at the midpoint of the first bit
    while pos < len(samples):
        idx = int(pos)
        if idx >= len(samples):
            break
        decoded.append(1 if samples[idx] >= 0.5 else 0)
        pos += effective_period
    return decoded


# ── text / bits helper ────────────────────────────────────────────────────────

def text_to_bits(text: str) -> list[int]:
    """Convert ASCII text to a flat list of bits (MSB first per byte)."""
    bits: list[int] = []
    for ch in text:
        byte = ord(ch)
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def bitstring_to_bits(s: str) -> list[int]:
    """Convert a string like '10110010' to [1,0,1,1,0,0,1,0]."""
    for ch in s:
        if ch not in ("0", "1"):
            raise ValueError(f"Invalid character {ch!r} in bit string — use only 0 and 1")
    return [int(c) for c in s]


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate NRZ and Manchester bit encoding"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--text", default="Hi",
                       help="ASCII text to encode (default: 'Hi')")
    group.add_argument("--bits", metavar="BITSTRING",
                       help="Raw bit string, e.g. 10110010")
    args = parser.parse_args()

    if args.bits:
        try:
            bits = bitstring_to_bits(args.bits)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        source_desc = f"bits={args.bits}"
    else:
        bits = text_to_bits(args.text)
        source_desc = f"text={args.text!r}"
        # For display, show only the first 8 bits (first character)
        bits = bits[:16]   # show first 2 bytes max to keep output readable

    print("=" * 60)
    print("  Physical Layer Encoding Simulation")
    print("=" * 60)
    print(f"  Input: {source_desc}")
    print(f"  Bits ({len(bits)}): {bits}")

    nrz_samples  = nrz_encode(bits)
    man_samples  = manchester_encode(bits)

    print(render_waveform("NRZ Encoding:", nrz_samples, bits))
    print(render_waveform("Manchester Encoding:", man_samples, bits))

    print("\n--- Baud-rate analysis ---")
    print_analysis("NRZ",         bits, nrz_samples)
    print_analysis("Manchester",  bits, man_samples)

    # Long-run demo (shows the NRZ clock-recovery problem)
    long_run = [1] * 8
    print(f"\n--- Long run of 1s: {long_run} ---")
    print("  NRZ produces a flat line — receiver can't count bits without a perfect clock.")
    print("  Manchester produces 8 visible transitions — always countable.")
    print(render_waveform("NRZ (ambiguous):", nrz_encode(long_run), long_run))
    print(render_waveform("Manchester (countable):", manchester_encode(long_run), long_run))

    # Clock drift simulation
    long_bits = [1, 0] * 8   # 16 alternating bits
    nrz_long  = nrz_encode(long_bits)
    print("\n--- NRZ clock-drift simulation ---")
    print(f"  Original bits:  {long_bits}")
    for drift in (0, 10_000, 50_000):
        decoded = nrz_decode_with_drift(nrz_long, drift)
        match   = (decoded == long_bits)
        status  = "OK" if match else "MISMATCH (bits lost)"
        print(f"  Drift {drift:>6} ppm → decoded={decoded}  {status}")

    print("\n  Manchester is immune to clock drift because mid-bit transitions")
    print("  let the receiver resynchronise on every bit period.")
    print()


if __name__ == "__main__":
    main()

# Trace Bits Across a Cable

> A network cable does not carry ones and zeros — it carries voltage levels, and turning voltage levels into bits requires a carefully designed encoding scheme.

**Type:** Learn
**Languages:** Python
**Prerequisites:** None (Phase 1 start)
**Time:** ~30 minutes

## Learning Objectives
- Explain why raw binary cannot be sent directly over a wire
- Describe how NRZ (Non-Return-to-Zero) encoding maps bits to voltages
- Describe how Manchester encoding solves the clock synchronization problem NRZ creates
- Write a Python simulation of both encoding schemes
- Interpret a timing diagram showing voltage transitions for a given bit sequence

## The Problem

Before any packet, frame, or protocol exists, there is a fundamental problem: how do you represent a "1" and a "0" using an electrical wire?

The naive answer is: high voltage = 1, low voltage = 0. Send 8 high voltages in a row and you have sent `11111111`. This is called NRZ (Non-Return-to-Zero) encoding. It seems obvious and correct — but it breaks down almost immediately in practice.

The core problem is clock synchronization. The sender and receiver must agree on when one bit ends and the next begins. With NRZ, a long sequence of `1111111111111111` (sixteen ones) looks like an unbroken high voltage on the wire. The receiver cannot count the bits because there are no transitions to count. If the sender's clock is even 0.01% faster than the receiver's, after 10,000 bits the receiver will have counted 10,001 bits and every subsequent bit will be wrong.

Manchester encoding solves this by guaranteeing a transition in the middle of every bit period, regardless of whether the bit is a 0 or a 1. The receiver uses those transitions to resynchronize its clock continuously. This is why Ethernet (classic 10BASE-T and 100BASE-TX) uses a variant of this approach (4B5B encoding followed by NRZI, but Manchester encoding in the original 10Mbps standard).

Understanding physical encoding matters because:
1. It explains why network hardware has clock recovery circuits
2. It explains baud rate vs. bit rate (they are different things)
3. It gives you the mental model for why fiber and wireless use different encodings
4. It is the foundation for everything above it in the stack

## The Concept

### NRZ Encoding

In NRZ (Non-Return-to-Zero), the voltage level directly represents the bit value:

```
Bit:     1    0    1    1    0    0    0    1
         _    _    __        _
        | |  | |  |  |      | |
Volt:   | |  | |  |  |      | |
  High  | |  | |  |  |      | |
  Low  _|  |_|  |_|  |_____|  |_
              ^
              This long low section — how does the receiver
              know it was THREE zeros and not TWO?
              Answer: only by counting clock cycles.
              If clocks drift, bits are miscounted.
```

### Manchester Encoding

In Manchester encoding, each bit is represented by a voltage *transition*, not a voltage *level*:

```
Convention (IEEE 802.3):
  Bit 1: High-to-Low transition in the middle of the bit period
  Bit 0: Low-to-High transition in the middle of the bit period

Bit:      1      0      1      1      0      0      1
        _    _        _    _  _    _
       | |  | |      | |  | || |  | |       _
       | |  | |      | |  | || |  | |      | |
High   | |  | |      | |  | || |  | |      | |
Low   _|  |_  |___|_  |_|  |  |_|  |___|_|  |_

        ^     ^     ^     ^     ^     ^     ^
        These mid-bit transitions are ALWAYS present.
        The receiver uses them to recover the clock.
```

Every bit period contains exactly one mandatory transition in the middle. Additional transitions may occur at the boundary between bits. The receiver can always find the clock by looking for the mid-bit transition.

### Baud Rate vs. Bit Rate

These terms are often confused:
- **Baud rate** (or symbol rate): the number of signal changes per second
- **Bit rate**: the number of bits per second

In NRZ, each signal level represents one bit, so baud rate = bit rate.

In Manchester encoding, each bit requires at least one transition (and possibly two), so the baud rate is always at least 2× the bit rate. This is a disadvantage — Manchester encoding is bandwidth-inefficient. You need twice the signal frequency to carry the same number of bits.

Modern encodings like 4B5B (used in 100BASE-TX) and 8B10B (used in gigabit Ethernet) offer a middle ground: they use slightly more bandwidth than NRZ but guarantee enough transitions for clock recovery.

```
Encoding      Bandwidth efficiency    Clock recovery
----------    --------------------    ---------------
NRZ           100% (1 bit/symbol)     Poor (no guaranteed transitions)
Manchester    50% (1 bit/2 symbols)   Excellent (guaranteed mid-bit transition)
4B5B          80% (4 bits/5 symbols)  Good (limits run-length of same bits)
8B10B         80% (8 bits/10 symbols) Excellent (used in Gigabit Ethernet)
```

## Build It

### Step 1 — Implement NRZ encoding

Create a file called `encoding.py`:

```python
# encoding.py
# Simulate NRZ and Manchester encoding for a bit stream

def nrz_encode(bits: list[int]) -> list[float]:
    """
    NRZ encoding: 1 -> high voltage (+1.0), 0 -> low voltage (0.0)
    Returns a list of voltage samples, 2 samples per bit period.
    """
    samples = []
    for bit in bits:
        voltage = 1.0 if bit == 1 else 0.0
        # Two samples per bit period (beginning and end of bit)
        samples.append(voltage)
        samples.append(voltage)
    return samples


def manchester_encode(bits: list[int]) -> list[float]:
    """
    Manchester encoding (IEEE 802.3 convention):
      Bit 1: High first half, Low second half  (+1.0 -> 0.0)
      Bit 0: Low first half, High second half  (0.0 -> +1.0)
    Returns a list of voltage samples, 2 samples per bit period.
    """
    samples = []
    for bit in bits:
        if bit == 1:
            # Bit 1: high-to-low transition
            samples.append(1.0)  # First half of bit period
            samples.append(0.0)  # Second half of bit period
        else:
            # Bit 0: low-to-high transition
            samples.append(0.0)  # First half of bit period
            samples.append(1.0)  # Second half of bit period
    return samples


def print_waveform(label: str, samples: list[float]) -> None:
    """Print an ASCII art waveform for a list of voltage samples."""
    high_line = ""
    low_line  = ""
    for i, v in enumerate(samples):
        if v == 1.0:
            high_line += "──"
            low_line  += "  "
        else:
            high_line += "  "
            low_line  += "──"
        # Add transition markers between samples
        if i < len(samples) - 1 and samples[i] != samples[i + 1]:
            if v == 1.0:
                high_line += "╮"
                low_line  += "╰"
            else:
                high_line += "╯"
                low_line  += "╭"
        elif i < len(samples) - 1:
            # No transition — just continue
            if v == 1.0:
                high_line += "─"
                low_line  += " "
            else:
                high_line += " "
                low_line  += "─"
    print(f"\n{label}")
    print("High │" + high_line)
    print("Low  │" + low_line)


def print_bit_labels(bits: list[int]) -> None:
    """Print bit labels aligned under the waveform."""
    label_line = "Bits │"
    for bit in bits:
        label_line += f"  {bit}  "
    print(label_line)


# ----- Main demonstration -----

if __name__ == "__main__":
    # Example bit stream
    bits = [1, 0, 1, 1, 0, 0, 0, 1]

    print("=" * 55)
    print("Physical Layer Encoding Simulation")
    print("=" * 55)
    print(f"Input bits: {bits}")

    # Encode using both methods
    nrz_samples = nrz_encode(bits)
    manchester_samples = manchester_encode(bits)

    print_waveform("NRZ Encoding:", nrz_samples)
    print_bit_labels(bits)

    print_waveform("Manchester Encoding:", manchester_samples)
    print_bit_labels(bits)

    # Show the problem with NRZ: long run of same bits
    long_run = [1, 1, 1, 1, 1, 1, 1, 1]
    print(f"\n--- Long run of 1s: {long_run} ---")
    print_waveform("NRZ (ambiguous — how many 1s?):", nrz_encode(long_run))
    print_waveform("Manchester (always countable):", manchester_encode(long_run))
```

Run it:
```bash
python3 encoding.py
```

### Step 2 — Observe the output

You will see two waveforms for the bit stream `[1, 0, 1, 1, 0, 0, 0, 1]`:
- NRZ: the voltage levels change only when bits change value
- Manchester: every bit has a guaranteed mid-period transition

For the long run `[1, 1, 1, 1, 1, 1, 1, 1]`:
- NRZ shows an unbroken flat line — impossible to count bits without a perfect clock
- Manchester shows 8 distinct transitions, each clearly marking one bit period

### Step 3 — Add a clock drift simulation

Extend `encoding.py` to simulate what happens when the receiver's clock drifts:

```python
def nrz_decode_with_drift(samples: list[float], drift_ppm: float) -> list[int]:
    """
    Simulate NRZ decoding with clock drift.
    drift_ppm: parts per million of clock rate difference.
               Positive = receiver clock is faster (misses bits at end).
    Returns the decoded bits (may have errors near the end).
    """
    # Perfect timing: sample at position 1, 3, 5, 7, ... (middle of each 2-sample period)
    # With drift: the sampling point slowly shifts
    decoded_bits = []
    samples_per_bit = 2.0
    # Receiver thinks sample rate is (1 + drift_ppm/1e6) * actual rate
    effective_period = samples_per_bit / (1 + drift_ppm / 1_000_000)

    sample_pos = 0.5  # Start at middle of first bit
    while sample_pos < len(samples):
        index = int(sample_pos)
        if index >= len(samples):
            break
        decoded_bits.append(1 if samples[index] >= 0.5 else 0)
        sample_pos += effective_period

    return decoded_bits


if __name__ == "__main__":
    # ... (previous code) ...

    # Clock drift demonstration
    long_bits = [1, 0, 1, 0, 1, 0, 1, 0,   # 8 bits
                 1, 0, 1, 0, 1, 0, 1, 0]    # 8 more bits
    nrz_samples = nrz_encode(long_bits)

    print("\n--- Clock Drift Simulation (NRZ) ---")
    print(f"Original  bits: {long_bits}")

    for drift in [0, 10_000, 50_000]:
        decoded = nrz_decode_with_drift(nrz_samples, drift_ppm=drift)
        match = decoded == long_bits
        print(f"Drift {drift:>6} ppm: {decoded} {'OK' if match else 'MISMATCH!'}")
```

Add this function to `encoding.py` and add the drift simulation block to `if __name__ == "__main__"`. Run it again to see how even moderate clock drift causes bit errors in NRZ.

### Step 4 — Calculate baud rates

Add this analysis to understand the bandwidth cost of Manchester encoding:

```python
def analyze_encoding(name: str, bits: list[int], samples: list[float]) -> None:
    """Count transitions and calculate effective bandwidth."""
    transitions = sum(
        1 for i in range(len(samples) - 1)
        if samples[i] != samples[i + 1]
    )
    print(f"\n{name}:")
    print(f"  Bits transmitted:   {len(bits)}")
    print(f"  Signal transitions: {transitions}")
    print(f"  Transitions/bit:    {transitions / len(bits):.2f}")
    print(f"  Min signal freq:    {transitions / (2 * len(bits)):.2f} × bit_rate")
    # Manchester always needs at least 1× bit_rate signal frequency,
    # and up to 2× if there are many transitions at bit boundaries.

bits = [1, 0, 1, 1, 0, 0, 0, 1]
analyze_encoding("NRZ", bits, nrz_encode(bits))
analyze_encoding("Manchester", bits, manchester_encode(bits))
```

## Exercises

1. **Bit extraction** — Write a `manchester_decode()` function that takes Manchester-encoded samples and returns the original bit stream. Hint: sample the second half of each bit period and convert the voltage back to a bit value.

2. **Long run test** — Generate the bit sequence `[0, 0, 0, 0, 0, 0, 0, 0]`. What does the NRZ waveform look like? What does Manchester look like? Which is unambiguous even without a reference clock?

3. **4B5B table** — The 4B5B encoding uses a lookup table that maps every 4-bit nibble to a 5-bit code word. Look up the 4B5B table online. Implement a Python dictionary for it and write `encode_4b5b(nibbles)`. Why does every 5-bit code word have at most two consecutive zeros?

4. **Baud rate calculation** — A network link carries 100 Mbps using Manchester encoding. What is the minimum signal frequency (in MHz) required on the physical wire? What about NRZ? (Answer: Manchester requires 100 MHz minimum; NRZ would require only 50 MHz for worst-case alternating bits, but 0 Hz for all-same bits.)

5. **Real encoding research** — Look up what encoding scheme Gigabit Ethernet (1000BASE-T) actually uses. It is not NRZ or Manchester — what problem does it solve that these two cannot?

## Key Terms

| Term | What people say | What it actually means |
|------|----------------|------------------------|
| NRZ | "direct binary encoding" | Non-Return-to-Zero. Maps 1→high voltage, 0→low voltage. Simple but vulnerable to clock drift during long runs of identical bits. |
| Manchester encoding | "transition coding" | An encoding where each bit is represented by a voltage transition (high-to-low for 1, low-to-high for 0 in IEEE 802.3). Guarantees a transition every bit period, enabling clock recovery. Used in original 10 Mbps Ethernet. |
| baud rate | "symbol rate" | The number of signal changes per second on the physical medium. Distinct from bit rate — one symbol can carry multiple bits (in advanced modulations) or one bit can require multiple symbols (in Manchester). |
| clock recovery | "synchronization" | The process by which the receiver extracts a timing reference from the incoming signal transitions, so it knows exactly when to sample each bit. Required because separate clock signals cannot be practically transmitted alongside data over long distances. |
| run-length | "consecutive identical bits" | The number of consecutive identical bit values (e.g., six 1s in a row = run-length of 6). Encodings like 4B5B and 8B10B limit maximum run-length to ensure enough transitions for clock recovery. |

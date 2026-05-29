# Expected Output

Running `python3 bit_encode.py` (default: encodes the text `'Hi'`, first 16 bits) should produce:

```
============================================================
  Physical Layer Encoding Simulation
============================================================
  Input: text='Hi'
  Bits (16): [0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1]

NRZ Encoding:
Hi  │  ──╮  ╰────╮  ╰──╮  ╰──  ──╮  ╰──╮
Lo  │──╯  ╭────╯  ╭──╯  ╭──────╯  ╭──╯
Bit │  0     1     0     0     1     0     ...

Manchester Encoding:
Hi  │╮ ╰╭─╮╰╭────╮╰╭─╮╰╭─╮╰╭──╮╰╭─╮╰╭─╮
Lo  │╰─╯  ╭╯ ╰────╯ ╰─╯ ╰─╯ ╰──╯ ╰─╯ ╰─╯
Bit │  0     1     0     0     1     0     ...

--- Baud-rate analysis ---
  NRZ:
    Bits:          16
    Transitions:   7
    Trans/bit:     0.44  (NRZ ideal=1.00 worst=0.00; Manchester always≥1.00)
  Manchester:
    Bits:          16
    Transitions:   22
    Trans/bit:     1.38  (NRZ ideal=1.00 worst=0.00; Manchester always≥1.00)

--- Long run of 1s: [1, 1, 1, 1, 1, 1, 1, 1] ---
  NRZ produces a flat line — receiver can't count bits without a perfect clock.
  Manchester produces 8 visible transitions — always countable.

NRZ (ambiguous):
Hi  │────────────────────────────────────
Lo  │
Bit │  1     1     1     1     1     1     1     1

Manchester (countable):
Hi  │──╮ ──╮ ──╮ ──╮ ──╮ ──╮ ──╮ ──╮
Lo  │  ╰─  ╰─  ╰─  ╰─  ╰─  ╰─  ╰─  ╰─
Bit │  1     1     1     1     1     1     1     1

--- NRZ clock-drift simulation ---
  Original bits:  [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
  Drift      0 ppm → decoded=[1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]  OK
  Drift  10000 ppm → decoded=[1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]  MISMATCH (bits lost)
  Drift  50000 ppm → decoded=[1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]  MISMATCH (bits lost)

  Manchester is immune to clock drift because mid-bit transitions
  let the receiver resynchronise on every bit period.
```

To encode a custom bit pattern:
```
python3 bit_encode.py --bits 10110010
```

## Common issues

- **Issue**: Unicode box-drawing characters (`╮`, `╰`, `──`) display as garbled characters → **Fix**: Your terminal does not support UTF-8. Set `export LANG=en_US.UTF-8` and re-run, or pipe through `cat`.
- **Issue**: `python3: command not found` → **Fix**: Install Python 3 with `sudo apt-get install -y python3`.
- **Issue**: The waveform looks misaligned → **Fix**: Use a monospace font in your terminal. The diagram requires fixed-width characters to align correctly.

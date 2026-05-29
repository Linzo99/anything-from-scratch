# Expected Output

Running `python3 subnet_calc.py 192.168.1.0/24` should produce:

```
======================================================
  Subnet: 192.168.1.0/24
======================================================
  Network address  : 192.168.1.0
  Broadcast address: 192.168.1.255
  First host       : 192.168.1.1
  Last host        : 192.168.1.254
  Total addresses  : 256  (2^8)
  Usable hosts     : 254  (total - network - broadcast)
  Subnet mask      : 255.255.255.0
  Mask (binary)    : 11111111.11111111.11111111.00000000
======================================================
```

Running `python3 subnet_calc.py 192.168.1.0/24 --split 4` should produce:

```
Splitting 192.168.1.0/24 into 4 subnet(s):
  Bits borrowed   : 2
  New prefix      : /26
  Subnets created : 4  (exact)
  Hosts/subnet    : 62

  #    Network            Broadcast          First Host         Last Host          Usable
  ──────────────────────────────────────────────────────────────────────────────────────
  1    192.168.1.0        192.168.1.63       192.168.1.1        192.168.1.62       62
  2    192.168.1.64       192.168.1.127      192.168.1.65       192.168.1.126      62
  3    192.168.1.128      192.168.1.191      192.168.1.129      192.168.1.190      62
  4    192.168.1.192      192.168.1.255      192.168.1.193      192.168.1.254      62

  How the split works:
    base_prefix  = 24
    num_subnets  = 4
    bits_borrowed = ceil(log2(4)) = 2
    new_prefix   = 24 + 2 = 26
    subnet_size  = 2^(32-26) = 64
    subnets start at network + 0, +64, +128, ...
```

Other useful examples:
```
python3 subnet_calc.py 10.0.0.0/8 --split 256    # creates 256 /16 subnets
python3 subnet_calc.py 172.16.0.0/16 --split 8   # creates 8 /19 subnets
python3 subnet_calc.py 192.168.0.0/24 --split 5  # rounds up to 8 (/27)
```

## Common issues

- **Issue**: `Subnets created: 8  (rounded up from 5)` when asking for 5 subnets → **Fix**: This is correct. You can only borrow whole bits, and 3 bits = 8 subnets (2^3). You cannot create exactly 5 subnets — you get 8 and use the 5 you need.
- **Issue**: `Usable hosts: 0` for `/32` → **Fix**: A `/32` host route has 1 address total and 0 usable. Use `/30` (2 usable) for the smallest point-to-point subnet, or `/31` for RFC 3021 P2P links.
- **Issue**: `Error: Cannot create N subnets from /P: would require /33` → **Fix**: The parent block is too small to be split that many times. Use a larger parent block or request fewer subnets.

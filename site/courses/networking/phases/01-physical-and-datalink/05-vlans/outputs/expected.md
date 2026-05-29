# Expected Output

Running `python3 vlan_tag.py` (default VLAN 10) should produce:

```
============================================================
  802.1Q VLAN Tag — Construction and Parsing Demo
============================================================

[1] Building an untagged Ethernet frame (IPv4)

Untagged frame:
  ────────────────────────────────────────────────────────
  Destination MAC : aa:bb:cc:dd:ee:ff
  Source MAC      : 11:22:33:44:55:66
  EtherType       : 0x0800  (IPv4)
  Payload         : 4 bytes
    First 16B hex : deadbeef
  ────────────────────────────────────────────────────────
  Raw bytes: aabbccddeeff1122334455660800deadbeef

[2] Inserting 802.1Q tag  VID=10  PCP=0  DEI=0

Tagged frame:
  ────────────────────────────────────────────────────────
  Destination MAC : aa:bb:cc:dd:ee:ff
  Source MAC      : 11:22:33:44:55:66
  EtherType       : 0x8100  (802.1Q VLAN tag)
  ┌─ 802.1Q Tag ────────────────────────────────────
  │  TPID (Tag Protocol ID): 0x8100  (always 0x8100)
  │  TCI  (Tag Control Info): 0x000a
  │    PCP  (Priority):  0  (0=best-effort, 7=highest)
  │    DEI  (Drop Elig): 0  (0=keep, 1=drop if congested)
  │    VID  (VLAN ID):  10
  └──────────────────────────────────────────────────
  Inner EtherType : 0x0800  (IPv4)
  Payload         : 4 bytes
    First 16B hex : deadbeef
  ────────────────────────────────────────────────────────
  Raw bytes: aabbccddeeff11223344556681000000 0800deadbeef
  (tag = 8100 000a: TPID=0x8100, TCI=0x000a → PCP=0, DEI=0, VID=10)

  The 4-byte tag in binary:
    1000000100000000  ← TPID = 0x8100
    000 0 000000001010  ← TCI: PCP=000 DEI=0 VID=000000001010
                                  VID=10 (decimal)

[3] Stripping the VLAN tag back to untagged frame

Stripped frame:
  ... (same as original untagged frame)
  Stripped == original: True  (PASS)

[4] Parsing a known tagged frame  (VLAN 20, PCP=3)

Pre-built tagged frame:
  Destination MAC : ff:ff:ff:ff:ff:ff
  Source MAC      : aa:bb:cc:dd:ee:ff
  EtherType       : 0x8100  (802.1Q VLAN tag)
  ┌─ 802.1Q Tag ────────────────────────────────────
  │  TPID: 0x8100
  │  TCI:  0x6014
  │    PCP: 3
  │    DEI: 0
  │    VID: 20
  └──────────────────────────────────────────────────
  Inner EtherType : 0x0806  (ARP)
  ...

[5] VLAN ID range reference:
     0–0      Reserved — no VLAN
     1–1      Default VLAN (avoid for security)
     2–1001   Normal user VLANs
  1002–1005   FDDI and Token Ring (legacy)
  1006–4094   Extended range (IOS only on some platforms)
  4095–4095   Reserved
```

To tag with VLAN 42 and priority 5:
```
python3 vlan_tag.py --vlan 42 --pcp 5
```

## Common issues

- **Issue**: `ValueError: VID must be 0–4095` → **Fix**: VLAN IDs are 12 bits wide (0–4095). Use `--vlan 1` through `--vlan 4094` for normal VLANs.
- **Issue**: `Stripped == original: False` → **Fix**: This should never happen with the built-in example. If it does, a byte was corrupted — check that the hex strings are correct.
- **Issue**: TCI value `0x000a` seems wrong for VID=10 → **Fix**: It is correct. `0x000a` = decimal 10 = 0000 0000 0000 1010 in binary. The top 3 bits (PCP=0) and bit 12 (DEI=0) are all zero, leaving the VID in the low 12 bits as `000000001010` = 10.

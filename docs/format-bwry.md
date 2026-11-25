# JD-BWRY-class register LUT (535 B at register 0x20)

Our decode of the register table of JD7966x-class black/white/yellow/red controllers. Example panels: 2.9in
(most custom work), 2.66in, 3.5in, 1.54in and 4.2in ("x4" variant), 7.5in. Everything is our own measurement.

Code: `tools/epdlut/bwry.py` (codec, builder, DC models, x4 repair), `lzss.py` (MTP store codec), `lint.py`.

## 1. Layout (measured)

| Bytes | Content |
|---|---|
| 0-6 | header: VGHL, VSPL_0, rail byte 2, rail byte 3, rail byte 4, VCOM, PLL (plain binary) |
| 7 | repeat M of block 0 row 0 (`EF` = 1) |
| 8 + 88k, k = 0-5 | six blocks of 8 rows x 11 B, same row grammar and byte code as S6 ([format-s6.md](format-s6.md) 2-3) |

- Block 0 = LUTC (VCOM), blocks 1-4 = pixel codes 0-3, block 5 = per-frame **Mode-1 select** (section 4).
- The image stops at byte 534: block 5's byte 87 does not exist. Our codec decodes with a virtual `EF` pad byte.
- x4 parts (4.2in, 1.54in) use 535 B + 1 pad byte; their read-back wraps at 536 B.
- *How we found this:* the S6 codec decoded the stock waves of this family into six blocks of equal length; block
  edits moved exactly one code; BUSY timing matched the S6 timing model exactly (M x R x TP structure).

## 2. Physical levels (measured)

The level bytes (b0 for group A, b1 for group B) hold a 2-bit field per phase, active low:

| Field | hi bit | lo bit |
|---|---|---|
| phase 1 | bit 5 | bit 2 |
| phase 2 | bit 3 | bit 0 |
| phase 3 | bit 1 | bit 6 |
| field 4 (unused in pixel blocks) | bit 7 | bit 4 |

- hi only = **W** (VSN, drives white), lo only = **K** (VSP, drives black), both = **L** (weak black, VSPL), none = **0**.
- Raw dose: K and W strong (<= 5 frames), weak levels slow, 0 V inert.
- *How:* a field-check table that set one raw bit per phase on four codes, read optically; then the scope.

## 3. Header and rails (measured)

- The controller ignores the 7 header bytes in the `0x20` stream. Rails come from the power registers. Our host code
  keeps the analog values a table was built for in its header and writes them to the registers.
- Rail law on the 2.9in: `|V| = 2.975 + 0.0991 x code` (about 3.0 + 0.1 x code).
- Custom-mode VCOM: we send VDCS `0xA0` / `0xA4` (bit 7 = use the register VCOM). Stock uses the MTP VCOM.
- Which header byte feeds which rail in Mode 1 (byte 2 or byte 3) is disputed between our scope reading and our DC
  fit. Our tables put the same value in bytes 2 and 3, chosen inside the stock range, so either reading is a stock value.
- Stay inside your panel's stock header envelope (decode your own MTP bands, section 9). On our 2.9in:
  byte 1 17-47, byte 2 0x22-0x32, byte 3 0x78, byte 4 17-44, PLL 02 or 08.

## 4. Mode-1 block (measured)

Block 5's lo bit, per frame, selects "Mode 1" for every code in that frame. In Mode 1 a W pixel draws -VSN_1
(a weaker white rail, set by a header/PWR byte) instead of -15 V. Only W loads VSN in Mode 1.
- Mode-1 W (about 7.4 V) gives a clean white; -15 V W turns white yellowish.
- A shallow VSN_1 creeps up about 1.2 V/s, then holds.
- *How:* scope on the source output while toggling block 5 bits; optical white comparison.

## 5. Terminator (measured)

A row with M = 0 ends a block. A block that uses all 8 rows ends after row 7 (stock colour waves do this). A block
with spare rows but no M = 0 row did not finish: a 25-frame 0 V table ran for more than 60 s and washed the chart
out. Fill unused blocks with 0 V for the full length; stock never has an empty block, and all six stock blocks
have equal length. `bwry.build()` does all of this.

## 6. Frame time (measured, 2.9in)

| PLL | ms per frame |
|---|---|
| 02 | 19.97 |
| 07 | 8.38 |
| 08 (stock) | rate from a 3-bit LUTC code: 79.9 / 40.0 / 20.1 / 15.5 / 13.6 / 12.0 / 10.1 / 8.5 |

x4 4.2in: PLL 02 19.80 ms, PLL 03 15.22 ms. Windowed partial tables shorter than 50 frames ran one frame longer than
the model (K10|W10: 11 frames -> 239 ms).

## 7. DC models and gate (our rule)

`bwry.dc()` sums V x frames per code. Two models, because the Mode-1 rail order is disputed:
- **Model B** ("Mode-aware", balances every stock band we decoded within about 15 V x frames except three):
  Mode 0: K +15, W -15, L +V(byte 1); Mode 1: K +15, W -V(byte 2), L +V(byte 4).
- **Model A** (scope field order): Mode 1: K +V(byte 2), W -V(byte 3), L +V(byte 4); Mode 0 as B.

Our gate: |DC| <= 15 V x frames per code under **both** models (full tables), or |code 0 + code 1| <= 15 for
differential window partials (a pixel toggles between the two codes). Re-trim whenever VSN_1 changes.
Why it matters: custom whites with a net -1785 V x frames left stuck-yellow cells; net 0 left none.
The model may miss a VCOM-offset term (open).

## 8. x4 read repair (measured)

On the x4 parts (4.2in, 1.54in) a register read-back (`0xA1`) has bit 0 of each byte one position early. Repair:
`t[i] = (a[i] & 0xFE) | (a[i-1] & 1)` (`bwry.x4_bit0_repair`). With it, the x4 timing decodes with the plain code.
The table is loaded at RST from the real sensor and we could not force or offset it.
*How:* the repaired read-backs matched the MTP store decode (section 9) byte-exactly.

## 9. MTP store container (measured; read-only)

How the stock waveform bands are stored in the controller's MTP (we only **read** it):
- 6144 B. It starts with a short fixed preamble and the temperature-threshold table (bytes 3-18).
- From byte 0x11, bit 22 (= byte 0x13, bit 6) a bitstream starts, read LSB-first:
  - flag bit 0 -> literal, 8 bits;
  - flag bit 1 -> back-reference: length 8 bits (+3), then distance 14 bits.
- Output: 2 bytes, then one 535 B table per temperature band, coldest band first.
- *How:* known plaintext. Bands we had read back through `0xA1` appear byte-exactly in the decoded stream: 23 of 23
  on four panel types. The decode also gave bands we never reached.
- `python -m epdlut.lzss decode YOUR_MTP_READ.bin --byte 0x11 --bit 22 --skip 2 --split 535 --out bands/`
- The 7.3in S6 OTP is **not** stored in this format.
- Band edges on the 2.9in are 0.5-1.5 deg C above the stored thresholds (2/5/8/11/15/20/25/30/35 deg C; the 25 deg C
  edge changes nothing because two neighbouring bands hold the same table).

## 10. Practical notes

- LUT placement: before PON on the 2.9in, 4.2in, 3.5in and 1.54in; **after the full init** on the 7.5in
  (an earlier upload is overwritten).
- In windowed partials (`0x83` window) our window fill helper had codes 2 and 3 swapped; check your own path.
- BWRY TSC can read 97.5 deg C on the first power-up after a replug (3.5in). Re-RST if TSC is outside -25..50 deg C.
- Pixel code to colour is panel-specific (2.9in: code 2 = red; 7.5in: code 2 = yellow). Permute before writing a palette.

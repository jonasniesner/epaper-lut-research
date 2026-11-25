# S6-class register LUT (800 B at register 0x20)

Our decode of the waveform table that Spectra 6 controllers of the SPD1657A class accept in register `0x20`.
We worked it out on two example panels: a 7.3in single-chip panel and a 7.09in dual-chip panel. Where they differ,
both are given. Everything here is our own measurement; nothing is quoted from a datasheet.

Code: `tools/epdlut/s6.py` (codec), `timing.py` (frame time), `charge.py` (DC), `lint.py` (checks).

Status words: **measured** = shown on glass, by BUSY timing or on a scope; **inferred** = fits the data, not tested
by a direct edit; **open** = not known.

## 1. Layout (measured)

| Bytes | Block | Role |
|---|---|---|
| 0-7 | header | byte 0 `FF`; bytes 1-4 weak-rail codes; byte 5 VCOM code; byte 6 rate code; byte 7 = repeat M of LUTC row 0 |
| 8-95 | LUTC | 8 rows x 11 B. Shared timeline for every pixel: VCOM bits and frame-rate bits |
| 96 + 88k | slot k (k = 0-7) | 8 rows x 11 B. Drives only pixels whose code is k |

- Slot k drives pixel code k, no offset. Stock colour order: 0 K, 1 W, 2 Y, 3 R, 5 B, 6 G.
  *How we found this:* blanked one slot at a time and watched which colour stopped changing.
- **800 B vs 799 B.** A stored stock set is 799 B: 7 header bytes + 9 x 88 B. Our 800 B uploads carry one surplus
  byte at the end (byte 799). The controller ignores it. Treat byte 799 as don't-care.
  *How we found this:* consecutive stock sets in a multi-set read overlap by exactly one byte. Nic Limper pointed out
  that the extra byte sits at the end, not the start, in his review of our notes (see [Nic Limper](https://github.com/nlimper)).
- The controller uses one table of at most 1024 B from `0x20`; registers `0x21`-`0x2F` had no effect even zeroed (7.09in).
- **Select bit:** PSR (register `0x00`) byte 2 bit 7 switches from the OTP waveform to the register table
  (7.3in `5F 69` -> `5F E9`; 7.09in `DF 69` -> `DF E9`). *How:* toggled the bit with a visibly different table loaded.

## 2. Row grammar (measured)

Each row is 11 bytes, but its record starts one byte earlier:

```
[M] b0 b1 | b2 b3 b4 | b5  | b6 b7 b8 | b9  | (b10 = M of the next row)
    levels  phases A   R_A   phases B   R_B
```

- **The repeat M of row i is byte 10 of row i-1.** For row 0 of a block, M is the byte just before the block:
  header byte 7 for the LUTC, byte 87 of the previous block for a slot. Stock tables have `EF` there (= 1).
- `FF` decodes to 0, so `FF` in byte 10 silences the next row. **When you blank a slot, keep its byte 87**, or the
  next block loses its first row.
- A row runs `M x [ R_A x (A1 A2 A3) then R_B x (B1 B2 B3) ]` frames:
  `frames(row) = M x (R_A x (A1 + A2 + A3) + R_B x (B1 + B2 + B3))`.
- A block's length is the sum of its rows.
  *How we found this:* single-bit edits of the time, repeat and M bytes, timed by BUSY. The model predicts 255 of 267
  timing probes within 5 % on the 7.09in, 38/38 within 2 % on the 7.3in, and stock sets within 0.4 %.

## 3. Byte code (measured)

All time, repeat and M bytes are 8-bit numbers, active low (a cleared bit counts), with a scrambled bit order:

```
value = 1*b4 + 2*b7 + 4*b6 + 8*b1 + 16*b0 + 32*b3 + 64*b2 + 128*b5     (bk = bit k is 0)
```

Examples: `FF` = 0, `EF` = 1, `7F` = 2, `BF` = 4, `AF` = 5, `3F` = 6. In b4 and b8 (the last time byte of each group)
bit 5 is not a time bit: it is the K level bit of phase A3 / B3, so those two times are 7-bit (max 127).
The code is a bijection: our codec round-trips every table we stored byte-exactly (1565 files, 800 B and 535 B).
*How:* bit-by-bit timing probes; pairs of bits add exactly.

## 4. Levels (measured)

Each phase has three active-low level bits, which we call S, W and K:

| Phase (time byte) | S | W | K |
|---|---|---|---|
| A1 (b2) | b0 bit 2 | b0 bit 5 | b0 bit 3 |
| A2 (b3) | b0 bit 1 | b0 bit 0 | b0 bit 6 |
| A3 (b4) | b0 bit 4 | b0 bit 7 | **b4 bit 5** |
| B1 (b6) | b1 bit 2 | b1 bit 5 | b1 bit 3 |
| B2 (b7) | b1 bit 1 | b1 bit 0 | b1 bit 6 |
| B3 (b8) | b1 bit 4 | b1 bit 7 | **b8 bit 5** |

That gives seven driven levels plus a float:

| Level | Rail (scope, both panels) | Optical role |
|---|---|---|
| 0 | driven, near 0 V | grounds the pixel |
| S | VSL (about -15 V) | drives yellow-bright |
| W | VSL_LV (PWR data byte 3) | white without the yellow; slow |
| SW | VSL_LV2 (PWR data byte 5) | blue's intermediate level |
| K | VSH (about +15 V) | black; kills red |
| SK | VSH_LV (PWR data byte 2) | dark but keeps red |
| WK | VSH_LV2 (PWR data byte 4) | dark, stock green uses it |
| SWK | source floats, holds the previous level | **not** the same as 0 |

- The last pulse sets the colour.
- PWR data bytes are numbered from 0 (`3F 00 b2 b3 b4 b5`).
- *How we found this:* saturated single-level dose curves on a black and a white prior (optics), then a scope on
  the source output of one pixel column (rails). SWK vs 0: an SWK tail behaved like no tail at all, a level-0 frame
  grounded the pixel (2.8-3.1 dE00 apart on the 7.09in).

## 5. What stock sets look like (measured, structure only)

We publish no stock tables. The structure we saw on both panels, which the recipes rely on:
- every block has the same length (a stock table that is not all-equal is a bad read);
- row 0 = a long lead pulse (group A) plus balanced S/K pairs repeated R_B times (group B);
- row 1 (and row 2 on the 7.09in) = a short balanced S/K pair repeated many times (the "shake");
- the remaining rows = the forming track that sets the colour; the W track on the 7.3in contains a long level-0 dwell row,
  and the G track has an internal level-0 dwell that matters (see [partial-modes.md](partial-modes.md));
- stock sets are DC-balanced against 0 V within 0.69 S-frames (7.3in) and 1.43 (7.09in) at nominal +-15 V rails.

## 6. Frame time (measured)

PLL (register `0x30`): bit 3 clear = fixed rate code `PLL & 7`. Bit 3 set (stock `08`) = dynamic: each frame uses the
3-bit rate code of the LUTC row that covers it (rate bit 0 = b0 bit 4, bit 1 = b0 bit 7, bit 2 = b1 bit 4 of that LUTC
row); frames past the LUTC end run at code 0.

| ms per frame | 7.3in | 7.09in |
|---|---|---|
| PLL 02 | 23.46 (+39 ms per refresh) | 20.4 |
| PLL 04 | 15.55-15.66 | 13.5-13.6 |
| PLL 05 | 13.45-13.61 | 11.9-12.0 |
| PLL 08, rate code 0-7 | 40.4 / 31.4 / 23.5 / 20.2 / 15.6 / 13.4 / 11.9 / 10.1 | 81.1 / 40.6 / 20.35 / 15.7 / 13.6 / 12.0 / 10.2 / 8.5 |
| stock | rate code 3 | rate code 2 |

- **The refresh lasts as long as the longest block, used or not** (LUTC and all 8 slots). An unused long slot costs time.
- 7.09in: frame = DRF time / 40 at PLL 08, no fixed overhead (scope).
- *How:* BUSY timing of probe tables at each PLL; on the 7.09in also the scope on the frame clock.

## 7. Codes 4 and 7

- **7.09in: hardwired holds.** Their slot contents are ignored; at most 6 driven codes per refresh. A stock-table region
  update needs no extra command: write 4 or 7 to the pixels that must not change. *How:* filled slots 4/7 with strong
  drive; those pixels never changed.
- **7.3in: live.** Slots 4 and 7 drive like any other (8 codes per refresh). Stock copies slot 1 into them. A "hold"
  on the 7.3in is an empty slot (all level 0 / no frames) that your table provides.
- **JD7601 (Nic Limper's data): live**, and the stock waveform has no hold code there either (see [Nic Limper](https://github.com/nlimper)).
  So the hardwired hold looks specific to the 7.09in chip.

## 8. Custom mode ignores the header (measured)

With the select bit set, the rails come from PWR (`0x01`), VCOM from VDCS (`0x82`) and the frame rate from PLL (`0x30`).
The header is used only in OTP mode (bytes 1-4 weak-rail codes, `|V| = 3.0 + 0.1 x code`; byte 5 VCOM code; byte 6 rate).
- For a byte-true replica of a stock set, write PWR data bytes 2-5 = the set's header bytes 1-4 decoded
  (`epdlut.recipe replica` prints them), and on the 7.3in VDCS `0x0F` (= the stock VCOM, -49.6 mV per code).
- The PWR value is what you get: the weak rails are stiff (<= 17 mV droop under load).
- Book weak levels with the PWR weights, never with header weights, when you compute charge for a custom table.
- *How:* header edits with no visible or timing effect; scope on the rails while changing PWR and the header.

## 9. LUTC: VCOM bits (measured)

Per LUTC group byte, each phase has a (lo, hi) VCOM pair: phase 1 = (bit 2, bit 5), phase 2 = (bit 0, bit 3),
phase 3 = (bit 6, bit 1). On the 7.3in, lo/hi swing VCOM by about +-14.8 V; on the 7.09in they did nothing.
Stock 7.3in sets never use them and none of our tables do. `lint.py` fails any table that sets them unless you pass
`--allow-vcom-swing`. *How:* scope on VCOM while toggling the bits.

## 10. End hold (measured, rule still open)

A slot that drives up to the last frame keeps acting at that level until power-off (POF): 6-12 dE00 on the 7.3in,
2.5-2.8 on the 7.09in, in tests where POF was not actually executed. One level-0 end frame, or PSR FOPT `00`
(`5F 89` / `DF 89`), removed it there. *Credit:* the end-hold effect was first described by Nic Limper on the JD7601
("+NL+"); we measured its size on our panels and added the FOPT and POF tests.

With POF sent correctly (`02 00`) right after BUSY:
- one level-0 end frame **broke** the 7.3in set-6 replica (K 10.8, B 10.7 dE00 vs stock);
- a later set-matched test found one end frame and FOPT 00 harmless but useless, and a 7.09in end-frame table was not hurt.

Our current practice: right-aligned tables that end on the forming level, always followed by POF. Treat the end frame
as a per-table property and test it on your panel. `lint.py` reports driven endings as INFO.

## 11. Border (measured)

CDI (`0x50`) bits 7-5 (VBD) pick which slot drives the border: 7.3in `3F` -> slot 1, `1F` -> slot 0;
7.09in `17/37/57/77` -> slots 0-3, `F7` = no border drive. A custom table must fill that slot or the border floats.
Our partial tables put the HOME track (K16 0x6 S16, balanced) in the border slot. *How:* scope on the border
electrode plus a decode of the stock border drive (216/216 runs matched).

## 12. Hang patterns (measured on the 7.09in)

- Eight `00` bytes in a row anywhere, or an all-zero 8 B header with the select bit set, makes BUSY never release.
  Recover with RST.
- Some upload paths refuse bytes `00`, `01`, `11` (our 7.3in lab firmware did); pad a frame to avoid them
  (`lint.py --forbid 00,01,11`).

## 13. Dual-chip panels (7.09in class, one example)

- Upload the same table to **both** chips (main and slave chip select). The main chip owns VDCS, PWR, CDI and the clock;
  power and booster commands go to the main chip only.
- BUSY is the wired AND of both chips. The slave cannot refresh alone (it holds BUSY low until RST).
- POF does not abort a refresh; only RST does, and the scan front then freezes mid-panel.
- **A TSC (`0x40`) read reloads `0x20` from OTP** and returns the previous reading (prime it with a dummy read).
  So read the temperature **before** the upload, never between upload and refresh.
- Use a BUSY timeout of at least 60 s for custom tables (cold stock sets run 42-49 s).

## 14. Temperature bands

The controller picks its OTP set from the sensor value it latches at RST. Edges we measured:
- 7.3in: 2.5 / 5.5 / 8.5 / 11 / 15.5 / 19 / **24.5** / 29.5 / 33.5-34 deg C (set 6 = 19-24.5, set 7 = 24.5-29.5);
  hysteresis about 1 deg C or less.
- 7.09in: the set 4 | set 5 edge sits at 25.5-26 deg C. Which number the warm set carries (5 or 6) is still open.

A custom table must be built from the **same set the chip would run now**. Built from the neighbour set, W and G
(7.3in) or K, R and B (7.09in) shift by 1-3.5 dE00. Forced temperature commands did not move the set on the 7.3in.

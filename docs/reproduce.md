# Reproduce the three headline results

You need: an S6-class 7.3in or 7.09in panel (or a JD-BWRY 2.9in for recipe C), a board that lets you send raw
controller commands over SPI, ideally with a read line (MISO), a BUSY input, and a camera or spectrophotometer.
Read [safety.md](safety.md) first. Install nothing beyond Python 3.9+; run the tools from `tools/`:

```
cd tools && python -m unittest discover -s ../tests     # should print OK
```

Command bytes below are what worked on our example panels. Check them against your own driver.

## A. Byte-true stock replica in custom mode (tests your upload path)

If this does not match a stock refresh, nothing else will.

1. Let the panel rest at room temperature (inside the README window). Do a normal stock full refresh of a test chart.
2. Read the panel temperature **now** (TSC, `0x40`; on the 7.09in send one dummy read first, the result lags by one).
   Note which stock set the chip uses at this temperature ([format-s6.md](format-s6.md) 14).
3. Read back the live table. On our 7.3in a register read of `0xA1` returned the table the chip had loaded at RST
   (800 B). On our 7.09in, the register read-back (command + 8) and a `0x93` read of the stored sets worked; a stored
   set is `read[799*s : 799*s + 800]`. Save it as `SET.bin`. Do not publish it.
4. `python -m epdlut.recipe replica SET.bin replica.bin --pwr-prefix "3F 00"` (7.09in: `"0F 00"`).
   It prints the PWR bytes (data bytes 2-5 = the set's header rail codes) and the lint result.
5. Refresh with it:
   RST, your normal init, PWR = the printed bytes, VDCS `0x0F` (7.3in), PSR select bit set (`5F E9` / `DF E9`),
   write `0x20` with the 800 B (both chips on the 7.09in), image data, PON, DRF, wait for BUSY, **POF `02 00`**.
   No TSC read between the upload and DRF.
6. Compare with step 1. Expected: within 0.4 dE00 per colour (7.3in set 6: K 0.08 ... G 0.13).
   BUSY time = stock (7.3in warm set 22.3 s at PLL 02).

## B. Fast full and flashing partial on the 7.3in

1. Steps A.1-A.3 to get `SET.bin` for the live band.
2. Fast full: `python -m epdlut.recipe fast73 SET.bin f1d.bin --row0-drop 5` (F1d, 689 frames, 16.2 s;
   `--row0-drop 4` gives F1e, 709 frames, 16.7 s with more margin).
3. Flashing partial: `python -m epdlut.recipe flash73 SET.bin s3.bin` (S3: codes K 0, Y 2, R 3, B 5, W 6;
   code 1 = border/HOME; code 4 = hold for unchanged pixels). 15.17 s.
4. Check: `python -m epdlut.lint s3.bin --pwr "<printed>" --codes 0,1,2,3,5,6` and
   `python -m epdlut.timing s3.bin --panel 7.3 --pll 02`.
5. Refresh as in A.5, using PLL `02`. For the partial: write code 4 to every unchanged pixel, the target colour code to
   changed pixels. Use the lean cycle (no init or RST between updates; write PWR and VDCS every update; POF every update).
6. Expected (camera, against a stock refresh of the same image): F1d median 0.33 dE00; S3 median 0.40.
   Stock refresh at least every 10 partials.

## C. Sub-second partials from the published tables

No stock-derived data needed.

1. 7.3in home/mark: `luts/s6/s73_homemark_H16M10.bin`, PWR `3F 00 1E 18 23 3E`, PLL `02`, CDI `3F` (border = slot 1).
   Code 1 = HOME (pale yellow), code 5 = MARK (navy); write code 4 to pixels that must not change (its slot is empty).
   Drive a pixel only when it changes state. `python -m epdlut.lint luts/s6/s73_homemark_H16M10.bin --pwr "3F 00 1E 18 23 3E" --codes 1,5`.
   Expected: BUSY 0.93 s; contrast 55-65 dE00; 100 toggles without drift beyond an untouched strip.
2. 7.09in: `luts/s6/s709_homemark_P1b.bin`, PWR `0F 00 1A 24 30 38`, PLL `04`, both chips. Code 0 = MARK, code 1 = HOME (border), code 4 or 7 = hold. Expected 0.73 s,
   contrast 21-27 dE00.
3. 2.9in BWRY windowed partial: `luts/bwry/bwry29_BW2_kick3_w10.bin`. Per update: window `0x83`, image, CDI, LUT
   (select bit set; header values from `luts/manifest.json` `write_with`), PON, DRF, POF. Check
   `python -m epdlut.lint luts/bwry/bwry29_BW2_kick3_w10.bin --pair`. Expected: DRF 1.24 s; K 1.6 / W 2.4 dE00 vs stock.
   Black outside the window fades if you cut the supply every update; stock refresh at least every ~20 updates.

## Measuring

- Compare against a stock refresh of the **same image in the same session**, same lighting.
- Rest the panel >= 5 min before both the reference and the test (BWRY especially).
- Log the panel temperature with every capture.

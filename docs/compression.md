# How well tables compress

For firmware that stores many tables. Measure on your own set: `python -m epdlut.compress luts/s6 luts/bwry [--dict SET.bin]`.

## On the tables in this repo

| Group | n | Raw | Raw deflate | LZSS (len8/dist14, the MTP format) |
|---|---|---|---|---|
| 800 B S6 (`luts/s6`) | 8 | 800 | median 38 B (20.8x) | median 44 B |
| 535 B BWRY (`luts/bwry`) | 9 | 535 | median 84 B (6.4x) | median 94 B (5.7x) |

These tables are short and regular, so they compress unusually well.

## On our full lab set (not published)

| Set | n | Raw | Raw deflate | zlib | LZMA2 | LZSS | PackBits | Byte RLE |
|---|---|---|---|---|---|---|---|---|
| S6 custom tables | 308 | 800 | 124 (6.4x) | 130 | 126 | 144 (5.6x) | 261 | 338 |
| S6 stock sets (7.09in) | 14 | 800 | 333 (2.4x) | 339 | 358 | 448 (1.8x) | 606 | 1059 |
| BWRY 535 B (custom + stock bands) | 104 | 535 | 214 (2.5x) | 220 | 205 | 276 (1.9x) | 408 | 581 |

Tables derived from a stock set, with that set as a deflate preset dictionary:

| Table | Deflate | With stock dictionary |
|---|---|---|
| 7.09in G7_N8_mixB | 191 | 113 |
| 7.09in F3c / G13 | 324 / 315 | 114 / 122 |
| 7.3in S3 | 200 | 100 |
| 7.3in L1b | 222 | 109-137 |
| 7.3in F1d | 235 | 57 |

## Takeaways

- Byte RLE and PackBits do not help: bytes repeat in 11-byte row patterns, not in runs.
- LZ-family codecs work. Raw deflate is the smallest of the simple options.
- A stock-set dictionary shrinks derived tables 2-4x more. Options for firmware:
  1. store deflate or LZSS blobs;
  2. store a delta against the stock set read back from the chip (needs a readable bus);
  3. store the recipe ("drop shake rows, stretch phase x k") and rebuild on the device, as `recipe.py` does on the host.
- The BWRY MTP store is already LZSS, so one small LZSS decoder can serve both.

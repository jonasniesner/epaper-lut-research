# Recipes for stock-derived tables

Some of our best tables are edits of a stock waveform set. We do not publish those tables or the stock sets. Instead,
each JSON here describes the edit, and `tools/epdlut/recipe.py` applies it to **your own read-back** of your own
panel's set (see [docs/reproduce.md](../docs/reproduce.md)).

| Recipe | Lab name | Panel | Refresh | Lab result |
|---|---|---|---|---|
| replica_s6 | C0 / set replicas | 7.3in, 7.09in | = stock | within 0.4 dE00 of stock |
| fast73_F1d | F1d | 7.3in | 16.2 s | median 0.33 |
| fast73_F1e | F1e | 7.3in | 16.7 s | margin over F1d |
| flash73_S3 | S3_N0_wgap0 | 7.3in | 15.17 s | median 0.40 |
| flash73_L1b | L1b | 7.3in | 17.6 s | median 0.49-0.57 over 20 updates |
| track73_N1 | N1/N2 | 7.3in | 8.8-10.6 s per update | changed 1.0-1.4 |
| fast709_F3c | F3c | 7.09in | 21.67 s | worst 0.69 |
| fast709_G13 | G13 | 7.09in | 17.5 s | worst 2.04 |
| mix709_G7_N8_mixB | G7_N8_mixB | 7.09in | 11.5 s | median 0.60-0.74, worst < 1.7 |

- The builder output is not byte-identical to our lab tables (row packing and balance details differ). F1d/F1e
  matched byte-for-byte on our sets; S3, L1b and all N1 tracks matched segment-for-segment; F3c matched our
  split-rail variant; G13 and G7_N8_mixB differ in padding or prefix. Frame counts and drive structure follow the edits.
- Always lint the output and build from the set that matches the live temperature band.
- The 7.3in recipes assume the slot order of our 7.3in (K 0, W 1, Y 2, R 3, B 5, G 6). Check yours.
- `tests/` runs every recipe on synthetic sets (built from scratch with the same row structure, no stock data).

# Table classification

Every lab table was put in one of three classes. Method: compare each table's 10-byte rows and drive-segment
sequences against our stock sets (7.3in sets, 7.09in stored sets, BWRY stock bands and stock 16-colour waves), and
check the builder source that made it.

- **from-scratch** (may be published): built only from our own synthetic segments; no stock row appears in it
  (row match 0 %) and its builder took no stock input.
- **vendor-derived** (recipe only): an edit of a stock set, or a byte-true / near copy of one.
- **unsure** (excluded): anything we could not settle.

## Included (17, in `luts/`)

S6: `s73_homemark_H16M10`, `s73_homemark_H12M6`, `s73_tick_ladder`, `s709_homemark_P1a`, `s709_homemark_P1b`,
`s709_mark_ticks`, `s709_dose_ladder`, `s6_test_SK20` (generated).
BWRY: `bwry29_K10W10`, `bwry29_ky_p1`, `bwry29_BW2_kick3_w10`, `bwry29_B4_shake_n2`, `bwry29_WF_t2e1w1`,
`bwry29_H_t2f20`, `bwry29_x18n_p02`, `bwry29_ANIM2_n10`, `bwry_test_null` (generated).

Note on S6 headers: header bytes 1-6 of the S6 lab tables still hold the rail, VCOM and rate codes of the stock set
used as a template (7 bytes, no waveform data). Custom mode ignores them. We judged this not to be a copy of a
waveform; overwrite them if you prefer.

## Vendor-derived: recipe only (not published as tables)

- 7.3in: byte-true replicas (C0, C1, C7, all replica sets), F1a-F1f and F1d6/F1d7, F2*, F3*, F4*, G1-G3 shake
  variants, C2, L1_* and L1b*, S0-S4, N1*/N2*/N2G*/N2H*, the G-track variants (GL, GQ, GD, GZ, GBT, GF1e), short tracks
  (T* family), OW2*, F1g*, F2_Ktick_N2/N3, W1-W3, P2_F1*, ANIM1_n4/n8.
- 7.09in: F1*, F2*, F3*, G1-G14, L1_N*, L4_H*, G4-G10 including G7_N8_mixB and G7_HE_mixB, OW_T*, OW_TL.
- BWRY: tables built from stock waves (F3_stock07/08, stock wave edits).

## Unsure: excluded

- HM1 (carries a full stock 8-byte header).
- Not reviewed table by table, so excluded: M709A/B, Q_SP2*, T156/T186/T195, DOSE_*, and scope/timing probe tables
  (r73_*, r709_*, v73/v709, ks73, kp73, l0_*, eh73, lz73, dr73, bd73, rl73, fm73, m_*, M1-M4, Z852, SW_swatch, X1_tail1).
- The `bwry29_x18n_p02` lineage: its structure follows an earlier "x18" layout we designed after studying stock
  waves; row match to stock is 0 % and it was built from our own segments, so we include it, but flag the call.

## From-scratch but not included

S1_*, other BWRY F1_f* fast-run variants, P3_v*, W_k*, the other WF_* and F2_x18 variants. Left out to keep the set
small; they are near-duplicates of included tables or failed without adding information.

# Open questions

- **Spectrophotometer checks.** Almost all partial and fast-full results are camera-relative. Not yet measured with a
  spectrophotometer: G7_N8_mixB in both bands, F1d white, the 7.3in final palette.
- **End-frame rule.** One level-0 end frame broke the 7.3in replica in one test (R-0187) and was harmless in a later
  set-matched test (R-0229, R-0201). Until settled: always POF, and treat the end frame as a per-table property.
- **Live band switching.** No table switch across a real temperature crossing has been tested. Hysteresis is unknown.
  Per-band tables exist only for 7.3in sets 6/7 and 7.09in sets 4/5.
- **7.09in set numbering.** Whether the warm set is number 5 or 6.
- **7.09in red and green partials.** Every short R tail fails; G cannot be balanced.
- **7.3in green.** Needs its internal dwell; shortest 12.0 s from W/Y/R/B, 15.3 s from K. R -> W misses at full length.
- **BWRY Mode-1 rail order.** Header byte 2 vs byte 3 (scope vs DC fit). Our DC gate checks both models.
- **BWRY DC model** may miss a VCOM offset term.
- **BWRY fast full.** K over a red prior unsolved.
- **BWRY black fade** outside the window: one lab panel faded strongly on one day only; one product unit, one night.
- **2.66in windowed partial** is dead while the 2.9in works. Unexplained.
- **x4 variant** (4.2in, 1.54in): timing solved, no custom partial or fast work.
- **VCOM neutrality** of the stock VDCS value is unproven: level 0 lifts black by about +8 L* over 20 s regardless of VCOM.
- **Production POF.** Whether common open-source drivers send POF with its data byte has not been checked on a scope.
- **Unit spread.** One unit per model (two for the 2.9in). Our BWRY 16-colour work showed 14 % spread between units.
- **Long-term effects** on panel lifetime: not studied.

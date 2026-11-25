# All refresh modes we tested

One line per mode. Panels: 7.3in (S6 class, one unit "unit A"), 7.09in (S6 class, dual chip, one unit), 2.9in, 2.66in,
3.5in, 1.54in, 4.2in, 7.5in (JD-BWRY class). Status is for the example panel only. Details of the partial modes are in
[partial-modes.md](partial-modes.md).

| # | Mode | Family | Status | Refresh | Quality | R-ids |
|---|---|---|---|---|---|---|
| 1 | Stock full refresh | all | reference | 7.3: 22.3 s; 7.09: 30.2 s / 34.5 s; 2.9: 19.7 s or 34.2 s by band | reference | R-0001, R-0031, R-0194 |
| 2 | Stock with a faster frame clock (PLL) | all | works, colour cost | 7.09 PLL 04 22.6 s; 2.9 PLL 07 9.2 s; 7.3 PLL 08 19.2 s | 7.09 max 2.7; 2.9 about -8 % chroma | R-0032, R-0046, R-0013 |
| 3 | Booster fast tail | BWRY 2.66 only | partial [1 ex] | 14.2 s vs 19.4 s | red -20 % chroma | R-0058 |
| 4 | Byte-true stock replica in custom mode | S6 | verified | = stock | 0.04-0.4 | R-0186, R-0229, R-0240 |
| 5 | Custom fast full (shake trim) | S6 | verified | 7.3 16.2-16.7 s; 7.09 17.5-21.7 s | 7.3 median 0.33; 7.09 worst 0.7-2.0 | R-0199, R-0205, R-0231, R-0201, R-0204 |
| 6 | Custom fast full | BWRY 2.9 | failed | best white 13-15 s | K over R 15-25 | R-0198, R-0200, R-0202, R-0219 |
| 7 | Stock hold codes 4/7 | S6 7.09 | verified [1 ex] | stock | held region untouched | R-0032 |
| 8 | Flashing partial | S6 | verified | 7.3 15.17 s; 7.09 11.5 s | median 0.40 / 0.60-0.74 | R-0234, R-0231, R-0240, R-0242 |
| 9 | Transition-aware partial | S6 7.09 | verified [1 ex] | 9.0-10.3 s | median 0.54-0.82 | R-0228, R-0240 |
| 10 | Host-aware per-update table | S6 7.3 | verified [1 ex] | 8.8-10.6 s | changed 1.0-1.4 | R-0239, R-0241 |
| 11 | Colour-subset table | S6 7.3 | verified [1 ex] | 13.55 s | = control | R-0234 |
| 12 | Short tracks / one-way ticks | S6 | verified, prior-specific | 1.0-13.2 s | <= 1.5 | R-0236, R-0220, R-0221 |
| 13 | Sub-second home/mark | S6 | verified, limited | 0.51-0.94 s | 7.3 contrast 55-65; 7.09 21-27 | R-0021, R-0199, R-0201 |
| 14 | Grey dose ladder | S6 | partial | about 0.9 s per step | 3-4 grey levels | R-0208, R-0210 |
| 15 | In-refresh animation | S6 7.3 / BWRY 2.9 | [prov] | +10 s | 7.3 clean end; 2.9 8-12 off | R-0211 |
| 16 | Multi-pass for more colours | S6 7.09 / BWRY | [prov] (S6) | 7.09 20.1 + 4.9 s | 31-37 distinct states | R-0037, R-0213, R-0214, R-0216 |
| 17 | BWRY 16-colour mode (3 passes) | BWRY 2.9/3.5/1.54/4.2/7.5 | verified on glass | 2.9: 20.6 + 1.8 + 1.8 s | 16 states, min pair 5.7-7.2 dE00 (spectro) | R-0099, R-0100 |
| 18 | S6 single-pass, 8 codes, custom palette | S6 7.3 | verified [1 ex] | about 22 s | 35 states (22 chromatic) | R-0007, R-0012 |
| 19 | BWRY windowed partial | BWRY 2.9 (dead on 2.66) | verified | 0.13-0.26 s DRF | best: K 1.6 / W 2.4 | R-0045, R-0198, R-0237, R-0238 |
| 20 | BWRY full-frame BW-only | BWRY 2.9 | failed | 10-18 s | K 3.6-11 short | R-0219, R-0237 |
| 21 | Truncation by RST | S6 | superseded | - | non-uniform scan front | R-0022 |
| 22 | Forced temperature to pick a set | S6 7.3, x4, 2.9 | failed (7.09: one command pins a set) | - | - | R-0014, R-0053, R-0046 |
| 23 | Fast BW via a short edit table | BWRY 2.66 | failed | 1.8 s | ghosts | - |
| 24 | Supply cut after every refresh | S6 7.3 | harmless [prov, 1 ex] | - | ink within +-0.5 L* over 20 cycles | R-0222 |

Notes:
- 2: dose follows time. Green on the 7.09in needs about 20 ms frames; rate codes 5-7 on the 7.3in lose K and G by 9-19 dE00.
- 4 is the acceptance test for any upload path: if the replica does not match stock, nothing else will.
- 5: start from the live stock set, remove S/K shake pairs, keep forming rows and frame time. Scrub (stock refresh)
  every ~10 fast refreshes: 20 back-to-back fast refreshes grew the worst error from 2.0 to 4.1.
- 16/17: BWRY 16-colour is a three-pass *mode*: pass 1 a full colour wave, passes 2-3 short edit waves, each with its own
  535 B table and one 2-bit plane. No green or blue exists on these panels. Dithered mixes darken non-linearly.
- 18: the 7.3in can show 8 programmed colours in one refresh because codes 4 and 7 are live.

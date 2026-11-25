# Results index

R-ids are the identifiers of our internal lab result log. They are kept so that numbers in these docs can be traced;
the underlying lab reports are not published (they contain raw captures and chip read-backs).

Flags: **[1 ex]** one example panel only. **[cam]** camera-relative colour (dE00 against a same-session stock refresh
of the same image; no spectrophotometer). **[spectro]** measured with a spectrophotometer. **[prov]** provisional in our
log (not repeated, or a known confound). No flag on a measurement means BUSY timing, scope, or byte-level decode.

## Format and timing

| R-id | Result | Flags |
|---|---|---|
| R-0001 | 7.3in: all 10 stock sets decoded; warm sets 949 frames = 22.3 s, cold up to 52.6 s; stock sets DC-balanced | |
| R-0005 | 7.3in scope: rails, VCOM, levels, rate codes, border; bare POF ignored | [1 ex] |
| R-0007 | 7.3in: register table at 0x20 is live; slot k = pixel code k | [1 ex] |
| R-0008 | Refresh length = longest block; offline timing model calibrated | |
| R-0011 | End hold: a slot that drives to the last frame keeps acting until POF (tests without working POF) | [cam] |
| R-0013 | Custom mode ignores the header; frame time per PLL | |
| R-0014 | Forced temperature does not move the set (7.3in) | [1 ex] |
| R-0031 | 7.09in scope: rails, VCOM, gate rails, border, frame ladder | [1 ex] |
| R-0032 | 7.09in: select bit, one table at 0x20, codes 4/7 hold, hang patterns | [1 ex] |
| R-0033 | Row grammar, scrambled byte code, level bits | |
| R-0043 | BWRY: stock band read, header decode, band edges vs thresholds | |
| R-0044 | BWRY scope: rails, Mode 1, VCOM, PLL 08 rate select | [1 ex] |
| R-0045 | BWRY table decode: 6 blocks, Mode-1 block, terminator, DC gate; windowed partial works on 2.9in | [cam] |
| R-0053 | x4 variant (4.2in/1.54in): 536 B wrap | [prov] |
| R-0135 | 7.3in: band map of the 10 stock sets | [1 ex] |
| R-0161 | BWRY MTP store is LZSS; 23/23 read bands byte-exact in the decode | |
| R-0162 | x4: read-back bit-0 skew, plain timing code after repair | |
| R-0186 | 7.3in: byte-true stock replica in custom mode = stock (K 0.08 ... G 0.13) | [1 ex] [cam] |
| R-0187 | 7.3in: one level-0 end frame broke the replica (K 10.8, B 10.7) | [1 ex] [cam] |
| R-0229 | 7.3in: custom-W tint was a set mismatch; end frame / FOPT 00 harmless there | [1 ex] [cam] [prov] |

## Stock behaviour

| R-id | Result | Flags |
|---|---|---|
| R-0046 | Faster PLL on stock: 2.9in floor 9.2 s, about -8 % chroma | [cam] |
| R-0194 | 2.9in stock refresh bimodal 19.7 s / 34.2 s by band | [prov] |
| R-0222 | 7.3in: cutting the supply after each refresh holds ink within +-0.5 L* over 20 cycles | [1 ex] [cam] [prov] |

## S6 fast full

| R-id | Result | Flags |
|---|---|---|
| R-0199 | 7.3in: shake trim to 16.2 s passes the ghost chart; PLL 08 rate codes 5-7 fail; home/mark stable 100 updates | [1 ex] [cam] |
| R-0205 | 7.3in: shake-trim floor 689 frames (16.2 s) over 12 trials; 709 frames (16.7 s) has margin | [1 ex] [cam] |
| R-0231 | 7.3in: set-matched tables remove the W/G offset; F1d median 0.33 | [1 ex] [cam] [prov] |
| R-0201 | 7.09in: F3c (no shake, rate code 7 opening) = stock at 21.7 s, worst 0.69; home/mark 0.51-0.73 s | [1 ex] [cam] |
| R-0204 | 7.09in: G13 17.5 s, worst 2.04; scrub every ~10 | [1 ex] [cam] |

## S6 partial

| R-id | Result | Flags |
|---|---|---|
| R-0020 | 7.3in blue on white 1.23 s, single use | [1 ex] [cam] |
| R-0021 | 7.3in home/mark toggle: limit cycle, drift cause, drive only changed pixels | [1 ex] [cam] |
| R-0208 | One-way partials on the lean path; grey ladder about 4 steps | [1 ex] [cam] [prov] |
| R-0210 | 7.09in one-way partials; R impossible inside the both-rail gate; S/K pairs only reach light blue | [1 ex] [cam] |
| R-0211 | 7.3in in-refresh animation with a clean end | [1 ex] [cam] [prov] |
| R-0215 | Right-align forming tracks | [1 ex] [cam] [prov] |
| R-0220 | G from white, chains, black ticks, ghost charts | [1 ex] [cam] [prov] |
| R-0221 | 7.09in one-way follow-ups and first flashing partial; toggles matter | [1 ex] [cam] |
| R-0223 | 7.09in flashing partial shake-count sweep N2-N8, 20 updates | [1 ex] [cam] |
| R-0224 | 7.3in flashing partial; W top-up cannot lift a dark prior | [1 ex] [cam] [prov] |
| R-0225 | 7.3in L1b (N = 2), 20-update endurance | [1 ex] [cam] [prov] |
| R-0228 | 7.09in transition-aware partial with spare codes | [1 ex] [cam] |
| R-0233 | 7.3in dashboard demo, 10 updates | [1 ex] [cam] |
| R-0234 | 7.3in S3: no shake + no W idle gap = 15.17 s, median 0.40; colour-subset 13.55 s | [1 ex] [cam] |
| R-0235 | 7.3in S3 on shapes, text and 2-8 px detail | [1 ex] [cam] |
| R-0236 | 7.3in short single-colour tracks; B from W in 1.0 s | [1 ex] [cam] |
| R-0239 | 7.3in N1 transition matrix + N2 host-aware partial | [1 ex] [cam] |
| R-0240 | 7.09in G7_N8_mixB 11.5 s works in both bands | [1 ex] [cam] |
| R-0241 | 7.3in G needs its internal dwell; matched G 12.0 s from W | [1 ex] [cam] |
| R-0242 | 7.09in G7_N8_mixB 100 updates, no drift | [1 ex] [cam] |

## JD-BWRY

| R-id | Result | Flags |
|---|---|---|
| R-0198 | 2.9in fast full and windowed partial run; BW partial cannot write white over colour | [cam] |
| R-0200 | 2.9in white kicks, per-target times, resync cadence | [cam] |
| R-0202 | 2.9in rest rule; rested white frontier | [cam] |
| R-0217 | 2.9in lab board black fade tied to the controller power cycle | [cam] [prov] |
| R-0219 | 2.9in BW-only re-score: no full table passes on K/W cells | [cam] |
| R-0237 | 2.9in product unit: lean cycle no fade, BW2_kick3_w10 best, shake no help | [1 ex] [cam] [prov] |
| R-0238 | 2.9in product unit: 100-update endurance on the product cycle | [1 ex] [cam] [prov] |

## More colours

| R-id | Result | Flags |
|---|---|---|
| R-0012 | 7.3in single-pass custom tables: 35 states | [1 ex] [cam] |
| R-0037 | 7.09in two-pass: 31-37 distinct states | [1 ex] [cam] [prov] |
| R-0213 / R-0214 / R-0216 | 7.09in two-pass at split rails: gate fixed, state count unchanged | [1 ex] [cam] |
| R-0050 | BWRY 16-colour: no real green | [spectro] |
| R-0099 / R-0100 | BWRY 16-colour palettes on 7.5in / 4.2in: min pair 5.7 / 7.2 dE00 | [1 ex] [spectro] |
| R-0058 | SSD2677 3.97in: stock only, abandoned | [1 ex] |
| R-0022 | 7.3in two-pass by RST truncation | superseded |

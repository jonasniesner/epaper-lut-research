# Partial and fast update modes

Every partial mode we tried, working and failed. Numbers are from one example panel per model unless stated
([1 ex]) and are camera-relative dE00 against a same-session stock refresh of the same image ([cam]).
Our pass bar: median <= 1.5 and worst <= 3 dE00. R-ids point to [results.md](results.md).

Tables marked **(recipe)** are derived from a stock waveform set and are published only as a recipe
(`recipes/`, `tools/epdlut/recipe.py`). Tables marked **(table)** are in `luts/`.

## Shared rules (S6 class)

- One table per update. Every slot runs for the whole refresh, so **refresh length = longest track**.
- **Right-align forming tracks**: put the level-0 pad *before* the track, so every colour ends on the last frame.
  A finished K, B or G track followed by idle level 0 washes out. Exception: the 7.3in stock G track needs its
  internal level-0 dwell (>= 15 frames); removing it cost 2.2 dE00.
- Unchanged pixels get a hold code: 4 or 7 on the 7.09in (hardwired), an empty slot on the 7.3in.
- **Lean host cycle** (7.3in): no controller init per update, no RST; load the table, write PWR and VDCS each update,
  refresh, POF. Our heavy cycle (init twice + RST) washed held dark ink by +1.25 L* per update.
- Build each table from the stock set the chip runs now (temperature band, [format-s6.md](format-s6.md) 14).
- The border slot must hold a balanced track (we use HOME: K16, 0 x 6, S16).

## S6: working

| Mode | Panel | Refresh | Quality | Where |
|---|---|---|---|---|
| Flashing partial, no shake ("S3") | 7.3in | 15.17 s (stock 22.3 s) | median 0.40 | recipe `flash73` |
| Flashing partial, 2 shakes ("L1b") | 7.3in | 17.6 s | W from dark 0.57; 20 updates median 0.49-0.57 | recipe `flash73 --shake 2 --keep-w-gap` |
| Flashing partial, mixed sets ("G7_N8_mixB") | 7.09in | 11.5 s (stock 30-35 s) | median 0.60-0.74, worst < 1.7 in both bands; 100 updates +0.06 | recipe `mix709` |
| Transition-aware (spare codes) | 7.09in | 9.0-10.3 s | median 0.54-0.82, worst 2.2-2.8 | recipe notes only |
| Host-aware per-update table ("N2") | 7.3in | 8.8 s dashboard, 10.6 s random | changed 1.0-1.4; 100 updates no drift | recipe `track73` + host assembly |
| Colour-subset table | 7.3in | K/Y/B only 13.55 s | = control | recipe `flash73`, unused slots empty |
| Short single-colour tracks | 7.3in | B from W 1.0 s; Y 5.2 s, B 4.9 s from any prior | <= 1.5, prior-specific | recipe `track73 --scale` |
| One-way K tick | 7.3in / 7.09in | 13.2 s / 9.6 s | no fade on the lean path | recipe notes only |
| Sub-second home/mark | 7.3in | 0.93 s | contrast 55-65 dE00; 100 updates stable | table `s73_homemark_H16M10` |
| Sub-second home/mark | 7.09in | 0.51-0.73 s | contrast only 21-27 dE00 | tables `s709_homemark_P1a/P1b` |
| Stock hold codes (region update) | 7.09in | stock length | held region untouched | no table: write 4/7 in the frame |

Details:
- **Flashing partial.** Changed pixels get N balanced S/K toggles, then a right-aligned forming tail; held pixels a hold
  code. On the 7.3in the shake is cosmetic: S3 (no shake, the 205-frame W idle gap removed) beats L1b. On the 7.09in the
  toggles matter (B over an R prior: 13.8 dE00 with none, 2.5 with 8). G7_N8_mixB takes W rows from the cool set and
  K/Y/B from the warm set, stretches the B phases x1.493 to match the stock dynamic-PLL pulse widths, and runs at PLL 04.
  It scored the same in both bands. W top-up tails cannot lift a dark prior; W needs a real forming track.
- **Transition-aware.** In a K/W/Y/B update codes 3 and 6 are free. Use them as "hard B" and "hard K" with a
  stronger erase (S8K8 x 10) inside the idle pad of the shorter tracks. Costs the R and G codes. K-first shakes break blue.
- **Host-aware (N2).** Per update, include only the target colours present, each at the shortest track that passed
  from the priors present. Shortest passing tracks on the 7.3in, set 6, PLL 02, BUSY seconds:

  | from \ to | W | K | Y | R | B | G |
  |---|---|---|---|---|---|---|
  | W | hold | 10.8 | 6.9 | 10.8 | 1.0 | 12.0 |
  | K | 11.5 | hold | 5.2 | 10.8 | 3.9 | 15.3 |
  | Y | 11.5 | 10.8 | hold | 14.6 | 3.9 | 12.0 |
  | R | 11.5 (misses, 1.63) | 10.8 | 6.9 | hold | 7.4 | 12.0 |
  | B | 9.0 | 10.8 | 3.5 | 10.8 | hold | 12.0 |
  | G | 9.0 | 10.8 | 3.5 | 14.6 | 3.9 | hold |

  Host overhead on our rig (about 14 s of streaming and upload) exceeds the fastest refresh: cache tables on the device.
- **Home/mark.** HOME = K16, 0 x 6, S16 (pale yellow on the 7.3in); MARK = S10 K10 (navy). Drive a pixel only when it
  changes. Shorter recipes (H12M6) or faster frame rates drift 2-3x faster.

## S6: partial or limited

| Mode | Result |
|---|---|
| Grey dose ladder (repeated S/K pairs) | about 4 grey steps (7.3in) / 3 (7.09in), then saturates; tables `s73_tick_ladder`, `s709_dose_ladder` [prov] |
| Mark ticks (7.09in) | land light blue, 16-20 dE00 from black; earlier ticks stable; table `s709_mark_ticks` |
| Blue on white, 1.23 s | single use: white drifts 8 -> 17 dE00 over 10 toggles |
| In-refresh animation (7.3in) | a long table can flicker driven regions and still end clean (+10 s) [prov] |

## S6: failed

| Mode | Why |
|---|---|
| Green partial on the 7.09in | cannot be balanced (net charge 4.2 S-frames at 21.9 s) |
| Red partial on the 7.09in | every short tail misses R (1.9-2.3); one-way R works only at 30.5 s (no gain) |
| Fast tracks from white at PLL 04 (7.09in) | none passed; at PLL 08 B 8.5 s and G 23.5 s pass, R fails every tail |
| Half-length K and R tracks (7.3in) | miss; only Y and B work at half length |
| Moving the shake before the pre-pulse | 28 dE00 |
| Truncating a refresh by RST for two-pass mixing | the scan front freezes mid-panel: non-uniform (superseded) |
| Forcing a temperature set by command | does not move the set on the 7.3in |

## JD-BWRY: windowed partial (2.9in)

Sequence per update: partial window (`0x83`), image data, CDI, register LUT (LUT select bit), PON, refresh, POF.

| Table | Refresh | Result |
|---|---|---|
| `bwry29_BW2_kick3_w10` (best) | 1.24 s (DRF) | product unit, lean cycle: K 1.6 / W 2.4 dE00; 100 updates, product cycle: K 3.1 / W 2.9 [prov] |
| `bwry29_K10W10` | 0.24 s | fine for counters; pixels toggled back and forth drift to 12-20 dE00 |
| `bwry29_ky_p1` | 1.1 s | K <-> Y counter; Y stable to 0.9 dE00 but 8.5 from stock yellow |
| `bwry29_B4_shake_n2` | 1.88 s | negative result: a local shake makes white worse (5.6-5.9) |
| `bwry_test_null` | 0.42 s | all 0 V: smoke test; held black within +0.03 L* per cycle |

- **Dead on the 2.66in** (14 hypotheses tried, the refresh returns in 0 ms). Why the 2.9in works is open.
- A BW partial cannot write white over a colour.
- **Fade of black outside the window**: on the product unit +3.5 L* after 20 updates and +7-8 after 100 when the supply
  is cut after every update; one stock refresh restores it. With the lean cycle (one link; RST, init, LUT and PON once,
  then only window, data, CDI and refresh per update) it stayed within +0.9. On our lab board the same panel faded
  +23 L* in 20 updates on one day and +1.6 over 90 the day before (panel state, unexplained).
- The lean cycle keeps the rails up between updates. If you use it, bound it: POF after N updates or T seconds idle,
  and always before sleep.

## JD-BWRY: full-frame fast (failed)

| Table | Result |
|---|---|
| `bwry29_WF_t2e1w1` | best fast white, 13.0 s (Mode-0 K kicks, end on 1 Mode-0 K + 1 Mode-0 W frame); black 8-11 short |
| `bwry29_H_t2f20` | best black of the family (K 2.3-3.6), 17.9 s: no faster than stock |
| `bwry29_x18n_p02` | 9.0 s but cannot clear a Y/R prior (27-30 dE00) |
| `bwry29_ANIM2_n10` | in-refresh animation works, end image 8.7-11 off stock |

No table under 19.8 s passed our 4x4 ghost chart. K over a red prior stays 15-25 dE00. Measure with >= 5 min rest
before both the reference and the test; dense stock refreshing alone darkens yellow-over-red by up to 9 L*.

## Other families

- 2.66in BWRY: booster tail (three commands before PON) gives 14.2 s vs 19.4 s, red -20 % chroma; a short "edit"
  table gives 1.8 s but ghosts.
- UC8176-style 2.6in BW and SSD2677 3.97in: stock only.

## State the sender must hold

A partial or fast update is only correct if whoever builds it knows enough about what is on the glass. "Sender" means
the host or the device, whichever builds the update.

| Mode | What the sender must know |
|---|---|
| Stock full, BWRY16, multi-pass | Nothing per pixel. Multi-pass needs to know that a stock scrub happened right before pass 1. |
| Fast full (S6) | Fast refreshes since the last stock one; the current temperature band. |
| Flashing partial | The previous image (changed/unchanged mask); partials since the last stock refresh; the band at build time. |
| Transition-aware | Each pixel's previous colour (hard transitions go on the spare codes). |
| Host-aware (N2) | Each pixel's previous colour, and the set of transitions in this update (picks the tracks). |
| Short tracks, one-way ticks | The exact previous colour: tracks only work from the prior they were tuned on. |
| Home/mark | Each pixel's state (home or mark) and the toggle count since the last resync. |
| BWRY windowed | The window's previous content; whether it contains colour; update count; whether the link and rails are still up. |

For every mode also keep: whether the last refresh was stock or custom; the last pre-upload temperature read and the
band it picked. Keep this across sleep and power loss. **If it is lost, the next update must be a stock full refresh.**

## Update budget

Partial and fast updates build up error and charge. We suggest an explicit budget:
- **Each panel profile states a budget per mode**: how many such updates are allowed before a stock full refresh.
  Our starting values: S6 fast full about 10; S6 flashing partial 10 (we tested 100 with a stock refresh every 10);
  BWRY windowed about 20 when the supply is cut each update; home/mark by its toggle limit; multi-pass 0 (always scrub
  first). Confirm them per panel.
- **The device keeps the counter**, survives sleep and power loss, and resets it only on a stock full refresh.
  Mixed modes: count per mode or use a weighted shared count.
- **The device reports it**: the budget per mode in its capability read, and the remaining count (plus "next update
  must be full") in every refresh reply.
- **The device enforces it**: when the budget is spent it refuses the partial with a clear status, or turns it into a
  stock full refresh (a per-profile choice). The sender may always force a full refresh early.
- A band change, unknown prior state, or a firmware or table change sets the budget to 0.
- After heavy partial or fast use, do 2-3 stock refreshes before parking the panel.

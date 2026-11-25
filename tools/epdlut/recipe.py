# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""Recipe builder: apply our documented edits to YOUR OWN read-back of your panel's stock waveform set.

We do not publish stock waveform images or tables derived from them. Read the set your panel uses at its current
temperature band yourself (docs/reproduce.md, section 3), save it as an 800 B file, and run a recipe on it.
Outputs are not byte-identical to our lab tables (our builders differed in row packing and balance details);
frame counts and drive structure follow the same edits. Always lint the output (python -m epdlut.lint) and
compare with the expected numbers in recipes/*.json.

    python -m epdlut.recipe replica  SET.bin OUT.bin --pwr-prefix "3F 00"
    python -m epdlut.recipe fast73   SET.bin OUT.bin --row0-drop 5          (F1d; 4 = F1e)
    python -m epdlut.recipe flash73  SET.bin OUT.bin [--shake 2] [--keep-w-gap]   (S3 = defaults, L1b = --shake 2 --keep-w-gap)
    python -m epdlut.recipe track73  SET.bin OUT.bin --colour B --scale 0.5     (N1/N2 track library entry)
    python -m epdlut.recipe fast709  SET4.bin OUT.bin --variant G13             (or F3c)
    python -m epdlut.recipe mix709   SET4.bin SET5.bin OUT.bin                  (G7_N8_mixB)
Each prints the PWR bytes to write with the table, the frame count and the lint result.
"""
from __future__ import annotations

import argparse
import copy
import sys

from . import charge, lint, s6
from .s6 import Phase, Row, pack, pad_rows, rows_frames

# ------------------------------------------------------------------ helpers


def read_set(path: str, index: int | None = None) -> bytes:
    """800 B set image. index: for a multi-set store laid out as consecutive 800 B images that overlap by one
    byte (what we saw on the 7.09in 0x93 read), take bytes [799*index : 799*index + 800]."""
    d = open(path, "rb").read()
    if index is not None:
        d = d[799 * index:799 * index + 800]
    if len(d) < 800:
        raise SystemExit(f"{path}: need 800 bytes, got {len(d)}")
    return d[:800]


def pwr_from_header(e: bytes, prefix: str) -> str:
    """custom mode takes the weak rails from PWR; a replica needs PWR data bytes 2..5 = the set's header codes."""
    codes = s6.decode_table(e).header_rail_codes()
    return prefix.strip() + " " + " ".join(f"{c:02X}" for c in codes)


def volts(pwr: str) -> dict:
    return charge.level_volts(charge.weak_codes_from(b"", pwr, "custom"))


def q_rows(rows: list, V: dict) -> float:
    return sum(V[s6.norm_level(lv)] * n for r in rows for lv, n in r.segments()) / V["S"]


def lead_in(q: float, V: dict, style: str = "strong") -> list:
    """rows that cancel charge q (S-frames): strong = S or K frames, weak = W or WK frames."""
    if abs(q) <= 0.5:
        return []
    if style == "strong":
        lv, w = ("K", 1.0) if q > 0 else ("S", 1.0)
    else:
        lv = "WK" if q > 0 else "W"
        w = abs(V[lv] / V["S"])
    return pack([(lv, int(abs(q) / w))])          # truncated, as in our lab builds (residual |q| < 1)


def is_level0(r: Row) -> bool:
    return all(s6.norm_level(p.level) in ("",) for p in r.phases if p.tp)


def strip_leading_level0(rows: list) -> list:
    rows = list(rows)
    while rows and is_level0(rows[0]):
        rows = rows[1:]
    return rows


def strip_trailing_level0(rows: list) -> list:
    rows = list(rows)
    while rows and is_level0(rows[-1]):
        rows = rows[:-1]
    return rows


def stretch(rows: list, f: float) -> list:
    """scale every phase time (repeat structure kept)."""
    out = copy.deepcopy(rows)
    for r in out:
        for p in r.phases:
            if p.tp:
                p.tp = max(1, round(p.tp * f))
    return out


def shake_prefix(n: int, a: int = 10) -> list:
    return pack([("S", a), ("K", a)] * n) if n else []


HOME = [("K", 16), ("", 6), ("S", 16)]          # our 'home' track (P1), balanced, used for the border slot


def assemble(base: bytes, tracks: dict, lutc=None, right_align: bool = True) -> bytes:
    """tracks {slot: rows}; other slots empty. right_align: pad level 0 BEFORE every track so all end on the last
    frame. lutc None = one level-0 timeline of the table length (fixed PLL); else a [(frames, rate)] schedule."""
    t = s6.decode_table(base)
    L = max(rows_frames(r) for r in tracks.values())
    for k in range(8):
        s6.set_block(t, k, [])
    for k, rows in tracks.items():
        n = rows_frames(rows)
        s6.set_block(t, k, (pad_rows(L - n) if right_align else []) + rows)
    if lutc is None:
        s6.set_block(t, "LUTC", pad_rows(L))
    else:
        s6.set_block(t, "LUTC", s6.lutc_schedule_rows(lutc))
    return s6.finalize(t, last_byte=base[799])


def report(name: str, e: bytes, pwr: str, panel: str, pll: int, codes=None):
    r = lint.lint_s6(e, panel, pwr, pll, codes=codes)
    t = s6.decode_table(e)
    print(f"{name}: {t.refresh_frames()} frames; PWR {pwr}; PLL {pll:02X}; lint {'PASS' if r['pass'] else 'FAIL'}")
    for x in r["fail"] + r["warn"] + r["info"]:
        print("   ", x)
    return r


# ------------------------------------------------------------------ recipes


def check_73_structure(t: s6.Table, row0_drop: int):
    """the 7.3in sets we read: row 0 = pre-pulse (group A) + balanced S/K pairs repeated R_B times (group B);
    row 1 = a short S/K pair repeated R_A times. Refuse other structures."""
    for k in [0, 1, 2, 3, 5, 6]:
        r0, r1 = t.slots[k].rows[0], t.slots[k].rows[1]
        b_lv = {s6.norm_level(p.level) for p in r0.phases[3:] if p.tp}
        a1_lv = {s6.norm_level(p.level) for p in r1.phases[:3] if p.tp}
        if not (b_lv <= {"S", "K"} and r0.RB >= row0_drop and a1_lv <= {"S", "K"} and r1.RA > 1):
            raise SystemExit(f"slot {k}: row structure differs from the sets we edited (see docs/format-s6.md 5); "
                             f"refusing to guess")


def fast73(e: bytes, row0_drop: int = 5) -> bytes:
    """F1d (row0_drop 5) / F1e (4): remove the row-1 shake and `row0_drop` of the row-0 S/K pairs, in every block
    (LUTC included, so the LUTC still covers every slot)."""
    t = s6.decode_table(e)
    check_73_structure(t, row0_drop)
    for k in ["LUTC"] + list(range(8)):
        rows = copy.deepcopy(t.block(k).rows)
        if rows[1].M and rows[1].frames():
            rows[1].RA = 0
        rows[0].RB = max(0, rows[0].RB - row0_drop)
        s6.set_block(t, k, rows)
    out = s6.finalize(t, last_byte=e[799])
    d = s6.decode_table(out)
    if d.lutc.frames() < max(d.slots[k].frames() for k in range(8)):
        raise SystemExit("LUTC shorter than a slot after the trim: unexpected structure")
    return out


def tail(t: s6.Table, k: int, n: int, V: dict, style: str = "strong") -> list:
    """last n forming rows of slot k (rows after row 0, trailing level-0 rows dropped) + a balancing lead-in."""
    forming = strip_trailing_level0(s6.live_rows(t.slots[k].rows[1:]))
    rows = forming[-n:]
    return lead_in(q_rows(rows, V), V, style) + rows


def flash73(e: bytes, shake: int = 0, keep_w_gap: bool = False, w_gap_min: int = 100) -> tuple[bytes, dict]:
    """S3_N0_wgap0 (defaults) / L1b (shake 2, keep_w_gap). From the F1e trim of YOUR set:
    K/Y/R tails = last 3 forming rows, B tail = last 2, each balanced with a strong lead-in; W = the whole F1e W
    slot (slot 1) with its long level-0 dwell row removed (S3) or kept (L1b); optional S10/K10 x shake prefix on
    every changed track; tracks right-aligned. Slot map: K 0, Y 2, R 3, B 5, W 6; border slot 1 = HOME track;
    code 4 empty = hold for unchanged pixels."""
    f1e = fast73(e, 4)
    t = s6.decode_table(f1e)
    pwr = pwr_from_header(e, "3F 00")
    V = volts(pwr)
    tracks = {0: tail(t, 0, 3, V), 2: tail(t, 2, 3, V), 3: tail(t, 3, 3, V), 5: tail(t, 5, 2, V)}
    w = s6.live_rows(t.slots[1].rows)
    if not keep_w_gap:
        w = [r for r in w if not (is_level0(r) and r.frames() >= w_gap_min)]
    tracks[6] = w
    for k in list(tracks):
        tracks[k] = shake_prefix(shake) + tracks[k]
    tracks[1] = pack(HOME)
    return assemble(e, tracks), {"pwr": pwr, "codes": [0, 1, 2, 3, 4, 5, 6]}


def gapless_scaled(rows: list, f: float, V: dict) -> list:
    """N1/N2 track variant: level-0 phases >= 15 frames in non-repeated groups removed; for f < 1 also long single
    drive phases (>= 20 fr) and repeated groups (R >= 3) scaled by f; then rebalanced by nudging the longest
    single drive phase (+-80 frames)."""
    out = copy.deepcopy(rows)
    for r in out:
        if r.M != 1 or not r.frames():
            continue
        for ph, rk in ((r.phases[:3], "RA"), (r.phases[3:], "RB")):
            rep = getattr(r, rk)
            if rep == 1:
                for p in ph:
                    if s6.norm_level(p.level) == "" and p.tp >= 15:
                        p.tp = 0
                    elif f < 1 and s6.norm_level(p.level) != "" and p.tp >= 20:
                        p.tp = max(1, round(p.tp * f))
            elif f < 1 and rep >= 3:
                setattr(r, rk, max(1, round(rep * f)))
    if f < 1 and abs(q_rows(out, V)) > 0.5:
        best = (abs(q_rows(out, V)), None, None)
        for r in out:
            if r.M != 1:
                continue
            for ph, rk in ((r.phases[:3], "RA"), (r.phases[3:], "RB")):
                if getattr(r, rk) != 1:
                    continue
                for i, p in enumerate(ph):
                    if not s6.norm_level(p.level) or not p.tp:
                        continue
                    base, top = p.tp, (127 if i == 2 else 255)
                    for d in range(-min(base - 1, 80), 81):
                        if base + d > top:
                            continue
                        p.tp = base + d
                        q2 = abs(q_rows(out, V))
                        if q2 < best[0] - 1e-9:
                            best = (q2, p, base + d)
                    p.tp = base
        if best[1] is not None:
            best[1].tp = best[2]
    return [r for r in out if r.frames()]


def track73(e: bytes, colour: str, f: float, rail: float = 14.98) -> tuple[bytes, dict]:
    """one N1-style single-colour table: the S3 track of `colour` (G: the F1e G slot), gapless and scaled by f,
    right-aligned in its N2 slot (K0 Y2 R3 B5 W6 G7), border slot 1 = HOME, code 4 hold.
    Balance is computed at `rail` volts for the strong rails (14.98 V = what we measured on the 7.3in)."""
    pwr = pwr_from_header(e, "3F 00")
    V = charge.level_volts(charge.weak_codes_from(b"", pwr, "custom"), rail, -rail)
    s3, _ = flash73(e)
    src = {"K": (s3, 0), "Y": (s3, 2), "R": (s3, 3), "B": (s3, 5), "W": (s3, 6), "G": (fast73(e, 4), 6)}
    slot = {"K": 0, "Y": 2, "R": 3, "B": 5, "W": 6, "G": 7}
    tb, k = src[colour]
    rows = strip_leading_level0(s6.live_rows(s6.decode_table(tb).slots[k].rows))
    rows = gapless_scaled(rows, f, V)
    return assemble(e, {slot[colour]: rows, 1: pack(HOME)}), {"pwr": pwr, "codes": [slot[colour], 1, 4]}


def fold_balance(row0: Row, rest: list, V: dict) -> list:
    """keep the opening row and fold the balance pulse into its first phase (lengthen a same-level lead, shorten
    an opposite one) or add a lead-in row."""
    r = copy.deepcopy(row0)
    q = q_rows([r], V) + q_rows(rest, V)
    if abs(q) <= 0.5:
        return [r]
    lv, n = ("K", round(q)) if q > 0 else ("S", round(-q))
    p0 = r.phases[0]
    if r.M == 1 and r.RA == 1:
        l0 = s6.norm_level(p0.level)
        if l0 == lv and p0.tp + n <= 255:
            p0.tp += n
            return [r]
        if l0 in ("S", "K") and l0 != lv and p0.tp > n:
            p0.tp -= n
            return [r]
    return pack([(lv, n)]) + [r]


def fast709(e: bytes, variant: str = "G13") -> tuple[bytes, dict]:
    """7.09in fast full from YOUR set-4 image. F3c: drop stock rows 1-2 (shake); G13: drop rows 1-3.
    Opening (row 0) rebalanced in place, openings padded to one length, LUTC rate schedule at PLL 08:
    F3c: opening at rate code 7, rest code 2. G13: opening code 7, first 50 % of the colour rows code 3, rest 2."""
    pwr = pwr_from_header(e, "0F 00")
    V = volts(pwr)
    t = s6.decode_table(e)
    colour_from = 3 if variant == "F3c" else 4
    slots = {}
    for k in [0, 1, 2, 3, 5, 6]:
        rows = copy.deepcopy(t.slots[k].rows)
        rest = s6.live_rows(rows[colour_from:])
        slots[k] = (fold_balance(rows[0], rest, V), rest)
    olen = max(rows_frames(o) for o, _ in slots.values())
    tracks = {k: pad_rows(olen - rows_frames(o)) + o + rest for k, (o, rest) in slots.items()}
    L = max(rows_frames(r) for r in tracks.values())
    if variant == "F3c":
        sched = [(olen, 7), (L - olen, 2)]
    else:
        a = round((L - olen) * 0.5)
        sched = [(olen, 7), (a, 3), (L - olen - a, 2)]
    return assemble(e, tracks, lutc=sched, right_align=True), {"pwr": pwr, "pll": 0x08, "codes": [0, 1, 2, 3, 5, 6]}


def two_level_prefix(qn: float, qm: float, Vn: dict, Vm: dict, max_frames: int = 400) -> list:
    """(level, frames) pairs that cancel the charge at nominal (qn) AND measured (qm) rails together (our 7.09in
    'both-rail' gate). Searches level pairs, solves the 2 x 2 system, then nudges the integer counts."""
    import itertools
    best = None
    lv_all = ("S", "K", "SK", "W", "WK", "SW")
    wn = {lv: Vn[lv] / Vn["S"] for lv in lv_all}
    wm = {lv: Vm[lv] / Vm["S"] for lv in lv_all}
    for l1, l2 in itertools.combinations(lv_all, 2):
        det = wn[l1] * wm[l2] - wn[l2] * wm[l1]
        if abs(det) < 1e-4:
            continue
        a0 = (-qn * wm[l2] + qm * wn[l2]) / det
        b0 = (-qm * wn[l1] + qn * wm[l1]) / det
        if a0 < -3 or b0 < -3 or a0 + b0 > max_frames:
            continue
        for da in range(-3, 4):
            for db in range(-3, 4):
                x, y = int(round(a0)) + da, int(round(b0)) + db
                if x < 0 or y < 0:
                    continue
                rn, rm = qn + wn[l1] * x + wn[l2] * y, qm + wm[l1] * x + wm[l2] * y
                res = max(abs(rn), abs(rm))
                sc = (0, x + y, res) if res <= 0.9 else (1, res, x + y)     # inside the gate: shortest wins
                if best is None or sc < best[0]:
                    best = (sc, [(lv, n) for lv, n in ((l1, x), (l2, y)) if n])
    for lv in ("W", "SW", "WK", "SK"):                 # strong + weak pair, scanned (shorter solutions)
        for y in range(1, 241):
            for sl in ("S", "K"):
                x0 = -(qn + wn[lv] * y) / wn[sl]
                for x in (int(x0) - 1, int(x0), int(x0) + 1, int(x0) + 2):
                    if x < 0:
                        continue
                    rn, rm = qn + wn[sl] * x + wn[lv] * y, qm + wm[sl] * x + wm[lv] * y
                    res = max(abs(rn), abs(rm))
                    sc = (0, x + y, res) if res <= 0.9 else (1, res, x + y)
                    if best is None or sc < best[0]:
                        best = (sc, [(a_, n) for a_, n in ((sl, x), (lv, y)) if n])
    return best[1] if best else []


def prefix_row(pre: list, padn: int) -> list:
    """one row: group A = the (up to 2) balancing phases, group B = level-0 padding (B1/B2 up to 255, B3 127)."""
    if not pre and not padn:
        return []
    if any(n > 255 for _, n in pre) or padn > 637:
        return pack(pre + [("", padn)])
    a = [Phase(lv, n) for lv, n in pre] + [Phase("", 0)] * (3 - len(pre))
    b, left = [], padn
    for cap in (255, 255, 127):
        x = min(cap, left)
        b.append(Phase("", x))
        left -= x
    return [Row(1, 1 if pre else 0, 1 if padn else 0, a + b)]


MEAS_709 = (14.82, -14.69)            # strong rails we measured on the 7.09in


def mix709(e4: bytes, e5: bytes, shake: int = 8, a: int = 16, b_stretch: float = 20.08 / 13.45) -> tuple[bytes, dict]:
    """G7_N8_mixB from YOUR set-4 and set-5 images: per changed code, `shake` x (S16 K16) toggles, then the stock
    forming rows 5-7 of that code: W from set 4, K and Y from set 5, B from set 5 with every phase time-stretched
    x1.493 (PLL 08 pulse widths at PLL 04). Each track gets a two-level balancing prefix at the very start (both-rail
    gate), then level-0 padding, then the track, so all tracks end on the last frame.
    Set-5 rails, PLL 04. Codes 4/7 are the hardwired holds on this chip; R and G are not covered."""
    pwr = pwr_from_header(e5, "0F 00")
    wc = charge.weak_codes_from(b"", pwr, "custom")
    Vn, Vm = charge.level_volts(wc), charge.level_volts(wc, *MEAS_709)
    t4, t5 = s6.decode_table(e4), s6.decode_table(e5)

    def form(t, k):
        return [r for i, r in enumerate(copy.deepcopy(t.slots[k].rows)) if i in (5, 6, 7) and r.M and r.frames()]
    src = {0: form(t5, 0), 1: form(t4, 1), 2: form(t5, 2), 5: stretch(form(t5, 5), b_stretch)}
    body = {k: shake_prefix(shake, a) + rows for k, rows in src.items()}
    pre = {k: two_level_prefix(q_rows(b, Vn), q_rows(b, Vm), Vn, Vm) for k, b in body.items()}
    L = max(sum(n for _, n in pre[k]) + rows_frames(b) for k, b in body.items())
    tracks = {}
    for k, b in body.items():
        padn = L - rows_frames(b) - sum(n for _, n in pre[k])
        tracks[k] = prefix_row(pre[k], padn) + b
    return assemble(e5, tracks, right_align=False), {"pwr": pwr, "pll": 0x04, "codes": [0, 1, 2, 5],
                                                     "measured": MEAS_709}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("replica"); p.add_argument("set"); p.add_argument("out"); p.add_argument("--pwr-prefix", default="3F 00")
    p.add_argument("--panel", default="7.3")
    p = sub.add_parser("fast73"); p.add_argument("set"); p.add_argument("out"); p.add_argument("--row0-drop", type=int, default=5)
    p = sub.add_parser("flash73"); p.add_argument("set"); p.add_argument("out"); p.add_argument("--shake", type=int, default=0)
    p.add_argument("--keep-w-gap", action="store_true")
    p = sub.add_parser("track73"); p.add_argument("set"); p.add_argument("out"); p.add_argument("--colour", required=True)
    p.add_argument("--scale", type=float, default=1.0)
    p = sub.add_parser("fast709"); p.add_argument("set"); p.add_argument("out"); p.add_argument("--variant", default="G13", choices=("G13", "F3c"))
    p = sub.add_parser("mix709"); p.add_argument("set4"); p.add_argument("set5"); p.add_argument("out")
    for s in sub.choices.values():
        s.add_argument("--index", type=int, help="set index inside a multi-set read (799 B stride)")
    a = ap.parse_args(argv)
    if a.cmd == "mix709":
        e, meta = mix709(read_set(a.set4, a.index), read_set(a.set5, a.index))
        panel = "7.09"
    else:
        src = read_set(a.set, a.index)
        if a.cmd == "replica":
            e, meta, panel = src, {"pwr": pwr_from_header(src, a.pwr_prefix)}, a.panel
        elif a.cmd == "fast73":
            e, meta, panel = fast73(src, a.row0_drop), {"pwr": pwr_from_header(src, "3F 00")}, "7.3"
        elif a.cmd == "flash73":
            (e, meta), panel = flash73(src, a.shake, a.keep_w_gap), "7.3"
        elif a.cmd == "track73":
            (e, meta), panel = track73(src, a.colour.upper(), a.scale), "7.3"
        else:
            (e, meta), panel = fast709(src, a.variant), "7.09"
    open(a.out, "wb").write(e)
    pll = meta.get("pll", 0x02 if panel == "7.3" else 0x04)
    r = report(a.out, e, meta["pwr"], panel, pll, meta.get("codes"))
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

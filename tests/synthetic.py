# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""Synthetic 'stock-like' S6 sets for the recipe tests. Made up from scratch: they only copy the ROW STRUCTURE
the recipes expect (row 0 = lead pulse + S/K pairs, row 1 = short S/K pairs, then forming rows), not any real
waveform. They are not meant to drive a panel."""
from epdlut import charge, s6
from epdlut.s6 import Phase, Row


def _balance(rows, V):
    q = sum(V[s6.norm_level(lv)] * n for r in rows for lv, n in r.segments()) / V["S"]
    p = rows[0].phases[0]
    lv, n = ("K", round(q)) if q > 0 else ("S", round(-q))
    p.level, p.tp = lv, max(1, n)
    return rows


def fake_set_73(header=bytes([0xFF]) + bytes(s6.enc(c) for c in (0x1E, 0x18, 0x23, 0x3E, 0x0F, 0x03))):
    V = charge.level_volts(dict(zip(charge.WEAK_ORDER, (0x1E, 0x18, 0x23, 0x3E))))
    forming = {0: [("K", 30), ("", 20), ("K", 40)], 1: [("W", 50), ("", 5), ("W", 60)],
               2: [("S", 40), ("", 10), ("SK", 20)], 3: [("SK", 60), ("S", 2), ("SK", 50)],
               5: [("SW", 40), ("K", 3), ("SW", 30)], 6: [("WK", 50), ("", 10), ("WK", 40)]}
    t = s6.blank_table(header)
    L = None
    blocks = {}
    for k, segs in forming.items():
        r0 = Row(1, 1, 11, [Phase("", 1), Phase("", 5), Phase("", 0), Phase("S", 10), Phase("K", 10), Phase("", 0)])
        r1 = Row(1, 40, 0, [Phase("S", 2), Phase("K", 2), Phase("", 0)] + [Phase("", 0)] * 3)
        rest = s6.pack(segs[:2]) + s6.pack(segs[2:]) + ([Row(1, 1, 0, [Phase("", 150)] + [Phase("", 0)] * 5)] if k == 1 else [])
        rows = _balance([r0, r1] + rest, V)
        blocks[k] = rows
    L = max(s6.rows_frames(r) for r in blocks.values())
    for k, rows in blocks.items():
        n = s6.rows_frames(rows)
        rows[-1:] = rows[-1:] + ([Row(1, 1, 0, [Phase("", L - n)] + [Phase("", 0)] * 5)] if L > n else [])
        s6.set_block(t, k, rows)
    lut0 = Row(1, 1, 11, [Phase("", 6), Phase("", 0), Phase("", 0), Phase("", 10), Phase("", 10), Phase("", 0)])
    lut1 = Row(1, 40, 0, [Phase("", 2), Phase("", 2)] + [Phase("", 0)] * 4)
    s6.set_block(t, "LUTC", [lut0, lut1] + s6.pad_rows(L - lut0.frames() - lut1.frames()))
    return s6.finalize(t)


def fake_set_709(shift=0):
    """8 live rows per slot: row 0 lead, rows 1-2 S/K pair rows, row 3 a long S/K row, rows 4-7 forming."""
    codes = (0x1A, 0x24 - shift, 0x30, 0x38)
    header = bytes([0xFF]) + bytes(s6.enc(c) for c in codes + (0x14, 0x08))
    V = charge.level_volts(dict(zip(charge.WEAK_ORDER, codes)))
    lv = {0: "K", 1: "W", 2: "S", 3: "SK", 5: "SW", 6: "WK"}
    t = s6.blank_table(header)
    for k, f in lv.items():
        rows = [Row(1, 1, 0, [Phase("", 1), Phase("", 20), Phase("", 0)] + [Phase("", 0)] * 3),
                Row(1, 20, 0, [Phase("S", 2), Phase("K", 2), Phase("", 0)] + [Phase("", 0)] * 3),
                Row(1, 10, 0, [Phase("S", 4), Phase("K", 4), Phase("", 0)] + [Phase("", 0)] * 3),
                Row(1, 2, 0, [Phase("S", 20), Phase("K", 20), Phase("", 0)] + [Phase("", 0)] * 3),
                Row(1, 1, 0, [Phase(f, 30), Phase("", 10), Phase(f, 20)] + [Phase("", 0)] * 3),
                Row(1, 3, 0, [Phase(f, 8), Phase("", 4), Phase(f, 8)] + [Phase("", 0)] * 3),
                Row(1, 1, 0, [Phase("", 15), Phase(f, 25), Phase("", 0)] + [Phase("", 0)] * 3),
                Row(1, 1, 0, [Phase(f, 12), Phase("", 1), Phase("", 0)] + [Phase("", 0)] * 3)]
        s6.set_block(t, k, _balance(rows, V))
    return s6.finalize(t)

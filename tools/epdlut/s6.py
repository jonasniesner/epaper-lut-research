# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""Codec for S6-class register LUTs (800 B image written to register 0x20).

Layout (our decode, see docs/format-s6.md):
  bytes 0..7    header. Byte 0 = FF; bytes 1..4 = weak-rail codes, byte 5 = VCOM code, byte 6 = rate code
                (all three used only in stock/OTP mode); byte 7 = repeat M of LUTC row 0.
  bytes 8..95   LUTC block (8 rows x 11 B, shared timeline, VCOM bits + frame-rate bits).
  96 + 88 k     slot k drives pixel code k (8 rows x 11 B).
Row (11 B): b0 b1 level bits | b2 b3 b4 phase times A1..A3 | b5 R_A | b6 b7 b8 times B1..B3 | b9 R_B |
            b10 = M of the NEXT row. Row 0's M is the byte before the block.
Time order of a row: M x [ R_A x (A1 A2 A3) then R_B x (B1 B2 B3) ].
Byte coding: active low, scrambled binary:
  value = 1 b4 + 2 b7 + 4 b6 + 8 b1 + 16 b0 + 32 b3 + 64 b2 + 128 b5   (bk = bit k cleared)
  In b4 and b8, bit 5 is the K level bit of phase A3 / B3, so those times are 7-bit (max 127).
Levels: 3 active-low bits per phase, S W K. Levels "", S, W, SW, K, SK, WK; "SWK" (all three) floats.

decode_table() / encode_table() are an exact bijection on bytes.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field

BIT_W = {4: 1, 7: 2, 6: 4, 1: 8, 0: 16, 3: 32, 2: 64, 5: 128}
# (byte, bit) of the S, W, K level bits for each phase
LEVEL_BITS = {"A1": ((0, 2), (0, 5), (0, 3)), "A2": ((0, 1), (0, 0), (0, 6)), "A3": ((0, 4), (0, 7), (4, 5)),
              "B1": ((1, 2), (1, 5), (1, 3)), "B2": ((1, 1), (1, 0), (1, 6)), "B3": ((1, 4), (1, 7), (8, 5))}
TP_BYTE = {"A1": 2, "A2": 3, "A3": 4, "B1": 6, "B2": 7, "B3": 8}
PHASES = ("A1", "A2", "A3", "B1", "B2", "B3")
LEVELS = ("", "S", "W", "SW", "K", "SK", "WK", "SWK")
LUTC_OFF = 8
TABLE_LEN = 800
N_SLOTS = 8


def slot_offset(k: int) -> int:
    return 96 + 88 * k


def val(x: int, skip5: bool = False) -> int:
    """decode one timing / repeat byte."""
    v = (~x) & 0xFF
    return sum(w for b, w in BIT_W.items() if (v >> b) & 1 and not (skip5 and b == 5))


def enc(v: int, skip5: bool = False) -> int:
    """encode one timing / repeat value (bit 5 left at 1 = off when skip5)."""
    if not 0 <= v <= (127 if skip5 else 255):
        raise ValueError(f"value {v} out of range")
    x = 0xFF
    for b, w in BIT_W.items():
        if skip5 and b == 5:
            continue
        if v & w:
            x &= ~(1 << b) & 0xFF
    return x


@dataclass
class Phase:
    level: str
    tp: int


@dataclass
class Row:
    M: int
    RA: int
    RB: int
    phases: list            # 6 Phase: A1 A2 A3 B1 B2 B3

    def frames(self) -> int:
        a = sum(p.tp for p in self.phases[:3])
        b = sum(p.tp for p in self.phases[3:])
        return self.M * (self.RA * a + self.RB * b)

    def segments(self) -> list:
        out = []
        for _ in range(self.M):
            for _ in range(self.RA):
                out += [(p.level, p.tp) for p in self.phases[:3] if p.tp]
            for _ in range(self.RB):
                out += [(p.level, p.tp) for p in self.phases[3:] if p.tp]
        return out


def empty_row() -> Row:
    return Row(0, 0, 0, [Phase("", 0) for _ in range(6)])


@dataclass
class Block:
    rows: list              # 8 Row
    m_in: int               # M of row 0 (decoded from the byte before the block)
    tail_byte: int          # raw byte 87 (= row-0 M source of the next block)

    def segments(self, merge: bool = True) -> list:
        s = [x for r in self.rows for x in r.segments()]
        return merge_segments(s) if merge else s

    def frames(self) -> int:
        return sum(r.frames() for r in self.rows)


@dataclass
class Table:
    header: bytes
    lutc: Block
    slots: list             # 8 Block
    raw: bytes = field(repr=False, default=b"")

    @property
    def sha(self) -> str:
        return hashlib.sha1(self.raw).hexdigest()[:12]

    def block(self, k):
        return self.lutc if k == "LUTC" else self.slots[k]

    def block_frames(self) -> dict:
        d = {"LUTC": self.lutc.frames()}
        d.update({k: s.frames() for k, s in enumerate(self.slots)})
        return d

    def refresh_frames(self) -> int:
        """the refresh lasts as long as the longest block, used or not (measured on the 7.3)."""
        return max(self.block_frames().values())

    def header_rail_codes(self) -> list:
        """header bytes 1..4 decoded: weak-rail codes in PWR order (VSH_LV, VSL_LV, VSH_LV2, VSL_LV2)."""
        return [val(b) for b in self.header[1:5]]


def merge_segments(s: list) -> list:
    out = []
    for lv, n in s:
        if n == 0:
            continue
        if out and out[-1][0] == lv:
            out[-1] = (lv, out[-1][1] + n)
        else:
            out.append((lv, n))
    return out


def norm_level(lv: str, keep_swk: bool = True) -> str:
    if lv == "SWK" or set(lv) == set("SWK"):
        return "SWK" if keep_swk else ""
    return "".join(c for c in "SWK" if c in lv)


# ------------------------------------------------------------------ decode
def _level_raw(b: bytes, ph: str) -> str:
    return "".join(n for n, (by, bit) in zip("SWK", LEVEL_BITS[ph]) if not (b[by] >> bit) & 1)


def decode_block(e: bytes, o: int) -> Block:
    rows = []
    for r in range(8):
        b = e[o + 11 * r:o + 11 * r + 11]
        M = val(e[o + 11 * r - 1])
        ph = [Phase(_level_raw(b, p), val(b[TP_BYTE[p]], skip5=TP_BYTE[p] in (4, 8))) for p in PHASES]
        rows.append(Row(M, val(b[5]), val(b[9]), ph))
    return Block(rows, val(e[o - 1]), e[o + 87])


def decode_table(e: bytes) -> Table:
    e = bytes(e)
    if len(e) != TABLE_LEN:
        raise ValueError(f"S6 table must be {TABLE_LEN} B, got {len(e)}")
    return Table(e[:8], decode_block(e, LUTC_OFF), [decode_block(e, slot_offset(k)) for k in range(N_SLOTS)], e)


def segments(t, k, merge: bool = True, keep_swk: bool = True) -> list:
    """time-ordered (level, frames) of slot k (or 'LUTC')."""
    t = t if isinstance(t, Table) else decode_table(t)
    s = [(norm_level(lv, keep_swk), n) for lv, n in t.block(k).segments(merge=False)]
    return merge_segments(s) if merge else s


# ------------------------------------------------------------------ encode (exact)
def _encode_row(row: Row, next_m_byte: int) -> list:
    b = [0xFF] * 11
    for p, ph in zip(PHASES, row.phases):
        for n, (by, bit) in zip("SWK", LEVEL_BITS[p]):
            if n in ph.level:
                b[by] &= ~(1 << bit) & 0xFF
    for p, ph in zip(PHASES, row.phases):
        i = TP_BYTE[p]
        sk = i in (4, 8)
        x = enc(ph.tp, skip5=sk)
        if sk:
            x = (x & 0xDF) | (b[i] & 0x20)          # keep the K level bit already placed in bit 5
        b[i] = x
    b[5], b[9] = enc(row.RA), enc(row.RB)
    b[10] = next_m_byte
    return b


def encode_block(blk: Block) -> bytes:
    out = []
    for r, row in enumerate(blk.rows):
        nxt = enc(blk.rows[r + 1].M) if r < 7 else blk.tail_byte
        out += _encode_row(row, nxt)
    return bytes(out[:87] + [blk.tail_byte])


def encode_table(t: Table) -> bytes:
    e = bytes(t.header) + encode_block(t.lutc)
    for s in t.slots:
        e += encode_block(s)
    return e


def finalize(t: Table, last_byte: int = 0xFF) -> bytes:
    """re-chain every row-0 M source (header byte 7, each block's byte 87) from the rows, then encode.
    Byte 799 (after slot 7) is a surplus byte; it is set to `last_byte`."""
    hdr = bytearray(t.header)
    hdr[7] = enc(t.lutc.rows[0].M)
    t.header = bytes(hdr)
    blocks = [t.lutc] + list(t.slots)
    for i, blk in enumerate(blocks):
        blk.m_in = blk.rows[0].M
        blk.tail_byte = enc(blocks[i + 1].rows[0].M) if i + 1 < len(blocks) else last_byte
    e = encode_table(t)
    d = decode_table(e)
    if encode_table(d) != e or d.block_frames() != t.block_frames():
        raise AssertionError("finalize: round trip failed")
    return e


# ------------------------------------------------------------------ building rows
def pack(segs: list, M: int = 1) -> list:
    """time-ordered (level, frames) -> canonical rows: up to 6 phases per row (R_A = R_B = 1); a run longer than
    127 frames becomes its own row with R_A repeats (+ remainder)."""
    segs = merge_segments([(norm_level(a), b) for a, b in segs if b])
    rows, pend = [], []

    def flush():
        while pend:
            ph = pend[:6]
            del pend[:6]
            a, b = ph[:3], ph[3:]
            phases = [Phase(lv, n) for lv, n in a] + [Phase("", 0)] * (3 - len(a)) + \
                     [Phase(lv, n) for lv, n in b] + [Phase("", 0)] * (3 - len(b))
            rows.append(Row(M, 1, 1 if b else 0, phases))

    for lv, n in segs:
        while n > 0:
            if n <= 127:
                pend.append((lv, n))
                n = 0
            else:
                flush()
                R = min(255, n // 127)
                rows.append(Row(M, R, 0, [Phase(lv, 127)] + [Phase("", 0)] * 5))
                n -= 127 * R
    flush()
    return rows


def pad_rows(n: int) -> list:
    """level-0 rows lasting n frames (A1 time up to 255 per row)."""
    out = []
    while n > 0:
        a = min(n, 250)
        out.append(Row(1, 1, 0, [Phase("", a)] + [Phase("", 0)] * 5))
        n -= a
    return out


def live_rows(blk_or_rows) -> list:
    rows = blk_or_rows.rows if isinstance(blk_or_rows, Block) else blk_or_rows
    return [copy.deepcopy(r) for r in rows if r.M and r.frames()]


def rows_frames(rows: list) -> int:
    return sum(r.frames() for r in rows)


def set_block(t: Table, k, rows: list) -> None:
    rows = live_rows(rows)
    if len(rows) > 8:
        raise ValueError(f"block {k}: {len(rows)} rows > 8")
    t.block(k).rows = rows + [empty_row() for _ in range(8 - len(rows))]


def blank_table(header7: bytes = b"\xff" * 7) -> Table:
    """all blocks empty (every byte FF except the given header bytes)."""
    e = bytearray(b"\xff" * TABLE_LEN)
    e[:7] = header7[:7]
    return decode_table(bytes(e))


# ------------------------------------------------------------------ LUTC (VCOM + frame-rate bits)
# Per group byte (b0 for A, b1 for B), the three phases carry a (lo, hi) VCOM bit pair:
#   phase 1 = (bit 2, bit 5), phase 2 = (bit 0, bit 3), phase 3 = (bit 6, bit 1).
# Rate code (PLL with bit 3 set): bit 0 of the code = b0 bit 4, bit 1 = b0 bit 7, bit 2 = b1 bit 4.
LUTC_VCOM_BITS = ((2, 5), (0, 3), (6, 1))
RATE_BITS = ((0, 4, 1), (0, 7, 2), (1, 4, 4))      # (byte, bit, weight)


def lutc_rows_raw(e: bytes) -> list:
    """per LUTC row: dict(M, RA, RB, rate, A/B = [(vcom_state, tp)])."""
    out = []
    for r in range(8):
        o = LUTC_OFF + 11 * r
        b = e[o:o + 11]

        def grp(x, tps):
            st = []
            for (lo, hi), tp in zip(LUTC_VCOM_BITS, tps):
                l_, h_ = not (x >> lo) & 1, not (x >> hi) & 1
                st.append(("both" if l_ and h_ else "lo" if l_ else "hi" if h_ else "0", tp))
            return st
        ta = [val(b[2]), val(b[3]), val(b[4], skip5=True)]
        tb = [val(b[6]), val(b[7]), val(b[8], skip5=True)]
        rate = sum(w for by, bit, w in RATE_BITS if not (b[by] >> bit) & 1)
        out.append(dict(row=r, M=val(e[o - 1]), RA=val(b[5]), RB=val(b[9]), rate=rate, A=grp(b[0], ta), B=grp(b[1], tb)))
    return out


def lutc_timeline(e: bytes) -> list:
    """time-ordered (vcom_state, rate_code, frames) for the LUTC."""
    seq = []
    for r in lutc_rows_raw(e):
        for _ in range(r["M"]):
            for _ in range(r["RA"]):
                seq += [(s, r["rate"], tp) for s, tp in r["A"] if tp]
            for _ in range(r["RB"]):
                seq += [(s, r["rate"], tp) for s, tp in r["B"] if tp]
    out = []
    for s, rt, n in seq:
        if out and out[-1][0] == s and out[-1][1] == rt:
            out[-1] = (s, rt, out[-1][2] + n)
        else:
            out.append((s, rt, n))
    return out


def lutc_swing_bits(e: bytes) -> list:
    """(row, byte, value) for every LUTC row with a VCOM lo/hi bit cleared (= a VCOM swing)."""
    bad = []
    for r in range(8):
        o = LUTC_OFF + 11 * r
        for i, mask in ((0, 0x6F), (1, 0xEF)):     # all bits except the rate bits must stay set
            if (e[o + i] | (~mask & 0xFF)) != 0xFF:
                bad.append((r, i, e[o + i]))
    return bad


def lutc_schedule_rows(sched: list) -> list:
    """sched = [(frames, rate_code), ...] -> LUTC rows with no VCOM swing (level bits only carry the rate)."""
    rows = []
    for n, rate in sched:
        lv_a = ("S" if rate & 1 else "") + ("W" if rate & 2 else "")    # b0 bit 4 = A3 'S', b0 bit 7 = A3 'W'
        lv_b = "S" if rate & 4 else ""                                    # b1 bit 4 = B3 'S'
        q, r = divmod(n, 100)
        for reps, length in ((q, 100), (1 if r else 0, r)):
            if reps:
                rows.append(Row(1, reps, 0, [Phase("", length), Phase("", 0), Phase(lv_a, 0),
                                             Phase("", 0), Phase("", 0), Phase(lv_b, 0)]))
    if len(rows) > 8:
        raise ValueError("LUTC schedule needs more than 8 rows")
    return rows


def describe(e: bytes, name: str = "") -> str:
    """human-readable decode used for the luts/*.txt files."""
    t = decode_table(e)
    L = [f"# {name}  S6 800 B  sha1 {hashlib.sha1(e).hexdigest()}",
         f"header {e[:8].hex(' ')}",
         f"block frames {t.block_frames()}  refresh = {t.refresh_frames()} frames"]
    tl = lutc_timeline(e)
    L.append(f"LUTC (vcom, rate, frames): {tl if tl else 'empty'}")
    for k in range(N_SLOTS):
        s = segments(t, k)
        if s:
            L.append(f"slot {k}: " + " ".join(f"{lv or '0'}x{n}" for lv, n in s) + f"   ({sum(n for _, n in s)} fr)")
            for i, r in enumerate(t.slots[k].rows):
                if r.M and r.frames():
                    a = " ".join(f"{p.level or '0'}{p.tp}" for p in r.phases[:3] if p.tp)
                    b = " ".join(f"{p.level or '0'}{p.tp}" for p in r.phases[3:] if p.tp)
                    L.append(f"    row {i}: M={r.M} [RA={r.RA} x ({a})] [RB={r.RB} x ({b})]")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        print(describe(open(f, "rb").read(), f))

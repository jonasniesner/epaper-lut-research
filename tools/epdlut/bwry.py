# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""Codec, builder and DC models for JD-BWRY-class register LUTs (535 B image written to register 0x20).

Layout (our decode, see docs/format-bwry.md):
  bytes 0..6   header: VGHL, VSPL_0, rail byte 2, rail byte 3, rail byte 4, VCOM, PLL (plain binary).
               The controller ignores these in the 0x20 stream; our host code uses them as the analog
               parameters it writes to the registers.
  byte 7       M of block 0 row 0.
  8 + 88 k     block k, k = 0..5, rows in the same 11 B grammar and timing code as S6.
               block 0 = LUTC (VCOM), blocks 1..4 = pixel codes 0..3, block 5 = per-frame Mode-1 select.
  The image stops at byte 534: block 5's byte 87 does not exist (decoded with a virtual pad byte EF).
Physical levels: per phase a 2-bit field in the level byte (b0 for group A, b1 for group B), active low:
  phase 1 = (hi bit 5, lo bit 2), phase 2 = (hi bit 3, lo bit 0), phase 3 = (hi bit 1, lo bit 6),
  field 4 = (bit 7, bit 4) (unused in pixel blocks).
  hi only = "W" (VSN, drives white), lo only = "K" (VSP, drives black), both = "L" (weak black), none = "0".
A row with M = 0 ends a block (terminator); a block using all 8 rows ends after row 7. A block with spare rows
but no M = 0 row did not finish (BUSY stayed busy for > 60 s on a 25-frame table).
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass

from .s6 import enc, val

LEN = 535
PAD = 0xEF
NBLK = 6
FIELDS = ((5, 2), (3, 0), (1, 6))          # (hi, lo) bit per phase
F4 = (7, 4)
NAME = {(0, 0): "0", (1, 0): "W", (0, 1): "K", (1, 1): "L"}
CODE = {v: k for k, v in NAME.items()}
HEADER_FIELDS = ("VGHL", "VSPL_0", "RAIL_2", "RAIL_3", "RAIL_4", "VCOM", "PLL")


def blk_off(k: int) -> int:
    return 8 + 88 * k


@dataclass
class BRow:
    M: int
    RA: int
    RB: int
    A: list          # 3 (level, tp)
    B: list          # 3 (level, tp)
    f4: tuple = ("0", "0")       # field 4 of b0 / b1, kept for an exact round trip
    x5: tuple = (1, 1)           # raw bit 5 of b4 / b8 (not a timing bit), kept for an exact round trip

    def frames(self) -> int:
        return self.M * (self.RA * sum(n for _, n in self.A) + self.RB * sum(n for _, n in self.B))

    def segments(self) -> list:
        s = []
        for _ in range(self.M):
            for _ in range(self.RA):
                s += [x for x in self.A if x[1]]
            for _ in range(self.RB):
                s += [x for x in self.B if x[1]]
        return s


def zero_row(n: int = 0, M: int = 0) -> BRow:
    return BRow(M, 1 if n else 0, 0, [("0", n), ("0", 0), ("0", 0)], [("0", 0)] * 3)


@dataclass
class BBlock:
    rows: list       # 8 BRow
    tail: int        # raw byte 87 (row-0 M source of the next block)

    def frames(self) -> int:
        total = 0
        for r in self.rows:
            if r.M == 0:
                break                      # terminator
            total += r.frames()
        return total

    def segments(self) -> list:
        s = []
        for r in self.rows:
            if r.M == 0:
                break
            s += r.segments()
        return merge(s)

    def terminated(self) -> bool:
        """an M = 0 row ends the block; a block that uses all 8 rows ends after row 7 (seen in stock colour waves)."""
        return any(r.M == 0 for r in self.rows) or all(r.M for r in self.rows)


@dataclass
class Table535:
    header: bytes    # 8 B (7 header + byte 7)
    blocks: list     # 6 BBlock
    raw: bytes = b""

    def frames(self) -> list:
        return [b.frames() for b in self.blocks]

    def duration_frames(self) -> int:
        return max(self.frames())

    def per_frame(self, k: int) -> list:
        return [lv for lv, n in self.blocks[k].segments() for _ in range(n)]


def merge(s: list) -> list:
    out = []
    for lv, n in s:
        if not n:
            continue
        if out and out[-1][0] == lv:
            out[-1] = (lv, out[-1][1] + n)
        else:
            out.append((lv, n))
    return out


def _fields(x: int) -> list:
    return [NAME[(int(not (x >> hi) & 1), int(not (x >> lo) & 1))] for hi, lo in FIELDS]


def decode(e: bytes) -> Table535:
    e = bytes(e)
    if len(e) != LEN:
        raise ValueError(f"BWRY table must be {LEN} B, got {len(e)}")
    p = e + bytes([PAD])
    blocks = []
    for k in range(NBLK):
        o = blk_off(k)
        rows = []
        for r in range(8):
            b = p[o + 11 * r:o + 11 * r + 11]
            M = val(p[o + 11 * r - 1])
            ta = [val(b[2]), val(b[3]), val(b[4], skip5=True)]
            tb = [val(b[6]), val(b[7]), val(b[8], skip5=True)]
            la, lb = _fields(b[0]), _fields(b[1])
            f4 = (NAME[(int(not (b[0] >> F4[0]) & 1), int(not (b[0] >> F4[1]) & 1))],
                  NAME[(int(not (b[1] >> F4[0]) & 1), int(not (b[1] >> F4[1]) & 1))])
            rows.append(BRow(M, val(b[5]), val(b[9]), list(zip(la, ta)), list(zip(lb, tb)), f4,
                             ((b[4] >> 5) & 1, (b[8] >> 5) & 1)))
        blocks.append(BBlock(rows, p[o + 87]))
    return Table535(p[:8], blocks, e)


def _lvbyte(levels: list, f4: str) -> int:
    x = 0xFF
    for (hi, lo), lv in zip(FIELDS, levels):
        h, l_ = CODE[lv]
        if h:
            x &= ~(1 << hi) & 0xFF
        if l_:
            x &= ~(1 << lo) & 0xFF
    h, l_ = CODE[f4]
    if h:
        x &= ~(1 << F4[0]) & 0xFF
    if l_:
        x &= ~(1 << F4[1]) & 0xFF
    return x


def _row_bytes(r: BRow, nxt: int) -> list:
    b = [0xFF] * 11
    b[0] = _lvbyte([lv for lv, _ in r.A], r.f4[0])
    b[1] = _lvbyte([lv for lv, _ in r.B], r.f4[1])
    b[2], b[3] = enc(r.A[0][1]), enc(r.A[1][1])
    b[4] = (enc(r.A[2][1], skip5=True) & 0xDF) | (r.x5[0] << 5)
    b[5] = enc(r.RA)
    b[6], b[7] = enc(r.B[0][1]), enc(r.B[1][1])
    b[8] = (enc(r.B[2][1], skip5=True) & 0xDF) | (r.x5[1] << 5)
    b[9] = enc(r.RB)
    b[10] = nxt
    return b


def encode(t: Table535) -> bytes:
    out = bytes(t.header)
    for blk in t.blocks:
        bb = []
        for r, row in enumerate(blk.rows):
            nxt = enc(blk.rows[r + 1].M) if r < 7 else blk.tail
            bb += _row_bytes(row, nxt)
        out += bytes(bb[:87] + [blk.tail])
    if len(out) != LEN + 1:
        raise AssertionError(len(out))
    return out[:LEN]


# ------------------------------------------------------------------ builder
def pack(segs: list) -> list:
    """time-ordered (level, frames), level in 0 W K L -> rows (6 phases per row, runs > 127 get R_A repeats)."""
    segs = merge([(lv, n) for lv, n in segs if n])
    rows, pend = [], []

    def flush():
        while pend:
            ph = pend[:6]
            del pend[:6]
            a = ph[:3] + [("0", 0)] * (3 - len(ph[:3]))
            b = ph[3:] + [("0", 0)] * (3 - len(ph[3:]))
            rows.append(BRow(1, 1, 1 if ph[3:] else 0, a, b))

    for lv, n in segs:
        while n > 0:
            if n <= 127:
                pend.append((lv, n))
                n = 0
            else:
                flush()
                R = min(255, n // 127)
                rows.append(BRow(1, R, 0, [(lv, 127), ("0", 0), ("0", 0)], [("0", 0)] * 3))
                n -= 127 * R
    flush()
    return rows


def build(header7: bytes, block_segs: dict, end_frames: int = 1) -> bytes:
    """535 B table from {block index: [(level, frames), ...]}.
    Every block is padded with 0 V to one common length (+ end_frames of 0 V), unused blocks are 0 V for the whole
    length (stock never has an empty block), and every block gets an M = 0 terminator row."""
    dur = max(sum(n for _, n in v) for v in block_segs.values()) + end_frames
    hdr = bytes(header7[:7]) + bytes([enc(1)])
    blocks = []
    for k in range(NBLK):
        segs = list(block_segs.get(k, []))
        rest = dur - sum(n for _, n in segs)
        segs.append(("0", rest))
        rows = pack(segs)
        if len(rows) > 7:
            raise ValueError(f"block {k}: needs {len(rows)} rows, max 7 + terminator")
        rows += [zero_row() for _ in range(8 - len(rows))]
        blocks.append(BBlock(rows, PAD))
    for k in range(NBLK - 1):                          # chain: byte 87 = next block's row-0 M
        blocks[k].tail = enc(blocks[k + 1].rows[0].M)
    hdr = bytes(hdr[:7]) + bytes([enc(blocks[0].rows[0].M)])
    e = encode(Table535(hdr, blocks))
    d = decode(e)
    assert d.frames() == [dur] * NBLK, d.frames()
    assert all(b.terminated() for b in d.blocks)
    return e


# ------------------------------------------------------------------ x4 read repair
def x4_bit0_repair(a: bytes) -> bytes:
    """x4 parts (4.2in / 1.54in): a register read-back has bit 0 of each byte skewed by one byte position.
    Repair: t[i] = (a[i] & 0xFE) | (a[i-1] & 1). (Applies to read-backs only, never to uploads.)"""
    a = bytes(a)
    return bytes([a[0]] + [(a[i] & 0xFE) | (a[i - 1] & 1) for i in range(1, len(a))])   # byte 0: bit 0 unknown, kept


# ------------------------------------------------------------------ DC models
def rail_v(code: int) -> float:
    """measured rail law on the 2.9in (scope): |V| = 2.975 + 0.0991 x code (about 3.0 + 0.1 x code)."""
    return 2.975 + 0.0991 * code


def dc(e: bytes, model: str = "B", vsn1: float | None = None) -> list:
    """net V x frames per pixel code 0..3.
    Mode of a frame: Mode 1 when block 5 drives K or L in that frame (its lo bit), else Mode 0.
    model B ('Mode-aware'; balances all stock bands we decoded):
        Mode 0: K +15, W -15, L +V(byte 1); Mode 1: K +15, W -V(byte 2), L +V(byte 4)
    model A (scope field order): Mode 1: K +V(byte 2), W -V(byte 3), L +V(byte 4); Mode 0 as B.
    vsn1: override the Mode-1 W rail in volts."""
    t = decode(e)
    h = t.header
    m5 = t.per_frame(5)
    out = []
    for k in range(1, 5):
        net = 0.0
        for i, lv in enumerate(t.per_frame(k)):
            if lv == "0":
                continue
            mode1 = i < len(m5) and m5[i] in ("K", "L")
            if not mode1:
                v = {"K": 15.0, "W": -15.0, "L": rail_v(h[1])}[lv]
            elif model == "B":
                v = {"K": 15.0, "W": -(vsn1 or rail_v(h[2])), "L": rail_v(h[4])}[lv]
            else:
                v = {"K": rail_v(h[2]), "W": -(vsn1 or rail_v(h[3])), "L": rail_v(h[4])}[lv]
            net += v
        out.append(round(net, 1))
    return out


FRAME_MS = {0x02: 19.97, 0x07: 8.38}                    # fixed PLL codes measured on the 2.9in
DYN_MS = [79.9, 40.0, 20.1, 15.5, 13.6, 12.0, 10.1, 8.5]  # PLL 08: 3-bit rate code from the LUTC


def describe(e: bytes, name: str = "") -> str:
    t = decode(e)
    L = [f"# {name}  JD-BWRY 535 B  sha1 {hashlib.sha1(e).hexdigest()}",
         "header " + " ".join(f"{f}={b:02X}" for f, b in zip(HEADER_FIELDS, t.header[:7])),
         f"block frames {t.frames()} -> refresh {t.duration_frames()} frames",
         f"DC per code (V x frames) model A {dc(e, 'A')}  model B {dc(e, 'B')}"]
    names = ["LUTC", "code 0", "code 1", "code 2", "code 3", "Mode-1 select"]
    for k in range(NBLK):
        s = t.blocks[k].segments()
        L.append(f"block {k} ({names[k]}): " + " ".join(f"{lv}x{n}" for lv, n in s) +
                 f"   terminator {'yes' if t.blocks[k].terminated() else 'NO'}")
    return "\n".join(L)


def copy_table(t: Table535) -> Table535:
    return copy.deepcopy(t)


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        print(describe(open(f, "rb").read(), f))

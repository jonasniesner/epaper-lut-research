# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""LZSS codec in the token format we found in the JD-BWRY MTP waveform store (docs/format-bwry.md, section 9).

Bitstream, LSB-first within each byte. Token: 1 flag bit.
  flag 0 -> literal: 8 bits (LSB-first).
  flag 1 -> back-reference: length (8 bits) + 3, then distance (14 bits) back into the output.
The same codec works as a compact store for our own tables (docs/compression.md).

    python -m epdlut.lzss decode STORE.bin --byte 0x11 --bit 22 [--split 535 --skip 2 --out DIR]
    python -m epdlut.lzss encode TABLE.bin OUT.lzss
"""
from __future__ import annotations

import argparse
from pathlib import Path

LEN_BITS, DIST_BITS, MIN_MATCH = 8, 14, 3


class BitReader:
    def __init__(self, data: bytes, bitpos: int = 0):
        self.d, self.p = data, bitpos

    def left(self) -> int:
        return len(self.d) * 8 - self.p

    def read(self, n: int) -> int:
        v = 0
        for i in range(n):
            byte = self.d[(self.p + i) >> 3]
            v |= ((byte >> ((self.p + i) & 7)) & 1) << i
        self.p += n
        return v


class BitWriter:
    def __init__(self):
        self.bits = []

    def write(self, v: int, n: int):
        self.bits += [(v >> i) & 1 for i in range(n)]

    def getvalue(self) -> bytes:
        out = bytearray((len(self.bits) + 7) // 8)
        for i, b in enumerate(self.bits):
            out[i >> 3] |= b << (i & 7)
        return bytes(out)


def decode(data: bytes, bitpos: int = 0, max_out: int = 1 << 20, n_out: int | None = None) -> tuple[bytes, int]:
    """returns (output, end bit position). Stops at n_out bytes, at the end of data, or at an invalid distance."""
    r = BitReader(data, bitpos)
    out = bytearray()
    while r.left() >= 9 and len(out) < (n_out or max_out):
        p0 = r.p
        if r.read(1) == 0:
            out.append(r.read(8))
            continue
        if r.left() < LEN_BITS + DIST_BITS:
            r.p = p0
            break
        n = r.read(LEN_BITS) + MIN_MATCH
        d = r.read(DIST_BITS)
        if d == 0 or d > len(out):
            r.p = p0
            break
        for _ in range(n):
            out.append(out[-d])
    if n_out is not None:
        out = out[:n_out]
    return bytes(out), r.p


def encode(data: bytes) -> bytes:
    """greedy encoder (longest match in the 16383-byte window). Output decodes with decode(..., n_out=len(data))."""
    w = BitWriter()
    i, L = 0, len(data)
    win = (1 << DIST_BITS) - 1
    maxm = (1 << LEN_BITS) - 1 + MIN_MATCH
    while i < L:
        best, bd = 0, 0
        for s in range(max(0, i - win), i):
            m = 0
            while i + m < L and data[s + m] == data[i + m] and m < maxm:
                m += 1
            if m > best:
                best, bd = m, i - s
        if best >= MIN_MATCH:
            w.write(1, 1)
            w.write(best - MIN_MATCH, LEN_BITS)
            w.write(bd, DIST_BITS)
            i += best
        else:
            w.write(0, 1)
            w.write(data[i], 8)
            i += 1
    return w.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description="LZSS (len8+3 / dist14, LSB-first) decode/encode")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decode")
    d.add_argument("file")
    d.add_argument("--byte", type=lambda x: int(x, 0), default=0, help="byte offset of the bitstream")
    d.add_argument("--bit", type=int, default=0, help="extra bit offset counted from --byte")
    d.add_argument("--skip", type=int, default=0, help="output bytes before the first table")
    d.add_argument("--split", type=int, default=0, help="split the output into tables of this size")
    d.add_argument("--out")
    e = sub.add_parser("encode")
    e.add_argument("file")
    e.add_argument("out")
    a = ap.parse_args(argv)
    if a.cmd == "encode":
        src = Path(a.file).read_bytes()
        z = encode(src)
        Path(a.out).write_bytes(z)
        print(f"{len(src)} -> {len(z)} B")
        return
    raw = Path(a.file).read_bytes()
    out, end = decode(raw, a.byte * 8 + a.bit)
    print(f"decoded {len(out)} B, stream ended at byte {end // 8} bit {end % 8}")
    if a.split and a.out:
        o = Path(a.out)
        o.mkdir(parents=True, exist_ok=True)
        body = out[a.skip:]
        for i in range(len(body) // a.split):
            (o / f"table_{i:02d}.bin").write_bytes(body[i * a.split:(i + 1) * a.split])
        print(f"wrote {len(body) // a.split} tables of {a.split} B to {o} (coldest band first on the panels we read)")


if __name__ == "__main__":
    main()

# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""Measure how well register LUTs compress (docs/compression.md).

    python -m epdlut.compress luts/s6 luts/bwry [--dict REFERENCE.bin]
Per size group (800 B / 535 B): median compressed size for raw deflate, zlib, LZMA2 (raw), our LZSS
(len8/dist14, the MTP format), PackBits and byte RLE. --dict: also raw deflate with REFERENCE as preset dictionary
(use your own stock set read-back; tables derived from a stock set shrink 2-4x more).
"""
from __future__ import annotations

import argparse
import hashlib
import lzma
import statistics as st
import zlib
from pathlib import Path

from . import lzss


def rle(b: bytes) -> int:
    n, i = 0, 0
    while i < len(b):
        j = i
        while j < len(b) and b[j] == b[i] and j - i < 255:
            j += 1
        n += 2
        i = j
    return n


def packbits(b: bytes) -> int:
    n, i, L = 0, 0, len(b)
    while i < L:
        j = i
        while j + 1 < L and b[j + 1] == b[i] and j - i < 127:
            j += 1
        if j - i >= 2:
            n += 2
            i = j + 1
        else:
            k = i
            while k < L and k - i < 128 and not (k + 2 < L and b[k] == b[k + 1] == b[k + 2]):
                k += 1
            k = max(k, i + 1)
            n += 1 + (k - i)
            i = k
    return n


def deflate_raw(b: bytes, zdict: bytes | None = None) -> int:
    c = zlib.compressobj(9, zlib.DEFLATED, -15, zdict=zdict) if zdict else zlib.compressobj(9, zlib.DEFLATED, -15)
    return len(c.compress(b) + c.flush())


def sizes(b: bytes, zdict: bytes | None = None) -> dict:
    d = {"deflate_raw": deflate_raw(b), "zlib9": len(zlib.compress(b, 9)),
         "lzma2_raw": len(lzma.compress(b, format=lzma.FORMAT_RAW, filters=[{"id": lzma.FILTER_LZMA2, "preset": 9}])),
         "lzss_8_14": len(lzss.encode(b)), "packbits": packbits(b), "byte_rle": rle(b)}
    if zdict:
        d["deflate_dict"] = deflate_raw(b, zdict)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--dict")
    a = ap.parse_args(argv)
    zd = Path(a.dict).read_bytes() if a.dict else None
    groups = {}
    for d in a.dirs:
        for f in sorted(Path(d).rglob("*.bin")):
            b = f.read_bytes()
            groups.setdefault(len(b), {})[hashlib.md5(b).hexdigest()] = (f.name, b)
    for size, items in sorted(groups.items()):
        res = {}
        for name, b in items.values():
            for k, v in sizes(b, zd if size == len(zd or b"") else None).items():
                res.setdefault(k, []).append(v)
        print(f"{size} B tables, n = {len(items)} unique")
        for k, v in res.items():
            m = st.median(v)
            print(f"   {k:12s} median {m:6.0f} B  ratio {size / m:4.1f}x  (min {min(v)}, max {max(v)})")


if __name__ == "__main__":
    main()

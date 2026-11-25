# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""lutlint: static checks for register LUTs before upload. Exit code 0 = pass, 1 = fail.

S6 (800 B) rules:
  L0 length      every block <= 20000 frames (corrupt images decode to huge lengths)
  L1 longest     refresh = longest block (used or not); WARN if the longest block is an unused slot;
                 FAIL if --busy-timeout is shorter than the predicted refresh
  L3 DC          |q_sf| <= 1 per used and border slot (nominal rails; also measured rails if --vsh/--vsl given)
  L4 end level   INFO/WARN: a used slot that drives to the last frame holds that level until POF
  L5 PWR         custom mode needs explicit PWR bytes (custom mode takes the weak rails from PWR, not the header)
  L6 border      the slot selected by CDI bits 7-5 must have frames
  L7 hang        no 8 x 00 run anywhere, no all-zero 8 B header (hangs the 7.09in class with the LUT select bit)
  L8 byte gate   optional (--forbid 00,01,11): bytes some upload paths refuse
  VCOM           LUTC VCOM swing bits: FAIL unless --allow-vcom-swing
JD-BWRY (535 B) rules:
  B0 round trip, B1 all blocks equal length, B2 every block ends (an M = 0 row, or all 8 rows used),
  B3 LUTC (block 0) carries no VCOM drive, B4 DC per code |net| <= 15 V x frames under model A and model B
  (--pair: |code0 + code1| <= 15 for differential partials), B5 header inside --envelope (JSON) if given.
Sequence rule (--seq FILE, one step per line: RST | INIT | TSC | UPLOAD | REFRESH | POF):
  S1 an UPLOAD must be followed by its REFRESH with no RST/INIT/TSC in between (a TSC read reloads 0x20 on the
     7.09in class; RST reloads the OTP table on every panel); S2 every REFRESH is followed by POF.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import bwry, charge, s6, timing

MAX_FRAMES = 20000


def lint_s6(e: bytes, panel: str = "7.3", pwr=None, pll: int = 0x02, cdi=None, codes=None, busy_timeout=None,
            measured=None, forbid=(), allow_vcom_swing=False) -> dict:
    F, W, I = [], [], []
    prof = timing.PROFILES[panel]
    t = s6.decode_table(e)
    bf = t.block_frames()
    if max(bf.values()) > MAX_FRAMES:
        F.append(f"L0 block length {max(bf.values())} > {MAX_FRAMES}: corrupt or mis-decoded table")
        return {"pass": False, "fail": F, "warn": W, "info": I}
    cdi = prof.cdi_default if cdi is None else cdi
    if codes is None:
        codes = [k for k in range(8) if k not in prof.hold_codes]
    longest = max(bf.values())
    who = [k for k, v in bf.items() if v == longest]
    vbd = (cdi >> 5) & 7
    border = None if vbd == 7 else vbd
    if not any(k == "LUTC" or k in codes or k == border for k in who):
        W.append(f"L1 the longest block {who} ({longest} fr) is unused: the refresh lasts it anyway")
    rs = timing.refresh_s(e, panel, pll)
    I.append(f"L1 refresh {longest} frames = {rs} s at PLL {pll:02X}")
    if busy_timeout is not None and rs and busy_timeout < rs:
        F.append(f"L1 BUSY timeout {busy_timeout} s < predicted refresh {rs} s")
    if pwr is None:
        F.append("L5 no PWR given: custom mode runs on the PWR rails; pass the bytes the firmware writes")
    else:
        g = charge.gate(e, pwr, "custom", codes, cdi, prof.hold_codes, 1.0, measured,
                        allow_end_driven=True, allow_vcom_swing=allow_vcom_swing)
        F += ["L3 " + x if "swing" not in x else "VCOM " + x for x in g["fail"]]
        for x in g["warn"]:
            (I if "end hold" in x else W).append(("L4 " if "end hold" in x else "L3 ") + x)
        I.append(f"L3 q_sf {g['q_sf']}")
    if border is not None and bf[border] == 0:
        F.append(f"L6 border slot {border} (CDI {cdi:02X}) is empty")
    if e[:8] == b"\x00" * 8:
        F.append("L7 all-zero header")
    if b"\x00" * 8 in e:
        F.append(f"L7 8 x 00 run at byte {e.find(bytes(8))}")
    bad = [i for i, b in enumerate(e) if b in forbid]
    if bad:
        F.append(f"L8 {len(bad)} forbidden byte(s), first at {bad[0]}")
    return {"pass": not F, "fail": F, "warn": W, "info": I}


def lint_bwry(e: bytes, pair: bool = False, envelope: dict | None = None, tol: float = 15.0) -> dict:
    F, W, I = [], [], []
    t = bwry.decode(e)
    if bwry.encode(t) != e:
        F.append("B0 codec round trip not byte-exact")
    fr = t.frames()
    if len(set(fr)) != 1:
        F.append(f"B1 blocks differ in length {fr}")
    for k, b in enumerate(t.blocks):
        if not b.terminated():
            F.append(f"B2 block {k}: spare rows but no M = 0 terminator row (BUSY may never release)")
    if any(lv != "0" for lv, _ in t.blocks[0].segments()):
        F.append("B3 LUTC drives VCOM (not covered by our gate)")
    a, b = bwry.dc(e, "A"), bwry.dc(e, "B")
    I.append(f"B4 DC model A {a}, model B {b} (V x frames per code 0..3)")
    for name, d in (("A", a), ("B", b)):
        if pair:
            if abs(d[0] + d[1]) > tol:
                F.append(f"B4 pair balance |c0 + c1| = {abs(d[0] + d[1]):.1f} > {tol} (model {name})")
            for k in (2, 3):
                if abs(d[k]) > tol:
                    F.append(f"B4 code {k} |DC| {abs(d[k]):.1f} > {tol} (model {name})")
        else:
            for k, v in enumerate(d):
                if abs(v) > tol:
                    F.append(f"B4 code {k} |DC| {abs(v):.1f} > {tol} (model {name})")
    if envelope:
        for i, nm in enumerate(bwry.HEADER_FIELDS):
            rng = envelope.get(nm)
            if rng and not rng[0] <= t.header[i] <= rng[1]:
                F.append(f"B5 header {nm} = 0x{t.header[i]:02X} outside the envelope {rng}")
    I.append(f"refresh {t.duration_frames()} frames")
    return {"pass": not F, "fail": F, "warn": W, "info": I}


def lint_sequence(lines) -> dict:
    F, W = [], []
    pending = None
    refreshed = None
    for n, ln in enumerate(lines, 1):
        k = ln.strip().split("#")[0].strip().upper()
        if not k:
            continue
        if k == "UPLOAD":
            pending = n
        elif k in ("RST", "INIT", "TSC") and pending:
            F.append(f"S1 line {n} {k} after the upload at line {pending} and before its refresh")
            pending = None
        elif k == "REFRESH":
            if refreshed:
                F.append(f"S2 refresh at line {refreshed} has no POF before the next refresh")
            pending, refreshed = None, n
        elif k == "POF":
            refreshed = None
    if refreshed:
        F.append(f"S2 refresh at line {refreshed} is not followed by POF")
    return {"pass": not F, "fail": F, "warn": W, "info": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description="lint a register LUT (800 B S6 or 535 B JD-BWRY)")
    ap.add_argument("table", nargs="?")
    ap.add_argument("--seq")
    ap.add_argument("--panel", default="7.3", choices=sorted(timing.PROFILES))
    ap.add_argument("--pwr")
    ap.add_argument("--pll", default="02")
    ap.add_argument("--cdi")
    ap.add_argument("--codes")
    ap.add_argument("--busy-timeout", type=float)
    ap.add_argument("--vsh", type=float)
    ap.add_argument("--vsl", type=float)
    ap.add_argument("--forbid", default="")
    ap.add_argument("--allow-vcom-swing", action="store_true")
    ap.add_argument("--pair", action="store_true", help="BWRY differential partial: pair balance of codes 0+1")
    ap.add_argument("--envelope", help="BWRY: JSON {field: [min, max]} of your panel's stock header values")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.seq:
        r = lint_sequence(open(a.seq).read().splitlines())
    elif a.table:
        e = open(a.table, "rb").read()
        if len(e) == 800:
            codes = [int(x) for x in a.codes.split(",")] if a.codes else None
            meas = (a.vsh, a.vsl) if a.vsh is not None and a.vsl is not None else None
            forbid = tuple(int(x, 16) for x in a.forbid.split(",") if x)
            r = lint_s6(e, a.panel, a.pwr, int(a.pll, 16), int(a.cdi, 16) if a.cdi else None, codes,
                        a.busy_timeout, meas, forbid, a.allow_vcom_swing)
        elif len(e) == 535:
            env = json.load(open(a.envelope)) if a.envelope else None
            r = lint_bwry(e, a.pair, env)
        else:
            ap.error(f"unknown table size {len(e)}")
    else:
        ap.error("TABLE or --seq")
    if a.json:
        print(json.dumps(r, indent=1))
    else:
        print("PASS" if r["pass"] else "FAIL")
        for tag in ("fail", "warn", "info"):
            for x in r[tag]:
                print(f"  {tag:4s} {x}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""Charge (DC balance) calculator and gate for S6-class tables.

Level -> rail map (scope measurements on the 7.3in and 7.09in):
  S = VSL (-15 V)   W = VSL_LV   SW = VSL_LV2   K = VSH (+15 V)   SK = VSH_LV   WK = VSH_LV2
  "" (level 0) = driven to about 0 V;  SWK = source floats (counted as 0 and flagged).
Weak rails in custom mode come from PWR (0x01) data bytes 2..5 = VSH_LV, VSL_LV, VSH_LV2, VSL_LV2 (plain binary),
|V| = 3.0 + 0.1 x code (VSL_LV2: 3.04 + 0.0992 x code). In stock mode the same four codes sit in header bytes 1..4.
q_sf = sum(V x frames) / V(S): net charge in "S-frames" (one frame at the strong rail). S = +1, K = -1.
Lab gate: |q_sf| <= 1 for every used slot and the border slot, at nominal rails AND (if given) measured rails.

    python -m epdlut.charge TABLE.bin --pwr "3F 00 1E 18 23 3E" [--codes 0,1,2,3,5,6] [--vsh 14.82 --vsl -14.69]
"""
from __future__ import annotations

import argparse
import json

from . import s6

WEAK_ORDER = ("VSH_LV", "VSL_LV", "VSH_LV2", "VSL_LV2")
RAIL_OF = {"S": "VSL", "W": "VSL_LV", "SW": "VSL_LV2", "K": "VSH", "SK": "VSH_LV", "WK": "VSH_LV2",
           "": "0V", "SWK": "float"}


def parse_hex(x) -> bytes:
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    return bytes.fromhex(str(x).replace(" ", "").replace(",", ""))


def pwr_data(pwr) -> bytes:
    p = parse_hex(pwr)
    if len(p) == 7 and p[0] == 0x01:
        p = p[1:]
    if len(p) != 6:
        raise ValueError("PWR must be 6 data bytes")
    return p


def level_volts(weak_codes: dict, vsh: float = 15.0, vsl: float = -15.0) -> dict:
    r = {"VSH": vsh, "VSL": vsl, "0V": 0.0, "float": 0.0,
         "VSH_LV": 3.0 + 0.1 * weak_codes["VSH_LV"], "VSH_LV2": 3.0 + 0.1 * weak_codes["VSH_LV2"],
         "VSL_LV": -(3.0 + 0.1 * weak_codes["VSL_LV"]), "VSL_LV2": -(3.04 + 0.0992 * weak_codes["VSL_LV2"])}
    return {lv: r[RAIL_OF[lv]] for lv in RAIL_OF}


def weak_codes_from(table: bytes, pwr=None, mode: str = "custom") -> dict:
    if mode == "custom":
        return dict(zip(WEAK_ORDER, pwr_data(pwr)[2:6]))
    return dict(zip(WEAK_ORDER, (s6.val(b) for b in table[1:5])))


def slot_q(segs: list, V: dict) -> float:
    return sum(V[lv] * n for lv, n in segs) / V["S"]


def charge(table: bytes, pwr=None, mode: str = "custom", codes=None, cdi: int = 0x3F, hold_codes=(),
           vsh: float = 15.0, vsl: float = -15.0) -> dict:
    t = s6.decode_table(table)
    V = level_volts(weak_codes_from(table, pwr, mode), vsh, vsl)
    vbd = (cdi >> 5) & 7
    border = None if vbd == 7 else vbd
    if codes is None:
        codes = [k for k in range(8) if k not in hold_codes]
    T = t.refresh_frames()
    out = {}
    for k in range(8):
        segs = s6.segments(t, k)
        n = sum(x for _, x in segs)
        last = segs[-1][0] if segs else ""
        out[k] = {"used": k in codes, "border": k == border, "frames": n,
                  "q_sf": round(slot_q(segs, V), 3) if segs else 0.0,
                  "ends_driven": bool(segs) and n == T and last not in ("",),
                  "swk_frames": sum(x for lv, x in segs if lv == "SWK")}
    return {"refresh_frames": T, "border_slot": border, "level_V": {(k or "0"): round(v, 3) for k, v in V.items()},
            "slots": out}


def gate(table: bytes, pwr=None, mode: str = "custom", codes=None, cdi: int = 0x3F, hold_codes=(), tol: float = 1.0,
         measured: tuple | None = None, allow_end_driven: bool = True, allow_vcom_swing: bool = False) -> dict:
    """FAIL if a used or border slot has |q_sf| > tol (nominal rails, and measured rails if given), the LUTC swings
    VCOM (unless allowed), or a used slot ends on a drive level at the refresh end (unless allowed: our current
    practice when POF follows immediately; see docs/format-s6.md 'End hold')."""
    fail, warn = [], []
    reps = [("nominal", charge(table, pwr, mode, codes, cdi, hold_codes))]
    if measured:
        reps.append(("measured", charge(table, pwr, mode, codes, cdi, hold_codes, vsh=measured[0], vsl=measured[1])))
    for tag, r in reps:
        for k, s in r["slots"].items():
            if not (s["used"] or s["border"]) or not s["frames"]:
                continue
            if abs(s["q_sf"]) > tol + 1e-9:
                fail.append(f"slot {k}{' (border)' if s['border'] else ''}: |q| {abs(s['q_sf']):.2f} > {tol} S-frames ({tag} rails)")
            if tag == "nominal" and s["ends_driven"]:
                (warn if allow_end_driven else fail).append(f"slot {k}: ends on a drive level at the refresh end (end hold until POF)")
            if tag == "nominal" and s["swk_frames"]:
                warn.append(f"slot {k}: {s['swk_frames']} SWK (floating) frames counted as 0")
    r0 = reps[0][1]
    if r0["border_slot"] is not None and r0["slots"][r0["border_slot"]]["frames"] == 0:
        warn.append(f"border slot {r0['border_slot']} is empty: the border is not driven")
    sw = s6.lutc_swing_bits(table)
    if sw and not allow_vcom_swing:
        fail.append(f"LUTC VCOM swing bits set in {len(sw)} row byte(s)")
    return {"pass": not fail, "fail": fail, "warn": warn,
            "q_sf": {k: s["q_sf"] for k, s in r0["slots"].items() if s["used"] or s["border"]}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="S6 per-slot charge and the |q| gate")
    ap.add_argument("table")
    ap.add_argument("--pwr", help="PWR data bytes the firmware writes (custom mode)")
    ap.add_argument("--mode", default="custom", choices=("custom", "stock"))
    ap.add_argument("--codes")
    ap.add_argument("--cdi", default="3F")
    ap.add_argument("--hold", default="", help="hardwired hold codes, e.g. 4,7 on the 7.09in")
    ap.add_argument("--vsh", type=float)
    ap.add_argument("--vsl", type=float)
    ap.add_argument("--tol", type=float, default=1.0)
    a = ap.parse_args(argv)
    e = open(a.table, "rb").read()
    codes = [int(x) for x in a.codes.split(",")] if a.codes else None
    hold = tuple(int(x) for x in a.hold.split(",") if x)
    meas = (a.vsh, a.vsl) if a.vsh is not None and a.vsl is not None else None
    g = gate(e, a.pwr, a.mode, codes, int(a.cdi, 16), hold, a.tol, meas)
    print(json.dumps(g, indent=1))
    return 0 if g["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""Frame-time model: refresh length from table bytes and the PLL (0x30) value.

PLL bit 3 clear: fixed rate code = PLL & 7. Bit 3 set ("dynamic", stock value 08): the rate code of each frame
comes from the LUTC row that covers it (3 rate bits); frames past the LUTC end run at code 0.
All numbers are our measurements (BUSY timing and scope), ms per frame. See docs/format-s6.md section 6.

    python -m epdlut.timing TABLE.bin --panel 7.3 --pll 02
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from . import bwry, s6


@dataclass
class Profile:
    name: str
    family: str                                    # "s6" | "bwry"
    fixed_ms: dict = field(default_factory=dict)   # rate code (PLL & 7) -> ms, PLL bit 3 clear
    dyn_ms: dict = field(default_factory=dict)     # LUTC rate code -> ms, PLL bit 3 set
    overhead_ms: float = 0.0                       # constant per refresh
    hold_codes: tuple = ()                         # pixel codes the chip never drives
    cdi_default: int = 0x3F
    note: str = ""


PROFILES = {
    "7.3": Profile("7.3in S6 (SPD1657A class)", "s6",
                   fixed_ms={0: 36.82, 1: 31.45, 2: 23.46, 3: 20.18, 4: 15.55, 5: 13.45, 6: 11.88, 7: 10.12},
                   dyn_ms={0: 40.38, 1: 31.44, 2: 23.49, 3: 20.21, 4: 15.55, 5: 13.44, 6: 11.89, 7: 10.12},
                   overhead_ms=39.0, cdi_default=0x3F,
                   note="all 9 blocks count for the refresh length, used or not"),
    "7.09": Profile("7.09in dual-chip S6", "s6",
                    fixed_ms={1: 40.8, 2: 20.4, 3: 15.95, 4: 13.6, 5: 11.98, 6: 10.17, 7: 8.49},
                    dyn_ms={0: 81.1, 1: 40.55, 2: 20.35, 3: 15.68, 4: 13.58, 5: 12.0, 6: 10.2, 7: 8.53},
                    overhead_ms=0.0, hold_codes=(4, 7), cdi_default=0x37,
                    note="frame = DRF/40 at PLL 08, no fixed overhead; codes 4 and 7 are hardwired holds"),
    "2.9bwry": Profile("2.9in JD-BWRY", "bwry", fixed_ms={2: 19.97, 7: 8.38},
                       dyn_ms=dict(enumerate(bwry.DYN_MS)), overhead_ms=0.0,
                       note="PLL 08 stock = 20 ms (rate code 2 in the LUTC); windowed tables < 50 frames run +1 frame"),
    "4.2x4": Profile("4.2in JD-BWRY x4 variant", "bwry", fixed_ms={2: 19.80, 3: 15.22}),
}


def s6_frame_list(e: bytes, pll: int, prof: Profile) -> list:
    """ms of each frame up to the refresh end."""
    t = s6.decode_table(e)
    n = t.refresh_frames()
    if not pll & 0x08:
        ms = prof.fixed_ms.get(pll & 7)
        return [ms] * n
    rates = []
    for _, rate, cnt in s6.lutc_timeline(e):
        rates += [rate] * cnt
    rates += [0] * max(0, n - len(rates))
    return [prof.dyn_ms.get(r) for r in rates[:n]]


def refresh_s(e: bytes, panel: str, pll: int) -> float | None:
    prof = PROFILES[panel]
    if prof.family == "s6":
        fl = s6_frame_list(e, pll, prof)
    else:
        t = bwry.decode(e)
        n = t.duration_frames()
        ms = prof.fixed_ms.get(pll & 7) if not pll & 0x08 else 20.0   # dynamic: stock-like LUTC assumed
        fl = [ms] * n
    if any(x is None for x in fl):
        return None
    return round((sum(fl) + prof.overhead_ms) / 1000.0, 3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="predict refresh time from table bytes")
    ap.add_argument("table")
    ap.add_argument("--panel", default="7.3", choices=sorted(PROFILES))
    ap.add_argument("--pll", default="02")
    a = ap.parse_args(argv)
    e = open(a.table, "rb").read()
    pll = int(a.pll, 16)
    s = refresh_s(e, a.panel, pll)
    print(f"{a.table}: {s} s at PLL {pll:02X} ({PROFILES[a.panel].name})" if s is not None else
          f"{a.table}: frame time for PLL {pll:02X} not measured on {a.panel}")


if __name__ == "__main__":
    main()

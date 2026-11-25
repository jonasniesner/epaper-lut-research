# SPDX-FileCopyrightText: 2026 Jonas Niesner
# SPDX-License-Identifier: MIT
"""python -m unittest discover -s tests   (from the repo root)"""
import hashlib
import json
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from epdlut import bwry, lint, lzss, recipe, s6, timing  # noqa: E402
import synthetic  # noqa: E402

MAN = json.loads((ROOT / "luts/manifest.json").read_text())["tables"]


class TestIncludedTables(unittest.TestCase):
    def test_manifest_files_exist_and_hash(self):
        for m in MAN:
            e = (ROOT / "luts" / m["file"]).read_bytes()
            self.assertEqual(hashlib.sha1(e).hexdigest(), m["sha1"], m["name"])

    def test_roundtrip_exact(self):
        for m in MAN:
            e = (ROOT / "luts" / m["file"]).read_bytes()
            if len(e) == 800:
                self.assertEqual(s6.encode_table(s6.decode_table(e)), e, m["name"])
                self.assertEqual(s6.decode_table(e).refresh_frames(), m["frames"], m["name"])
            else:
                self.assertEqual(len(e), 535)
                self.assertEqual(bwry.encode(bwry.decode(e)), e, m["name"])
                self.assertEqual(bwry.decode(e).duration_frames(), m["frames"], m["name"])

    def test_lint_passes(self):
        for m in MAN:
            e = (ROOT / "luts" / m["file"]).read_bytes()
            w = m["write_with"]
            if len(e) == 800:
                panel = "7.09" if m["name"].startswith("s709") else "7.3"
                r = lint.lint_s6(e, panel, w["PWR"], int(m["pll"], 16), codes=w["codes"])
            else:
                r = lint.lint_bwry(e, pair="window" in w.get("note", ""))
            self.assertTrue(r["pass"], (m["name"], r["fail"]))

    def test_predicted_time(self):
        for m in MAN:
            e = (ROOT / "luts" / m["file"]).read_bytes()
            panel = "7.09" if m["name"].startswith("s709") else ("7.3" if len(e) == 800 else "2.9bwry")
            self.assertAlmostEqual(timing.refresh_s(e, panel, int(m["pll"], 16)), m["predicted_s"], places=3)

    def test_txt_matches(self):
        for m in MAN:
            e = (ROOT / "luts" / m["file"]).read_bytes()
            txt = (ROOT / "luts" / m["file"]).with_suffix(".txt").read_text()
            self.assertIn(hashlib.sha1(e).hexdigest(), txt)


class TestLZSS(unittest.TestCase):
    def test_tables(self):
        for m in MAN:
            e = (ROOT / "luts" / m["file"]).read_bytes()
            z = lzss.encode(e)
            self.assertLess(len(z), len(e))
            self.assertEqual(lzss.decode(z, n_out=len(e))[0], e)

    def test_random_and_offset(self):
        rnd = random.Random(1)
        data = bytes(rnd.choice(b"\xff\xef\x7f\xbf") for _ in range(3000)) + os.urandom(200)
        z = lzss.encode(data)
        self.assertEqual(lzss.decode(z, n_out=len(data))[0], data)
        # a stream that starts mid-byte (the MTP store starts at bit 22 after byte 0x11)
        w = lzss.BitWriter()
        w.write(0b101, 3)
        bits = lzss.BitReader(z)
        for _ in range(len(z) * 8):
            w.write(bits.read(1), 1)
        self.assertEqual(lzss.decode(w.getvalue(), bitpos=3, n_out=len(data))[0], data)


class TestCodecs(unittest.TestCase):
    def test_s6_value_code_bijection(self):
        for x in range(256):
            self.assertEqual(s6.enc(s6.val(x)), x)

    def test_bwry_build_terminated(self):
        e = bwry.build(bytes(7), {1: [("K", 10)], 2: [("W", 10)]})
        t = bwry.decode(e)
        self.assertEqual(t.frames(), [11] * 6)
        self.assertTrue(all(b.terminated() for b in t.blocks))
        self.assertTrue(lint.lint_bwry(e, pair=True)["pass"])

    def test_x4_repair(self):
        t = bytes(range(0, 256, 3))
        skew = bytes([(t[j] & 0xFE) | (t[j + 1] & 1) for j in range(len(t) - 1)] + [t[-1]])   # bit 0 one byte early
        self.assertEqual(bwry.x4_bit0_repair(skew)[1:-1], t[1:-1])

    def test_sequence_rule(self):
        self.assertTrue(lint.lint_sequence(["TSC", "UPLOAD", "REFRESH", "POF"])["pass"])
        self.assertFalse(lint.lint_sequence(["UPLOAD", "TSC", "REFRESH", "POF"])["pass"])
        self.assertFalse(lint.lint_sequence(["UPLOAD", "REFRESH"])["pass"])


class TestRecipes(unittest.TestCase):
    """recipes on synthetic sets (no vendor data in this repo): they must run and pass the gate."""

    def setUp(self):
        self.s73 = synthetic.fake_set_73()
        self.s4, self.s5 = synthetic.fake_set_709(0), synthetic.fake_set_709(2)

    def test_fast73(self):
        base = s6.decode_table(self.s73).refresh_frames()
        for drop in (4, 5):
            e = recipe.fast73(self.s73, drop)
            self.assertEqual(s6.decode_table(e).refresh_frames(), base - 160 - 20 * drop)
            self.assertTrue(lint.lint_s6(e, "7.3", recipe.pwr_from_header(self.s73, "3F 00"), 2)["pass"])

    def test_flash73(self):
        for kw in ({}, {"shake": 2, "keep_w_gap": True}):
            e, meta = recipe.flash73(self.s73, **kw)
            r = lint.lint_s6(e, "7.3", meta["pwr"], 2, codes=meta["codes"])
            self.assertTrue(r["pass"], r["fail"])
            t = s6.decode_table(e)
            self.assertEqual(t.slots[4].frames(), 0)                 # hold code
            L = t.refresh_frames()
            for k in (0, 1, 2, 3, 5, 6):
                self.assertEqual(t.slots[k].frames(), L)              # right-aligned to one length

    def test_track73(self):
        for c in "KWYRBG":
            for f in (0.25, 1.0):
                e, meta = recipe.track73(self.s73, c, f)
                r = lint.lint_s6(e, "7.3", meta["pwr"], 2, codes=meta["codes"])
                self.assertTrue(r["pass"], (c, f, r["fail"]))

    def test_fast709(self):
        for v in ("F3c", "G13"):
            e, meta = recipe.fast709(self.s4, v)
            r = lint.lint_s6(e, "7.09", meta["pwr"], meta["pll"], codes=meta["codes"])
            self.assertTrue(r["pass"], (v, r["fail"]))
            self.assertEqual(sum(n for _, _, n in s6.lutc_timeline(e)), s6.decode_table(e).refresh_frames())

    def test_mix709(self):
        e, meta = recipe.mix709(self.s4, self.s5)
        r = lint.lint_s6(e, "7.09", meta["pwr"], 4, codes=meta["codes"], measured=meta["measured"])
        self.assertTrue(r["pass"], r["fail"])


if __name__ == "__main__":
    unittest.main()

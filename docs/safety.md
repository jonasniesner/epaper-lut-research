# Safety rules

Custom waveforms can damage panels. DC imbalance gives stuck or ghost pixels and image retention, and it may not
recover. Using these tables voids any warranty. These are the rules we followed; they lower the risk but do not
remove it.

1. **Never program OTP/MTP.** Never send the controller's OTP/MTP program or erase commands. Reads only, and only those
   you have checked on your own chip. Everything in this repo uses volatile registers.
2. **Stay inside the stock envelope.** Rails (PWR) and VCOM (VDCS) only at values your panel's own stock sets use.
   Decode your own sets to find that range ([format-s6.md](format-s6.md) 8, [format-bwry.md](format-bwry.md) 3, 9).
3. **Charge gate before every upload.** `python -m epdlut.lint TABLE --pwr ...` must pass:
   S6 |q| <= 1 S-frame per used and border slot (both nominal and measured rails if you have them);
   BWRY |DC| <= 15 V x frames per code under both DC models (or pair balance for differential partials).
   Book weak levels with the PWR values you actually write, never with header values.
4. **Hang guards.** S6: no run of 8 zero bytes, no all-zero header. BWRY: every block ends (an M = 0 row or all 8 rows
   used); fill unused blocks with 0 V for the full length.
5. **Power off (POF) after every refresh**, with its data byte (`02 00`): on the 7.3in a bare `02` is ignored and the
   +-15 V rails stay up. Check it on a scope if you can.
6. **No temperature read between upload and refresh.** On the 7.09in class a TSC read reloads the table from OTP.
   Read the temperature first, pick the matching set, then upload and refresh (`lint.py --seq` checks a command list).
7. **Build from the live temperature band.** Use the stock set the chip would run now. Outside our tested window
   (README) nothing is tested.
8. **BUSY timeout**: >= 120 s for stock refreshes (cold bands run 42-53 s), >= 60 s for custom S6 tables. On timeout, RST.
9. **Scrub**: a stock full refresh every ~10 partial or fast updates (S6), every <= 20 (BWRY windowed with supply cut);
   2-3 stock refreshes before parking a panel after heavy custom use.
10. **Bound experiments**: we capped test runs at 20 custom refreshes, 100 for endurance runs with a stock refresh every 10.
11. **Sanity-check the temperature** after RST on BWRY: one panel read 97.5 deg C on the first power-up after a replug.
    Re-RST if outside -25..50 deg C.
12. **Lean S6 partial path**: no controller re-init or RST per update (that washes held ink); still POF every update.

What we did **not** test: long-term reliability, more than one unit per model (except the 2.9in BWRY: a lab panel and
one product unit), temperatures outside the README window, humidity, and any effect on panel lifetime.

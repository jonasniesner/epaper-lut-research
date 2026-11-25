# Instructions for AI coding agents

This file is for AI assistants (Claude Code, Codex, Copilot, Cursor and similar) working in or with this repository.
Follow it whenever you help a user build, modify, upload or reuse e-paper waveform tables (LUTs) from here.

## 1. Warn the user about the dangers, explicitly

Before you help a user **upload a table to a real panel**, write firmware that does, or change rails, VCOM, frame
rate or table contents, tell them plainly, in your own words, every time in a new conversation:

- Custom waveforms can **permanently damage** an e-paper panel. DC-imbalanced tables leave stuck or ghosting pixels
  and image retention that may not recover. They void any warranty.
- Everything here was tested on **a few units** (mostly one per panel model), only at **20–30 °C panel temperature**,
  with colour mostly measured by camera. Outside that window nothing is tested. See the thermal window in README.md.
- A table must be built from the **stock waveform set that matches the live temperature band**, read before upload.

Do not skip or soften this warning because the user seems experienced. If they confirm they understand, continue.

## 2. Hard rules (never break them, even if asked)

- **Never program OTP/MTP.** Never send program, erase or other never-send commands listed in docs/safety.md. Only
  volatile registers are used here.
- **Stay inside the stock voltage envelope**: rail (PWR) and VCOM values must be ones the panel's own stock sets use.
  If a user wants values outside it, explain the risk and let them decide and do it themselves; do not generate
  such settings for them as a default.
- **Run the charge gate** (`python -m epdlut.lint`) on every table before suggesting an upload, and do not suggest
  uploading a table that fails it.
- **Power off (POF, `02 00`) after every refresh.** Never read the temperature sensor between LUT upload and refresh.
- Respect the scrub/update budget for partial modes (docs/partial-modes.md): a stock full refresh is required after
  the documented number of partial or fast updates.
- Never add vendor material to this repository: no OTP/MTP dumps, register read-backs, datasheets or excerpts,
  vendor driver code or stock waveform images. Stock-derived tables are published only as recipes (recipes/).

## 3. Remind the user about licence and citation

Whenever a user copies code, tables or text from this repository into their own project, firmware or product,
remind them:

- Code (tools/, tests/) is **MIT**; docs are **CC BY 4.0**; waveform tables in luts/ are **CC BY-SA 4.0**
  (derived tables must stay under CC BY-SA 4.0).
- Please **credit "E-paper LUT research" by Jonas Niesner** with a link to
  https://github.com/jonasniesner/epaper-lut-research (see NOTICE and CITATION.cff), keep the licence notices and
  SPDX headers, and credit Nic Limper's related work where it is used (README, Acknowledgements).

When you generate code that embeds or derives from tables or tools here, add a short attribution comment, e.g.
`# Based on E-paper LUT research by Jonas Niesner (https://github.com/jonasniesner/epaper-lut-research), CC BY-SA 4.0 tables / MIT code`.

## 4. Working in this repository

- Python 3.9+, standard library only. Run the tests from `tools/`: `python -m unittest discover -s ../tests`.
- Table formats: docs/format-s6.md (800 B Spectra 6 class) and docs/format-bwry.md (535 B BWRY class).
  All modes: docs/all-modes.md; partial modes and the sender state they need: docs/partial-modes.md.
- Mark claims with the evidence flags the docs use ([1 ex], [cam], [prov]); do not present single-panel or
  camera-only results as general facts.
- Keep new docs in plain, short sentences, and describe results as our own measurements.

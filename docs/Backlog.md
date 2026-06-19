# PK232PY — Development Backlog

**Last updated:** 2026-06-19 (v16)
**Current version:** v0.1 (development)

---

## Priority 1 — Next implementation sprint

### Packet — Connect/Disconnect & MHEARD

- ✅ Connect/Disconnect flow (T33–T37) **software-verified via the mock TNC**
  (`tools/mock_tnc_bbs.py`) — the mock replaces the second AX.25 station for
  software tests. Connect/CONNECTED/DATA/Disconnect logic confirmed.
- **Open:** T38 Unproto with digipeater path
- **Open:** T39 Connect/Unproto mutual exclusion
- **Open:** MHEARD response (`MH` frame) → MheardPanel entries (T41–T42)
- **Open:** T35/T37 hardware re-test: real AX.25 second station (the mock
  proves the software logic; on-air behaviour still needs a real TNC + station)

*Note: monitoring on 144.800 MHz has replaced most RX-only tests.
T38/T39, MHEARD and the T35/T37 hardware re-test still need a real station.*

### Packet — Remaining toggle/button tests

- T43 EAS toggle (`EA Y` / `EA N`)
- T44 PASSALL toggle
- T45 HBAUD change
- T46 Monitor level change
- T47 MailDrop button (`MI` frame)
- T48 VHF vs HF init frames (VH Y / VH N)
- T49 Keyboard focus after button click
- T50 Dest + UNPROTO fields
- T51 Mode switch away from VHF Packet (`VH N`)

---

## Priority 2 — Improvements

### APRS — Phase 2

| Item | Notes |
|------|-------|
| MHEARD panel: show APRS stations | Populate from received Mic-E + Position frames |
| Beacon TX | UNPROTO APRS VIA WIDE1-1,WIDE2-1; periodic timer |
| Beacon config UI | Position (lat/lon from INI), symbol, comment, interval |
| Mic-E lon decode verify | Test with west-of-0° and lon > 100° stations |

### FAX closed-loop test tooling — formalise tests

- `tools/fax_wav_generator.py` + `tools/fax_decoder_test.py` provide a
  closed-loop WEFAX test path (generator → WAV → decoder). Working.
- **Open:** formal test cases T66–T68 (FAX closed-loop decode for
  weather/pattern/text) still to be added to `Testplan.md`.
- **Open:** `make_weather_image()` — the real weather-chart path is not
  resolvable locally; `WEATHER_IMAGE_CANDIDATES` does not match the actual
  file (e.g. `tools/Wetterkarte.jpg`), so it falls back to
  `wetterkarte_decoded.png`. Extend the candidate list.

### Testing tools (dev-only)

- `mock_tnc_bbs.py`: dev-only mock TNC + mini-BBS for Packet connected-mode
  tests (T33–T37, T83–T84) with no real TNC, radio or second station.
  Start: `python tools/mock_tnc_bbs.py [--trace]`.

### TxController — CTRL+D EOT (Status nach Paket 2a/2b)

**Paket 1 — Umbenennung (erledigt, cc2adff):**
`BaudotTxController` → `TxController`, Datei `tx_controller.py`,
Attribut `self._tx_ctrl`. Neue Methode `set_mspeed_ms(ms)` für Modes
ohne sinnvolle Baudrate.

**Paket 2a — CW/Morse (erledigt, 437e8a1):**
`morse_screen.py`: `tx_input` auf `TxInputWidget` umgestellt.
`[^D]` EOT → RC (wie Baudot). ACK-getaktet, `_MORSE_TXCTRL_MS = 50`.
Hardware-Tests T69–T72 ausstehend.

**Paket 2b — AMTOR (erledigt, 8087564):**
`amtor_screen.py`: `tx_input` auf `TxInputWidget` umgestellt.
TX-Aktivierung: KEIN btn_send / XM-Frame. CONNECTED-Link-Message →
`on_send_start()` in `_make_link_handler()`. ARQ-EOT → PTOVER `\x1A`
(Ctrl-Z, eingebettet im Datenstrom, wartet auf Puffer-leer). FEC-EOT
→ `on_send_stop()`. ARQ/FEC-Unterscheidung via `btn_fec.isChecked()`,
NIE via `mode.name`. `_AMTOR_TXCTRL_MS = 50`.
Hardware-Tests T73–T79 ausstehend (T73 zuerst!).
CRITICAL CAVEAT: `_make_link_handler()` triggert auf "connected" im
Link-Message-Text. Falls der TNC anderen Text schickt → Handler anpassen.

**Paket 3 — Stop Sending (offen):**
Neuer "Stop TX"-Button auf allen TX-fähigen Screens.
AMTOR → `AM` (Mnemonic, Stby + TNC-Puffer löschen; NICHT `R`).
Baudot/ASCII/Morse → RC + `on_send_stop()` + `clear()`.
Packet → TBD (kein EOT-Konzept).

### Help system — ausdifferenzieren
- `help_baudot.md` exists as one large file
- Split into topic-specific files as needed:
  - `help_macros.md`
  - `help_shortcuts.md`
  - `help_ctrl_chars.md`
- Add Help buttons to further dialogs (TNC Config, etc.)

### TX_STATE_MACHINE.md §8 — Control Characters update
- Update §8 table: `[^T:n]` als implemented eintragen
- `[^S]` aus Planned entfernen (entschieden: nicht implementieren)
- Sentinel-Encoding dokumentieren: `\x1b` + str(n)
- Backspace-Handling (dict-basiert, variable Länge) dokumentieren

### TooltipManager
- `TooltipManager` — central tooltip registration for buttons

### MSPEED from TNC config
- Auto-set `TxController.set_mspeed()` / `set_mspeed_ms()` from `PK232.INI` MSPEED
  parameter on Host Mode activation (currently hardcoded to 50 Baud default)
- Config dialog already has MSPEED field for Morse — extend to Baudot/ASCII

### Macro control characters in dialog
- `MacroTextEdit` supports CTRL+D and CTRL+T:n
- Verify CTRL+T:n dialog works correctly inside MacroEditDialog

### T18 — Multi-cycle colour test
- Formal test: 3x SEND→RECEIVE→SEND without macros
- Verify no colour drift after each cycle

### AMTOR Dest (le_dest) Autofill
- AMTOR le_dest (Ziel-SELCAL) is editable but not pre-filled
- Consider populating from last used callsign or history list

---

## Priority 3 — Future / v0.2+

### ASCII RTTY — full TX/RX integration
- Same TxController integration as Baudot
- Currently wired but untested

### AMTOR ARQ TX integration — ✅ Erledigt (Paket 2b, 8087564)
AMTOR nutzt TxController. TX startet bei ARQ CONNECTED
(kein btn_send, kein XM-Frame — TNC managed 100 Bd ARQ timing).

### PACTOR I TX integration
- Similar to AMTOR

### QSO Log
- SQLite-based log (`log/` directory already planned)

### MailDrop
- TNC mailbox functionality (`maildrop/` directory planned)

---

## Completed (2026-06-19 — Mock-TNC BBS sprint)

| Item | Notes |
|------|-------|
| Mock TNC + mini-BBS (`tools/mock_tnc_bbs.py`) | In-process `LoopbackTNC` duck-types serial.Serial via `SerialManager.set_port_factory()`; mini-BBS answers CONNECT/L/R/D. Exercises Packet connected mode (T33–T37, T83–T84) without a TNC, radio or second station. Dev-only, GPL v2. |
| CO/DI frame CTL bug ($4F instead of $41) | `_on_packet_connect/_disconnect` built the channel frame but sent it via `send_command()` (forces CTL=$4F, channel lost). Now uses `send_channel_command()` → correct $41. Fixed 47f5845. |
| Connect-button gating (prevent double CO) | `PacketBaseScreen.set_link_state()` + gating in `_make_link_handler`/`_on_packet_connect`: Connect disabled while connected/calling, re-enabled (and released) on disconnect; Disconnect starts disabled. |
| Packet Connect/Disconnect software tests (T33–T37) | PASS against the mock; T83/T84 added to Testplan. Hardware re-test (real second station) tracked under Priority 1. |

---

## Completed (2026-06-18 — FAX live image decode + TX polish)

| Item | Notes |
|------|-------|
| FAX live decode — `EpsonFaxParser` | Length-driven, frame-overlapping parser for the `$3F` Epson 9-pin printer-graphics stream (ESC L bit image + ESC A band separators) → 8-row grayscale bands → `FaxImageWidget`. Hardware-verified (Testplan T82). Unit tests in `src/pk232py/tests/test_epson_fax_parser.py`. |
| FAX display pixel aspect | `PIXEL_ASPECT = 120/72` vertical stretch (ESC L 120 dpi H / ESC A 8 → 72 dpi V), smooth scaling — fixes the squashed image / oval circle. |
| FAX smoothing slider | Non-destructive inverse-halftoning (`scipy.ndimage.gaussian_filter`, anisotropic `σ=(σ, σ·PIXEL_ASPECT)`, throttled recompute). Slider 0 = exact raw bilevel preserved. |
| FAX LOCK button | Force Receive (mnemonic `LO`) + parser reset / `_fax_receiving`. |
| FAX Stop button | Freeze image + ignore further data + parser reset; LOCK/Clear re-enable. |
| FAX FAXNEG = display-only invert | No longer sends `FN` to the TNC (TNC-side FN only affected subsequent lines → banded polarity). |
| `fax_wav_generator.py --target tnc` | Bench WAVs at the PK-232 demod centre (1200/2200 Hz) vs `--target sw` (1500/2300 Hz). |
| Testplan T81 / T82 | T81 = WAV→TNC bargraph sync; T82 = full live Epson decode (aspect, smoothing, start/stop, polarity). |

---

## Completed (v16 — 2026-06-14)

| Item | Notes |
|------|-------|
| TxController — Paket 1 (Umbenennung) | `BaudotTxController` → `TxController`, Datei `tx_controller.py`, `set_mspeed_ms()` ergänzt. commit cc2adff |
| TxController — Paket 2a (Morse) | Morse auf TxController gehoben, `[^D]` EOT → RC, ACK-getaktet. commit 437e8a1 |
| TxController — Paket 2b (AMTOR) | `amtor_screen.py`: TxInputWidget, CONNECTED→start, PTOVER ARQ-EOT. commit 8087564 |
| Clear TX / Clear RX buttons — all opmode screens | Done. TX-capable screens (AMTOR, CW/Morse, HF Packet, VHF Packet) emit `clear_tx_req` / `clear_rx_req` (signal pattern, wired by `MainWindow`); receive-only Signal/SIAM + NAVTEX got a local `_on_clear_rx()` slot; FAX got a local `_on_clear_image()` slot ("Clear Image"). |
| FAX closed-loop test tooling (`tools/`) | `fax_wav_generator.py` (WEFAX test-WAV generator: weather/pattern/text) + `fax_decoder_test.py` standalone decoder. Generator GPL v2, decoder GPL v3 (test-only, never shipped). |
| `fax_decoder_test.py` — fractional line length | Fixes accumulating line drift / slant (parallelogram) for non-integer samples-per-line. |
| `fax_decoder_test.py` — header detection | Detects the keyed 300 Hz APT start on the demod stream + tolerant run-length tracking. |
| `Sources2Text.ps1` — export `tools/**/*.py` | Export now includes `tools/` Python files (production code first, tools after). |

## Completed (v15 — 2026-05-17)

| Item | Notes |
|------|-------|
| Bug: CO on channel 0 → channel 1 | `build_ch_cmd(1, b'CO', ...)` in `_on_packet_connect()` |
| Bug: DI on channel 0 → channel 1 | `build_ch_cmd(1, b'DI')` in `_on_packet_disconnect()` (Claude Code) |
| Bug: `on_connect_toggled` AttributeError | Naming fix in `_wire_packet_buttons()` and disconnect handler |
| T31 VHF Packet init frames | ✅ PA, VH Y, HB 1200, MX 4, SL 10, MN Y — confirmed on TNC |
| T40 Monitor frames on 144.800 MHz | ✅ $3F frames received, decoded, displayed with UTC timestamps |
| APRS decoder v3 (`aprs_decoder.py`) | Mic-E (lat/lon), Position, Position+Time, Telemetry, Weather, Message, Third-party, Item, Object |
| APRS HTML display | Colour-coded cards in QTextEdit: orange/blue/green/yellow/pink per type |
| APRS button + dual-buffer | Toggle re-renders full frame history; raw mode unchanged |
| Mic-E backtick prefix fix | Strip `` ` ``/`'` before lon decoding — fixes 68°E → 16°E |
| Claude Code workflow | Established for direct file changes; patch scripts only as fallback |

## Completed (v14 — 2026-05-08)

| Item | Version | Notes |
|------|---------|-------|
| FAX: ESC L Spalten-Decoder | v14 | 8-Pin Epson Format korrekt dekodiert |
| FAX: Stream-Parser in fax_test.py | v14 | Frame-übergreifender ESC L Parser |
| FAX: LOCK Button | v14 | Host-Mnemonic LO |
| FAX: ASPECT ComboBox | v14 | IOC-Tabelle statt SpinBox |
| FAX: FSPEED Index-Fix | v14 | FS sendet Index 0-4 statt RPM-Wert |
| Host Mode Exit → Verbose | v14 | `_exiting_host_mode_by_user` Flag |
| PACTOR capability detection | v14 | Banner-Erkennung, ComboBox/Menü disabled |
| params_uploader race condition | v14 | 120ms Idle-Detection in write_verbose_wait() |

## Completed (v13)

| Item | Version | Notes |
|------|---------|-------|
| CTRL+T `[^T:n]` timed marker | v13 | Purple marker, QInputDialog for n (1–10) |
| Bugfix: text after `[^T:n]` not sent | v13 | `_tx_queue.clear()` fix |
| `_eot_positions` → dict-Liste | v13 | Variable Marker-Länge |

## Completed (v11/v12)

| Item | Version | Notes |
|------|---------|-------|
| HF Packet screen | v11 | `HFPacketScreen` |
| VHF Packet screen | v11 | `VHFPacketScreen` |
| Packet integration in MainWindow | v11 | `_wire_packet_buttons()`, 8 slots |
| PACTOR/AMTOR/Packet QLineEdit focus fix | v12 | `ScreenFocusController` |
| PACTOR MYPTCALL → QLabel | v12 | Populated from AppConfig |
| AMTOR identity labels → QLabel | v12 | Display-only |

---

## Known issues (monitor)

| Issue | Severity | Notes |
|-------|----------|-------|
| `MSPEED 20 Baud → 150ms/char` in log | Minor | Falls back to 150ms — cosmetic log noise |
| `CMD NAK: mnemonic=b'XL' error=0x07` | Minor | XL not supported by v7.1 — expected |
| `CMD NAK: mnemonic=b'EE' error=0x07` | Minor | EE not supported — expected |
| HFPacket/VHFPacket: CMD_RESP reaches mode | Minor | `handle_frame()` logs "unhandled frame" for ACKs — harmless |
| T18 (multi-cycle colour) | Open | Not formally tested |
| T32 HF Packet init frames | Open | Not tested |

---

*OE3GAS | PK232PY Project | 2026-06-16*
# PK232PY — Development Backlog

**Last updated:** 2026-06-14 (v16)
**Current version:** v0.1 (development)

---

## Priority 1 — Next implementation sprint

### Packet — Connect/Disconnect & MHEARD (needs second station)

- Test T33–T36: Connect flow (CO frame → CONNECTED status pill)
- Test T37–T39: Disconnect flow, Unproto toggle, mutual exclusion
- Parse MHEARD response (`MH` frame) into MheardPanel entries (T41–T42)

*Note: monitoring on 144.800 MHz has replaced most RX-only tests.
T33–T39 require a second AX.25 station.*

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

### CTRL+D (EOT) in weiteren Opmodes

CTRL+D als End-of-Transmission Marker ist in Baudot RTTY vollständig
implementiert (BaudotTxController). Die gleiche Funktionalität soll in
folgenden Modes ergänzt werden:

- **AMTOR** — ARQ: EOT sendet `\x04`, TNC wechselt zurück zu STANDBY
- **CW/Morse** — EOT sendet `\x04` oder `AR` (je nach TNC-Konfiguration)

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
- Auto-set `BaudotTxController.set_mspeed()` from `PK232.INI` MSPEED
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
- Same BaudotTxController integration as Baudot
- Currently wired but untested

### AMTOR ARQ TX integration
- Rate-limited TX not needed (AMTOR is ARQ — TNC manages retransmission)

### PACTOR I TX integration
- Similar to AMTOR

### QSO Log
- SQLite-based log (`log/` directory already planned)

### MailDrop
- TNC mailbox functionality (`maildrop/` directory planned)

---

## Completed (v16 — 2026-06-14)

| Item | Notes |
|------|-------|
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

*OE3GAS | PK232PY Project | 2026-06-14*
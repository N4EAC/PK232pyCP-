# PK232PY — Test Plan
**Updated: 2026-06-16 (v16) — Paket 2a/2b TxController (Morse + AMTOR), T69–T79**
**Previous stand: 2026-06-16 (v16) — CW/Morse TxController tests T69–T72 (Paket 2a)**

---

## Change History

| Version | Files | Content |
|---------|-------|---------|
| v3 | `modes/morse.py`, `modes/amtor.py`, `modes/signal_analysis.py` | Mode name fixes |
| v4 | `main_window.py` | TX window yellow, `_flush_tx_buffer`, RX colour, Fast Init |
| v5 | `main_window.py` | Removed duplicate methods |
| v6 | `main_window.py` | No RC for Baudot/ASCII/Morse |
| v7 | `main_window.py` | `QApplication.instance().installEventFilter(self)` |
| v8 | `main_window.py` | Full TX logic in app-wide `eventFilter` |
| v9 | `main_window.py` | Buffer flush on SEND toggle |
| **v10** | `baudot_tx_controller.py` *(new)* | `BaudotTxController` — rate-limited TX, DATA_ACK, EOT |
| **v10** | `ui_theme.py`, `macro_store.py` *(new)* | Theme + macro extraction |
| **v10** | `opmode_rtty_base.py` | `TxInputWidget` |
| **v10b** | multiple | TX_MAX=512, paste fix, Help viewer |
| **v11** | `packet_screen.py` *(new)* | `HFPacketScreen`, `VHFPacketScreen`, `MheardPanel` |
| **v11** | `main_window.py` | Packet integration: `_wire_packet_buttons()` |
| **v12** | `screen_focus_controller.py` *(new)* | `ScreenFocusController` |
| **v12** | `main_window.py` | eventFilter fixes, identity label population, PACTOR screen guard |
| **v15** | `main_window.py` | Bug: CO/DI channel 0→1; `on_connect_toggled` naming fix |
| **v15** | `aprs_decoder.py` *(new)* | APRS decoder v3: Mic-E, Position, WX, Telemetry, HTML cards |
| **v15** | `packet_screen.py` | `btn_aprs` toggle, `APRS_CAPABLE`, `_STYLE_APRS_ON/OFF` |
| **v15** | `main_window.py` | `_packet_raw_frames` buffer, `decode_html()` path, dual-buffer redraw |
| **v16** | `tx_controller.py` *(renamed)* | `BaudotTxController` → `TxController`; `set_mspeed_ms()` added (cc2adff) |
| **v16** | `morse_screen.py`, `main_window.py` | Morse on TxController: `TxInputWidget`, `[^D]` EOT → RC, ACK-paced; `_is_txctrl_mode()` helper, `_MORSE_TXCTRL_MS=50` (437e8a1) |
| **v16** | `tx_controller.py`, `morse_screen.py`, `amtor_screen.py`, `main_window.py` | TxController: Morse (Paket 2a) + AMTOR (Paket 2b); CONNECTED triggers `on_send_start()`; PTOVER for ARQ EOT (8087564) |

---

## Test Environment

- TNC: AEA PK-232MBX, Firmware v7.1
- Software: PK232PY v0.1, Python 3, PyQt6
- OS: Windows 11
- Serial capture: AirDrive USB Logger
- APRS test signal: 144.800 MHz (OE3XWJ-10 digipeater area)

---

## Test Block 1 — Connection & Initialization

### T01 — Normal Connect + Host Mode
**Status:** ✅ OK (since v7/v8)

### T02 — Fast Initialization
**Status:** ✅ OK (since v4)

---

## Test Block 2 — Baudot RTTY TX/RX

### T03 — Focus without mouse click
**Status:** ✅ OK (since v7/v8)

### T04 — Receive (RECEIVE active)
**Status:** ✅ OK (since v4)

### T05 — Pre-type during RECEIVE then SEND
**Status:** ✅ OK (v10)

### T06 — Live typing during active SEND
**Status:** ✅ OK (v10)

### T07 — SEND → RECEIVE transition
**Status:** ✅ OK (v10)

### T08 — "Still to transmit" warning
**Status:** ✅ OK (v10)

### T09 — SEND button second click → RECEIVE
**Status:** ✅ OK (v10)

### T10 — ALT+X / ALT+R keyboard shortcuts
**Status:** ✅ OK (v10)

### T11 — CTRL+D EOT marker
**Status:** ✅ OK (v10)

### T12 — CTRL+D Backspace (atomic delete)
**Status:** ✅ OK (v10)

### T13 — Edit protection for sent chars
**Status:** ✅ OK (v10)

### T14 — Edit with Backspace in unsent zone
**Status:** ✅ OK (v10)

### T15 — Paste (CTRL+V)
**Status:** ✅ OK (v10b)

### T16 — TX buffer full
**Status:** ✅ OK (v10b)

### T17 — Clear TX during SEND
**Status:** ⬜ OPEN

### T18 — Multi-cycle colour test
**Status:** ⬜ OPEN

---

## Test Block 2b — CW/Morse TxController (Paket 2a / 437e8a1)

### T69 — Morse SEND: ACK-Färbung + genau 1 [TX] pro Zeichen
1. Host Mode aktiv → ComboBox → **CW / Morse** → **SEND**
2. Einige Buchstaben tippen (z.B. "CQ CQ")

**Expected result:**
- Jedes Zeichen erscheint nach DATA_ACK grün/ACK-gefärbt im TX-Fenster
  (identisches Verhalten wie Baudot RTTY)
- Im Monitor: genau EIN `[TX]`-Eintrag pro Tastendruck — kein Doppelsenden
- Sendefluss flüssig; stockt er → `_MORSE_TXCTRL_MS` in `main_window.py`
  senken (derzeit 50 ms)

**Diagnose bei Fehler:**
- Doppelsenden → `char_ready`-Guard in `_wire_mode_callbacks` prüfen
- Zeichen nicht gefärbt → `char_typed`-Verbindung zu `TxController` prüfen

**Status:** ⬜ OPEN (Hardware-Test ausstehend)

---

### T70 — Morse CTRL+D EOT: wartet auf letztes Zeichen
1. SEND aktiv → Text "599" tippen → **CTRL+D** drücken
   ([^D] erscheint orange im TX-Fenster)
2. Nichts weiter tun — warten

**Expected result:**
- TNC sendet "599" vollständig aus
- ERST nach DATA_ACK des letzten Zeichens schaltet App auf RECEIVE (RC)
- Kein vorzeitiges Umschalten mittendrin

**Diagnose bei Fehler:**
- Schaltet zu früh → `_ack_idx`-zu-`_eot_positions`-Zuordnung in
  `tx_controller.py` prüfen

**Status:** ⬜ OPEN (Hardware-Test ausstehend)

---

### T71 — Morse Macro mit eingebettetem [^D]
1. Macro anlegen: Text + [^D] am Ende (z.B. "73 DE OE3GAS [^D]")
2. SEND → Macro-Button klicken

**Expected result:**
- Macro vollständig gesendet, danach RECEIVE
- Umschaltung erst nach letztem bestätigtem Zeichen — nicht mittendrin
- Kein Crash (war vorher latenter Bug: Macro-Pfad emittiert `char_typed`,
  das alte Plain-QTextEdit hatte dieses Signal nicht)

**Status:** ⬜ OPEN (Hardware-Test ausstehend)

---

### T72 — Morse WPM-Tempo: Software interferiert nicht
1. MSPEED-Spinbox auf verschiedene WPM-Werte setzen (z.B. 10, 20, 40 WPM)
2. Text senden, Tempo beobachten

**Expected result:**
- Sendetempo ausschließlich vom TNC (MSPEED-Einstellung) gesteuert
- Software-Timer (`_MORSE_TXCTRL_MS = 50`) bremst den Fluss nicht und
  läuft dem TNC nicht vor
- Kein BUFFER_FULL-Dialog bei normalem Text

**Status:** ⬜ OPEN (Hardware-Test ausstehend)

---

## Test Block 2c — AMTOR TxController (Paket 2b / 8087564)

### T73 — AMTOR Link-Message-Text: CONNECTED erkennbar
**KRITISCH — muss als erster AMTOR-Test durchgeführt werden.**
Paket 2b aktiviert den TxController beim Empfang des Link-Message-Texts
"connected". Dieser Test verifiziert, dass der TNC tatsächlich diesen
Text schickt.

1. Host Mode aktiv → ComboBox → **AMTOR**
2. Monitor-Fenster öffnen (alle Frames sichtbar)
3. ARQ-Call zu einer zweiten AMTOR-Station aufbauen
   (btn_arq → Ziel-SELCAL eingeben → Verbindung abwarten)
4. Monitor beobachten während des Verbindungsaufbaus

**Expected result:**
- Im Monitor erscheint ein Link-Message-Frame mit dem Text
  "CONNECTED" (Groß-/Kleinschreibung egal, da `msg.lower()` verwendet)
- Unmittelbar danach im Monitor:
  `[AMTOR] CONNECTED → TxController started`
- Status-Pill auf AmtorScreen zeigt **● CONNECTED** (grün)

**Diagnose bei Fehler — CONNECTED-Text fehlt oder anders:**
- Monitor zeigt anderen Text (z.B. "LINK ESTABLISHED", "ARQ LINK UP"
  oder ähnliches) → `_make_link_handler()` in `main_window.py` anpassen:
  den `"connected" in m`-Check um den tatsächlichen TNC-Text erweitern.
  Exakten Text aus Monitor-Log entnehmen und in CC melden.
- `[AMTOR] CONNECTED → TxController started` fehlt →
  `on_link_message`-Route in `_wire_mode_callbacks` prüfen

**Status:** ⬜ OPEN (Hardware-Test ausstehend, zweite AMTOR-Station
benötigt)

---

### T74 — AMTOR ARQ TX: ACK-Färbung + 1 [TX] pro Zeichen
*Voraussetzung: T73 bestanden (CONNECTED erkannt, TxController gestartet)*

1. AMTOR, ARQ-Verbindung steht (● CONNECTED) → Zeichen tippen

**Expected result:**
- Jedes Zeichen erscheint nach DATA_ACK grün/ACK-gefärbt im TX-Fenster
- Im Monitor: genau EIN `[TX]`-Eintrag pro Zeichen
- Sendefluss flüssig (3-Zeichen-ARQ-Blöcke, TNC steuert 100-Bd-Timing)

**Diagnose bei Fehler:**
- Zeichen werden nicht gesendet → TxController nicht gestartet (T73-Diagnose)
- Doppelsenden → `char_ready`-Guard in `_wire_mode_callbacks` prüfen

**Status:** ⬜ OPEN (Hardware-Test ausstehend, zweite AMTOR-Station
benötigt)

---

### T75 — AMTOR ARQ CTRL+D EOT: PTOVER-Rollentausch
*Voraussetzung: T74 bestanden*

1. ARQ-Verbindung steht → Text "599 DE OE3GAS" tippen → **CTRL+D**
2. Warten bis alle Zeichen gesendet

**Expected result:**
- Nach DATA_ACK des letzten Zeichens erscheint im Monitor:
  `[AMTOR] EOT — PTOVER (\x1A) sent, ARQ turnaround`
- ARQ-Verbindung bleibt aktiv (kein DISCONNECT)
- ISS↔IRS-Rollentausch: Gegenstation wird zur sendenden Station
- NICHT: sofortiger Link-Abbruch oder RC-Befehl

**Diagnose bei Fehler:**
- Link bricht ab → fälschlicherweise OV-Befehl statt \x1A gesendet
- Kein Rollentausch → PTOVER-Zeichen nicht als $1A vom TNC erkannt
  (Betriebsart prüfen: nur in AMTOR-ARQ, nicht in FEC)

**Status:** ⬜ OPEN (Hardware-Test ausstehend, zweite AMTOR-Station
benötigt)

---

### T76 — AMTOR ARQ CTRL+D in Macro
*Voraussetzung: T75 bestanden*

1. Macro mit eingebettetem [^D] anlegen (z.B. "599 [^D]")
2. ARQ-Verbindung steht → Macro abspielen

**Expected result:**
- Macro vollständig gesendet, dann PTOVER-Rollentausch
- Kein vorzeitiges Umschalten — erst nach letztem ACK

**Status:** ⬜ OPEN (Hardware-Test ausstehend, zweite AMTOR-Station
benötigt)

---

### T77 — AMTOR FEC TX: Zeichen fließen, kein PTOVER
*FEC braucht keine zweite Station — Rundspruch ohne ARQ-Verbindung.*

1. ComboBox → AMTOR → **btn_fec** drücken (FEC-Modus aktivieren)
2. Text senden
3. CTRL+D drücken

**Expected result:**
- Zeichen werden gesendet und ACK-gefärbt
- Bei [^D]: `on_send_stop()` wird aufgerufen (kein PTOVER \x1A)
- Monitor zeigt: `[AMTOR] EOT — FEC TX done, controller stopped`
- KEIN Link-Abbruch (es gab keine ARQ-Verbindung)

**Diagnose bei Fehler:**
- PTOVER wird in FEC gesendet → btn_fec.isChecked()-Abfrage in
  `_on_baudot_eot()` prüfen

**Status:** ⬜ OPEN (Hardware-Test ausstehend)

---

### T78 — AMTOR DISCONNECT: TxController gestoppt
*Voraussetzung: ARQ-Verbindung aktiv*

1. ARQ-Verbindung steht, Text im TX-Fenster → Verbindung trennen
   (btn_stby oder Gegenstation bricht ab)

**Expected result:**
- Monitor zeigt: `[AMTOR] DISCONNECTED → TxController stopped`
- Status-Pill → **● STBY**
- Kein weiterer TX-Versuch nach Disconnect

**Status:** ⬜ OPEN (Hardware-Test ausstehend, zweite AMTOR-Station
benötigt für Gegenstation-Abbruch; STBY-Button allein testbar)

---

### T79 — AMTOR TxController: kein Doppelsenden nach Mode-Switch
1. Baudot RTTY → AMTOR → zurück zu Baudot → wieder AMTOR
   (mehrfacher Mode-Switch)
2. Nach jedem Wechsel: Text senden

**Expected result:**
- Pro Zeichen immer genau EIN [TX] im Monitor
- Keine gestapelten Signal-Verbindungen durch wiederholtes _wire_mode_callbacks

**Status:** ⬜ OPEN (Hardware-Test ausstehend)

---

## Test Block 3 — Macros

### T19–T22 — Macro buttons, edit dialog, CTRL+D in macro, paste
**Status:** ⬜ OPEN (partial — basic macro send confirmed manually)

---

## Test Block 4 — CTRL+T timed marker (v13)

### T23 — CTRL+T:n insert
### T24 — CTRL+T:n timing
### T25 — CTRL+T:n Backspace
### T26 — CTRL+T:n in macro
**Status:** ✅ OK (v13)

---

## Test Block 5 — Help System

### T27 — Help button in MacroEditDialog
### T28 — Help Viewer content
**Status:** ⬜ OPEN

---

## Test Block 6 — HF/VHF Packet

### T29 — HF Packet screen visible
1. Host Mode active → ComboBox → **HF Packet**

**Expected result:**
- HF Packet screen with Connect/Disconnect/Unproto/MailDrop/APRS(hidden) buttons
- HBAUD default 300, Monitor default 4

**Status:** ✅ OK (v11)

---

### T30 — VHF Packet screen visible
1. Host Mode active → ComboBox → **VHF Packet**

**Expected result:**
- VHF Packet screen with APRS button visible (hidden in HF Packet)
- HBAUD default 1200

**Status:** ✅ OK (v11/v15)

---

### T31 — VHF Packet init frames
1. Host Mode active → ComboBox → **VHF Packet** → check serial monitor

**Expected result:**
- `PA`, `VH Y`, `HB 1200`, `MX 4`, `SL 10`, `MN Y` frames sent and ACKed

**Status:** ✅ OK (v15 — confirmed 2026-05-17)

---

### T32 — HF Packet init frames
1. ComboBox → **HF Packet** → check serial monitor

**Expected result:**
- `PA`, `VH N`, `HB 300`, `MN Y`

**Status:** ⬜ OPEN

---

### T33 — Connect: empty Dest warning
1. VHF Packet, Dest empty → click **Connect**

**Expected result:** Warning dialog "Packet Connect"

**Status:** ⬜ OPEN

---

### T34 — Connect: CO frame sent
1. VHF Packet, Dest = "OE3XYZ-9" → click **Connect**

**Expected result:**
- Connect button pressed (blue)
- Serial: `01 40 01 43 4F ...` (CH_CMD ch=1, CO, callsign bytes)
- Status: **● CALLING**

**Status:** ⬜ OPEN

---

### T35 — CONNECTED status pill
1. TNC confirms AX.25 connection (second station)

**Expected result:**
- $50 LINK_MSG frame received
- Status pill → **● CONNECTED** (green)

**Status:** ⬜ OPEN (needs second station)

---

### T36 — DATA frame TX
1. VHF Packet, connected → type text, press Enter

**Expected result:**
- Serial: DATA frame on channel 1 with text content
- Echo appears in RX display (TX yellow)

**Status:** ⬜ OPEN (needs second station)

---

### T37 — Disconnect: DI frame
1. VHF Packet, connected → click **Disconnect**

**Expected result:**
- Serial: `01 40 01 44 49 17` (CH_CMD ch=1, DI)
- Status pill → **● STBY**

**Status:** ⬜ OPEN

---

### T38 — Unproto with digipeater path
1. UNPROTO via = "CQ VIA OE3XNR-8" → click **Unproto**

**Expected result:** Serial: `UN CQ VIA OE3XNR-8`

**Status:** ⬜ OPEN

---

### T39 — Connect and Unproto mutual exclusion
**Status:** ⬜ OPEN

---

### T40 — RX display: monitored frames (VHF/APRS)
1. VHF Packet, Monitor = 4/6, TNC tuned to 144.800 MHz
2. APRS button OFF (raw mode)

**Expected result:**
- Monitored frames in RX window with UTC timestamp `[HH:MM:SS]`
- Format: `[HH:MM:SS] SOURCE>PATH>APRS_ID <UI>:\n  PAYLOAD`
- Grey text on dark background

**Status:** ✅ OK (v15 — confirmed 2026-05-17, OE3XWJ-10 area)

---

### T41 — MHEARD Refresh
**Status:** ⬜ OPEN

### T42 — MHEARD Clear
**Status:** ⬜ OPEN

### T43 — Toggle EAS
**Status:** ⬜ OPEN

### T44 — Toggle PASSALL
**Status:** ⬜ OPEN

### T45 — HBAUD change
**Status:** ⬜ OPEN

### T46 — Monitor level change
**Status:** ⬜ OPEN

### T47 — MailDrop button
**Status:** ⬜ OPEN

### T48 — VHF vs HF Packet init frames
**Status:** ⬜ OPEN (T31 passed for VHF, T32 open for HF)

### T49 — Keyboard focus after button click
**Status:** ⬜ OPEN

### T50 — Dest and UNPROTO fields accept input
**Status:** ⬜ OPEN

### T51 — Mode switch away from Packet: VHF OFF
**Status:** ⬜ OPEN

---

## Test Block 7 — PACTOR / AMTOR Identity Labels (v12)

### T52–T58
**Status:** ⬜ OPEN

---

## Test Block 8 — APRS Decoder (v15)

### T59 — APRS button toggle
1. VHF Packet, frames already received → click **APRS** button

**Expected result:**
- Button turns amber/orange
- RX display re-renders all buffered frames as HTML cards
- Frame types correctly colour-coded:
  - Mic-E → orange, 🚐 icon
  - Position/Position+Time → blue, 📡 icon
  - Telemetry → yellow, 📊 icon
  - Weather → green, 🌦 icon
  - Message/Telem-config → pink, 📨 icon
  - Third-party → light grey, 🌐 icon

**Status:** ✅ OK (v15 — confirmed 2026-05-17)

---

### T60 — APRS toggle OFF: raw restored
1. APRS ON (HTML cards displayed) → click APRS again

**Expected result:**
- Button returns to inactive style
- RX display re-renders all frames as plain text with timestamps
- Original content fully restored, no data loss

**Status:** ✅ OK (v15 — confirmed 2026-05-17)

---

### T61 — Mic-E position decode
1. APRS ON, receive Mic-E frame (APRS-ID = TXxxxx, TWxxxx etc.)

**Expected result:**
- Latitude decoded from destination field (e.g. TXQU09 → 48.2515°N)
- Longitude decoded from info bytes (e.g. `,]kX` → 16.0965°E)
- Values geographically plausible for OE3 area
- Comment shown after `—` separator if present (e.g. frequency info)

**Status:** ✅ OK (v15 — OE3PDB-2: 48.25°N / 16.10°E confirmed)

---

### T62 — Position+Time decode
1. APRS ON, receive `@` position frame

**Expected result:**
- UTC timestamp shown (e.g. `UTC 12:13 (day 17)`)
- Lat/lon in decimal degrees
- Symbol name shown (e.g. `Digi`, `IGate`, `WX-Station`)
- Comment on second line

**Status:** ✅ OK (v15 — OE3SZA-15 Hochkogel Digipeater confirmed)

---

### T63 — Telemetry chip display
1. APRS ON, receive `T#` frame

**Expected result:**
- Seq number + digital byte on first line
- A1–A5 values as individual chips

**Status:** ✅ OK (v15 — OE1SCS-4 T#221 confirmed)

---

### T64 — Weather data chips
1. APRS ON, receive WX station frame (APEWX*, symbol `_`)

**Expected result:**
- Position decoded
- Weather chips: wind, gust, temp (°F), baro (mb), humidity (%)

**Status:** ✅ OK (v15 — OK1VCF-5 confirmed)

---

### T65 — APRS buffer cleared on mode switch
1. VHF Packet, frames received → switch to Baudot RTTY → switch back to VHF Packet

**Expected result:**
- RX display empty on return
- `_packet_raw_frames` buffer cleared
- APRS button resets to inactive

**Status:** ⬜ OPEN

---

## FAX closed-loop decode (tools/) — T66–T68

Closed-loop test path: `tools/fax_wav_generator.py` → WAV →
`tools/fax_decoder_test.py`. No TNC, radio or live audio. Generator and
decoder verified 2026-06-14; both decoder bugs (line-drift slant, header
detection) fixed in the same session.

### T66 — FAX closed-loop: weather chart
The source image is the committed, copyright-free fixture
`tools/synthetic_weatherchart.png` (deterministically generated by
`tools/make_synthetic_weatherchart.py` — regenerate with
`python tools/make_synthetic_weatherchart.py` if it is ever deleted). The real
DWD chart (`tools/Wetterkarte.jpg`, © Deutscher Wetterdienst) is gitignored and
must not be committed; it is only a local fallback.

1. From repo root: `python tools/fax_wav_generator.py`
   (generates all three WAVs into the current directory; the console must print
   `weather chart: using '…/tools/synthetic_weatherchart.png'`)
2. `python tools/fax_decoder_test.py tools/fax_test_wetterkarte.wav`
3. Mode = **Auto-detect headers**, LPM 120, IOC 576 → **Decode**

**Expected result:**
- Decode succeeds (no "No image lines decoded" error)
- Synthetic chart fully rendered, recognisable (concentric isobars, H/T pressure
  markers, coastline strokes, station plots, faint grayscale gradients)
- Status line: `Start line` set (small value), `Stop line` set,
  `Phasing offset` small (~0), `image_height` ≈ 600
- Width ≈ 905 px (IOC-576 derived — narrower than the 1152 px source; expected,
  not a defect)

**Status:** ⬜ OPEN (needs local run)

---

### T67 — FAX closed-loop: geometry/resolution pattern
1. `python tools/fax_decoder_test.py tools/fax_test_pattern.wav`
2. Decode once with **Auto-detect headers**, once with **Skip header detection**

**Expected result:**
- Circle is **round**, centred — NOT an ellipse and NOT a slanted/sheared
  parallelogram (verifies fractional-line-length fix: drift ≤ 0.02 px/line)
- Vertical lines straight (no horizontal shear top-to-bottom)
- Horizontal lines straight; thickness bars (1/2/4/8/16/32 px) individually
  distinguishable down to the resolution limit
- DIAGNOSIS POINTER: if the circle appears as an **ellipse**, LPM/IOC mismatch
  (check both set to 120 / 576); if it appears as a **parallelogram**, the
  line-drift slant has regressed (fractional line bounds in decode_wav)

**Status:** ⬜ OPEN (needs local run)

---

### T68 — FAX closed-loop: text page (slant regression check)
1. `python tools/fax_decoder_test.py tools/fax_test_text.wav`
2. Decode with **Skip header detection** first, then **Auto-detect headers**

**Expected result:**
- Lorem-Ipsum text legible, Arial metric intact
- Skip-header mode: first and last text line start in the **same column**
  (left-margin drift ≈ 0, measured ~0.0124 px/line — no parallelogram)
- Auto-detect mode: top phasing band and trailing black bar are **trimmed**
  (only the clean text block remains) — confirms header start/stop detection
- Status line: `Start line` set, `Stop line` set, `Phasing offset` small

**Status:** ⬜ OPEN (needs local run)

---

## Open Items Summary

| Priority | Topic | Tests |
|----------|-------|-------|
| High | Packet Connect/Disconnect (2nd station) | T33–T39 |
| High | Packet MHEARD | T41–T42 |
| Medium | Packet toggles/buttons | T43–T51 |
| Medium | PACTOR/AMTOR identity, focus | T52–T58 |
| Low | APRS buffer on mode switch | T65 |
| Medium | FAX closed-loop decode (tools/) — steps written, local run pending | T66–T68 |
| Low | Multi-cycle RTTY colour | T18 |
| Low | Macro full integration | T19–T22 |
| Low | Help Viewer | T27–T28 |
| Medium | CW/Morse TxController (Paket 2a) | T69–T72 |
| Medium | AMTOR TxController (Paket 2b) — T73 zuerst! | T73–T79 |

---

## Serial Capture — Reference Frames

| Frame (hex) | Meaning |
|-------------|---------|
| `01 4F 58 4D 17` | XM — PTT ON / DIDDLE start |
| `01 4F 52 43 17` | RC — switch to RECEIVE |
| `01 20 xx 17` | DATA — one character `xx` to TNC |
| `01 5F 58 58 00 17` | DATA-ACK from TNC |
| `01 40 01 43 4F xx... 17` | CH_CMD ch=1 CO callsign — AX.25 Connect |
| `01 40 01 44 49 17` | CH_CMD ch=1 DI — AX.25 Disconnect |
| `01 3F xx... 17` | Monitor frame ($3F) — APRS/AX.25 received |
| `01 50 xx... 17` | LINK_MSG ($50) — CONNECTED / DISCONNECTED |
| `01 4F 48 4F 4E 17` | HOST OFF — exit Host Mode |
| `01 4F 4D 4E xx 17` | MN — set Monitor level |
| `01 4F 48 42 xx 17` | HB — set HBAUD |
| `01 4F 56 48 xx 17` | VH — VHF ON (Y) or OFF (N) |
| `01 4F 55 4E xx 17` | UN — set UNPROTO path |

---

*Created: 2026-05-01 | Updated: 2026-06-16 (v16) | OE3GAS | PK232PY Project*
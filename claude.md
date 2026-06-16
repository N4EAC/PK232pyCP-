# CLAUDE.md — PK232PY Project Context

> This file is the single entry point for Claude Code to understand the
> PK232PY project. Read it completely before touching any source file.
> Last updated: 2026-06-16

---

## Project Name

**PK232PY** — A modern Python/PyQt6 terminal application for controlling an
AEA PK-232MBX multi-mode TNC (Terminal Node Controller) for amateur radio
digital mode operation.

- Repository: `github.com/oe3gas/PK232py`
- Local path: `E:\PK232\pk232py_repo`
- License: GPL v2
- Developer: OE3GAS (Gerhard)

---

## Purpose

PCPackRatt (the original Windows 9x software for the PK-232MBX) is no longer
maintained and barely runs on modern Windows. PK232PY replaces it with a clean
PyQt6 desktop application that supports all operating modes of the PK-232MBX:
Baudot RTTY, ASCII RTTY, AMTOR, CW/Morse, PACTOR I, NAVTEX, Signal/SIAM,
HF FAX, HF Packet (AX.25), and VHF Packet (AX.25/APRS).

Target milestone: **Beta release**.

---

## Current Status (v16 — 2026-06-16)

### What is done

All 10 opmode screens are implemented and integrated into `MainWindow` via
`QStackedWidget`:

| Screen        | File                    | TX | Macros | Notes                       |
|---------------|-------------------------|----|--------|-----------------------------|
| Baudot RTTY   | `baudot_screen.py`      | ✓  | ✓      | ITA-2, 5-bit, full TX ctrl  |
| ASCII RTTY    | `ascii_screen.py`       | ✓  | ✓      | 7-bit                       |
| AMTOR         | `amtor_screen.py`       | ✓  | ✓      | ARQ + FEC/SELFEC             |
| CW / Morse    | `morse_screen.py`       | ✓  | ✓      | 5–99 WPM                    |
| PACTOR I      | `pactor_screen.py`      | ✓  | ✓      | ARQ + FEC/Unproto            |
| NAVTEX        | `navtex_screen.py`      | —  | —      | Receive only                |
| Signal/SIAM   | `signal_screen.py`      | —  | —      | Receive only                |
| HF FAX        | `fax_screen.py`         | —  | —      | Receive only, image display |
| HF Packet     | `packet_screen.py`      | ✓  | —      | AX.25, APRS decode          |
| VHF Packet    | `packet_screen.py`      | ✓  | —      | AX.25, APRS, MHEARD panel   |

### Active/recently completed work

- PACTOR capability detection: `b"PACTOR"` in boot banner → `SerialManager.has_pactor = True`
- `write_verbose_wait()` race condition fixed: 120 ms idle detection (`_IDLE_S = 0.12`)
- APRS decoder: Mic-E, Position, Telemetry, Weather (T# / WX chips confirmed OK)
- RTTY TX fully reimplemented with `char_ready = pyqtSignal(str)` in `RttyBaseScreen`
- `ScreenFocusController`: installed on individual QLineEdit fields (le_dest, le_unproto)
- Identity fields (`lbl_mycall`, `lbl_myptcall`, etc.) are QLabel, not QLineEdit
- Clear TX / Clear RX buttons on all opmode screens (TX-capable: `clear_tx_req`/
  `clear_rx_req` signal pattern wired by `MainWindow`; receive-only Signal/NAVTEX:
  local Clear RX slot; FAX: local "Clear Image" slot)
- FAX closed-loop test tooling under `tools/` (`fax_wav_generator.py` +
  `fax_decoder_test.py`); decoder is test-only and never shipped

### Open / next sprint

- Packet: Connect/Disconnect flow (T33–T39) — needs second AX.25 station
- Packet: MHEARD panel (T41–T42)
- Packet: Remaining toggle/button tests (T43–T51)
- PACTOR/AMTOR: identity, focus tests (T52–T58)
- APRS: buffer cleared on mode switch (T65)
- CTRL+D EOT: Paket 2b (AMTOR) + Paket 3 (Stop Sending) offen — siehe
  `Backlog.md` für vollständige Architektur-Entscheidungen.
- Hardware-Test Paket 2a (Morse): steht aus.

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.14 |
| UI framework | PyQt6 |
| Serial communication | pyserial |
| Config persistence | INI file via `configparser` |
| QSO log | SQLite |
| IDE | VS Code |
| Shell | PowerShell (Windows 11) |
| Version control | Git (branch: main) |
| Virtual environment | venv at repo root |

**Hardware:** AEA PK-232MBX, firmware v7.1 (PACTOR-extended), COM16,
Prolific USB-Serial adapter, 9600 baud.

---

## Repository Structure

```
src/pk232py/
  config.py              AppConfig dataclasses + INI read/write
  main.py                Entry point
  mode_manager.py        Mode switching state machine
  comm/
    constants.py         Protocol magic numbers (SOH / ETB / CTL ranges)
    frame.py             HostFrame model, builder functions, FrameParser
    hostmode.py          High-level Host Mode command API
    serial_manager.py    SerialManager — owns the port + all threads
    pk232_hostmode_sub.py  Subprocess for Host Mode entry
  modes/
    base_mode.py         BaseMode lifecycle contract
    baudot.py / ascii_rtty.py / amtor.py / morse.py / pactor.py
    navtex.py / signal_mode.py / fax.py
    packet_hf.py / packet_vhf.py
  ui/
    main_window.py       MainWindow — QStackedWidget, menus, mode switching
    screens/
      opmode_rtty_base.py   RttyBaseScreen, MacroStore, theme helpers
      tx_controller.py      TxController — pure ACK-driven TX state machine for
                            character-ACK modes (Baudot, ASCII, Morse, soon
                            AMTOR). Was baudot_tx_controller.py until Paket 1
                            (cc2adff); no serial I/O, no widget refs.
      baudot_screen.py / ascii_screen.py / amtor_screen.py / morse_screen.py
      pactor_screen.py / navtex_screen.py / signal_screen.py / fax_screen.py
      packet_screen.py     PacketBaseScreen + HFPacketScreen + VHFPacketScreen
      screen_focus_controller.py
  help/                  Markdown help files
  log/                   QSO log (SQLite)
  macros/                Macro system
  maildrop/              MailDrop (TNC mailbox)

tools/                   Standalone dev/test tools (NOT part of the shipped app)
  fax_wav_generator.py   WEFAX test-WAV generator (GPL v2)
  fax_decoder_test.py    Standalone WEFAX audio decoder, test-only (GPL v3)
  README.md              Scope + licence note for tools/
```

---

## Important Conventions

### 1. Source of truth

**`pk232py_sources.txt`** (generated by `Sources2Text.ps1`) is the single
authoritative source for all code. All code analysis and verification runs
against this file. Git branch/hash are irrelevant to the working process.

The export now covers `src/pk232py/**/*.py` (production code first) **and**
`tools/**/*.py` (standalone tools, listed after). Markdown is still exported
only from `src/pk232py/help/` — so `tools/README.md` is not included, which
is fine.

### 2. Workflow

```
1. Discuss + analyse in Claude.ai project context
2. Make file changes directly via Claude Code terminal:
   cd E:\PK232\pk232py_repo  →  claude
3. After changes: run Sources2Text.ps1
4. Upload pk232py_sources.txt to Claude project knowledge
5. Report "sources aktualisiert"
```

No patch scripts. No intermediate copies. One file per module per commit.

### 3. Serial communication — CRITICAL

**ALWAYS use direct serial I/O** (`port.write()` / `read_until()`).
**NEVER use a worker thread or queue for Host Mode frames.**

The Windows Prolific USB driver only delivers ACKs when `read()` is called
directly on the port. Queue/worker delays ACKs until port close.
This is a proven hardware constraint — not negotiable.

After the Host Mode subprocess exits, always create a **fresh `serial.Serial()`
object**. Reusing the old object causes 20–35 second buffering delays.

### 4. TNC Protocol facts (firmware v7.1)

- Commands without PACTOR option → `?What?`: `MYPTCALL`, `PT200`, `PTOVER`,
  `PTHUFF`, `ARQTOL`, `MOPT`, `EXPERT OFF`
- Verbose mode commands require `\r\n` (CR+LF) termination
- Wakeup: single `$2A` (`*`) byte, no CR needed
- Host Mode exit binary sequence: `$01 $4F $48 $4F $4E $17` (NOT text `HOST OFF\r`)
- Both `HP Y` and `HP $00` are valid success responses
- `MOPT` = Morse Option (CW); `ARQTOL` = AMTOR ARQ tolerance
- `PT` mnemonic = PACTIME, not PACTOR. PACTOR activation = verbose `PACTOR\r\n`
- FAX mode stays in Host Mode (FA command); does not exit it

### 5. UI conventions

- All UI text in **English**
- `Qt.FocusPolicy.NoFocus` on **all** QPushButtons (never steal TX focus)
- `QTimer.singleShot(0)` for initial TX window focus after widget construction
- Block cursor via `setCursorWidth(averageCharWidth())` in `style_tx_widget()`
- `QTextEdit.insertPlainText()` — not `append()` — for streaming characters
- Filter `\r` characters before display
- Mode name keys in screen dict must exactly match `ModeManager.ALL_MODES` constants
- Identity fields are `QLabel` (not `QLineEdit`), populated from `AppConfig`
- `ScreenFocusController` installed only on editable `QLineEdit` fields

### 6. EventFilter architecture (two levels + controller)

**Level 1 — MainWindow (app-wide):** `QApplication.instance().installEventFilter(self)`
Intercepts all keypresses. Redirects to `tx_input` unless: modal dialog open,
ALT+X/ALT+R shortcut, `screen.focus_ctrl.is_active() == True`, or `obj is tx_input`.

**Level 2 — Opmode screen (widget-scoped):** `self.installEventFilter(self)`
Fallback for cases where Level 1 doesn't redirect. Uses parent-chain walk
because `obj` may be an internal Qt child widget.

**Level 3 — ScreenFocusController:** `QObject` installed directly on individual
QLineEdit fields. Reliable FocusIn/FocusOut tracking at field scope.

### 7. Opmode switch state machine

Four states: `M0` NO MODE → `M1` ACTIVATING → `M2` ACTIVE → `M3` SWITCHING.
The 300 ms `_ACTIVATE_DELAY_MS` timer fires `_send_init_frames()`.
Path B (PACTOR) temporarily exits Host Mode — see `OPMODE_SWITCH_STATE_MACHINE.md`.

### 8. Connection state machine

Eight states: `C0` OFFLINE → `C1` PORT OPEN → `C2` INITIALISING →
`C3` VERBOSE → `C4` UPLOADING → `C5` SWITCHING → `C6` HOST MODE → `C7` ERROR.
See `SERIAL_CONNECTION_STATE_MACHINE.md` for full detail.

### 9. PACTOR capability detection

`b"PACTOR"` in boot banner → `SerialManager.has_pactor = True`.
Default is `True` when no banner is present (permissive).
When `False`: PACTOR ComboBox and Parameters menu are disabled; upload
commands (`MYPTCALL`, `ARQTOL`, `MOPT`, `EXPERT OFF`, `PTHUFF`, `PT200`,
`PTOVER`) are skipped.

### 10. File encoding

Python-generated files must not be deployed via PowerShell copy
(encoding corruption risk). Use patch scripts with explicit UTF-8 or
Windows `copy` command. `main_window.py` is prone to corruption at ~line 1503
(second file appended) — check for this and delete manually if needed.

### 11. TxController architecture

`TxController` (`tx_controller.py`, renamed from `BaudotTxController` in
Paket 1 / cc2adff) is the **mode-agnostic** ACK-driven TX/RX state machine —
no serial I/O, no widget refs. Key learnings from the 2026-06-16 session:

- `_is_txctrl_mode(mode)` in `main_window.py` is the **single source of truth**
  for which modes are driven by `TxController`. Currently
  `("Baudot RTTY", "ASCII RTTY", "CW / Morse")`; AMTOR is added in Paket 2b.
- **Morse** is ACK-paced — the TNC controls WPM. The software timer is only an
  overflow safety net: `_MORSE_TXCTRL_MS = 50` in `main_window.py`, fed via
  `set_mspeed_ms()` (direct-ms interval for modes with no meaningful Baud rate).
- **AMTOR EOT ≠ RC** (verified against the Technical Reference Manual):
  AMTOR-ARQ `[^D]` → `OV` (OVER — polite turnaround, ISS↔IRS role swap, link
  stays up); AMTOR-FEC `[^D]` → `RC` (no connection concept, like Baudot).
- **Packet uses NO TxController and NO `[^D]`.** AX.25 packetises at the ETB
  character and has no character-by-character ACK, so the EOT-marker concept
  does not fit. Packet needs a Stop-button instead of an EOT marker.
- **Stop Sending** (Paket 3, open): AMTOR → `AM` (mnemonic; standby + flush TNC
  TX buffer — NOT `R`, which does not flush); Baudot/ASCII/Morse → `RC` +
  flush the local `TxController` buffer (`on_send_stop()` + `clear()`).
- `char_ready` guard in `_wire_mode_callbacks`: only wire it when
  `not hasattr(tx, 'char_typed')`. A `TxInputWidget` already emits `char_typed`,
  so wiring `char_ready` as well would double-send.

See `Backlog.md` (TxController section) and `TX_STATE_MACHINE.md` for detail.

---

## Reference Documents in Project Knowledge

| File | Purpose |
|------|---------|
| `UI_DESIGN.md` | Authoritative UI design decisions (screen hierarchy, theme, buttons) |
| `MOCKUP_STATUS.md` | Screen implementation status and roadmap |
| `SERIAL_CONNECTION_STATE_MACHINE.md` | 8-state connection FSM, init sequence detail |
| `OPMODE_SWITCH_STATE_MACHINE.md` | Mode switch FSM, Path A vs Path B |
| `TX_STATE_MACHINE.md` | TX character flow, paste handling, backspace sentinel |
| `Eventfilter_architecture.md` | Three-level event filter architecture |
| `Backlog.md` | Prioritised open work items |
| `Testplan.md` | Test cases T01–T72 with pass/fail status |
| `pk232py_sources.txt` | Complete source code export (authoritative) |
| `AEA-PK-232-TechnicalReferenceManual.pdf` | Hardware reference (Host Mode protocol) |
| `PPWIN.HLP` | PCPackRatt help file (reference for UI feature parity) |

---

## Open Questions / Next Steps

### Immediate (next session)

1. **Packet Connect/Disconnect** — wire CO/DI frames, CONNECTED status pill (T33–T39);
   requires second AX.25 station on 144.800 MHz
2. **Packet MHEARD** — parse MH frame into MheardPanel (T41–T42)
3. **Packet toggle/button tests** — EAS, PASSALL, HBAUD, Monitor level,
   MailDrop, VHF init frames (T43–T51)

### Medium term

4. **Clear TX / Clear RX** — add to AMTOR, HF Packet, VHF Packet, Morse screens
5. **CTRL+D (EOT)** — extend to AMTOR and CW/Morse
6. **Theme persistence** — `[UI]` section in INI, `Configure → Appearance` dialog
7. **Tooltip system** — central `tooltips.py`, apply to all screens
8. **Help system** — split `help_baudot.md` into topic files, add Help buttons

### Before beta

9. **APRS Phase 2** — beacon TX, beacon config UI, MHEARD APRS stations
10. **PACTOR/AMTOR identity** — wire parameter dialogs to TNC commands (T52–T58)
11. **Parameter integration** — load/save screen parameters from AppConfig on mode switch

---

## Learning Mode Note

The developer operates in **"Lernmodus"** — learning alongside the code.
Every non-trivial code block should be accompanied by a brief explanation of:
- **What** it does
- **Why** this approach was chosen over alternatives
- Any **traps or gotchas** specific to PyQt6 or the PK-232 protocol

Prefer simple, proven patterns over clever solutions.
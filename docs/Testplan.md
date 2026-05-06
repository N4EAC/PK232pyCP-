# PK232PY — Test Plan
**Updated: 2026-05-05 (v12) — Focus controller, identity labels, PACTOR screen fix**
**Previous stand: 2026-05-05 (v11)**

---

## Change History

| Version | Files | Content |
|---------|-------|---------|
| v3 | `modes/morse.py`, `modes/amtor.py`, `modes/signal_analysis.py` | Mode name fixes (`"CW/Morse"` → `"CW / Morse"` etc.) |
| v4 | `main_window.py` | TX window yellow, `_flush_tx_buffer`, RX colour in `_log_terminal`, Fast Init |
| v5 | `main_window.py` | Removed duplicate methods (`_on_screen_send`, `_on_screen_receive`) |
| v6 | `main_window.py` | No RC for Baudot/ASCII/Morse; no auto-flush on SEND toggle |
| v7 | `main_window.py` | `QApplication.instance().installEventFilter(self)` — app-wide filter |
| v8 | `main_window.py` | Full TX logic in app-wide `eventFilter`: `insertPlainText` + `char_ready.emit` |
| v8b | `main_window.py` | `QApplication` added to global imports |
| v9 | `main_window.py` | Buffer flush on SEND toggle via `_on_rtty_char_ready` |
| **v10** | `ui/screens/baudot_tx_controller.py` *(new)* | `BaudotTxController` — rate-limited TX, DATA_ACK tracking, EOT marker, three-index system |
| **v10** | `ui/screens/ui_theme.py` *(new)* | Theme system extracted from `opmode_rtty_base.py` |
| **v10** | `ui/screens/macro_store.py` *(new)* | MacroStore + MacroEditDialog extracted from `opmode_rtty_base.py` |
| **v10** | `ui/screens/opmode_rtty_base.py` | `TxInputWidget` added: edit protection, colour_at, CTRL+D, paste handling |
| **v10** | `ui/main_window.py` | Integration of `BaudotTxController`: XM ACK dispatch, DATA_ACK, ALT+X/R shortcuts, CTRL+D shortcut conflict fixed |
| **v10b** | `ui/screens/baudot_tx_controller.py` | TX_MAX=512, pending_len (counts unsent only), BUFFER_FULL warning |
| **v10b** | `ui/screens/opmode_rtty_base.py` | Paste fix (external apps), pre-truncate at TX_MAX, _ctrl_ref cache, SEND/RECEIVE button labels with ALT shortcuts |
| **v10b** | `ui/main_window.py` | MSPEED fix in _on_screen_rbaud_changed, modal dialog guard in eventFilter, _buffer_full_shown flag |
| **v10b** | `ui/screens/macro_store.py` | Help button in MacroEditDialog |
| **v10b** | `ui/screens/help_viewer.py` *(new)* | HelpViewer QDialog with Markdown renderer, topic navigation |
| **v10b** | `help/help_baudot.md` *(new)* | Baudot RTTY help file |
| **v11** | `ui/screens/packet_screen.py` *(new)* | `HFPacketScreen`, `VHFPacketScreen`, `MheardPanel` — Packet opmode screens |
| **v11** | `ui/screens/__init__.py` | Added `HFPacketScreen`, `VHFPacketScreen` exports |
| **v11** | `ui/main_window.py` | Packet integration: `_wire_packet_buttons()`, 8 Packet slots, `_switch_opmode()` MYCALL init |
| **v12** | `ui/screens/screen_focus_controller.py` *(new)* | `ScreenFocusController` — field-scoped FocusIn/FocusOut tracking for editable QLineEdits |
| **v12** | `ui/main_window.py` | EventFilter: `pass` → `return` fix; `focus_ctrl.is_active()` check replaces unreliable isinstance |
| **v12** | `ui/main_window.py` | `_switch_opmode()`: populate PACTOR/AMTOR/Packet identity labels from AppConfig on mode switch |
| **v12** | `ui/main_window.py` | `_update_host_mode_ui()`: `mode_has_screen` guard — PACTOR stays on opmode screen |
| **v12** | `ui/main_window.py` | `_wire_pactor_buttons()`: PactorScreen type guard — prevents double Connect dialog |
| **v12** | `ui/screens/packet_screen.py` | `le_mycall` → `lbl_mycall` (QLabel, display-only) |
| **v12** | `ui/screens/pactor_screen.py` | `le_myptcall` → `lbl_myptcall` (QLabel, display-only) |
| **v12** | `ui/screens/amtor_screen.py` | `le_myselcal/myaltcal/myident` → QLabel (display-only) |
| **v12** | `ui/screens/*.py` | EventFilter: parent-chain walk `_is_input()` in all TX screens |

---

## Test Environment

- TNC: AEA PK-232MBX, Firmware v7.1
- Software: PK232PY v0.1, Python 3, PyQt6
- OS: Windows 11
- Serial capture: AirDrive USB Logger

---

## Test Block 1 — Connection & Initialization

### T01 — Normal Connect + Host Mode
1. Select `TNC → Connect + Host Mode`
2. Parameter upload runs through verbose terminal
3. Host Mode is activated

**Expected result:**
- Status indicator: blue **HOST MODE**
- ComboBox shows **Baudot RTTY**
- RECEIVE button **green**
- TX window has immediate focus (no mouse click needed)

**Status:** ✅ OK (since Patch v7/v8)

---

### T02 — Fast Initialization
1. Open `TNC → TNC Configuration`
2. Enable **Fast Initialization** → OK
3. Select `TNC → Connect + Host Mode`

**Expected result:**
- Verbose terminal shows: `[SYS] Fast Init — parameter upload skipped`
- No long parameter upload
- Host Mode is still activated

**Status:** ✅ OK (since Patch v4)

---

## Test Block 2 — Baudot RTTY TX/RX

### T03 — Focus without mouse click
1. Host Mode active, Baudot screen visible
2. Type immediately (without clicking TX window first)

**Expected result:**
- Characters appear **immediately** in TX window (yellow)
- No mouse click required

**Status:** ✅ OK (since Patch v7/v8)

---

### T04 — Receive (RECEIVE active)
1. RECEIVE button is green
2. TNC receives Baudot signal

**Expected result:**
- Received characters appear in RX window in **blue** (`#88ccff`)

**Status:** ✅ OK (since Patch v4)

---

### T05 — Pre-type during RECEIVE then SEND
1. RECEIVE active → type text in TX window (e.g. `CQ CQ DE OE3GAS`)
2. Text appears yellow in TX window (buffered)
3. Press SEND

**Expected result:**
- Buffer sent character by character at configured MSPEED rate
- Each character appears in RX window (amber = TX confirmed)
- TX characters turn **inverse yellow** (black on yellow) after DATA_ACK
- Serial capture: `01 4F 58 4D 17` (XM) followed by `01 20 xx 17` per character

**Status:** ✅ OK (v10 — BaudotTxController rate-limited flush)

---

### T06 — Live typing during active SEND
1. SEND active (red button)
2. Type characters

**Expected result:**
- Each keystroke appears **immediately** in TX window (yellow)
- After DATA_ACK: character turns **inverse yellow** in TX, appears **amber** in RX
- Serial capture: `01 20 xx 17` per character at MSPEED rate

**Status:** ✅ OK (v10)

---

### T07 — SEND → RECEIVE transition
1. SEND active, text has been sent
2. Press RECEIVE

**Expected result:**
- RECEIVE button turns **green**
- SEND button turns **grey**
- RC command sent to TNC
- Any unsent chars remain in TX window (yellow)

**Status:** ✅ OK (v10)

---

### T08 — "Still to transmit" warning
1. RECEIVE active → type a lot of text
2. Press SEND → immediately press RECEIVE

**Expected result:**
- Status bar shows: `⚠ TX buffer not empty — unsent chars remain`
- Remaining text stays in TX window (yellow, unsent)

**Status:** ✅ OK (v10 — warning moved to status bar)

---

### T09 — SEND button second click → RECEIVE
1. SEND active (red, blinking)
2. Click SEND again (second click = toggle off)

**Expected result:**
- SEND button turns **grey**
- RECEIVE button turns **green** automatically
- RC command sent to TNC

**Status:** ✅ OK (v10)

---

### T10 — ALT+X / ALT+R keyboard shortcuts
1. Host Mode active, Baudot screen
2. Press ALT+X → SEND activates
3. Press ALT+R → RECEIVE activates

**Expected result:**
- ALT+X: SEND button turns red, blinking; PTT activates
- ALT+R: RECEIVE button turns green; RC sent
- Button labels show `Send  [ALT+X]` and `Receive  [ALT+R]`

**Status:** ✅ OK (v10)

---

### T11 — CTRL+D EOT marker
1. RECEIVE active → type text, e.g. `CQ DE OE3GAS`
2. Press CTRL+D → `[^D]` marker appears (orange background)
3. Type more text after it, e.g. `PSE K`
4. Press SEND

**Expected result:**
- Text before `[^D]` is sent at MSPEED rate
- When `[^D]` is reached: automatic switch to RECEIVE
- Text after `[^D]` remains in TX (yellow, unsent)
- `[^D]` marker: white text on orange background

**Status:** ✅ OK (v10)

---

### T12 — CTRL+D Backspace (atomic delete)
1. Type `[^D]` with CTRL+D
2. Press Backspace once

**Expected result:**
- Entire `[^D]` marker deleted in one keystroke

**Status:** ✅ OK (v10)

---

### T13 — Edit protection for sent chars
1. Type and send some text (e.g. 5× `a`)
2. Press RECEIVE
3. Try to Backspace into the sent (inverse yellow) zone

**Expected result:**
- Backspace stops at the boundary of sent characters
- Sent characters (inverse yellow) cannot be deleted
- No `QTextCursor::setPosition out of range` warnings in log

**Status:** ✅ OK (v10)

---

### T14 — Edit with Backspace in unsent zone
1. RECEIVE active → type 20+ characters over multiple lines
2. Delete all with Backspace

**Expected result:**
- All typed (unsent) characters deletable
- No `QTextCursor out of range` errors in log

**Status:** ✅ OK (v10)

---

### T15 — Paste (CTRL+V)
1. Copy text to clipboard from another application
2. RECEIVE active → paste with CTRL+V into TX window

**Expected result:**
- Pasted text appears in TX window (yellow)
- On SEND: pasted text is sent at MSPEED rate
- Newlines in pasted text generate CR/LF frames

**Status:** ✅ OK (v10b)

---

### T16 — TX buffer full
1. RECEIVE active → paste text repeatedly until over 512 characters

**Expected result:**
- Buffer limit: 512 unsent characters
- Exactly ONE QMessageBox warning
- Text truncated at 512 chars, excess discarded

**Status:** ✅ OK (v10b)

---

### T17 — Clear TX during SEND
1. SEND active → click "Clear TX"

**Expected result:**
- TX window cleared
- `BaudotTxController` state reset
- SEND remains active (PTT stays on)

**Status:** ⬜ OPEN

---

### T18 — Multi-cycle SEND/RECEIVE colouring
1. Type text → SEND → wait for some ACKs → RECEIVE
2. Type more text → SEND again
3. Repeat 3× cycles

**Expected result:**
- Sent chars (inverse yellow) remain correctly coloured across cycles
- No position drift or wrong colouring

**Status:** ⬜ OPEN

---

## Test Block 3 — Macros

### T19 — Macro send during RECEIVE
1. RECEIVE active
2. Click Macro 1 button

**Expected result:**
- Macro text appears in TX window (yellow)
- On SEND: macro text sent at MSPEED rate

**Status:** ⬜ OPEN

---

### T20 — Macro send during SEND
1. SEND active
2. Click Macro 1 button

**Expected result:**
- Macro text immediately queued and sent at MSPEED rate
- Characters appear amber in RX after DATA_ACK

**Status:** ⬜ OPEN

---

### T21 — Macro Edit dialog
1. Click "Edit Macros"
2. Change name and text of Macro 1
3. Click Save → Close
4. Click Macro 1 button

**Expected result:**
- Save writes `Macro.txt`
- Button label updates to new name
- Sending uses new macro text

**Status:** ⬜ OPEN

---

### T22 — Macro with CTRL+D
1. Edit Macro 1 to contain text with `[^D]`
2. Send macro

**Expected result:**
- EOT marker in macro triggers RECEIVE at correct position

**Status:** ⬜ OPEN

---

## Test Block 4 — Mode switching

### T23 — Switch to ASCII RTTY
1. ComboBox → **ASCII RTTY**

**Expected result:**
- ASCII screen appears, RECEIVE button green, TX/SEND works as T05–T08

**Status:** ✅ OK (v10)

---

### T24 — Switch to CW / Morse
1. ComboBox → **CW / Morse**

**Expected result:**
- Morse screen appears, MSPEED/MWEIGHT fields visible

**Status:** ✅ OK (since Patch v3)

---

### T25 — Switch back to Baudot RTTY
1. From ASCII or Morse → ComboBox → **Baudot RTTY**

**Expected result:**
- Baudot screen correct, `BaudotTxController` state clean

**Status:** ✅ OK (v10)

---

## Test Block 5 — MSPEED

### T26 — MSPEED 45 Baud
1. Set RBAUD to 45
2. Type and send text during SEND

**Expected result:**
- Visible slowdown: ~167ms per character

**Status:** ✅ OK (v10b)

---

### T27 — MSPEED 300 Baud
1. Set RBAUD to 300
2. Type and send text during SEND

**Expected result:**
- Fast send: ~25ms per character, no timing errors

**Status:** ✅ OK (v10b)

---

### T28 — Help Viewer
1. Click "Edit Macros"
2. Click "Help" button in MacroEditDialog

**Expected result:**
- HelpViewer dialog opens, Markdown rendered, topic navigation works

**Status:** ⬜ OPEN

---

### T29 — MacroEditDialog keyboard focus
1. Click "Edit Macros"
2. Type text in macro name or text field

**Expected result:**
- Input goes into the dialog fields (not TX window)

**Status:** ✅ OK (v10b — modal dialog guard in eventFilter)

---

## Test Block 6 — HF Packet / VHF Packet

### T30 — Mode switch to HF Packet
1. Host Mode active, ComboBox → **HF Packet**

**Expected result:**
- HF Packet screen visible, title "HF Packet"
- MYCALL label shows configured callsign or "---"
- Status pill **● DISCONNECTED**, HBAUD = 300, Monitor = 4
- MHEARD panel visible, TX window focused

**Status:** ✅ OK (v12)

---

### T31 — Mode switch to VHF Packet
1. Host Mode active, ComboBox → **VHF Packet**

**Expected result:**
- VHF Packet screen, title "VHF Packet", HBAUD = 1200
- TNC init frames in monitor: `VH Y`, `HB 1200`, `MX 4`, `SL 10`, `MN Y`

**Status:** ⬜ OPEN

---

### T32 — Keyboard focus on Packet screen
1. HF Packet screen, click Connect with empty Dest
2. Type text after warning dialog

**Expected result:**
- Warning dialog appears, after close: keystrokes go to TX window

**Status:** ⬜ OPEN

---

### T33 — AX.25 Connect
1. HF Packet, type "OE3XYZ" in Dest, click **Connect**

**Expected result:**
- Connect button green, status **● CALLING**, serial: `CO OE3XYZ`
- On TNC CONNECTED: status **● CONNECTED**

**Status:** ⬜ OPEN

---

### T34 — Connect validation (empty Dest)
1. HF Packet, Dest empty, click **Connect**

**Expected result:**
- One warning: "Please enter a destination callsign in the Dest field."
- Connect stays grey, no TNC frame sent

**Status:** ⬜ OPEN

---

### T35 — AX.25 Disconnect
1. Connected, click **Disconnect**

**Expected result:**
- Status **● DISCONNECTED**, Connect button grey, serial: DI frame

**Status:** ⬜ OPEN

---

### T36 — TX while connected
1. Connected, type text in TX, press Enter

**Expected result:**
- Serial: `$20 xx` DATA frames visible

**Status:** ⬜ OPEN

---

### T37 — Unproto TX
1. HF Packet, NOT connected, click **Unproto**

**Expected result:**
- Unproto blue, status **● UNPROTO TX**, serial: `UN CQ`

**Status:** ⬜ OPEN

---

### T38 — Unproto with digipeater path
1. UNPROTO via = "CQ VIA OE3XNR-8", click Unproto

**Expected result:**
- Serial: `UN CQ VIA OE3XNR-8`

**Status:** ⬜ OPEN

---

### T39 — Connect and Unproto mutual exclusion
1. Connect active, click Unproto

**Expected result:**
- No inconsistent state

**Status:** ⬜ OPEN

---

### T40 — RX display: monitored frames
1. HF Packet, Monitor = 4, other stations active

**Expected result:**
- Monitored frames in RX window; Monitor 0 → silent

**Status:** ⬜ OPEN

---

### T41 — MHEARD Refresh
1. HF Packet, click **Refresh** in MHEARD panel

**Expected result:**
- Serial: `MH` frame; list entries appear in panel

**Status:** ⬜ OPEN

---

### T42 — MHEARD Clear
1. MHEARD has entries, click **Clear**

**Expected result:**
- Panel clears, no TNC command sent

**Status:** ⬜ OPEN

---

### T43 — Toggle EAS
1. HF Packet, click **EAS** (green), click again (grey)

**Expected result:**
- Serial: `EA Y` then `EA N`

**Status:** ⬜ OPEN

---

### T44 — Toggle PASSALL
1. Click **PASSALL** ON then OFF

**Expected result:**
- Serial: `PA Y` then `PA N`

**Status:** ⬜ OPEN

---

### T45 — HBAUD change
1. HF Packet, change HBAUD to 1200

**Expected result:**
- Serial: `HB 1200`

**Status:** ⬜ OPEN

---

### T46 — Monitor level change
1. Change Monitor to 0

**Expected result:**
- Serial: `MN 0`

**Status:** ⬜ OPEN

---

### T47 — MailDrop button
1. HF Packet, NOT connected, click **MailDrop**

**Expected result:**
- Serial: `MI` (MDCHECK) frame

**Status:** ⬜ OPEN

---

### T48 — VHF vs HF Packet init frames
1. Switch HF Packet → VHF Packet, observe monitor

**Expected result:**
- HF: `PA`, `VH N`, `HB 300`, `MN Y`
- VHF: `PA`, `VH Y`, `HB 1200`, `MX 4`, `SL 10`, `MN Y`

**Status:** ⬜ OPEN

---

### T49 — Packet screen keyboard focus after button click
1. VHF Packet, click **PASSALL**, type text

**Expected result:**
- Text appears in TX window (not on button)

**Status:** ⬜ OPEN

---

### T50 — Dest and UNPROTO fields accept input
1. HF Packet, click Dest → type "OE3XYZ-9"
2. Click UNPROTO via → type "CQ VIA RELAY"
3. Click elsewhere → type text

**Expected result:**
- Dest and UNPROTO fields accept input correctly
- After clicking elsewhere: keystrokes → TX window

**Status:** ⬜ OPEN

---

### T51 — Mode switch away from Packet: VHF OFF
1. VHF Packet active, switch to Baudot RTTY

**Expected result:**
- Serial: `VH N`, Baudot screen appears

**Status:** ⬜ OPEN

---

## Test Block 7 — PACTOR / AMTOR Identity Labels (v12)

### T52 — PACTOR: MYPTCALL label shows configured value
1. TNC → PACTOR Parameters → MYPTCALL = "OE3GAS" → OK
2. ComboBox → **PACTOR**

**Expected result:**
- MYPTCALL label shows "OE3GAS"
- Label not editable, tooltip: "Set via TNC → PACTOR Parameters"

**Status:** ⬜ OPEN

---

### T53 — PACTOR: MYPTCALL shows "---" when default
1. MYPTCALL = "NOCALL" (default), switch to PACTOR

**Expected result:**
- MYPTCALL label shows "---"

**Status:** ⬜ OPEN

---

### T54 — AMTOR: identity labels show configured values
1. TNC → AMTOR Parameters → MYSELCAL = "OEGS", MYALTCAL = "" → OK
2. ComboBox → **AMTOR ARQ**

**Expected result:**
- MYSELCAL = "OEGS", MYALTCAL = "---", MYIDENT = "---"
- Labels not editable

**Status:** ⬜ OPEN

---

### T55 — PACTOR: Dest field accepts keyboard input
1. Host Mode, PACTOR screen, click **Dest**, type "OE3XYZ"

**Expected result:**
- "OE3XYZ" in Dest, no redirection to TX window
- After clicking elsewhere: keystrokes → TX window

**Status:** ⬜ OPEN

---

### T56 — AMTOR: Dest field accepts keyboard input
1. Host Mode, AMTOR ARQ screen, click **Dest**, type "OEGS"

**Expected result:**
- "OEGS" in Dest, no redirection to TX window

**Status:** ⬜ OPEN

---

### T57 — No double warning on empty Packet Connect
1. HF Packet, Dest empty, click **Connect**

**Expected result:**
- Exactly **ONE** warning dialog, title "Packet Connect"
- No second dialog with title "PACTOR Connect"

**Status:** ⬜ OPEN

---

### T58 — PACTOR screen visible on mode switch
1. Host Mode active, any screen, ComboBox → **PACTOR**

**Expected result:**
- PACTOR screen appears immediately, no flash to Verbose terminal

**Status:** ⬜ OPEN

---

## Open Items

| Priority | Topic | Description |
|----------|-------|-------------|
| Medium | T17 | Clear TX during active SEND |
| Medium | T18 | Multi-cycle SEND/RECEIVE colouring |
| Medium | T19–T22 | Macro tests (full integration) |
| Medium | T28 | Help Viewer |
| Medium | T31–T51 | HF/VHF Packet (screen ✅, AX.25 TX/RX pending) |
| **v12** | T52–T58 | PACTOR/AMTOR identity labels + focus + double-dialog + PACTOR screen |
| Low | MSPEED from TNC config | Auto-set MSPEED from `PK232.INI` on Host Mode activation |
| Planned | CTRL+S marker | Insert `[^S]` → switches to SEND when reached |
| Planned | CTRL+T:n marker | Insert `[^T:5]` → RECEIVE, wait n seconds, back to SEND |
| Planned | Macro control chars | Enter CTRL+D/S/T markers in MacroEditDialog |
| Phase 2 | MHEARD parsing | Parse TNC MHEARD response into panel entries |
| Phase 2 | AX.25 TX/RX | Wire DATA/LINK_MSG frames to Packet screen RX display |

---

## Serial Capture — Reference Frames

| Frame (hex) | Meaning |
|-------------|---------|
| `01 4F 58 4D 17` | XM — PTT ON / DIDDLE start |
| `01 4F 58 4D 00 17` | XM ACK |
| `01 20 xx 17` | DATA — one character `xx` to TNC |
| `01 5F 58 58 00 17` | Data-ACK from TNC (normal) |
| `01 4F 52 43 17` | RC — switch to RECEIVE |
| `01 4F 52 43 00 17` | RC ACK |
| `01 4F 48 4F 4E 17` | HOST OFF — exit Host Mode |
| `01 3F xx 17` | Monitor frame / Baudot RX character from TNC |
| `01 40 xx xx ... 17` | CH CMD — channel command (CO, DI etc.) on channel xx |
| `01 20 xx ... 17` | DATA — packet data on channel xx |
| `01 50 xx ... 17` | LINK_MSG — link state message (CONNECTED, DISCONNECTED …) |
| `01 4F 55 4E xx 17` | UN — set UNPROTO path |
| `01 4F 4D 4E xx 17` | MN — set Monitor level |
| `01 4F 48 42 xx 17` | HB — set HBAUD |
| `01 4F 56 48 xx 17` | VH — VHF ON (Y) or OFF (N) |

---

*Created: 2026-05-01 | Updated: 2026-05-05 (v12) | OE3GAS | PK232PY Project*
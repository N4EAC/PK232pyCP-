# PK232PY — Development Backlog

**Last updated:** 2026-05-05 (v12)
**Current version:** v0.1 (development)

---

## Priority 1 — Next implementation sprint

### CTRL+S control character
- Insert `[^S]` marker (blue background) in TX window
- `TxInputWidget.keyPressEvent`: detect CTRL+S, insert `[^S]`, `_doc_extra += 3`
- `TxInputWidget` Backspace: atomic delete of `[^S]`, `_doc_extra -= 3`
- `BaudotTxController.on_char_typed`: handle `\x13` sentinel → switch to SEND
- `_on_macro_clicked`: detect `[^S]` in macro text, `_doc_extra += 3`
- `MacroTextEdit.keyPressEvent`: CTRL+S support in Edit Macros dialog
- Update `TX_STATE_MACHINE.md` §8

### CTRL+T:n control character
- Insert `[^T:n]` marker (purple background) in TX window
- Variable length: `[^T:5]` = 7 chars, `[^T:12]` = 8 chars → `_doc_extra += len-1`
- Behaviour: switch to RECEIVE, wait n seconds, switch back to SEND
- Requires QTimer in BaudotTxController for the wait
- Dialog for n input (or parse from marker text)
- Update `TX_STATE_MACHINE.md` §8

### Packet — AX.25 TX/RX Integration
- Wire DATA frames ($20) from TNC to RX display
- Wire LINK_MSG frames ($50) to status pill updates (CONNECTED/DISCONNECTED)
- Parse MHEARD response into MheardPanel entries
- Test T33–T51 (all currently OPEN)

---

## Priority 2 — Improvements

### Help system — ausdifferenzieren
- `help_baudot.md` exists as one large file
- Split into topic-specific files as needed:
  - `help_macros.md`
  - `help_shortcuts.md`
  - `help_ctrl_chars.md`
- Add Help buttons to further dialogs (TNC Config, etc.)
- `TooltipManager` — central tooltip registration for buttons

### MSPEED from TNC config
- Auto-set `BaudotTxController.set_mspeed()` from `PK232.INI` MSPEED
  parameter on Host Mode activation (currently hardcoded to 50 Baud default)
- Config dialog already has MSPEED field for Morse — extend to Baudot/ASCII

### Macro control characters in dialog
- `MacroTextEdit` already supports CTRL+D
- Add CTRL+S and CTRL+T:n support when those are implemented

### T18 — Multi-cycle colour test
- Formal test: 3x SEND→RECEIVE→SEND without macros
- Verify no colour drift after each cycle

### AMTOR Dest (le_dest) Autofill
- AMTOR le_dest (Ziel-SELCAL) is editable but not pre-filled
- Consider populating from last used callsign or history list
- ARQ dialog with callsign history (noted in ui_design.md) — future item

---

## Priority 3 — Future / v0.2+

### ASCII RTTY — full TX/RX integration
- Same BaudotTxController integration as Baudot
- Currently wired but untested

### AMTOR ARQ TX integration
- Rate-limited TX not needed (AMTOR is ARQ — TNC manages retransmission)
- Colour tracking may differ

### PACTOR I TX integration
- Similar to AMTOR

### QSO Log
- SQLite-based log (`log/` directory already planned)
- Log entries from RX window content

### MailDrop
- TNC mailbox functionality (`maildrop/` directory planned)

---

## Completed (this sprint — v11/v12)

| Item | Version | Notes |
|------|---------|-------|
| HF Packet screen | v11 | `HFPacketScreen` in `packet_screen.py` |
| VHF Packet screen | v11 | `VHFPacketScreen` in `packet_screen.py` |
| Packet integration in MainWindow | v11 | `_wire_packet_buttons()`, 8 slots |
| PACTOR/AMTOR/Packet QLineEdit focus fix | v12 | `ScreenFocusController` |
| PACTOR MYPTCALL → QLabel display | v12 | Populated from AppConfig on mode switch |
| AMTOR MYSELCAL/MYALTCAL/MYIDENT → QLabel | v12 | Populated from AppConfig on mode switch |
| PACTOR opmode screen on mode switch | v12 | `mode_has_screen` guard in `_update_host_mode_ui` |
| EventFilter `pass` → `return` fix | v12 | All screens affected |

---

## Known issues (monitor)

| Issue | Severity | Notes |
|-------|----------|-------|
| `MSPEED 20 Baud → 150ms/char` in log | Minor | Config reads wrong value, falls back to 150ms. Functional but cosmetic log noise. |
| `CMD NAK: mnemonic=b'XL' error=0x07` | Minor | XL (XLINK) not supported by PK-232MBX firmware v7.1 — expected NAK |
| `CMD NAK: mnemonic=b'EE' error=0x07` | Minor | EE not supported — expected NAK |
| Testplan T18 (multi-cycle colour) | Open | Not formally tested yet |
| T30–T51 Packet tests | Open | Screen/focus tests passing; AX.25 TX/RX integration pending |

---

*OE3GAS | PK232PY Project | 2026-05-05*
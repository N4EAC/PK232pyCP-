# PK232PY — Baudot RTTY Help

## Overview

PK232PY controls the AEA PK-232MBX multimode TNC in Host Mode.
The Baudot RTTY screen provides full TX/RX capability for ITA-2 Baudot teleprinter operation.

---

## Screen Layout

```
┌─────────────────────────────────────────────────────┐
│  Send [ALT+X]          │  Receive [ALT+R]           │
├─────────────────────────────────────────────────────┤
│  Switch figs │ Switch char │ Wide Shift │ RxRev ... │
├─────────────────────────────────────────────────────┤
│                                                     │
│  RX Window  (received text appears here)            │
│                                                     │
├─────────────────────────────────────────────────────┤
│  TX Window  (type here)                             │
├─────────────────────────────────────────────────────┤
│  Macro 1 │ Macro 2 │ ... │ Clear TX │ Edit Macros  │
└─────────────────────────────────────────────────────┘
```

---

## SEND / RECEIVE

| Button | Shortcut | Function |
|--------|----------|----------|
| **Send** | `ALT+X` | PTT on, TNC starts DIDDLE, queued text is transmitted |
| **Receive** | `ALT+R` | PTT off, TNC returns to receive mode |

**Colour coding in TX window:**
- **Yellow** — typed but not yet sent
- **Black on yellow (inverse)** — sent and confirmed by TNC (DATA_ACK received)

**Colour coding in RX window:**
- **Blue** — received from the air
- **Amber** — own transmitted text (confirmed sent)

---

## Typing and Editing

Text can be typed at any time — in RECEIVE mode as preparation,
or during SEND for live transmission.

The TX window always has keyboard focus. All keystrokes go directly
into the TX window — no mouse click required.

**Edit protection:** Characters that have already been sent to the TNC
(shown in inverse yellow) cannot be deleted or modified.
Only unsent characters (yellow) can be edited with Backspace.

**TX Buffer:** Maximum 512 characters can be queued at once.
A warning dialog appears if the limit is reached.
After sending, the buffer automatically becomes available again.

---

## Control Characters

Control characters can be inserted into the TX text to automate
switching between SEND and RECEIVE. They appear as coloured markers
in the TX window and are **not transmitted over the air**.

| Key | Marker | Colour | Function |
|-----|--------|--------|----------|
| `CTRL+D` | `[^D]` | Orange | Switch to RECEIVE when this position is reached during TX |
| `CTRL+S` | `[^S]` | Blue | Switch to SEND when this position is reached *(planned)* |
| `CTRL+T` | `[^T:5]` | Purple | Switch to RECEIVE, wait n seconds, then switch back to SEND |

**Example usage with CTRL+D:**
```
CQ CQ DE OE3GAS PSE K[^D]
```
The TNC transmits up to `[^D]`, then automatically switches to RECEIVE
so the operator can listen for a reply.

**Deleting control characters:**
A single `Backspace` deletes the entire marker at once (atomic delete).

---

## RBAUD — Transmission Speed

The RBAUD (Receive/Transmit Baud Rate) setting controls the Baudot
transmission speed. It must match the speed of the station you are
communicating with.

| RBAUD | ms/char | Notes |
|-------|---------|-------|
| 45 Baud | 167ms | Standard European RTTY speed |
| 50 Baud | 150ms | Common international speed |
| 75 Baud | 100ms | |
| 100 Baud | 75ms | |
| 110 Baud | 68ms | US Teletype standard |
| 150 Baud | 50ms | |
| 200 Baud | 38ms | |
| 300 Baud | 25ms | Fast RTTY |

The RBAUD setting affects both the TNC hardware (via RB command)
and the software TX rate-limiting — characters are sent to the TNC
at exactly the rate the TNC can transmit them.

---

## Macros

Six macros are available for frequently used text (callsign, CQ calls, etc.).

- Click a **Macro button** to insert the macro text into the TX window
- Macros work in both RECEIVE and SEND mode
- Click **Edit Macros** to edit macro names and texts
- Macros are saved to `Macro.txt` in the program directory

Control characters (`[^D]`, `[^T:n]`) can also be used in
macro texts to automate TX/RX switching.

**Macro text limits:** Name max. 10 characters, text max. 200 characters.

---

## Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| `ALT+X` | Switch to SEND |
| `ALT+R` | Switch to RECEIVE |
| `CTRL+D` | Insert `[^D]` EOT marker (auto-switch to RECEIVE) |
| `CTRL+T` | Insert `[^T:n]` timed marker (RECEIVE n seconds, then auto-SEND) |
| `CTRL+V` | Paste text from clipboard into TX window |
| `Backspace` | Delete last unsent character (or entire control marker) |

---

## Mode Buttons (Row 2)

| Button | TNC Command | Function |
|--------|------------|----------|
| Switch figs | SF | Switch TNC to figures shift |
| Switch char | SC | Switch TNC to letters shift |
| Wide Shift | WS toggle | Toggle wide/narrow frequency shift |
| RxRev | RR toggle | Reverse receive mark/space polarity |
| TxRev | TR toggle | Reverse transmit mark/space polarity |
| 5Bit | 5B toggle | 5-bit Baudot mode |
| 6Bit | 6B toggle | 6-bit extended Baudot mode |
| EAS | EAS toggle | EAS (Extended Alphabet Shift) mode |

---

## Tips for Operation

- **Before calling CQ:** Set RBAUD to match your intended speed (45 or 50 Baud for most European contacts)
- **Pre-type your CQ:** Type the full CQ call ending with `[^D]` while in RECEIVE, then press SEND — the TNC will transmit and automatically return to RECEIVE
- **Timed CQ loop:** Use `[^T:n]` to listen for n seconds and automatically resume sending — e.g. `CQ DE OE3GAS K[^D][^T:5]` transmits the CQ, listens 5 seconds, then keys up again
- **Monitor your own signal:** The RX window shows your transmitted text in amber after TNC confirmation — if characters are missing, check the RBAUD setting
- **Buffer management:** For long texts, use CTRL+D markers to break transmission into segments with listening pauses

---

*PK232PY v0.1 | OE3GAS | AEA PK-232MBX Host Mode*
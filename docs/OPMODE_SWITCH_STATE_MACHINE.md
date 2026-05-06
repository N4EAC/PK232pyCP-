# PK232PY — Opmode Switch State Machine Reference

** Explanation of socument sections in german **
Abschnitt 1 — Architektur-Überblick als ASCII-Diagramm: wer ruft wen in welcher Reihenfolge.
Abschnitt 2–3 — Die 4 Zustände (M0–M3) mit vollständiger Übergangstabelle. M3 "SWITCHING" ist der kritische Zustand: _active_mode ist bereits None, der neue Modus noch nicht ACTIVE.
Abschnitt 4 — Path A vs Path B — das ist das Kernproblem bei PACTOR: Path B verlässt temporär den Host Mode. Ohne diese Doku ist das unsichtbar.
Abschnitt 7 — Der ehrlichste Abschnitt: v0.1 verwendet einen blinden 300ms-Timer statt echtem ACK-Wait. Das ist der wahrscheinlichste Ursprung von Mode-Switch-Bugs. Der Weg zu v0.2 ist klar beschrieben.
Abschnitt 9–10 — _switch_opmode und _wire_mode_callbacks im Detail — inklusive der kritischen Disconnect-Regel bei den Buttons, die bei Nichtbeachtung zu mehrfachen Sendungen führt.
Abschnitt 11 — Die Name-Mapping-Tabelle: der häufigste stille Fehler ist ein Mismatch zwischen ComboBox-Namen und ModeManager-Namen.




**Scope:** The full lifecycle of switching between operating modes
(Baudot, ASCII, AMTOR, Morse, PACTOR, NAVTEX, Signal, FAX).

**Key files:**
- `src/pk232py/mode_manager.py`       — state owner (`ModeManager`)
- `src/pk232py/modes/base_mode.py`    — `BaseMode` lifecycle contract
- `src/pk232py/ui/main_window.py`     — UI reactions (`_on_mode_changed`, `_switch_opmode`)
- `src/pk232py/modes/*.py`            — per-mode frame definitions

**Last updated:** 2026-05-01

---

## 1. Architecture Overview

Three layers participate in every mode switch:

```
User action (ComboBox / Menu)
        │
        ▼
MainWindow._on_mode_selected(name)
        │
        ▼
ModeManager.set_mode(name)          ← state machine lives here
        │
        ├── deactivate old BaseMode
        ├── send activate frames → SerialManager → TNC
        ├── QTimer(_ACTIVATE_DELAY_MS = 300 ms)
        ├── send init frames → SerialManager → TNC
        ├── call new_mode.activate()
        └── emit mode_changed(name)
                │
                ▼
        MainWindow._on_mode_changed(name)
                │
                ├── _switch_opmode(name)   → QStackedWidget.setCurrentWidget()
                ├── _wire_mode_callbacks() → connect mode data callbacks to screens
                └── status bar update
```

---

## 2. States

| State ID | Name | `_active_mode` | `_pending_mode` | `_init_timer` |
|---|---|---|---|---|
| `M0` | **NO MODE** | `None` | `None` | stopped |
| `M1` | **ACTIVATING** | `None` | new mode instance | running |
| `M2` | **ACTIVE** | mode instance | `None` | stopped |
| `M3` | **SWITCHING** | `None` | new mode instance | running |

> **M3 vs M1:** M3 is a switch from one active mode to another.
> M1 is the first activation after entering Host Mode.
> In both cases the timer fires `_send_init_frames()` after 300 ms.

---

## 3. State Transition Table

| From | Event / Trigger | Action | Next |
|---|---|---|---|
| `M0` | `set_mode(name)`, not connected | Emit `mode_switch_failed`; no change | `M0` |
| `M0` | `set_mode(name)`, Host Mode required but not active | Emit `mode_switch_failed` | `M0` |
| `M0` | `set_mode(name)`, preconditions OK | Send activate frames; start timer | `M1` |
| `M1` | `_init_timer` fires (300 ms) | Send init frames; call `activate()`; emit `mode_changed` | `M2` |
| `M2` | `set_mode(new_name)` | `old.deactivate()`; send new activate frames; start timer | `M3` |
| `M3` | `_init_timer` fires (300 ms) | Send init frames; call `activate()`; emit `mode_changed` | `M2` |
| `M2` | Host Mode exits | `active_mode.deactivate()`; clear active mode | `M0` |
| Any | TNC disconnected | `deactivate()` if active; clear all | `M0` |

---

## 4. Mode Activation Types

Not all modes activate the same way. There are two paths:

### Path A — Host Mode Activation (normal)

Used by: **Baudot RTTY, ASCII RTTY, AMTOR ARQ, AMTOR FEC, CW/Morse,
NAVTEX, Signal (SIAM), FAX, HF Packet, VHF Packet**

```
Condition: mode.get_activate_frames() returns frames
           AND serial.is_host_mode == True

Sequence:
  1. For each frame in get_activate_frames():
         serial.send_command(frame[2:4], frame[4:-1])
  2. Start _init_timer (300 ms)
  3. [timer fires] → send init frames
```

### Path B — Verbose Mode Activation

Used by: **PACTOR** (no Host Mode mnemonic on firmware v7.1)

```
Condition: mode.verbose_command is set
           AND mode.get_activate_frames() returns []

Sequence (if currently in Host Mode):
  1. serial.exit_host_mode()   ← sends HOST OFF frame
  2. sleep(0.5)
  3. serial.write_verbose(verbose_cmd)   ← e.g. b"PACTOR\r\n"
  4. Start _init_timer (300 ms)

Sequence (if already in verbose mode):
  1. serial.write_verbose(verbose_cmd)
  2. Start _init_timer (300 ms)
```

> **Warning:** Path B temporarily leaves Host Mode. The UI shows
> "SWITCHING..." during this transition. The user must be informed
> via `_log_monitor()` before calling `exit_host_mode()`.

---

## 5. Per-Mode Activate and Init Frames

| Mode | `host_command` | `get_activate_frames()` | `get_init_frames()` |
|---|---|---|---|
| Baudot RTTY | `b'BA'` | `[build_command(b'BA')]` | RBAUD, ALFRTTY, USOS, XLENGTH, ERRCHAR, RXREV, TXREV, XMITOK |
| ASCII RTTY | `b'AS'` | `[build_command(b'AS')]` | RBAUD, similar to Baudot |
| AMTOR ARQ | `b'AM'` | `[build_command(b'AM')]` | MYSELCAL, MYALTCAL, MYIDENT |
| AMTOR FEC | `b'AM'` | `[build_command(b'AM')]` | same as ARQ |
| CW / Morse | `b'CW'` | `[build_command(b'CW')]` | MSPEED, MWEIGHT, MID, MOPTT |
| NAVTEX | `b'NA'` | `[build_command(b'NA')]` | NAVMSG, NAVSTN filters |
| Signal (SIAM) | `b'SI'` | `[build_command(b'SI')]` | (none) |
| FAX | `b'FA'` | `[build_command(b'FA')]` | FAX parameters |
| PACTOR | `b''` | `[]` | MYPTCALL (if set) |
| HF Packet | `b'PA'` | `[build_command(b'PA')]` | PACLEN, TXDELAY, FRACK, … |
| VHF Packet | `b'PA'` | `[build_command(b'PA')]` | PACLEN, TXDELAY, … |

> **AMTOR ARQ and FEC share one screen** (`AmtorScreen`) and the same
> activate command (`b'AM'`). They differ only in which sub-mode button
> is pressed after activation.

---

## 6. Detailed Sequence Diagram (Host Mode path)

```
MainWindow              ModeManager            SerialManager          TNC
     │                       │                       │                  │
     │ _on_mode_selected(n)  │                       │                  │
     │──────────────────────►│                       │                  │
     │                       │ old.deactivate()      │                  │
     │                       │ _pending_mode = new   │                  │
     │                       │                       │                  │
     │                       │ send_command(BA, …)   │                  │
     │                       │──────────────────────►│                  │
     │                       │                       │──SOH 4F BA ETB──►│
     │                       │                       │◄─SOH 4F BA 00 ETB│  ACK
     │                       │                       │                  │
     │                       │ [QTimer 300 ms]        │                  │
     │                       │                       │                  │
     │                       │ send_command(RB, 45)  │                  │
     │                       │──────────────────────►│                  │
     │                       │   … (init frames) …   │                  │
     │                       │                       │                  │
     │                       │ new.activate()         │                  │
     │                       │ emit mode_changed(n)   │                  │
     │                       │──────────────────────►│                  │
     │◄──────────────────────│                       │                  │
     │ _on_mode_changed(n)   │                       │                  │
     │ _switch_opmode(n)     │                       │                  │
     │ _wire_mode_callbacks()│                       │                  │
```

---

## 7. CMD_RESP ACK Handling (v0.1 vs v0.2)

### Current behaviour (v0.1)

The 300 ms timer is a **blind delay** — init frames are sent regardless
of whether the TNC ACKed the activate command.

```python
# ModeManager._handle_cmd_resp() — v0.1
if frame.is_ack:
    logger.debug("CMD ACK: %s", frame.mnemonic)
elif frame.cmd_error is not None:
    logger.warning("CMD NAK: mnemonic=%s error=0x%02X", ...)
# No state change — ACK/NAK is only logged
```

### Planned behaviour (v0.2)

Replace blind timer with proper ACK-wait state machine:

```
send activate frame
        │
        ▼
wait for CMD_RESP ($4F) with matching mnemonic
        │
        ├── ACK ($00)  → send init frames → activate()
        ├── NAK (error) → emit mode_switch_failed; restore prev mode
        └── timeout (1 s) → treat as NAK
```

> Until v0.2 is implemented: if the TNC rejects the mode switch,
> `_active_mode` will be set to the new mode anyway.
> The TNC stays in its previous mode, causing a mismatch.
> **This is the most likely source of mode-switch bugs.**

---

## 8. MainWindow Reactions to `mode_changed`

`_on_mode_changed(name: str)` does three things in order:

### 8.1 Status bar update
```python
self._sb_mode.setText(f"Mode: {name}")
self._log_monitor(f"[SYS] Mode switched to: {name}")
```

### 8.2 ComboBox sync (without triggering another switch)
```python
display_name = self._MODE_TO_DISPLAY.get(name, name)
self._mode_combo.blockSignals(True)
idx = self._mode_combo.findText(display_name)
if idx >= 0:
    self._mode_combo.setCurrentIndex(idx)
self._mode_combo.blockSignals(False)
```

### 8.3 Screen switch + button wiring
```python
self._switch_opmode(name)     # QStackedWidget.setCurrentWidget()
self._wire_mode_callbacks()   # connect mode data callbacks to screen widgets
```

---

## 9. `_switch_opmode` — Screen Switch Details

```python
def _switch_opmode(self, name: str) -> None:
    screen = self._opmode_screens.get(name)
    self._opmode_stack.setCurrentWidget(screen)

    # RTTY/Morse: pre-set RECEIVE button green
    # (TNC starts in receive for these modes)
    if name in ("Baudot RTTY", "ASCII RTTY", "CW / Morse"):
        screen.btn_receive.blockSignals(True)
        screen.btn_receive.setChecked(True)
        screen.btn_receive.blockSignals(False)
        screen._on_receive_toggled(True)

    # Focus TX window after switch
    QTimer.singleShot(0, self._focus_active_tx)
```

**AMTOR ARQ / AMTOR FEC** share `AmtorScreen` — `setCurrentWidget`
is called with the same widget for both names. No visual switch occurs;
only the AMTOR sub-mode buttons change state.

---

## 10. `_wire_mode_callbacks` — Callback Wiring

After every mode switch, the new mode's Python callbacks are connected
to the screen's UI elements:

| Callback | Wired to |
|---|---|
| `mode.on_data_received` | `_on_mode_data_received` → appends to `rx_display` |
| `mode.on_fec_received` | same as `on_data_received` (PACTOR FEC) |
| `mode.on_echo_received` | `_on_mode_echo_received` → RX display (yellow) |
| `mode.on_link_message` | `_make_link_handler(screen)` → screen status label + monitor |

Then `_wire_screen_buttons()` is called to connect SEND/RECEIVE buttons:

```python
# SEND button
screen.btn_send.toggled.connect(self._on_screen_send)

# RECEIVE button
screen.btn_receive.toggled.connect(self._on_screen_receive)

# char_ready signal (keypress → immediate TX)
screen.char_ready.connect(self._on_rtty_char_ready)
```

> **Critical:** Each call to `_wire_screen_buttons()` first
> **disconnects** existing connections to avoid stacked signals.
> Failure to disconnect causes every keypress to be sent N times.

---

## 11. Mode Name Mapping (ComboBox vs ModeManager)

The toolbar ComboBox shows simplified display names. ModeManager uses
full internal names. The mapping is defined in `MainWindow`:

| Display name (ComboBox) | ModeManager name |
|---|---|
| `Baudot RTTY` | `"Baudot RTTY"` |
| `ASCII RTTY` | `"ASCII RTTY"` |
| `AMTOR` | `"AMTOR ARQ"` ← default on select |
| `CW / Morse` | `"CW / Morse"` |
| `PACTOR` | `"PACTOR"` |
| `NAVTEX` | `"NAVTEX"` |
| `Signal (SIAM)` | `"Signal (SIAM)"` |
| `FAX` | `"FAX"` |

```python
# MainWindow constants:
_DISPLAY_TO_MODE = {"AMTOR": "AMTOR ARQ"}
_MODE_TO_DISPLAY = {"AMTOR ARQ": "AMTOR", "AMTOR FEC": "AMTOR"}
```

> **Keys in `_opmode_screens` must exactly match ModeManager names.**
> A mismatch causes `_switch_opmode()` to silently keep the old screen.

---

## 12. Guard Conditions in `set_mode`

```python
# 1. Must be connected
if not self._serial.is_connected:
    self.mode_switch_failed.emit("TNC not connected")
    return False

# 2. Host Mode required (unless mode has verbose_command)
needs_host = not getattr(cls, 'verbose_command', None)
if needs_host and not self._serial.is_host_mode:
    self.mode_switch_failed.emit("Host Mode not active")
    return False

# 3. Mode name must be known
if name not in MODE_BY_NAME:
    self.mode_switch_failed.emit(f"Unknown mode: {name!r}")
    return False

# 4. Don't re-switch to same mode (MainWindow guard, before set_mode call)
if mm_name == self._modes.current_mode_name:
    return   # no-op
```

---

## 13. Timing Constants

| Constant | Value | Location | Purpose |
|---|---|---|---|
| `_ACTIVATE_DELAY_MS` | 300 ms | `mode_manager.py` | Blind delay between activate and init frames |
| ACK timeout (planned) | 1000 ms | v0.2 | Max wait for CMD_RESP before treating as NAK |
| `exit_host_mode` sleep | 500 ms | `serial_manager.py` | PACTOR path: settle after HOST OFF |
| `_focus_active_tx` | `QTimer(0)` | `main_window.py` | Focus TX window after event loop settles |

---

## 14. Receive-Only Modes

NAVTEX, Signal (SIAM) and FAX have no TX capability.
Their screens have no `btn_send`, no `tx_input`, no `char_ready` signal.

`_wire_screen_buttons()` uses `hasattr()` guards:

```python
if hasattr(screen, "btn_send"):
    screen.btn_send.toggled.connect(self._on_screen_send)
# if no btn_send: silently skipped — no error
```

`_tx_input` property returns `None` for these screens:
```python
@property
def _tx_input(self):
    screen = self._opmode_stack.currentWidget()
    if hasattr(screen, "tx_input"):
        return screen.tx_input
    return None   # receive-only screens
```

`_on_screen_send()` and `_on_rtty_char_ready()` check `if tx is None: return`
as the first guard.

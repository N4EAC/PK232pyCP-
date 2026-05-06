# PK232PY — EventFilter Architecture

**Created: 2026-05-05 (v11) | Updated: 2026-05-05 (v12)**

---

## Overview

PK232PY uses a **two-level EventFilter architecture** plus a dedicated
`ScreenFocusController` for screens with editable input fields.

Understanding all three layers is critical when adding new opmode screens
or QLineEdit fields — getting this wrong causes silent keystroke redirection.

---

## Level 1 — MainWindow (app-wide, authoritative)

`MainWindow.__init__` installs an **application-wide** event filter:

```python
QApplication.instance().installEventFilter(self)
```

This runs **before** any widget receives a keyboard event.

### What MainWindow.eventFilter does

```
KeyPress received
│
├─ Not in Host Mode → pass through
│
├─ Modal dialog open → pass through
│
├─ ALT+X → activate SEND button
├─ ALT+R → activate RECEIVE button
│
├─ screen.focus_ctrl.is_active() == True → return super()  ← input field active
│
├─ obj is tx_input → pass through
│
└─ anything else → tx_input.setFocus() + sendEvent(tx_input, event)
```

### The ScreenFocusController check

```python
_focus_ctrl = getattr(screen, 'focus_ctrl', None)
if _focus_ctrl is not None and _focus_ctrl.is_active():
    return super().eventFilter(obj, event)
elif obj is not tx:
    # redirect to tx_input
    ...
```

This is the reliable way to let input fields keep keyboard focus.
Previous approaches (isinstance, parent-chain walk) failed because in an
app-wide filter `obj` may be an internal Qt child widget, not the QLineEdit.

---

## Level 2 — Opmode screen filters (widget-scoped, secondary)

Each screen with a TX window also installs its own filter:

```python
self.installEventFilter(self)   # widget-scoped, NOT app-wide
```

Fires only for events on the screen widget itself — acts as fallback
when the MainWindow filter's tx redirect does not apply.

### Standard pattern (all TX screens)

```python
def eventFilter(self, obj, event) -> bool:
    if event.type() == QEvent.Type.KeyPress:
        def _is_input(w):
            """Walk parent chain — obj may be internal Qt child widget."""
            while w is not None:
                if isinstance(w, (QTextEdit, QLineEdit)):
                    return True
                w = w.parent()
            return False
        if _is_input(self.focusWidget()) or _is_input(obj):
            return super().eventFilter(obj, event)
        if hasattr(self, "tx_input") and self.tx_input is not None:
            self.tx_input.setFocus()
            QApplication.sendEvent(self.tx_input, event)
            return True
    return super().eventFilter(obj, event)
```

### Do NOT use app-wide scope in screen filters

```python
# WRONG — intercepts ALL keypresses app-wide, including other screens
QApplication.instance().installEventFilter(self)

# CORRECT
self.installEventFilter(self)
```

---

## Level 3 — ScreenFocusController (field-scoped)

`screen_focus_controller.py` — `QObject` installed directly on individual QLineEdit fields.

### Why it is needed

In an app-wide EventFilter, `obj` is not always the logical widget:
`QTextEdit` and `QLineEdit` may deliver events via internal child widgets.
So `isinstance(obj, QLineEdit)` returns False even when the user types in a
QLineEdit. `ScreenFocusController` solves this by tracking FocusIn/FocusOut
at the field level — at that scope `obj` IS the QLineEdit itself.

### Usage

```python
# In screen __init__ (after _build_ui()):
from .screen_focus_controller import ScreenFocusController
self.focus_ctrl = ScreenFocusController(
    fields=[self.le_dest],    # only EDITABLE QLineEdit fields
    parent=self,
)
```

### Which fields go in focus_ctrl

Only editable QLineEdit fields — not QLabels, not read-only fields:

| Screen           | focus_ctrl fields           | Display-only (QLabel, excluded)               |
|------------------|-----------------------------|-----------------------------------------------|
| PactorScreen     | `le_dest`                   | `lbl_myptcall`                                |
| AmtorScreen      | `le_dest`                   | `lbl_myselcal`, `lbl_myaltcal`, `lbl_myident` |
| PacketBaseScreen | `le_dest`, `le_unproto`     | `lbl_mycall`                                  |
| RttyBaseScreen   | *(no focus_ctrl)*           | —                                             |
| MorseScreen      | *(no focus_ctrl)*           | —                                             |

---

## Display-only identity fields (QLabel)

These fields show TNC parameters and are not editable. They are `QLabel`
with `QFont("Courier New", 10, Bold)`, populated from `AppConfig` in
`_switch_opmode()`. Empty or "NOCALL" values show `"---"`.

| Label          | Screen       | Config source                |
|----------------|--------------|------------------------------|
| `lbl_mycall`   | PacketBase   | `AppConfig.hf_packet.mycall` |
| `lbl_myptcall` | Pactor       | `AppConfig.pactor.myptcall`  |
| `lbl_myselcal` | Amtor        | `AppConfig.amtor.myselcal`   |
| `lbl_myaltcal` | Amtor        | `AppConfig.amtor.myaltcal`   |
| `lbl_myident`  | Amtor        | `AppConfig.amtor.myident`    |

---

## Host Mode stack switching

`_update_host_mode_ui(False)` only switches to Verbose terminal view when
no opmode screen is registered for the current mode — preventing PACTOR
(which exits Host Mode temporarily) from showing the Verbose terminal:

```python
active_name = self._modes.current_mode_name
mode_has_screen = (active_name is not None
                   and active_name in self._opmode_screens)
if not mode_has_screen:
    self._stack.setCurrentIndex(1)
```

---

*Created: 2026-05-05 | Updated: 2026-05-05 (v12) | OE3GAS | PK232PY Project*
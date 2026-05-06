# PK232PY – UI Design Decisions

This document captures design decisions made during the mockup and implementation phase.
It is the authoritative reference for the implementation phase.

Last updated: 2026-05-05 (v12)

---

## 1. Screen Architecture

### Base Classes

```
opmode_rtty_base.py
    RttyBaseScreen          ← abstract base for RTTY-type screens
        BaudotScreen        ← baudot_screen.py
        AsciiScreen         ← ascii_screen.py

Standalone screens (do NOT inherit RttyBaseScreen):
    AmtorScreen             ← amtor_screen.py
    MorseScreen             ← morse_screen.py
    PactorScreen            ← pactor_screen.py
    NavtexScreen            ← navtex_screen.py   (receive only)
    SignalScreen            ← signal_screen.py   (receive only)
    FaxScreen               ← fax_screen.py      (receive only)
    PacketBaseScreen        ← packet_screen.py   (abstract base for HF + VHF Packet)
        HFPacketScreen      ← packet_screen.py
        VHFPacketScreen     ← packet_screen.py
```

### RttyBaseScreen — what the base provides

- Title label (left) + UTC clock (right) in first row
- RBAUD dropdown (label/values overridable via class attributes)
- Row 1: SEND / RECEIVE buttons (prominent, 46px high, NoFocus)
- Row 2: mode-specific buttons via `_build_mode_buttons(layout)` — subclass implements
- RX window (expands vertically)
- TX window (5 lines, block cursor, initial focus)
- Macro bar (6 macro buttons + Edit Macros, all NoFocus)
- EventFilter: all keypresses redirected to TX window
- `_no_focus_btn()` helper for creating NoFocus buttons

### Subclass responsibilities

```python
class BaudotScreen(RttyBaseScreen):
    MODE_TITLE  = "Baudot"           # title label text
    BAUD_LABEL  = "RBAUD (Speed):"   # dropdown label (optional override)
    BAUD_VALUES = [...]              # dropdown values (optional override)

    def _build_mode_buttons(self, layout: QHBoxLayout) -> None:
        # add mode-specific buttons to layout
        # must call layout.addStretch() at end
```

---

## 2. Receive-Only Screens

Screens that have no transmit capability:

| Screen   | No TX window | No macro bar | Reason                        |
|----------|:---:|:---:|-------------------------------|
| NAVTEX   | ✓   | ✓   | Pure broadcast receive         |
| FAX      | ✓   | ✓   | Pure broadcast receive         |
| Signal   | ✓   | ✓   | Passive analysis only          |

Rule: **if a mode cannot transmit, omit both TX window and macro bar.**

---

## 3. Theme System

### Files

All theme code lives in `opmode_rtty_base.py`:
- `THEMES` dict — two themes: `"dark"` and `"light"`
- `get_theme()` — returns current theme dict
- `set_theme(name)` — sets active theme
- `apply_app_style(app, theme)` — applies global QApplication stylesheet
- `style_rx_widget(widget)` — applies RX colors to a QTextEdit
- `style_tx_widget(widget)` — applies TX colors + block cursor to a QTextEdit

### Usage pattern

```python
# In every main() function:
app = QApplication(sys.argv)
app.setStyle("Fusion")
apply_app_style(app, theme)   # theme from --theme= CLI arg

# In _build_ui() after creating RX/TX widgets:
style_rx_widget(self.rx_display)
style_tx_widget(self.tx_input)
```

### Theme colors

| Element         | Dark theme     | Light theme    |
|-----------------|----------------|----------------|
| Window BG       | `#1e2830`      | `#f0f0f0`      |
| Input BG        | `#1a2430`      | `#ffffff`       |
| TX input BG     | `#1a2c1a`      | `#f0fff0`       |
| Button BG       | `#445566`      | `#d0d8e0`       |
| RX text color   | `#88ccff`      | `#000080`       |
| TX text color   | `#ffee88`      | `#006600`       |
| Label text      | `#d0e4f4`      | `#1a1a2e`       |

### Pending for implementation phase

- Persist theme choice in `pk232py.ini` (`[UI]` section, key `theme`)
- Theme selector in `Configure → Appearance` menu
- Dynamic theme switch without restart (call `apply_app_style` + re-apply
  `style_rx_widget` / `style_tx_widget` on all open screens)
- Font family + size settings to be integrated alongside theme in same dialog

---

## 4. Button Conventions

### SEND / RECEIVE (prominent buttons)

```python
# Width: fills same total width as the mode-button row below
ROW2_TOTAL = 7 * BTN_W + 6 * SPACING   # for 7-button rows
PROM_W     = (ROW2_TOTAL - SPACING) // 2

btn.setFixedWidth(PROM_W)
btn.setFixedHeight(46)
btn.setCheckable(True)
btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # never steal TX focus
```

| State           | Style                          |
|-----------------|--------------------------------|
| Inactive        | `STYLE_PROM_INACTIVE` (dark grey) |
| SEND active     | Blinking red (QTimer 400ms, `STYLE_SEND_ON` ↔ `STYLE_SEND_BLINK`) |
| RECEIVE active  | Solid green (`STYLE_RECEIVE_ON`) |

Mutual exclusion uses `blockSignals(True/False)` pattern — not QButtonGroup —
to allow custom styling alongside the state change.

### Toggle buttons (small, mode-specific)

```python
btn = make_toggle_button("Wide Shift")   # from opmode_rtty_base
# green = ON, grey = OFF
# width = BTN_W (90px), NoFocus policy already set inside make_toggle_button()
```

### Action buttons (one-shot, no toggle)

```python
btn = QPushButton("Switch figs")
btn.setFixedWidth(BTN_W)
btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
# no setCheckable() — sends single command to TNC
```

### Mode buttons (AMTOR / PACTOR-style, mutually exclusive)

```python
btn = _make_mode_button("ARQ", width=60, active_color="#3a7a3a")
btn.setCheckable(True)
btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
# stays pressed while mode is active
# deactivated by _on_mode_toggled() mutual exclusion logic
```

### NoFocus rule

**All buttons on all screens must have `NoFocus` policy.** A click activates
the button but never steals keyboard focus from the TX window. This is enforced:
- `make_toggle_button()` sets `NoFocus` internally
- `RttyBaseScreen._no_focus_btn()` helper for creating any other button
- Standalone screens set `NoFocus` explicitly on every QPushButton

---

## 5. TX Window Focus & Cursor

### Initial focus

```python
# In __init__, after _build_ui():
self.installEventFilter(self)
QTimer.singleShot(0, lambda: self.tx_input.setFocus())
```

`singleShot(0)` waits one event-loop cycle — the widget is fully rendered
before `setFocus()` is called, ensuring it works reliably.

### Block cursor

`style_tx_widget()` sets a wide cursor on the TX QTextEdit:

```python
char_w = widget.fontMetrics().averageCharWidth()
widget.setCursorWidth(char_w)
```

This produces a blinking block cursor instead of the thin default line cursor,
which is much more visible during fast TX input.

### EventFilter architecture — three levels

#### Level 1 — MainWindow (app-wide, authoritative)

`MainWindow.__init__` installs a single **application-wide** event filter:

```python
QApplication.instance().installEventFilter(self)   # in MainWindow.__init__
```

In Host Mode this filter redirects all keypresses to the active screen's
`tx_input`. Exceptions (checked in order):

1. Modal dialog open → pass through
2. ALT+X / ALT+R → handle SEND/RECEIVE shortcuts
3. `screen.focus_ctrl.is_active() == True` → pass through (input field active)
4. `obj is tx_input` → pass through
5. anything else → redirect to tx_input

#### Level 2 — Opmode screen filters (widget-scoped, secondary)

Each screen with a TX window installs a **widget-scoped** filter:

```python
self.installEventFilter(self)    # NOT QApplication.instance()
```

Acts as fallback when the MainWindow filter doesn't redirect (e.g. focus
on QStackedWidget after a NoFocus button click). Uses parent-chain walk
because `obj` in a widget-scoped filter may also be an internal child:

```python
def eventFilter(self, obj, event) -> bool:
    if event.type() == QEvent.Type.KeyPress:
        def _is_input(w):
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

Do NOT use `QApplication.instance().installEventFilter(self)` in screen
widgets — that intercepts ALL keypresses app-wide including other screens.

#### Level 3 — ScreenFocusController (field-scoped)

`screen_focus_controller.py` — `QObject` installed directly on individual
QLineEdit fields of screens that have editable input fields.

**Why it is needed:** In a Qt app-wide EventFilter, `isinstance(obj, QLineEdit)`
is unreliable — `obj` may be an internal child widget of QLineEdit, not
QLineEdit itself. `ScreenFocusController` installs via `field.installEventFilter(ctrl)`,
at which scope `obj` IS the QLineEdit and FocusIn/FocusOut are reliable.

```python
# In screen __init__ (after _build_ui()):
from .screen_focus_controller import ScreenFocusController
self.focus_ctrl = ScreenFocusController(
    fields=[self.le_dest],    # only EDITABLE QLineEdit fields
    parent=self,
)
```

Screens and their editable fields:

| Screen           | fields in focus_ctrl        | Display labels (QLabel, excluded)             |
|------------------|-----------------------------|-----------------------------------------------|
| PactorScreen     | `le_dest`                   | `lbl_myptcall`                                |
| AmtorScreen      | `le_dest`                   | `lbl_myselcal`, `lbl_myaltcal`, `lbl_myident` |
| PacketBaseScreen | `le_dest`, `le_unproto`     | `lbl_mycall`                                  |

Screens without focus_ctrl (no editable non-TX fields): RttyBaseScreen,
MorseScreen, NavtexScreen, SignalScreen, FaxScreen.

### Display-only identity fields (QLabel)

Identity parameters shown on screens are **QLabel**, not QLineEdit.
They are populated from `AppConfig` in `_switch_opmode()`.
Empty or `"NOCALL"` values show `"---"`.

| Attribute      | Screen       | Config source                | Set via                      |
|----------------|--------------|------------------------------|------------------------------|
| `lbl_mycall`   | PacketBase   | `AppConfig.hf_packet.mycall` | TNC → Configure → Parameters |
| `lbl_myptcall` | Pactor       | `AppConfig.pactor.myptcall`  | TNC → PACTOR Parameters      |
| `lbl_myselcal` | Amtor        | `AppConfig.amtor.myselcal`   | TNC → AMTOR Parameters       |
| `lbl_myaltcal` | Amtor        | `AppConfig.amtor.myaltcal`   | TNC → AMTOR Parameters       |
| `lbl_myident`  | Amtor        | `AppConfig.amtor.myident`    | TNC → AMTOR Parameters       |

Style: `QFont("Courier New", 10, QFont.Weight.Bold)`, initial text `"---"`.

See `EVENTFILTER_ARCHITECTURE.md` for full details including the Host Mode
stack switching behaviour for verbose-activation modes (PACTOR).

---

## 6. Layout Rules

### Title row (all screens)

```
[Mode Title  (bold)]     [UTC  HH:MM:SS  (Courier, bold, right-aligned)]
```

UTC clock uses `QTimer` interval 1000ms, `datetime.now(timezone.utc)`.
Call `self._update_utc()` immediately after creating the label (avoids
1-second blank on startup).

### Button rows above RX window

Standard order (top to bottom):
1. Parameter row (RBAUD dropdown, etc.)
2. Separator line
3. SEND / RECEIVE row (prominent)
4. Mode-specific button row
5. Separator line
6. RX window (stretch=1)
7. Separator line
8. TX window (5 lines, fixed height, block cursor)
9. Separator line
10. Macro bar

### TX window height calculation

```python
fm = self.tx_input.fontMetrics()
mc = self.tx_input.contentsMargins()
self.tx_input.setFixedHeight(fm.lineSpacing() * 5 + mc.top() + mc.bottom() + 8)
```

### Spacing constants (from opmode_rtty_base)

```python
BTN_W   = 90   # width of all small buttons
SPACING = 6    # gap between buttons (same in all rows)
```

---

## 7. Macro System

### MacroStore (in opmode_rtty_base.py)

- 6 macros, each with a name (max 10 chars) and text (max 200 chars)
- Persisted in `Macro.txt` (plain text, user-editable)
- File format: `NAME|TEXT` per line, `#` lines are comments
- CR/LF in text is escaped as `\n` / `\r` on save, unescaped on load
- Backslash escaped as `\\`

### MacroEditDialog (in opmode_rtty_base.py)

- Modal dialog, 6 rows (name field + 3-line text field each)
- Name field: `QLineEdit` with `setMaxLength(10)`
- Text field: `QTextEdit` with character limit enforced via `textChanged` signal
- Buttons: Save (writes Macro.txt), Load (reads Macro.txt), Close

### After dialog closes

```python
def _on_edit_macros(self) -> None:
    dlg = MacroEditDialog(self._macro_store, parent=self)
    dlg.exec()
    # Update button labels from store
    for i, btn in enumerate(self.macro_buttons):
        btn.setText(self._macro_store.names[i])
```

---

## 8. Screen-Specific Notes

### AMTOR (amtor_screen.py)

- Identity row: MYSELCAL, MYALTCAL, MYIDENT — **QLabel** (display-only)
  Populated from `AppConfig.amtor` on mode switch. Set via TNC → AMTOR Parameters.
- Dest (Ziel-SELCAL): editable QLineEdit (`le_dest`) — user enters target SELCAL
- Mode buttons (mutually exclusive): ARQ, FEC, SELFEC, ALIST, Pactor Listen
- STBY: one-shot button (NoFocus), resets all mode buttons
- ACHG: one-shot button (NoFocus), take over ARQ link
- HOLD: toggle button (NoFocus), hold TX buffer
- Status label: color-coded (grey=STBY, orange=CALLING, green=CONNECTED, blue=FEC TX)
- Toggle row: ARXTOR, RxRev, TxRev, RFEC, SRxAll, EAS, Switch figs, Switch char
- EventFilter + initial TX focus in `__init__`
- `ScreenFocusController` on `le_dest` only

### CW / Morse (morse_screen.py)

- MSPEED (5–99 WPM): QSpinBox with flanking +/- buttons (NoFocus)
- MWEIGHT (10–90): QSpinBox with flanking +/- buttons (NoFocus)
- MID (0–99 min): QSpinBox, `setSpecialValueText("off")` for value 0
- LOCK: one-shot button (NoFocus) — locks RX speed to signal
- MOPTT: toggle (NoFocus), initial state ON (default per manual)
- Special character reference table in QGroupBox below toggle buttons
- EventFilter + initial TX focus in `__init__`

### PACTOR I (pactor_screen.py)

- MYPTCALL: **QLabel** (`lbl_myptcall`) — display-only, populated from
  `AppConfig.pactor.myptcall` on mode switch. Set via TNC → PACTOR Parameters.
- Mode buttons (mutually exclusive, NoFocus): Connect, PTLIST, PTSEND
- Disconnect: one-shot (NoFocus), terminates active ARQ connection
- STBY: one-shot (NoFocus), return to PACTOR standby
- Dest callsign field (`le_dest`): editable QLineEdit — user enters destination
- Toggle row (all NoFocus): PT200 (default ON), PTHUFF (default ON), PTROUND, EAS
- Status label: STBY / CALLING / CONNECTED / LISTENING / FEC TX / DISCONNECTED
- EventFilter + initial TX focus in `__init__`
- `ScreenFocusController` on `le_dest` only

### HF Packet (packet_screen.py — HFPacketScreen)

- MYCALL: **QLabel** (`lbl_mycall`) — display-only, populated from
  `AppConfig.hf_packet.mycall` on mode switch.
- Dest (`le_dest`): editable QLineEdit — AX.25 connect destination
- UNPROTO via (`le_unproto`): editable QLineEdit — unproto path, default "CQ"
- HBAUD dropdown: 300 / 1200 Bd (default 300)
- Monitor level dropdown: 0–6 (default 4)
- Buttons: Connect (checkable), Disconnect, Unproto (checkable), MailDrop
- Toggle row (all NoFocus): EAS, PASSALL, MRPT, MID, SQUELCH
- Status pill: DISCONNECTED / CONNECTED / CALLING / UNPROTO TX
- MHEARD panel: callsign + time list with Refresh + Clear buttons
- `ScreenFocusController` on `le_dest` + `le_unproto`

### VHF Packet (packet_screen.py — VHFPacketScreen)

- Same as HF Packet, with these differences:
  - HBAUD default: 1200 Bd (values: 1200 / 9600)
  - Additional TNC init frames: `VH Y`, `MX 4`, `SL 10`
  - Suitable for 1200 Bd FM packet (Bell 202 modem)

### NAVTEX (navtex_screen.py)

- No TX window, no macro bar, no EventFilter
- NAVMSG filter: 10 checkboxes (A–J), mandatory classes A/B/D are `setEnabled(False)`
- "All" / "None" quick buttons affect only non-mandatory classes
- NAVSTN filter: free-text QLineEdit with "ALL" / "None" buttons
- `get_navmsg_filter()` → string for TNC command
- `get_navstn_filter()` → string for TNC command

### Signal / SIAM (signal_screen.py)

- No TX window, no macro bar, no EventFilter
- Confidence bar: QProgressBar 0–100, color changes by value:
  - ≥ 0.70: green `#3a9e3a`
  - ≥ 0.40: orange `#cc8800`
  - < 0.40: red `#cc3333`
- OK button: disabled until analysis returns a switchable result
  (disabled for Unknown, Noise, 6-Bit)
- Analysis log: QTextEdit with UTC timestamp per entry
- Demo mode: QTimer simulates TNC frame reception (mockup only — remove for production)

### FAX (fax_screen.py)

- No TX window, no macro bar, no EventFilter
- `FaxImageWidget(QLabel)`: accumulates pixel lines via `append_line(bytes)`
- `set_faxneg(bool)`: re-renders all stored lines with inversion
- `save_as_png(path)`: `QPixmap.save(path, "PNG")` — no external library needed
- FSPEED: QComboBox (0–4, maps to LPM values)
- ASPECT: QSpinBox (1–6), default 2
- Demo mode: QTimer 50ms per line, sinusoidal test pattern (mockup only)

---

## 9. Implementation Status (v12)

All opmode screens are implemented and integrated in MainWindow via `QStackedWidget`.

| Screen           | File                     | Version |
|------------------|--------------------------|---------|
| Baudot RTTY      | baudot_screen.py         | v10     |
| ASCII RTTY       | ascii_screen.py          | v10     |
| AMTOR ARQ/FEC    | amtor_screen.py          | v11/v12 |
| CW / Morse       | morse_screen.py          | v10     |
| PACTOR I         | pactor_screen.py         | v11/v12 |
| HF Packet        | packet_screen.py         | v11/v12 |
| VHF Packet       | packet_screen.py         | v11/v12 |
| NAVTEX           | navtex_screen.py         | v10     |
| Signal (SIAM)    | signal_screen.py         | v10     |
| FAX              | fax_screen.py            | v10     |

Key MainWindow integration points:
- `_switch_opmode()`: switches QStackedWidget; populates identity labels from AppConfig
- `_wire_screen_buttons()`: wires all buttons/signals for the active screen
- `_wire_packet_buttons()`: wires Packet-specific buttons (Connect, Disconnect, etc.)
- `_wire_identity_fields()`: wires `editingFinished` for editable identity fields
- `_update_host_mode_ui()`: `mode_has_screen` guard prevents PACTOR from showing Verbose terminal

New modules (v11/v12):
- `screen_focus_controller.py` — field-scoped focus tracking for editable QLineEdits
- `baudot_tx_controller.py` — rate-limited TX state machine (v10)
- `help_viewer.py` — Markdown help viewer (v10b)

### Tooltip system (planned)

Create `src/pk232py/ui/tooltips.py`:
```python
TOOLTIPS = {
    "EAS":      "Echo As Sent – show confirmed TX characters in RX window (EA)",
    "WIDESHFT": "Wide Shift – 850 Hz instead of 170 Hz frequency shift (WI)",
    # ...
}
```
PACTOR screen already has inline tooltips — migrate to central `tooltips.py`
for consistency across all screens.
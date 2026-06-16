# PK232PY -- TX/RX State Machine Reference

**Scope:** all character-ACK opmode screens — Baudot RTTY, ASCII RTTY and
CW/Morse (since Paket 2a / 437e8a1); AMTOR planned for Paket 2b.
**Implementation:** `TxController` in `src/pk232py/ui/screens/tx_controller.py`
(renamed from `BaudotTxController` / `baudot_tx_controller.py` in Paket 1,
cc2adff — the controller is mode-agnostic: no serial I/O, no widget refs).
**TxInputWidget** in `src/pk232py/ui/screens/opmode_rtty_base.py`
**Last updated:** 2026-06-16 (v16)

---

## 1. States

| State ID | Name | Description |
|----------|------|-------------|
| `S0` | **DISCONNECTED** | No serial connection. Buttons disabled. |
| `S1` | **STANDBY** | Connected + Host Mode active. TNC idle. |
| `S2` | **RECEIVE** | TNC decoding incoming signal. RX window filling. TX window editable, chars buffered in `_arr`. |
| `S3` | **SEND** | PTT active. TNC transmitting. Chars sent rate-limited via QTimer. |

---

## 2. State Transition Table

| From | Event | Action | Next |
|------|-------|--------|------|
| `S0` | Host Mode entered | Enable SEND + RECEIVE buttons, clear controller | `S2` |
| `S2` | SEND pressed (ALT+X) | Send `XM` frame, wait for XM ACK | `S3` |
| `S2` | RECEIVE pressed | Visual feedback only -- no TNC command | `S2` |
| `S3` | XM ACK received | `ctrl.on_send_start()` -- flush `_arr[_tx_sent_idx:]` to rate-limited queue | `S3` |
| `S3` | RECEIVE pressed (ALT+R) | `ctrl.on_send_stop()`, send `RC` frame | `S2` |
| `S3` | SEND pressed again | Same as RECEIVE pressed -- second click = toggle off | `S2` |
| `S3` | EOT marker `[^D]` reached | `eot_reached` signal -- automatic switch to RECEIVE | `S2` |
| Any | Host Mode exited | Disable buttons, reset controller | `S0` |
| Any | Serial disconnected | Disable buttons, reset controller | `S0` |

---

## 3. Three-Index System (proven 2026-05-02)

`TxController` maintains three indices into `_arr`:

| Index | Advances when | Meaning |
|-------|--------------|---------|
| `_tx_sent_idx` | `_queue_char()` called | Next char to be queued for TNC |
| `_ack_idx` | `on_data_ack()` called | Next char awaiting DATA_ACK from TNC |
| `_cycle_start` | `on_send_stop()` called | Document anchor for `colour_at()` |

**Critical rules:**

`on_send_stop()` — proven 2026-05-03:
```python
self._tx_sent_idx -= len(self._tx_queue)  # undo unsent chars in queue
self._tx_queue.clear()
self._cycle_start = self._tx_sent_idx     # anchor for colour_at()
self._ack_idx     = self._tx_sent_idx     # CRITICAL: clamp _ack_idx!
```

**Why both indices must be set to `_tx_sent_idx`:**
- `_cycle_start = _tx_sent_idx` — correct anchor for `colour_at()` in next cycle
- `_ack_idx = _tx_sent_idx` — prevents late ACKs from EOT marker being
  processed as new-cycle ACKs. Without this, chars typed during RECEIVE
  are never ACK'd (all arrive as "Late ACK ignored").

`on_send_start()` — proven 2026-05-03:
```python
self._ack_idx = self._cycle_start   # CRITICAL: re-align for new cycle
```
Then flushes from `_tx_sent_idx` -- NOT from `_ack_idx`.

**Why `_ack_idx = _cycle_start` at start:**
After RECEIVE, `_ack_idx` was clamped to `_tx_sent_idx` by `on_send_stop`.
Chars typed during RECEIVE go into `_arr[_tx_sent_idx:]` without advancing
`_tx_sent_idx` (since `_send_active=False`). On the next SEND, these chars
are flushed. Their ACKs arrive with idx=`_cycle_start`..N — which is correct
since `_cycle_start == _tx_sent_idx == _ack_idx` after `on_send_stop`.

`still_to_transmit()` returns True only if real chars (not `\x04`) remain
beyond `_tx_sent_idx`:
```python
return any(e['char'] != '\x04' for e in self._arr[self._tx_sent_idx:])
```

---

## 4. Rate-Limited TX (proven 2026-05-02)

Characters are NOT sent all at once into the TNC buffer.
A QTimer sends one character per `_mspeed_ms` interval.

**Formula:** `ms/char = 7500 / baud`  (7.5 bits/char for ITA-2 Baudot)

| Baud | ms/char | chars/sec |
|------|---------|-----------|
| 45   | 167ms   | 6.0       |
| 50   | 150ms   | 6.7       |
| 75   | 100ms   | 10.0      |
| 100  | 75ms    | 13.3      |
| 110  | 68ms    | 14.7      |
| 150  | 50ms    | 20.0      |
| 200  | 38ms    | 26.3      |
| 300  | 25ms    | 40.0      |

`set_mspeed(baud)` must be called in TWO places:
1. `_wire_screen_buttons()` -- on mode activation, from config
2. `_on_screen_rbaud_changed()` -- when user changes RBAUD dropdown

---

## 5. TX Buffer Limit

`TX_MAX = 512` -- counts only UNSENT chars (pending):
```python
pending = len(self._arr) - self._tx_sent_idx
if pending >= self.TX_MAX:
    self.warning.emit("BUFFER_FULL")
    return
```

`len(_arr)` is never the right check -- `_arr` grows forever (history).
`pending_len` property: `return max(0, len(self._arr) - self._tx_sent_idx)`

---

## 6. Colour Coding

**TX window:**
| Colour | Meaning |
|--------|---------|
| Yellow (`tx_color` from theme) | Typed but not yet sent |
| Black on yellow (`#000000` on `#ddaa00`) | Sent and confirmed (DATA_ACK received) |
| White on orange (`#ffffff` on `#cc4400`) | Control marker (e.g. `[^D]`) |

**RX window:**
| Colour | Meaning |
|--------|---------|
| Blue (`#88ccff`) | Received from air |
| Amber (`#ffaa00`) | Own transmitted text (confirmed sent) |
| Orange (`#ff9900`) | System warnings |

---

## 7. TxInputWidget -- Document Position Tracking

`colour_at(arr_idx)` maps array index to document position:
```python
doc_pos = _doc_offset + (arr_idx - _cycle_start) + _doc_extra
```

**`_doc_offset`** -- document position of the cycle start (set by `set_cycle_anchor()`)
**`_cycle_start`** -- `_arr` index of the cycle start
**`_doc_extra`** -- accumulated discrepancy between `_arr` entries and document chars

### Why _doc_extra is needed

Control markers like `[^D]` occupy MORE characters in the document than in `_arr`:
- `[^D]` = **4 document chars**, but **1 `_arr` entry** (`\x04`)
- This creates a discrepancy of **+3** per marker

Without tracking this, `colour_at()` colours the wrong positions after any control
marker is inserted.

### _doc_extra update rules

| Event | `_doc_extra` change |
|-------|---------------------|
| `[^D]` inserted (CTRL+D or macro) | `+= 3` |
| `[^D]` deleted (Backspace) | `-= 3` |
| `[^S]` inserted *(planned)* | `+= 3` |
| `[^S]` deleted *(planned)* | `-= 3` |
| `[^T:n]` inserted *(planned)* | `+= len('[^T:n]') - 1` |
| `[^T:n]` deleted *(planned)* | `-= len('[^T:n]') - 1` |
| `set_cycle_anchor()` called | baked into `_doc_offset`, reset to 0 |

**General formula:** `_doc_extra += (visual_chars - 1)` for any marker
that occupies more document positions than `_arr` entries.

### set_cycle_anchor

Called by MainWindow when switching SEND -> RECEIVE:
```python
doc_len = tx.document().characterCount() - 1
tx_input.set_cycle_anchor(doc_len, ctrl.cycle_start)
```

**CRITICAL:** Pass `document().characterCount() - 1` as `doc_offset`,
NOT `ctrl.tx_sent_idx`. The document length correctly accounts for
multi-char visual markers like `[^D]` (4 doc chars, 1 _arr entry).
Using `tx_sent_idx` causes `colour_at()` to be off by 3 per marker.

Implementation:
```python
def set_cycle_anchor(self, doc_offset: int, cycle_start: int) -> None:
    self._doc_offset  = doc_offset   # actual doc position, not array index
    self._cycle_start = cycle_start
    self._doc_extra   = 0   # reset for next cycle
```

---

## 8. Control Characters

Control characters automate TX/RX switching. They are inserted as
visible ASCII markers with coloured backgrounds and are NOT transmitted
over the air.

### Design Convention

All control markers use the format `[^X]` or `[^X:param]`:
- Visible ASCII -- works on all platforms and fonts
- No Private Use Unicode (renders as tofu/comma on Windows)
- Atomic Backspace via `_eot_positions` list in `TxInputWidget`
- Stored as `[^X]` in `Macro.txt` (human-readable)
- 1 entry in `_arr` per marker (regardless of display length)

### Implemented

| Key | Marker | Doc chars | Sentinel | Colour | Function |
|-----|--------|-----------|----------|--------|----------|
| `CTRL+D` | `[^D]` | 4 (fixed) | `\x04` | White on orange `#cc4400` | Switch to RECEIVE when reached during TX |
| `CTRL+T:n` | `[^T:n]` | variable — `[^T:5]` = 6 | `\x1b` + str(n) (e.g. `"\x1b5"`, `"\x1b10"`) | White on purple `#8800cc` | RECEIVE, wait n seconds, then SEND (n = 1–10, QInputDialog). Since v13 |

Both markers are tracked in `TxInputWidget._eot_positions`, a list of
`{'pos': int, 'len': int}` dicts — variable marker length is handled per entry,
so Backspace deletes the whole marker atomically and adjusts
`_doc_extra -= (len - 1)`.

### Planned

*(none)* — `CTRL+S` / `[^S]` ("switch to SEND when reached") was **dropped**:
decided not to implement. The *(planned)* `[^S]` rows in §7's `_doc_extra`
table above are retained only as a worked example of the general formula.

### Implementation Checklist for New Control Characters

When implementing a new control character (e.g. `[^S]`), update these 4 places:

1. **`TxInputWidget.keyPressEvent`** -- detect CTRL+S, insert `[^S]` with
   correct colour, append position to `_eot_positions`, `_doc_extra += 3`

2. **`TxInputWidget.keyPressEvent` Backspace** -- detect cursor after `[^S]`,
   delete 4 chars atomically, `_doc_extra -= 3`

3. **`_on_macro_clicked` in `main_window.py`** -- detect `[^S]` in macro text,
   insert visually, `_doc_extra += 3`, emit correct sentinel via `char_typed`

4. **`TxController.on_char_typed`** -- handle the sentinel char
   (e.g. `\x13` for `[^S]`) with appropriate state transition

`MacroTextEdit` in `macro_store.py` needs CTRL+S support for entering
the marker in the Edit Macros dialog (same approach as CTRL+D there).

---

## 9. Paste Handling (proven 2026-05-03)

`TxInputWidget.insertFromMimeData()` handles paste:
- Tries `source.text()` first (plain text -- most apps)
- Falls back to HTML stripping if `source.hasHtml()` (some Windows apps)
- Pre-truncates to `ctrl.TX_MAX - ctrl.pending_len` before iterating
- Emits `BUFFER_FULL` exactly ONCE if paste exceeds available space
- Controller is found via `_ctrl_ref` cache on widget (avoids repeated parent-chain walk)

---

## 10. Backspace Sentinel

When Backspace is pressed in `TxInputWidget`, `char_typed.emit('\x08', '')`
is sent to `TxController.on_char_typed()` as a sentinel:

```python
if char == '\x08':
    if len(self._arr) > self._tx_sent_idx:
        self._arr.pop()
    if self._ack_idx > len(self._arr):
        self._ack_idx = len(self._arr)   # clamp
    return
```

This keeps `_arr` in sync with the document so `colour_at()` positions
remain valid after editing.

---

## 11. Macro Integration

Macro text is inserted char by char via `_on_macro_clicked()` in `main_window.py`.
This bypasses `insertFromMimeData()` to avoid parent-chain lookup issues.

Control markers in macro text (`[^D]` etc.) are detected by 4-char lookahead
in the insertion loop:

```python
while i < len(text):
    if text[i:i+4] == '[^D]':
        # Insert visual marker, emit \x04, _doc_extra += 3
        i += 4
    elif text[i] == '\n':
        # Insert block, emit '\r\n'
        i += 1
    elif text[i].isprintable():
        # Insert char, emit char
        i += 1
```

---

## 12. Guard Conditions

All TNC frame sends must check:
```python
if not self._serial.is_connected or not self._serial.is_host_mode:
    return
```

---

## 13. Direct Serial Communication (proven 2026-05-02)

**CRITICAL:** All TNC communication MUST use direct serial writes
(`port.write()` / `read_until()`). NO Worker-Thread queues for Host Mode frames.

The Windows Prolific USB driver only delivers ACKs when read() is called
directly on the port. If ACKs are routed through a worker queue, they
only arrive when the port is closed.

This means: `send_data()` for DATA frames and `send_command()` for command
frames must write synchronously to the port, not via a queue.

---

## 14. Mode-Specific Receive Behaviour

| Mode | RECEIVE button action | TNC command sent |
|------|-----------------------|------------------|
| Baudot RTTY | Visual feedback only | `RC` (to drop PTT) |
| ASCII RTTY | Visual feedback only | `RC` (to drop PTT) |
| CW / Morse | Visual feedback only | `RC` (to drop PTT) |
| AMTOR ARQ | Not used -- use ALIST button | ALIST |
| AMTOR FEC | Not used -- use FEC button | FEC |
| NAVTEX | Automatic -- no button needed | None |
| FAX | Automatic -- no button needed | None |

---

## 15. TNC Mnemonics Used

| Action | Mnemonic | Host Mode frame (hex) |
|--------|----------|-----------------------|
| PTT ON / start TX | `XM` (XMIT) | `01 4F 58 4D 17` |
| XM ACK from TNC | | `01 4F 58 4D 00 17` |
| PTT OFF / back to RX | `RC` (RCVE) | `01 4F 52 43 17` |
| TX data (one char) | data frame | `01 20 xx 17` |
| DATA_ACK from TNC | | `01 5F 58 58 00 17` |
| Exit Host Mode | `HO` (HOST OFF) | `01 4F 48 4F 4E 17` |
| Monitor/RX frame | | `01 3F xx 17` |

---

## 16. Mode-specific EOT behaviour (verified against the Technical Reference Manual, session 2026-06-16)

The `[^D]` EOT marker does **not** map to the same TNC action in every mode.
AMTOR in particular must NOT use `RC` (which would drop the link).

| Mode | EOT action | TNC command | Note |
|------|-----------|-------------|------|
| Baudot RTTY | RC | `RC` | Since v10, proven |
| ASCII RTTY | RC | `RC` | Like Baudot |
| CW/Morse | RC | `RC` | Paket 2a, TxController ACK-paced |
| AMTOR-ARQ | OVER | `OV` | Polite turnaround, ISS↔IRS role swap, link stays up. NOT ACHG (= Break-In)! |
| AMTOR-FEC | RC | `RC` | No connection concept |
| Packet | — | — | No EOT; packetises at ETB; needs a Stop button (`AM`) |

Implementation note: `_on_baudot_eot()` must branch by mode for AMTOR
(ARQ → `OV`, FEC → `RC`), and AMTOR must be added to `_is_txctrl_mode()`
(Paket 2b, open).

---

## 17. TxController pacing per mode

| Mode | Pacing mechanism | Parameter |
|------|------------------|-----------|
| Baudot/ASCII | QTimer → mspeed from config (Baud) | `set_mspeed(baud)` |
| CW/Morse | ACK-paced; timer = overflow safety net only | `set_mspeed_ms(50)` = `_MORSE_TXCTRL_MS` |
| AMTOR (Paket 2b) | ACK-paced; 3-character ARQ blocks | `set_mspeed_ms(TBD)` |

`set_mspeed_ms(ms)` (added in Paket 1) takes a direct ms interval for modes
that have no meaningful Baud rate; `set_mspeed(baud)` only maps Baud → ms.

*OE3GAS | PK232PY Project | AEA PK-232MBX Host Mode*
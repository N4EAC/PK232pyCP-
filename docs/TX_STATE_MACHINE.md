# PK232PY -- TX/RX State Machine Reference

**Scope:** All character-ACK modes: Baudot RTTY, ASCII RTTY, CW/Morse,
AMTOR ARQ/FEC. See §18 for AMTOR-specific behaviour.
**Implementation:** `TxController` in `src/pk232py/ui/screens/tx_controller.py`
(renamed from `BaudotTxController` / `baudot_tx_controller.py` in Paket 1, cc2adff)
**TxInputWidget** in `src/pk232py/ui/screens/opmode_rtty_base.py`
**Last updated:** 2026-06-18 (v16 — edit-protection dynamic sent boundary, §7.1)

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

> **AMTOR exception:** AMTOR has no XM frame and no btn_send.
> `on_send_start()` is called from `_make_link_handler()` when the
> ARQ link reaches CONNECTED state. See §18.

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

> For modes without a meaningful Baud rate (Morse, AMTOR), use
> `set_mspeed_ms(ms)` instead (e.g. `_MORSE_TXCTRL_MS = 50`,
> `_AMTOR_TXCTRL_MS = 50` in `main_window.py`).

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
    self._sent_boundary = doc_offset # re-anchor edit-protection (see §7.1)
```

### 7.1 Edit protection — dynamic sent boundary (fixed 2026-06-18)

**User-facing behaviour (for the manual):**

Text that has already been transmitted to the TNC can no longer be edited.
The TX window is split into two zones by an invisible boundary:

- **Locked zone** (everything left of the boundary): characters already sent
  on air, shown black-on-yellow. The cursor cannot enter it, and Backspace,
  Delete, paste, and typing into it are all blocked. If the cursor is moved
  into this zone (Left / Home / Up / Page-Up, or a mouse click), it is snapped
  back to the boundary — the first still-editable position.
- **Editable zone** (boundary and right of it): characters typed but not yet
  confirmed sent. The operator may freely type, backspace, and correct here.

The boundary advances **live, character by character, while transmitting** —
each character locks the instant the TNC confirms it was sent (the per-character
ACK; in CW/Morse, when its `$2F` echo arrives). The operator therefore can
*always* keep typing ahead at the end of the buffer, but can *never* go back
and alter a character that is already on the air. On RECEIVE the whole buffer
sent so far is locked, and freshly typed text (before the next SEND) is editable
until it too is transmitted.

**Why this was needed:** previously the boundary (`_doc_offset`) was only
updated at cycle end (`set_cycle_anchor()`, on RECEIVE). During an active SEND
it stayed frozen at the previous RECEIVE position, so every character typed
*and sent within the current SEND cycle* lay to the right of the boundary and
stayed editable. The operator could move the cursor left into already-sent
text and insert characters — which were then transmitted out of order
(TX window showed `abcXXXdef`, RX window the actually-sent `abcdefXXX`).
The fix makes the boundary advance during the cycle, not only at its end.

**Implementation (`TxInputWidget`, `opmode_rtty_base.py`):**

| Member | Role |
|--------|------|
| `_doc_offset` | Static cycle-start anchor — set only at `set_cycle_anchor()` (RECEIVE). |
| `_sent_boundary` | **Dynamic** doc position just past the last *sent* char. Advances mid-cycle. |
| `_edit_boundary()` | Returns `max(_doc_offset, _sent_boundary)` — the first editable doc position. All protection checks use this, never `_doc_offset` directly. |

`_sent_boundary` advances in exactly the two places a character becomes "sent":

1. **`colour_at(arr_idx, sent=True)`** — fired per character on DATA_ACK
   (Baudot/ASCII/AMTOR) or per `$2F` echo in EAS/Morse. After colouring the
   char black-on-yellow: `_sent_boundary = max(_sent_boundary, doc_pos + 1)`.
2. **Immediate space colouring in `keyPressEvent`** — a Morse word-gap space is
   coloured as sent at keypress time (it has no `$5F` ACK path), so the same
   `_sent_boundary = max(_sent_boundary, space_doc_pos + 1)` advance is applied
   there too.

`_sent_boundary` is **re-anchored to `_doc_offset`** in `set_cycle_anchor()`
(start of each new cycle) and reset to 0 by the full `set_cycle_anchor(0, 0)`
reset on mode switch / Host Mode entry. It only ever grows within a cycle, so
`max(_doc_offset, _sent_boundary)` collapses to `_sent_boundary` once a cycle
is running; the `max` is a defensive guard against ordering edge cases.

The three protection sites all consult `_edit_boundary()`:
`_selection_touches_protected()`, `_push_cursor_to_boundary()` (post-correction
after every cursor-movement key), and the protected-zone snap in `keyPressEvent`.

> **Gotcha — intentional one-char grace window:** a character is editable from
> the moment it is typed until its ACK/echo returns. This is deliberate: it
> keeps end-of-buffer typing fluid. The cursor is *not* force-moved when an ACK
> advances the boundary past it; the snap happens on the next keystroke or
> cursor move instead. The net effect the operator sees is: already-on-air text
> is locked, the live tail is free.

---

## 7.2 Clear TX — full buffer flush (fixed 2026-06-18)

**User-facing behaviour (for the manual):** *Clear TX* empties the entire
transmit buffer, not just the on-screen text. If a transmission is in progress
when it is pressed, the radio stops keying immediately — any characters the TNC
had already buffered are discarded, not sent — and the station returns to
RECEIVE. (Frame-based Packet: a packet already handed over at Enter/ETB is
gone and cannot be recalled; Clear TX only discards the unsent line.)

**Why this was needed:** the old handler cleared only the PC-side buffer
(`_tx_ctrl`) and the screen but left PTT on, so the TNC kept transmitting the
characters it had already received — the operator saw a blank window while the
radio still sent the old text.

**Implementation (`MainWindow._on_clear_tx`):**

1. **Stop the TNC** — if `_send_active`, send the mode's stop command from
   `_CLEAR_TX_STOP_CMD`:

   | Mode | Stop cmd | Note |
   |------|----------|------|
   | Baudot / ASCII / CW-Morse | `RC` | Drop PTT, back to receive. |
   | AMTOR ARQ / FEC | `AM` | Standby + flush TNC TX buffer (NOT `R` — see §16). |
   | HF / VHF Packet | *(none)* | Frame-based; nothing keyed to flush. |
   | PACTOR | *(none)* | Runs outside Host Mode; no Host-Mode stop applies. |

2. **Clear PC side** — `tx.clear()`, `set_cycle_anchor(0, 0)` (also resets
   `_sent_boundary`, §7.1), `_tx_ctrl.clear()`, `_send_active = False`.
3. **Reflect RECEIVE in the UI** — uncheck `btn_send` / check `btn_receive`
   under `blockSignals` so the toggle handlers do **not** fire a second RC/AM.

> Replaces the earlier "preserve SEND, keep PTT on" behaviour. Hardware
> verification for the AMTOR `AM` flush and the Packet/PACTOR no-op is pending
> (Testplan **T17**, Paket 3 / Stop Sending).

---

## 7.3 doc_pos capture (Phase 1 of Lösung A, commit 5dcaf7e)

**Status:** Phase 1 done (capture). Phase 2 open (switch-over).

**Problem (diagnosis 2026-06-18):** `colour_at()` mixes two coordinate systems
— `_cycle_start` (an `_arr` index) and `_doc_offset` (a document position). The
formula `doc_pos = _doc_offset + (arr_idx - _cycle_start)` is only correct while
`cycle_start` sits at the document end. Echo-pacing leaves typed chars unsent,
so `_tx_sent_idx` drifts below the document length → after a SEND→RECEIVE→SEND
turnaround, colouring **and** the `_sent_boundary` (cursor lock) are shifted by
the unsent gap, and straggler echoes colour the wrong cell.

**Phase 1 (done):** `char_typed` extended to `(str, str, int)` — every `_arr`
entry stores its **absolute** `doc_pos`, captured by `TxInputWidget` *before*
the insert, across all insert paths (keypress, paste, CTRL+D/T, space, macro).
`on_char_typed` stores it and emits a read-only self-consistency log
(`DOCPOS … [OK/MISMATCH]`: captured vs previous entry + its visible width).
`colour_at` still runs the old formula — behaviour unchanged.
**E5 finding (headless + hardware):** a CR/LF block break occupies **1** doc
position, `[^D]` occupies **4**. Width rule:
`1 if display.startswith('<CR/LF>') else len(display)`.

**Phase 2 (open):** switch `colour_at`/`colour_char` to the stored `doc_pos`;
remove `_doc_offset` / `_cycle_start` / `_doc_extra` / `set_cycle_anchor`;
reduce `_edit_boundary()` to `_sent_boundary`. This fixes the SEND→RECEIVE→SEND
straggler bug structurally (no more coordinate mixing).

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
| AMTOR ARQ | Not used (no btn_receive). EOT [^D] → PTOVER \x1A (Ctrl-Z). See §18. | PTOVER char |
| AMTOR FEC | Not used (no btn_receive). EOT [^D] → on_send_stop(). See §18. | (none) |
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
| ARQ turnaround (PTOVER char) | embedded in data stream | `01 1A 17` (SOH \x1A ETB) |

---

## 16. Mode-specific EOT behaviour (verified against the Technical Reference Manual, session 2026-06-16)

The `[^D]` EOT marker does **not** map to the same TNC action in every mode.
AMTOR in particular must NOT use `RC` (which would drop the link).

| Mode | EOT action | TNC command | Note |
|------|-----------|-------------|------|
| Baudot RTTY | RC | `RC` | Since v10, proven |
| ASCII RTTY | RC | `RC` | Like Baudot |
| CW/Morse | RC | `RC` | Paket 2a, TxController ACK-paced |
| AMTOR-ARQ | PTOVER char | `\x1A` (Ctrl-Z) | Embedded in TX stream; polite ISS↔IRS turnaround, link stays up. NOT the `OV` host command (fires immediately, TRM p.179). See §18. |
| AMTOR-FEC | stop controller | `on_send_stop()` | No connection concept; no TNC command. See §18. |
| Packet | — | — | No EOT; packetises at ETB; needs a Stop button (`AM`) |

Implementation note (Paket 2b, 8087564): `_on_baudot_eot()` branches for AMTOR
(ARQ → PTOVER `\x1A`, FEC → `on_send_stop()`), with ARQ vs FEC read from
`btn_fec`/`btn_selfec` (never `mode.name`). AMTOR is in `_is_txctrl_mode()`.

---

## 17. TxController pacing per mode

| Mode | Pacing mechanism | Parameter |
|------|------------------|-----------|
| Baudot/ASCII | QTimer → mspeed from config (Baud) | `set_mspeed(baud)` |
| CW/Morse | **Echo-paced** — next char released on the `$2F` echo; ≤ `_EAS_WINDOW` ahead | `_EAS_WINDOW=1`, `_EAS_SAFETY_MS=4000` (see §17.1) |
| AMTOR ARQ/FEC | Timer-paced; 3-character ARQ blocks | `set_mspeed_ms(50)` = `_AMTOR_TXCTRL_MS` |

`set_mspeed_ms(ms)` (added in Paket 1) takes a direct ms interval for modes
that have no meaningful Baud rate; `set_mspeed(baud)` only maps Baud → ms.
For Morse, `set_mspeed_ms(50)` is still called but the value is unused while
EAS is on — echo-pacing (§17.1) drives the tempo instead.

### 17.1 Morse echo-pacing (fixed 2026-06-18)

**Problem.** The old Morse path fed the TNC one char per `_MORSE_TXCTRL_MS`
(= 50 ms) — far faster than the TNC keys at the selected WPM. The whole message
therefore piled up inside the **TNC's own transmit buffer**. `RC` only drops
PTT; it does **not** flush that buffer, so Clear TX / RECEIVE blanked the screen
but the leftover characters resumed keying on the next SEND (hardware-confirmed
2026-06-18).

**Fix.** In EAS mode the controller is **echo-paced**: the next queued char is
handed to the TNC only after the previous char's `$2F` echo confirms it was
keyed on air, so the TNC never holds more than `_EAS_WINDOW` (= 1) char ahead.
RECEIVE/Clear TX then genuinely stop TX (≤ 1 residual char).

| Member | Role |
|--------|------|
| `_tnc_inflight` | Chars emitted to the TNC awaiting their `$2F` echo. |
| `_EAS_WINDOW` (=1) | Max chars allowed in the TNC buffer ahead of echoes. |
| `_EAS_SAFETY_MS` (=4000) | Lost-echo fallback so TX cannot lock up. |

Flow (`tx_controller.py`):
- `_emit_to_tnc()` — pops one queued char; real chars → `send_to_tnc` +
  `_tnc_inflight += 1` **unless `_is_unkeyed(char)`** (the newline — sent but
  never echoed, see §17.2); markers (`\x04`/`\x1b`) end the burst (unchanged
  semantics). Returns `'sent'` / `'stop'` / `'empty'`.
- `_pump_eas()` — emits up to `_EAS_WINDOW` chars, then (re)arms the safety
  timer while `_tnc_inflight > 0`. Called when chars are queued.
- `on_echo_char()` — at the top: `_tnc_inflight -= 1` then `_pump_eas()` to
  release the next char. Decoupled from the colouring bookkeeping (`_echo_idx`)
  lower in the same method: one `$2F` byte == one keyed char == one freed slot.
- `_send_next_char()` (the QTimer slot) — in EAS this is **only** the
  echo-overdue safety net: it force-sends one char without touching
  `_tnc_inflight`, so persistently lost echoes degrade to `_EAS_SAFETY_MS`/char
  rather than overfilling. Non-EAS modes keep the original Baud-paced loop.

`_tnc_inflight` is reset to 0 in `on_send_start()`, `on_send_stop()` and
`clear()`. EAS is enabled only for `"CW / Morse"`
(`set_eas_mode(mode.name == "CW / Morse")`), so Baudot/ASCII/AMTOR are
unaffected.

### 17.2 EAS echo stream — the three character classes (hardware-verified 2026-06-18)

In EAS/Morse the characters in the TX stream behave **differently** in the
TNC's `$2F` echo stream. This table is the authoritative reference — every
echo-pacing and colouring decision derives from it:

| Class | Examples | Sent to TNC? | Keyed by TNC? | `$2F` echo? | Coloured | `_tnc_inflight` |
|-------|----------|--------------|---------------|-------------|----------|-----------------|
| Normal  | A–Z, 0–9, punctuation | yes | yes | **yes** | on echo | +1 |
| Space   | `0x20` | yes | yes (word gap) | **yes** (`$2F 0x20`) | on keypress (NOT on echo) | +1 |
| Newline | `\r\n` (`0d 0a`) | yes (2 bytes) | **no** (no symbol) | **no** | in echo scan, as sent | **0** (not counted) |
| Marker  | `\x04` (EOT), `\x1b…` (timed) | **no** | no | no | EOT logic only | 0 |

**Consequences in `on_echo_char()` / `_emit_to_tnc()`:**
- **Normal** — `_tnc_inflight += 1` on send; the echo decrements it and colours.
- **Space** — `_tnc_inflight += 1`, but `colour_char` is **not** emitted on the
  echo (`TxInputWidget` already coloured the space on keypress, b157209); the
  echo is only *consumed* to keep `_echo_idx` in sync.
- **Newline** — `_is_unkeyed(char)` → **not** counted in `_tnc_inflight`. The
  leading scan (and the EOT look-ahead) in `on_echo_char()` **skip** it: colour
  it as sent + mirror `'\n'` to RX, but consume **no** echo for it — the current
  echo belongs to the *next* real char, reached after the `continue`.
- **Marker** — never sent to the TNC; skipped in the scans (EOT fires its own
  turnaround logic).

**Why this is subtle:** Space and Newline are both "invisible" characters, yet
the TNC treats them **oppositely** — a space is a *keyed* word gap (echoed),
a newline is pure formatting (not echoed). This was only verifiable against the
real TNC. Wrong assumptions caused, in sequence: a **+1 offset per space**
(assumed no echo; reality: echo — commit 668c903) and a **4 s stall per char
after a newline** (assumed echo like space; reality: no echo — commit 5dce1c0).

---

## 18. AMTOR-Specific TX Behaviour (Paket 2b, 8087564)

AMTOR differs from Baudot/Morse in three fundamental ways:

### No PTT toggle — link state drives TX
AMTOR has no `btn_send` and no XM frame. The TxController starts when
the ARQ link reaches CONNECTED state:
```python
# In _make_link_handler() — fires when TNC sends link message with "connected"
if "connected" in msg.lower() and mode.name == "AMTOR ARQ":
    self._tx_ctrl.on_send_start()
```
**CRITICAL:** This depends on the TNC sending a link message containing
"connected". Verify with T73 (hardware test). If the TNC sends a different
text, update the `"connected" in m` check in `_make_link_handler()`.

On DISCONNECT: `on_send_stop()` is called from the same handler.

### EOT action depends on ARQ vs FEC sub-mode
ARQ and FEC are screen sub-states (btn_fec / btn_selfec), NOT separate
ModeManager modes. ModeManager always produces `"AMTOR ARQ"`.

| Sub-mode | [^D] action | Reasoning |
|----------|------------|-----------|
| ARQ (btn_fec and btn_selfec NOT checked) | Send PTOVER char `\x1A` | Polite ISS↔IRS turnaround; link stays up. Waits for buffer drain (TRM p.179). |
| FEC (btn_fec or btn_selfec IS checked) | `on_send_stop()` | No ARQ connection — TNC returns to standby naturally. |

**Do NOT use the OV host command** — it fires immediately without
waiting for the buffer (TRM p.179: "Die Umschaltung erfolgt so schnell
wie möglich"). PTOVER char embedded in the (already empty) data stream
is the correct mechanism.

### Timer: ACK-paced, not Baud-rate-paced
```python
self._tx_ctrl.set_mspeed_ms(_AMTOR_TXCTRL_MS)  # = 50 ms
```
The TNC controls 100 Bd ARQ timing. The timer is only a buffer-overflow
safety net. If TX flow stutters on hardware, reduce `_AMTOR_TXCTRL_MS`.

*OE3GAS | PK232PY Project | AEA PK-232MBX Host Mode*
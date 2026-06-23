# Control Characters

Control characters can be typed in the TX window using keyboard shortcuts.
They appear as markers (e.g. `[^D]`) and are interpreted by the TNC or by
PK232PY when reached during transmission.

PK232PY supports two TX control markers: **`[^D]`** (Ctrl-D) and **`[^T:n]`**
(Ctrl-T). They work in every keyed mode that uses the TX window
(Baudot RTTY, ASCII RTTY, CW/Morse, AMTOR).

---

## Supported Control Characters

| Key | Marker | Effect |
|-----|--------|--------|
| Ctrl-D | `[^D]` | EOT — end of transmission. When the marker is reached, the TX buffer is flushed and the mode returns to receive (Baudot/ASCII/Morse send `RC`; AMTOR ARQ sends the polite `\x1A` turnaround). |
| Ctrl-T | `[^T:n]` | Timed marker — Ctrl-T opens a small dialog to enter *n*; the marker `[^T:n]` is inserted into the TX stream. |

The marker is shown in the TX window with a coloured background (EOT `[^D]` =
white-on-orange) so you can see exactly where it sits in the buffer before it
is sent.

---

## Notes

- `[^D]` is the recommended way to end a transmission cleanly. It lets the TNC
  flush the buffer before dropping PTT, avoiding cut-off endings.
- Both markers can be placed inside **macros** — e.g. a macro that signs off
  and drops to receive automatically: `73 DE OE3GAS  K[^D]`
- Markers are inserted as single editable units: pressing Backspace on a
  `[^D]` / `[^T:n]` removes the whole marker, not one character at a time.

> **WRU / AAB (answerback):** these are *TNC parameters*, not TX control
> characters. The auto-answerback string (AAB) and the WRU flag are configured
> in **Parameters → Baudot / AMTOR Parameters**, and the TNC sends the
> answerback automatically — there is no Ctrl-key to type them in the TX window.

---

## See Also

- [Keyboard Shortcuts](shortcuts)
- [Macros](macros)
- [Baudot RTTY](baudot)
- [AMTOR](amtor)

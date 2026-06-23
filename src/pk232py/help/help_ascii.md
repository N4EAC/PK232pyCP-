# ASCII RTTY

ASCII RTTY uses the 7-bit ASCII character set instead of ITA-2 (Baudot). This
allows transmission of all printable ASCII characters including lowercase
letters, punctuation, and special characters that are not available in Baudot.

Typical use: data transfer, bulletin boards, stations requiring lowercase text.

---

## Differences from Baudot RTTY

| | Baudot RTTY | ASCII RTTY |
|---|---|---|
| Character set | ITA-2 (5-bit, uppercase only) | 7-bit ASCII (upper + lower) |
| Shift states | LTRS / FIGS | None needed |
| Error sensitivity | Lower (5 bits per char) | Higher (7 bits per char) |
| Common baud rates | 45, 50, 75 Bd | 110, 300 Bd |

Because ASCII uses 7 bits per character, it is more susceptible to errors
than Baudot at the same baud rate and signal conditions.

---

## Operation

Operation is identical to Baudot RTTY — see [Baudot RTTY](baudot) for the
full description of SEND/RECEIVE, macros, keyboard shortcuts, and
troubleshooting.

The main differences in practice:

- Set **RBAUD** to match the station (110 or 300 Bd are most common for ASCII).
- No ITA-2 shift buttons (FIGS/LTRS) — not needed with ASCII.

---

## Toggle Buttons

| Button | Function |
|--------|----------|
| **RXREV** | Swap mark/space tones on receive. |
| **TXREV** | Swap mark/space tones on transmit. |
| **WIDESHFT** | Wide shift (850 Hz) vs. standard shift (170 Hz). |

---

## See Also

- [Baudot RTTY](baudot) — the more common ITA-2 variant
- [Keyboard Shortcuts](shortcuts)
- [Macros](macros)

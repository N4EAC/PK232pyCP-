# CW / Morse

The PK-232MBX can send and receive International Morse Code. The TNC handles
all encoding and decoding internally — you type plain text and the TNC keys
the radio at the configured speed.

Note: Morse decoding by computer is inherently less reliable than decoding
FSK modes like RTTY. Irregular fist, QRM, and QSB all affect decode quality.
For casual copying, human decoding is usually superior.

---

## Sending

1. Set **MSPEED** (words per minute) in the parameter row. Range: 5–99 WPM.
2. Click **SEND** (or `Alt+X`). The TNC activates PTT.
3. Type in the TX window. The TNC keys each character at the configured speed.
   Characters are sent **echo-paced**: the next character is not handed to the
   TNC until the previous one has actually been keyed on air. This means
   the TNC never holds more than one character ahead, so **Clear TX** and
   **RECEIVE** genuinely stop transmission immediately.
4. Click **RECEIVE** (`Alt+R`) to drop PTT.

The `[^D]` EOT marker (`Ctrl-D`) returns to receive after the buffer empties.

---

## Parameters

| Parameter | Description |
|-----------|-------------|
| **MSPEED** | Sending speed in WPM (5–99). The TNC keys at this speed regardless of typing speed. |
| **MWEIGHT** | Dot/dash weight. 50 = standard timing. Higher values = heavier (longer) dots and dashes. |
| **MID** | Morse ID interval in 10-second steps. 0 = disabled. The TNC sends your callsign in Morse at the set interval. |

---

## Receiving

Switch to CW / Morse from the Mode dropdown. The TNC's Morse decoder starts
automatically. Decoded text appears in the RX window.

Click **LOCK** to force the decoder to lock onto the current signal's timing.
This is useful when the TNC is not tracking the incoming speed correctly.

The decoder works best with clean, machine-sent Morse at consistent speed.
Hand-sent Morse with varying timing may produce errors.

---

## Special Morse Characters

The PK-232MBX supports standard Morse prosigns. Enter these in the TX window:

| Character | Morse prosign | Meaning |
|-----------|---------------|---------|
| `*` or `<` | SK | End of contact |
| `+` | AR | End of message |
| `(` | KN | Over to specific station only |
| `=` | BT | Break / separator |
| `>` or `%` | KA | Attention |
| `&` | AS | Stand by / wait |
| `!` | SN | Understood |

---

## Troubleshooting

**The decoder produces garbage characters.**
Morse decoding is difficult in the presence of QRM or with irregular keying.
Try clicking **LOCK** to re-synchronise the decoder to the current signal.

**After Clear TX, the TNC keeps keying.**
This should not happen with the echo-paced TX in PK232PY — at most one
character remains in the TNC buffer. If it does occur, click **Clear TX**
again (sends RC to the TNC).

**MID sends the ID at unexpected times.**
MID sends a Morse ID (your callsign) at the configured interval after a
transmission. Set MID to 0 to disable.

---

## See Also

- [Keyboard Shortcuts](shortcuts)
- [Macros](macros)
- [Control Characters](controls)

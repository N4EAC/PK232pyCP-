# Baudot RTTY

Baudot RTTY (Radio TeleTYpe) is the oldest digital mode supported by the
PK-232MBX. It uses the ITA-2 (International Telegraph Alphabet No. 2)
character set — a 5-bit code with two shift states (letters and figures)
transmitted as FSK (Frequency Shift Keying).

Typical use: amateur radio RTTY contests, DX, HF bulletin stations.

---

## Before You Start

Set the receive baud rate (**RBAUD**) to match the station you want to
receive. The most common value is **45 Bd** (standard amateur RTTY). European
stations often use **50 Bd**. The TX speed is independent and set via
**MSPEED** in Parameters → Baudot Parameters.

Check signal polarity: if received text is completely garbled (all wrong
characters), try toggling **RXREV**.

---

## Receiving

Switch to Baudot RTTY from the Mode dropdown. The TNC immediately starts
decoding any FSK signal on the audio input. Decoded text appears in the
RX window in blue.

Tune the radio until the two audio tones fall within the TNC's passband.
For standard 170 Hz shift: mark tone ≈ 2125 Hz, space tone ≈ 1955 Hz
(USB convention). The exact frequencies depend on your radio and TNC
settings.

---

## Transmitting

1. Click **SEND** (or press `Alt+X`). The TNC activates PTT.
2. Type in the TX window. Characters are sent one by one, rate-limited to
   the configured TX speed.
3. Click **RECEIVE** (or press `Alt+R`) to drop PTT and return to receive.

The `[^D]` control character (EOT) can be inserted with `Ctrl-D` in the TX
window. When the TNC reaches `[^D]`, it sends RC and returns to receive
automatically — useful for ending a transmission without manually clicking
RECEIVE.

---

## Toggle Buttons

| Button | Function |
|--------|----------|
| **RXREV** | Swap mark/space tones on receive. Use when received text is garbled. |
| **TXREV** | Swap mark/space tones on transmit. Use when the other station reports garbled text. |
| **USOS** | Unshift On Space. Forces a return to letters mode on each space. Prevents the display getting stuck in figures mode after a missed LTRS shift. |
| **WIDESHFT** | Wide shift (850 Hz) vs. standard shift (170 Hz). Use for older or military stations using wide shift. |

---

## ITA-2 Shift Buttons

- **Switch FIGS**: force a shift to figures/numbers mode.
- **Switch LTRS**: force a shift back to letters mode.

Use these if the display gets stuck showing numbers when it should show
letters, or vice versa.

---

## Macros

Up to 6 macros can be stored for frequently used text (your callsign, CQ
call, signal report, etc.). Click a macro button to send the stored text
immediately. Click **Edit Macros** to define the macro names and texts.

Macros support the `[^D]` EOT marker — for example a CQ macro that ends
with `[^D]` will transmit the CQ call and then automatically return to
receive.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Alt+X` | Toggle SEND |
| `Alt+R` | Toggle RECEIVE |
| `Ctrl-D` | Insert EOT marker `[^D]` |
| `Ctrl-T` | Insert timed pause marker `[^T:n]` (n = seconds) |

---

## Troubleshooting

**Received text is completely wrong characters.**
Toggle **RXREV** — the signal polarity is inverted.

**Received text shows figures where letters should be.**
The ITA-2 shift state is stuck in FIGS. Enable **USOS** (Unshift On Space)
to recover automatically, or click **Switch LTRS** to force a shift.

**TX is active but nothing is being sent.**
Check that **MSPEED** is set correctly in Parameters → Baudot Parameters.
Also verify that PTT is connected (radio should show TX).

**The TX window is empty but the TNC keeps transmitting.**
Click **Clear TX** — this sends RC to the TNC and flushes its internal
buffer. The RECEIVE button alone does not flush the TNC buffer if characters
were already sent to it.

---

## See Also

- [ASCII RTTY](ascii) — 7-bit ASCII variant
- [Keyboard Shortcuts](shortcuts)
- [Macros](macros)
- [Control Characters](controls)

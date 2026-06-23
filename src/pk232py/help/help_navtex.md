# NAVTEX

NAVTEX (NAVigational TEleX) is an international system for broadcasting
navigational and meteorological warnings to ships at sea. It operates on
**518 kHz** using AMTOR Mode B (FEC/SITOR) at 100 baud.

In amateur radio, the same mode is used for information broadcasts and is
called **AMTEX** (ARRL terminology).

NAVTEX is **receive only** — there is no transmit function.

---

## Reception

Switch to NAVTEX from the Mode dropdown. The TNC begins decoding immediately.
Messages appear in the RX window as they are received. No tuning or manual
action is required once the radio is set to 518 kHz (USB, audio passband
centred on the signal).

Each message is displayed only once — the TNC remembers the headers of the
last 200 messages and suppresses duplicates automatically.

---

## Message Format

NAVTEX messages always begin with `ZCZC` followed by a 4-character header:

```
ZCZC PA99
      |||
      ||+-- Serial number (2 digits, 00–99)
      |+--- Message class (A–Z)
      +---- Station identifier (A–Z)
```

Messages end with `NNNN`.

---

## Message Classes

| Class | Content | Mandatory |
|-------|---------|-----------|
| A | Navigational warnings | ✅ Yes |
| B | Meteorological warnings | ✅ Yes |
| C | Ice warnings | No |
| D | Search and rescue information | ✅ Yes |
| E | Weather forecasts | No |
| F | Pilot service messages | No |
| G | DECCA system information | No |
| H | LORAN-C system information | No |
| I | Omega system messages | No |
| J | SATNAV messages | No |
| K–Z | Reserved | No |

Classes A, B, and D are **mandatory** — they cannot be suppressed and are
always displayed regardless of the NAVMSG filter setting.

---

## Filters

### NAVMSG — Message class filter

Controls which message classes are displayed:

- `ALL` — show all classes (default)
- `NONE` — suppress all non-mandatory classes
- Comma-separated list, e.g. `A,B,D,E` — show only these classes

Use the checkboxes in the screen to select classes, or type directly in
the NAVMSG field. Classes A, B, D are always shown (mandatory, shown greyed
out as permanently selected).

### NAVSTN — Station filter

Controls which transmitter stations are received:

- `ALL` — receive from all stations (default)
- `NONE` — suppress all (not useful in practice)
- Comma-separated list, e.g. `A,P,S` — receive only from these stations

Each NAVTEX transmitter has a unique letter identifier. Stations near your
location can be identified from the message headers you receive.

---

## Troubleshooting

**No messages are being received.**
Check that the radio is tuned to 518 kHz (USB mode, correct audio level).
NAVTEX transmissions are scheduled — they do not broadcast continuously.
Check a broadcast schedule for your region.

**Messages appear but text is garbled.**
Check audio level and signal quality. NAVTEX uses AMTOR Mode B FEC which
provides some error correction, but very weak signals will still produce
errors.

**Duplicate messages are appearing.**
The TNC suppresses duplicates based on the 4-character header. If a message
was received with many errors previously, the TNC may show it again on a
cleaner reception. This is by design.

---

## See Also

- [AMTOR](amtor) — the underlying Mode B (FEC) technology

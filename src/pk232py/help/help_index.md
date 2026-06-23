# PK232PY Help

PK232PY is a multimode terminal for the **AEA PK-232MBX** TNC (Terminal Node
Controller). It supports all operating modes of the PK-232MBX and communicates
with the TNC via the Host Mode protocol over a serial port.

---

## Getting Started

Before using any operating mode, you need to:

1. Connect the TNC to the PC via serial port (default: COM16, 9600 baud).
2. Click **Connect** in the toolbar to open the serial connection to the TNC.
   You may enter "verbose" mode (a simple terminal) or "host mode", where the
   TNC is fully controlled by the program.
3. Click **Host Mode** to enter Host Mode. The status indicator on the top
   right turns green.
4. Select an operating mode from the **Mode** dropdown.

---

## Operating Modes

| Mode | Type | Frequency range |
|------|------|----------------|
| [Baudot RTTY](baudot) | TX + RX | HF / VHF |
| [ASCII RTTY](ascii) | TX + RX | HF / VHF |
| [AMTOR](amtor) | TX + RX | HF |
| [CW / Morse](morse) | TX + RX | HF / VHF |
| [PACTOR I](pactor) | TX + RX | HF |
| [HF Packet](packet) | TX + RX | HF (300 Bd) |
| [VHF Packet](vhf) | TX + RX | VHF (1200 Bd, APRS) |
| [NAVTEX](navtex) | RX only | HF (518 / 490 kHz) |
| [HF FAX](fax) | RX only | HF (WEFAX) |
| [Signal / SIAM](signal) | Analysis | — |

See also the displayed firmware version of the connected PK-232. Depending on
the firmware there may be limitations, e.g. no PACTOR mode available.

---

## Common Topics

- [Keyboard Shortcuts](shortcuts)
- [Macros](macros)
- [Control Characters](controls)

---

## The Host Mode

PK232PY communicates with the TNC via the **Host Mode** protocol (AEA
proprietary). Host Mode uses a binary frame format over the serial port, which
allows the PC software to control all TNC functions precisely.

---

## About PK232PY

PK232PY replaces the legacy PCPackRatt software (Windows 9x) with a modern
Python/PyQt6 application that runs on current versions of Windows, macOS, and
Linux.

- Developer: OE3GAS + Anthropic Claude
- License: GPL v2
- Repository: github.com/oe3gas/PK232py

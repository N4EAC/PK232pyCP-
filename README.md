# PK232PY

[![CI](https://github.com/OE3GAS/pk232py/actions/workflows/ci.yml/badge.svg)](https://github.com/OE3GAS/pk232py/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v2](https://img.shields.io/badge/License-GPL_v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com/OE3GAS/pk232py)

**PK232PY** is a modern, cross-platform multimode terminal program for the
**AEA PK-232 / PK-232MBX** Terminal Node Controller (TNC). It brings back the
functionality of the legacy PCPackRatt software — which no longer runs on 64-bit
Windows 10/11 or on Linux — and implements the full AEA Host Mode protocol stack
in Python.

Host Mode is the hidden gem of the PK-232: a continuous binary channel between
TNC and host that gives far better control and performance than the plain
terminal interface. On top of what modern software allows, the PK-232 still
performs beautifully as a dedicated appliance for the classic digital modes —
RTTY (Baudot/ASCII), AMTOR (ARQ/FEC), CW, PACTOR I, NAVTEX and HF FAX — and it
carries a built-in signal-analysis (SIAM) capability that works well on RTTY.

With this project I hope to support a small revival of the PK-232 (MBX) on the
bands.

> **Status: v0.1.0-beta — public beta for testing.**
> All ten operating-mode screens are implemented and the Host Mode stack is
> working against real hardware, but many on-air paths have only been verified
> against a mock TNC so far. **Testers are wanted** — see *Known Limitations*
> and *Reporting Problems* below. Not yet recommended for unattended or
> mission-critical operation.

---

## Download & Run the Beta (Windows, no Python needed)

The easiest way to try PK232PY is the pre-built Windows executable. You do
**not** need Python or any developer tools.

1. **Download** from the [latest Release](https://github.com/OE3GAS/pk232py/releases/latest):
   - `pk232py.exe` — the program (single file, no installer)
   - `pk232py.exe.sha256` — its checksum

2. **Verify the download** (recommended). In PowerShell, in the download folder:
   ```powershell
   Get-FileHash pk232py.exe -Algorithm SHA256
   ```
   Compare the printed hash with the contents of `pk232py.exe.sha256`. They must
   match — if they don't, do not run the file and please open an issue.

3. **Windows SmartScreen / Defender warning — this is expected.**
   The beta is **not code-signed**, so Windows will warn you the first time.
   This does not mean the file is unsafe; it means Windows doesn't yet recognise
   the (unsigned) publisher. Two ways past it:
   - **When SmartScreen appears** ("Windows protected your PC"): click
     **More info → Run anyway**.
   - **Or clear the download mark first**: right-click `pk232py.exe` →
     **Properties** → tick **Unblock** at the bottom → **OK**, then start it
     normally.

   Code signing (via the free SignPath Foundation OSS programme) is planned for
   a later release, which will remove the warning.

4. **First run** unpacks to `%TEMP%` (~60–80 MB, a few seconds). Subsequent
   runs use the cached files and start quickly.

5. **Serial adapter.** If your PC has no RS-232 port, use a USB-to-serial
   adapter. Prolific- and FTDI-based adapters both work; install the
   manufacturer's driver so the adapter appears as a COM port. You can find the
   assigned port in **Device Manager → Ports (COM & LPT)**.

Then continue with *Quick Start* below.

---

## Features

- Full **AEA Host Mode** implementation (firmware v7.0 / v7.1 / v7.2)
- Ten operating-mode screens, switched from a single window:
  - **Baudot/RTTY** and **ASCII-RTTY** — full keyed TX with live colour tracking
  - **AMTOR** — ARQ + FEC/SELFEC
  - **CW / Morse** — 5–99 WPM, keyed TX with Echo-As-Sent colouring
  - **PACTOR I** — ARQ
  - **NAVTEX** — receive
  - **HF FAX** — live on-screen image decode (WEFAX), aspect-corrected
  - **Signal / SIAM** — signal analysis (receive)
  - **HF Packet** (AX.25, 300 Bd) and **VHF Packet** (1200 Bd) — with APRS
    decoding (Mic-E, position, telemetry, weather, messages) and an MHEARD panel
- **Macro system** for canned text and TX control markers
- **Context help** (F1) on every screen, plus per-control tooltips
- **Four themes** (Dark, Mono, Retro, Air) with INI persistence
- Modern **PyQt6** GUI
- Cross-platform: **Windows 10/11**, **Linux**, **macOS** (from source)

## Supported Hardware

| Model | Firmware | Support |
|-------|----------|---------|
| AEA PK-232MBX | v7.1 (Sep 1995) | ✅ Primary reference |
| AEA PK-232MBX | v7.2 (Aug 1998) | ✅ Supported |
| AEA PK-232MBX | v7.0 | ✅ Supported |
| AEA PK-232 (non-MBX) | any | ⚠️ Limited (no PACTOR/MailDrop) |

> **Not supported:** PK-232SC, PK-232SC+ (different firmware architecture).

The firmware version is shown in the TNC's start-up banner (e.g.
`Release 13-09-95` = v7.1). Please include it in any bug report.

---

## Known Limitations (beta)

Please read this before testing so your reports land where they help most.

- **On-air Packet connect/disconnect and MHEARD are software/mock-verified, not
  yet fully hardware-confirmed** against a second live AX.25 station. Testers
  with a real second station are especially welcome here.
- **PACTOR I** is currently receive/monitor oriented; keyed PACTOR TX is not yet
  complete.
- **AMTOR ARQ TX** starts automatically on a CONNECTED link (there is no manual
  SEND button in ARQ); this path still needs on-air confirmation with a partner
  station.
- **FAX image smoothing** needs `numpy` + `scipy`, which are **not bundled in
  the Windows .exe** to keep it small. Without them the raw (un-smoothed) image
  is shown — this is by design and logs a one-line warning. Running from source
  with `pip install scipy` enables smoothing.
- **PACTOR/MailDrop** require a PK-232**MBX**; on a non-MBX PK-232 those options
  are disabled.
- No **QSO log** and no **MailDrop** UI yet (planned for v1.0).

---

## Quick Start

1. Connect your PK-232MBX to a serial port (or USB-serial adapter).
2. Launch PK232PY (the `.exe`, or `python -m pk232py` from source).
3. Go to **Configure → TNC Configuration**.
4. Select TNC Model `PK232MBX`, set your COM port and baud rate (9600 for
   firmware v7.x).
5. Click **OK** — the program initialises the TNC and enters Host Mode.
6. Set your callsign via **Parameters → HF Packet Params → MGCALL**.
7. Select an operating mode and start working. Press **F1** on any screen for
   context help.

---

## Installation from Source

For Linux/macOS, or if you prefer to run from source on Windows.

### Requirements

- Python 3.10 or newer
- PyQt6, pyserial (installed automatically)
- Optional: `scipy` (enables FAX image smoothing)
- A USB-to-serial adapter if your PC has no RS-232 port

### Install and run

```bash
git clone https://github.com/OE3GAS/pk232py.git
cd pk232py
pip install -e .
python -m pk232py
```

---

## Development Setup

```bash
git clone https://github.com/OE3GAS/pk232py.git
cd pk232py
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for coding style, branch naming and the
pull-request workflow.

---

## Building the Windows Executable

Requirements: Python 3.10+ (CPython from python.org, **not** the Microsoft Store
build), Git, PowerShell 5+.

```powershell
git clone https://github.com/OE3GAS/pk232py.git
cd pk232py
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\pip install nuitka
.\build_windows.ps1
```

Output: `dist\pk232py.exe` — a single self-contained executable (Nuitka
onefile), no installation needed.

> To include FAX image smoothing in the build, install `scipy` into the same
> virtual environment before running the script
> (`.venv\Scripts\pip install scipy`). This noticeably increases the `.exe`
> size and start-up time, so it is left out of the standard beta build.

---

## Project Structure

```
pk232py/
├── src/pk232py/
│   ├── comm/          # Serial port, Host Mode protocol, KISS
│   ├── modes/         # Operating modes (Packet, PACTOR, AMTOR, ...)
│   ├── ui/            # PyQt6 GUI (main window, screens, dialogs)
│   ├── help/          # Markdown context-help files
│   ├── macros/        # Macro system
│   ├── log/           # QSO log (planned)
│   ├── maildrop/      # MailDrop (planned)
│   └── tests/         # Unit tests
├── tools/             # Standalone dev/test tools (not shipped)
├── build_windows.ps1  # Nuitka onefile build script
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## Roadmap

| Version | Milestone | Status |
|---------|-----------|--------|
| **v0.1.0-beta** | Host Mode stack; all ten operating-mode screens; keyed TX for Baudot/ASCII/Morse/AMTOR; live FAX decode; APRS + MHEARD; macros; context help; themes | ← **current** |
| post-beta | On-air hardware verification of Packet connect/disconnect + MHEARD; PACTOR I keyed TX; automated release builds on tags (GitHub Actions); code signing (SignPath) | planned |
| v1.0 | MailDrop, QSO log, full parameter persistence, complete documentation, stable release | planned |

---

## Contributing & Testing

Contributions are very welcome — especially **hardware testing**. If you own a
PK-232 / PK-232MBX, please try the beta and tell us how it goes. Read
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Reporting Problems

Please open an issue using the **Bug Report** template and include:
your OS, PK232PY version, TNC model and **firmware version** (from the start-up
banner), the serial port/adapter, and steps to reproduce. For ideas and
enhancements, use the **Feature Request** template.

---

## License

PK232PY is free software: you can redistribute it and/or modify it under the
terms of the **GNU General Public License version 2** as published by the Free
Software Foundation. See [LICENSE](LICENSE) for the full text.

---

## Background

The AEA PK-232MBX is a legendary multi-mode TNC from the late 1980s / early
1990s, and thousands are still in the hands of amateur radio operators
worldwide. The only software that ever supported its full Host Mode capability —
PCPackRatt for Windows — is a 32-bit Windows XP-era application that no longer
runs on modern 64-bit systems and was never available for Linux or macOS.

PK232PY aims to fill that gap.

---

*73 de OE3GAS*
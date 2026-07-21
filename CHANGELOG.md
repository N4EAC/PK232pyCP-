# Changelog

All notable changes to PK232PY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Work in progress toward v1.0 — see the roadmap in the README._

---

## [0.1.0-beta] - 2026-07-21

First public beta. All ten operating-mode screens are implemented and the AEA
Host Mode stack runs against real PK-232MBX hardware. Many on-air paths are so
far verified against a mock TNC; see *Known Limitations* in the README.

### Added

- **Host Mode protocol stack** — binary framing, command API, active-polling
  (HPOLL) architecture, capability detection (PACTOR), autobaud.
- **Ten operating-mode screens** switched from one window via `QStackedWidget`:
  - Baudot/RTTY and ASCII-RTTY with keyed TX and live TX colour tracking.
  - CW/Morse (5–99 WPM) with keyed TX and Echo-As-Sent character colouring.
  - AMTOR (ARQ + FEC/SELFEC); ARQ TX is triggered by the CONNECTED link state.
  - PACTOR I (receive/monitor).
  - NAVTEX (receive).
  - Signal / SIAM analysis (receive).
  - HF FAX — live on-screen WEFAX decode of the TNC's Epson 9-pin graphics
    stream, with pixel-aspect correction and an optional smoothing slider.
  - HF Packet (AX.25, 300 Bd) and VHF Packet (1200 Bd) with APRS decoding
    (Mic-E, position, telemetry, weather, messages) and an MHEARD panel.
- **Macro system** with TX control markers (`[^D]` EOT, `[^T:n]` timed).
- **Context help** (F1) on every screen and per-control tooltips.
- **Four themes** (Dark, Mono, Retro, Air) with INI persistence.
- **TNC configuration dialog**; firmware version detection from the start-up
  banner; `RESTART` / `RESET` support.
- **Windows onefile build** via Nuitka (`build_windows.ps1`).
- Developer tooling: in-process mock TNC + mini-BBS for connected-mode tests,
  and a closed-loop WEFAX WAV generator/decoder (both dev-only, not shipped).

### Known Limitations

- On-air Packet connect/disconnect and MHEARD are software/mock-verified, not
  yet fully hardware-confirmed against a live second station.
- PACTOR I keyed TX is not yet complete.
- FAX image smoothing requires `numpy` + `scipy`, which are not bundled in the
  Windows `.exe`; the raw image is shown instead (with a log warning).
- No QSO log and no MailDrop UI yet.

---

[Unreleased]: https://github.com/OE3GAS/pk232py/compare/v0.1.0-beta...HEAD
[0.1.0-beta]: https://github.com/OE3GAS/pk232py/releases/tag/v0.1.0-beta
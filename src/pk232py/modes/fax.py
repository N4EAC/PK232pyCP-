# pk232py - Modern multimode terminal for AEA PK-232 / PK-232MBX TNC
# Copyright (C) 2026  OE3GAS  —  GPL v2
"""FAX receive mode (HF weather-chart facsimile).

The PK-232MBX can receive HF weather-chart facsimile (WEFAX) broadcasts.
FAX is receive-only in practice. The TNC outputs the image over $3F as an
Epson 9-pin printer-graphics stream (ESC L double-density bit image +
ESC A band separators), which EpsonFaxParser decodes into grayscale image
rows for the host to render (live decode implemented; Testplan T82).

Key characteristics
-------------------
- Receive-only (weather charts, satellite images)
- Standard HF FAX frequencies: 4, 8, 12, 16, 22 MHz bands
- FSPEED: drum speed in RPM (default varies; common: 60, 90, 120, 240)
- ASPECT: line density control (1-6, affects image proportions)
- FAXNEG: negative image (invert black/white)
- GRAPHICS: print density (dot-matrix printer output, legacy)

Host Mode frame types
---------------------
  Incoming:
    $3F  RX_MONITOR  — Epson 9-pin printer-graphics stream (NOT grayscale);
                       decoded into image rows by EpsonFaxParser
    $5F  STATUS_ERR  — sync lost or other error

  Outgoing:
    $4F  build_command(b'FA')         — enter FAX mode (mnemonic FA)
    $4F  build_command(b'FS', speed)  — FSPEED drum RPM
    $4F  build_command(b'AY', aspect) — ASPECT line density
    $4F  build_command(b'FN', yn)     — FAXNEG (Y/N)

Host Mode mnemonics (TRM)
--------------------------
  FA   FAX     — enter FAX receive mode
  FS   FSPEED  — drum rotation speed (RPM)
  AY   ASPECT  — aspect ratio / line density (1-6, default 2=576 lpi)
  FN   FAXNEG  — negative image (Y/N)
  GR   GRAPHICS— print dot density (legacy printer output)
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, TYPE_CHECKING

from pk232py.comm.frame import build_command, FrameKind
from pk232py.modes.base_mode import BaseMode

if TYPE_CHECKING:
    from pk232py.comm.frame import HostFrame

logger = logging.getLogger(__name__)

# Common HF FAX drum speeds (RPM)
FSPEED_60  = 60
FSPEED_90  = 90
FSPEED_120 = 120
FSPEED_240 = 240

# TNC FSPEED index mapping: RPM value → TNC index (0-4)
# The TNC expects a single-digit index, NOT the RPM value.
# FS 0 = 90 LPM, FS 1 = 60 LPM, FS 2 = 120 LPM (standard),
# FS 3 = 180 LPM, FS 4 = 240 LPM
FSPEED_RPM_TO_IDX: dict[int, int] = {
    90:  0,
    60:  1,
    120: 2,   # standard WEFAX
    180: 3,
    240: 4,
}


# ---------------------------------------------------------------------------
# Epson 9-pin printer-graphics parser  (the REAL $3F FAX payload)
# ---------------------------------------------------------------------------
#
# LERNMODUS — what the PK-232 actually sends, and why this parser exists
# ----------------------------------------------------------------------
# WHAT: in FAX receive the PK-232 does NOT stream 8-bit grayscale scan lines
# over $3F (RX_MONITOR). It streams an Epson FX-80 / 9-pin dot-matrix PRINTER
# graphics command stream — literally the bytes it would send to a printer:
#
#     ESC 'L' n1 n2   then N = n1 + 256*n2 column bytes  (double-density bit image)
#     ESC 'A' n       set line spacing to n/72"          (block separator; ignore n)
#     CR / LF                                             (ignore)
#
# Each column byte encodes 8 VERTICAL dots, D7 = top pin. A set bit = a fired
# dot = BLACK on paper. So one "ESC L" block of N columns is 8 horizontal image
# rows, N pixels wide. The logged stream "1b 4c c0 03 …" is ESC L with
# N = 0xC0 + 256*0x03 = 960 columns, then 960 column bytes, blocks separated by
# "1b 41 08" (ESC A 8).
#
# WHY a stateful, frame-overlapping parser: $3F frames are chopped at arbitrary
# Host-Mode frame boundaries, so an ESC L header — or the N column bytes — can
# split across two frames. The parser keeps an internal buffer and a
# length-driven state machine that survives across feed() calls.
#
# GOTCHA 1 (the bug this fixes): the old path rendered the raw ESC bytes as a
# grayscale line, so "1b 4c c0 03 …" became garbage pixels and the line counter
# was meaningless.
# GOTCHA 2: 0x1B (ESC) is a perfectly valid DATA byte inside the N-column run.
# We must NEVER scan for escapes while in DATA — only the length N marks the end
# of a block. Escapes are recognised in the SCAN state only.
# GOTCHA 3: D7 is the TOP pin (mask = 1 << (7 - r)); using 1 << r mirrors every
# 8-row block vertically.

class EpsonFaxParser:
    """Parse the PK-232's Epson 9-pin printer-graphics $3F stream into 8-bit
    grayscale image rows. Qt-free and unit-testable.

    Feed each $3F payload (in order) to ``feed()``. For every completed image
    row the ``on_row`` callback fires once with a ``bytes`` of length N
    (0 = black, 255 = white). ``invert=True`` swaps the polarity — provided for
    a future fix; FAXNEG in the widget is left untouched.
    """

    _SCAN = 0
    _DATA = 1

    def __init__(
        self,
        on_row: Optional[Callable[[bytes], None]] = None,
        invert: bool = False,
    ) -> None:
        self.on_row = on_row
        self.invert = invert
        self.reset()

    def reset(self) -> None:
        """Clear the internal buffer and return to the SCAN state."""
        self._buf: bytearray = bytearray()
        self._state: int = self._SCAN
        self._cols: bytearray = bytearray()   # column bytes of the current block
        self._need: int = 0                     # N columns expected in this block

    def feed(self, data: bytes) -> None:
        """Feed one $3F payload chunk; emits rows as blocks complete."""
        self._buf.extend(data)
        self._process()

    def _process(self) -> None:
        buf = self._buf
        i = 0
        n = len(buf)
        while i < n:
            if self._state == self._DATA:
                # Pure length-driven collection. NO escape scanning here —
                # 0x1B is a valid column byte (GOTCHA 2).
                take = min(self._need - len(self._cols), n - i)
                self._cols.extend(buf[i:i + take])
                i += take
                if len(self._cols) >= self._need:
                    self._emit_block()
                    self._cols = bytearray()
                    self._need = 0
                    self._state = self._SCAN
                    continue
                break   # consumed all we have; wait for the next feed()

            # --- SCAN state ---
            b = buf[i]
            if b == 0x1B:                       # ESC
                if n - i < 2:
                    break                       # wait for the command byte
                cmd = buf[i + 1]
                if cmd == 0x4C:                 # 'L' — bit image, N columns follow
                    if n - i < 4:
                        break                   # wait for n1, n2
                    N = buf[i + 2] + 256 * buf[i + 3]
                    i += 4
                    if N == 0:
                        continue                # empty block — nothing to emit
                    self._need = N
                    self._cols = bytearray()
                    self._state = self._DATA
                    continue
                if cmd == 0x41:                 # 'A' — line spacing n/72"; ignore n
                    if n - i < 3:
                        break                   # wait for the parameter byte
                    i += 3
                    continue
                logger.debug("EpsonFaxParser: unhandled ESC %#04x — skipping", cmd)
                i += 2                          # defensive: drop ESC + that byte
                continue
            if b in (0x0D, 0x0A):               # CR / LF between blocks — ignore
                i += 1
                continue
            logger.debug("EpsonFaxParser: stray byte %#04x in SCAN — skipping", b)
            i += 1                              # defensive resync
        del buf[:i]                             # drop everything consumed this pass

    def _emit_block(self) -> None:
        """Emit the 8 image rows (top → bottom) of the completed column block."""
        cols = self._cols
        set_val, clear_val = (255, 0) if self.invert else (0, 255)
        for r in range(8):
            mask = 1 << (7 - r)                 # D7 = top pin (GOTCHA 3)
            row = bytes(set_val if (c & mask) else clear_val for c in cols)
            if self.on_row is not None:
                self.on_row(row)


class FAXMode(BaseMode):
    """HF Weather-chart FAX receive mode.

    Receive-only mode for HF facsimile broadcasts (WEFAX). The TNC delivers
    the image over RX_MONITOR ($3F) frames as an **Epson 9-pin printer-graphics
    stream** (ESC L bit image + ESC A band separators), NOT as grayscale scan
    lines. FAXMode holds an EpsonFaxParser, feeds every $3F payload to it in
    handle_frame(), and resets it in get_activate_frames(); the parser turns the
    stream into finished grayscale image rows and hands each one to
    on_data_received. (Live image decode is fully implemented and
    hardware-verified — Testplan T82.)

    Callbacks
    ---------
    ``on_data_received``  : ``Callable[[bytes], None]``
        Called once per decoded grayscale image row (0=black, 255=white),
        produced by EpsonFaxParser from the $3F Epson-graphics stream.
    """

    name         = "FAX"
    host_command = b'FA'   # Host Mode activation (FA mnemonic)

    def __init__(
        self,
        fspeed: int  = 120,   # drum speed RPM
        aspect: int  = 2,     # line density 1-6 (2=576 lpi standard)
        faxneg: bool = False,  # negative image
    ) -> None:
        super().__init__()
        self.fspeed = fspeed
        self.aspect = max(1, min(6, aspect))
        self.faxneg = faxneg

        self.on_data_received: Optional[Callable[[bytes], None]] = None

        # Decode the Epson 9-pin printer-graphics $3F stream into grayscale
        # rows. on_row → _emit_row reads self.on_data_received at call time, so
        # it works even though main_window sets that callback after __init__.
        self._parser = EpsonFaxParser(on_row=self._emit_row)

    def _emit_row(self, row: bytes) -> None:
        """Parser callback — forward one finished grayscale row downstream.

        Each row is a ready-to-render bytes() (0 = black, 255 = white), so the
        host's on_data_received (→ FaxImageWidget.append_line) is unchanged.
        """
        if self.on_data_received:
            self.on_data_received(row)

    def get_activate_frames(self) -> list[bytes]:
        """Return FA frame — switches TNC to FAX receive mode.

        Reset the Epson parser so a new FAX session starts with a clean buffer
        (no leftover half-block from a previous session).
        """
        self._parser.reset()
        return [build_command(b'FA')]

    def get_init_frames(self) -> list[bytes]:
        return [
            self.fspeed_frame(self.fspeed),
            self.aspect_frame(self.aspect),
            self.faxneg_frame(self.faxneg),
        ]

    def handle_frame(self, frame: "HostFrame") -> None:
        kind = frame.kind
        if kind == FrameKind.RX_MONITOR:
            # $3F carries Epson 9-pin printer graphics, NOT grayscale lines.
            # Feed the stateful parser; it emits finished rows via _emit_row.
            logger.debug("FAX RX %d bytes (Epson graphics)", len(frame.data))
            self._parser.feed(frame.data)
        elif kind == FrameKind.STATUS_ERR:
            logger.warning("FAX status error: %s", frame.data.hex())
        elif kind == FrameKind.CMD_RESP:
            logger.debug("FAX CMD_RESP: %s", frame.data.hex())
        else:
            logger.debug("FAX: unhandled frame %r", frame)

    @staticmethod
    def fspeed_frame(rpm: int) -> bytes:
        """FSPEED — drum rotation speed (mnemonic FS).

        The TNC expects the FSPEED INDEX (0-4), not the RPM value.
        Looks up rpm in FSPEED_RPM_TO_IDX; defaults to index 2
        (120 LPM) if the rpm value is not found.

        Args:
            rpm: Drum speed in RPM (60, 90, 120, 180, 240).
        """
        idx = FSPEED_RPM_TO_IDX.get(rpm, 2)   # default: 120 LPM
        return build_command(b'FS', str(idx).encode('ascii'))

    @staticmethod
    def aspect_frame(value: int) -> bytes:
        """ASPECT — line density / aspect ratio (mnemonic AY).

        Range 1-6.  Default 2 (576 lines per inch, standard WEFAX).
        Higher values stretch the image vertically.
        """
        return build_command(b'AY', str(max(1, min(6, value))).encode('ascii'))

    @staticmethod
    def faxneg_frame(enabled: bool) -> bytes:
        """FAXNEG — invert image (negative), mnemonic FN."""
        return build_command(b'FN', b'Y' if enabled else b'N')
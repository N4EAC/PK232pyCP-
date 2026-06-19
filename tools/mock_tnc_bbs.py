#!/usr/bin/env python3
# pk232py - Modern multimode terminal for AEA PK-232 / PK-232MBX TNC
# Copyright (C) 2026  OE3GAS  —  GPL v2
#
# This is a DEV-ONLY test tool. It is never shipped with the application.
# It is GPL v2 because it imports the project's GPL-v2 comm layer
# (pk232py.comm.frame / .constants) — NOT GPL v3 like fax_decoder_test.py.
"""mock_tnc_bbs.py — in-process mock PK-232 with a mini-BBS (dev-only).

Lets you exercise the Packet *connected* mode (Testplan T33–T39) with NO real
TNC, NO radio and NO second station. A ``LoopbackTNC`` object duck-types
``serial.Serial`` and is injected into ``SerialManager`` via a port factory, so
the whole application talks to it exactly as if it were a real port.

------------------------------------------------------------------------------
LERNMODUS — the three non-obvious ideas
------------------------------------------------------------------------------

1. THE SYNCHRONOUS-LOOPBACK TRICK (and why it does NOT break CLAUDE.md §3)
   CLAUDE.md §3 forbids putting a worker thread / queue BETWEEN the serial port
   and the app for Host Mode frames: the Windows Prolific driver only delivers
   ACKs when read() is called directly, so a worker delays them until close.
   The mock does NOT sit between the port and the app — it *is* the port.
   ``write()`` processes the bytes INLINE and appends the TNC's reply frames to
   an internal RX buffer; ``read()`` serves straight from that buffer. So a
   reply is readable on the very next read() — there is no worker, no queue, no
   deferral. (The mock spawns no threads of its own. It only guards its RX
   buffer with a lock because the app reads it from its own reader thread while
   the GUI thread writes — that is concurrent ACCESS of a passive object, not a
   worker interposed in the data path.)

2. THE HOST-MODE ENTRY SHORTCUT
   The real Host-Mode entry runs a SUBPROCESS (pk232_hostmode_sub.py) that
   opens a REAL serial port by name — it cannot talk to an in-process object,
   and a port factory cannot intercept it. But SerialManager.init_tnc() already
   has a clean second entry: after the ``*`` wakeup it checks the response for a
   SOH byte and, if present, declares the TNC "already in Host Mode" and starts
   a normal reader thread (no subprocess). So the mock answers the ``*`` wakeup
   with a SOH-bearing frame; the connection FSM reaches Host Mode through that
   existing path with zero subprocess and zero extra production code.

3. THE CHANNEL ECHO + TWO LAYERS
   Layer 1 (LoopbackTNC) is pure Host-Mode transport + link state: it parses
   host→TNC frames, answers GG polls, and turns CONNECT/DISCONNECT/data into
   BBS calls. Layer 2 (MiniBBS) is the application logic and knows nothing about
   framing. The AX.25 channel travels in the low nibble of the CONNECT frame's
   CTL byte; the mock latches it and reuses it on EVERY reply ($3x data, $5x
   link message) so the app's per-channel routing lines up.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time

# Reuse the project's comm layer — do NOT reimplement framing/escaping.
from pk232py.comm.constants import (
    SOH, ETB,
    CTL_TX_CMD,          # $4F  host→TNC general command (also $4F = RX cmd resp)
    CTL_TX_CMD_CH_BASE,  # $40  host→TNC channel command base (CO / DI)
    CTL_TX_DATA_BASE,    # $20  host→TNC data base
    CTL_RX_DATA_BASE,    # $30  TNC→host data base
    CTL_RX_MSG_BASE,     # $50  TNC→host link-message base
    CTL_RX_CMD_RESP,     # $4F  TNC→host command response
    CmdError,
    ctl_channel, ctl_type_range,
)
from pk232py.comm.frame import FrameParser, _dle_escape

logger = logging.getLogger("mock_tnc_bbs")


# ===========================================================================
# Layer 2 — the mini-BBS application (framing-agnostic pure logic)
# ===========================================================================

_PROMPT = "Command: "                       # no trailing newline (a prompt)
_MENU = (
    "Commands: L(ist messages), R(ead message #), D(isconnect)\r\n"
)
_LIST = (
    "List of Messages:\r\n"
    "#1 - Test-Message 1\r\n"
    "#2 - The Quick Brown Fox\r\n"
    "#3 - Alles Gute von der Pute\r\n"
    "#4 - Don't mess with Texas\r\n"
)
# Message bodies — the subject line itself is enough body (task spec).
_MESSAGES = {
    "1": "Test-Message 1",
    "2": "The Quick Brown Fox",
    "3": "Alles Gute von der Pute",
    "4": "Don't mess with Texas",
}


class MiniBBS:
    """Two-state BBS over connected data. Returns a list of (kind, text) where
    kind is 'link' (→ $5x link message) or 'data' (→ $3x channel data).

    It NEVER touches framing or channels — Layer 1 does that. The link-message
    wording contains the substrings the app's connected detector matches
    (``_make_link_handler``: 'connected' / 'disconnect', case-insensitive), so
    a real TNC using the same wording would drive the UI identically.
    """

    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"

    def __init__(self) -> None:
        self.state = self.DISCONNECTED
        self.target = ""

    def connect(self, target: str) -> list[tuple[str, str]]:
        """Remote station connected us: link message + welcome banner."""
        self.target = target
        self.state = self.CONNECTED
        banner = f"Willkommen bei {target} BBS\r\n" + _MENU + _PROMPT
        return [("link", f"CONNECTED to {target}"), ("data", banner)]

    def data(self, raw: bytes) -> list[tuple[str, str]]:
        """One line of connected input. Case-insensitive, trimmed, first token."""
        if self.state != self.CONNECTED:
            return []                       # ignore stray data when down
        parts = raw.decode("latin-1", "replace").strip().split()
        cmd = parts[0].upper() if parts else ""

        if cmd == "L":
            return [("data", _LIST + _PROMPT)]

        if cmd == "R":
            n = parts[1] if len(parts) > 1 else ""
            body = _MESSAGES.get(n)
            if body is None:
                return [("data", "No such message.\r\n" + _PROMPT)]
            return [("data", f"#{n}: {body}\r\n" + _PROMPT)]

        if cmd == "D":
            # Remote-initiated disconnect: farewell, then tear the link down.
            self.state = self.DISCONNECTED
            return [("data", f"Goodbye! {self.target} BBS\r\n"),
                    ("link", "DISCONNECTED")]

        # Anything else → repeat the menu.
        return [("data", _MENU + _PROMPT)]

    def disconnect(self) -> list[tuple[str, str]]:
        """Host-initiated disconnect (DI command) → tear the link down."""
        self.state = self.DISCONNECTED
        return [("link", "DISCONNECTED")]


# ===========================================================================
# Layer 1 — the mock TNC (duck-typed serial.Serial, Host-Mode transport)
# ===========================================================================

class LoopbackTNC:
    """In-process stand-in for ``serial.Serial`` — a PK-232 in Host Mode running
    a MiniBBS. Synchronous and single-threaded (see module docstring idea #1).

    Duck-types exactly the attributes/methods SerialManager (and its reader
    thread / init thread) use: write, read, read_until, in_waiting,
    reset_input_buffer, reset_output_buffer, flush, close, open, is_open, and
    the rts/dtr/port/baudrate/timeout attributes.
    """

    def __init__(self, *, port: str | None = None, baudrate: int = 9600,
                 timeout: float = 0.1, trace: bool = False, **_kwargs) -> None:
        # pyserial-compatible attributes the app reads/sets directly.
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.rts = False
        self.dtr = False

        self._open = True
        self._trace = trace
        self._rx = bytearray()              # TNC→host bytes waiting to be read
        self._lock = threading.Lock()       # guards _rx (app reads from a thread)
        self._parser = FrameParser(self._on_host_frame)   # decodes host→TNC
        self._bbs = MiniBBS()
        self._channel = 1                   # latched from CONNECT, echoed back

    # ------------------------------------------------------------------
    # serial.Serial duck-typing — attributes / lifecycle
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def flush(self) -> None:
        pass

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._rx.clear()

    def reset_output_buffer(self) -> None:
        pass

    @property
    def in_waiting(self) -> int:
        with self._lock:
            return len(self._rx)

    # ------------------------------------------------------------------
    # serial.Serial duck-typing — I/O
    # ------------------------------------------------------------------

    def write(self, data: bytes) -> int:
        """Process host→TNC bytes INLINE and append any reply to the RX buffer.

        Replies are available on the very next read() — no worker, no deferral
        (CLAUDE.md §3, module docstring idea #1).
        """
        if not self._open:
            raise RuntimeError("LoopbackTNC.write on a closed port")
        data = bytes(data)
        # The '*' autobaud wakeup is NOT a framed Host Mode frame (no SOH).
        # Answer it with a SOH-bearing frame so init_tnc detects Host Mode.
        if SOH not in data and b"*" in data:
            self._emit_wakeup_response()
            return len(data)
        self._parser.feed(data)             # frames → _on_host_frame
        return len(data)

    def read(self, size: int = 1) -> bytes:
        """Return up to *size* buffered bytes; block up to *timeout* if empty
        (mimics pyserial: returns what is available, or b'' on timeout)."""
        deadline = time.monotonic() + (self.timeout or 0.0)
        while True:
            with self._lock:
                if self._rx:
                    n = min(size, len(self._rx))
                    chunk = bytes(self._rx[:n])
                    del self._rx[:n]
                    return chunk
            if not self.timeout or time.monotonic() >= deadline:
                return b""
            time.sleep(0.005)

    def read_until(self, expected: bytes = b"\n", size: int | None = None) -> bytes:
        """Read until *expected* is seen, *size* bytes collected, or timeout
        (pyserial-compatible; provided for completeness)."""
        out = bytearray()
        deadline = time.monotonic() + (self.timeout or 0.0)
        while True:
            chunk = self.read(1)
            if chunk:
                out.extend(chunk)
                if expected and out.endswith(expected):
                    break
                if size is not None and len(out) >= size:
                    break
            elif not self.timeout or time.monotonic() >= deadline:
                break
        return bytes(out)

    def cancel_read(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Host-Mode transport — incoming frame handling
    # ------------------------------------------------------------------

    def _on_host_frame(self, frame) -> None:
        """Dispatch one decoded host→TNC frame (called inline from write())."""
        ctl, data = frame.ctl, frame.data
        self._trace_io(">> host", ctl, data)

        if ctl == CTL_TX_CMD:                         # $4F general command
            mnem = data[:2]
            if mnem == b"GG":                         # GG poll
                self._handle_poll()
            else:                                     # any other command → ACK
                self._push_frame(CTL_RX_CMD_RESP, mnem + bytes([CmdError.OK]))
            return

        rng = ctl_type_range(ctl)
        ch = ctl_channel(ctl)
        if rng == CTL_TX_CMD_CH_BASE:                 # $4x channel command
            self._channel = ch                        # latch + echo (idea #3)
            mnem = data[:2]
            if mnem == b"CO":
                target = data[2:].decode("latin-1", "replace").strip()
                if target:                            # CONNECT <call>
                    self._emit_bbs(self._bbs.connect(target))
                # bare 'CO' = link-status query — not part of the BBS; ignore.
            elif mnem == b"DI":                       # DISCONNECT (host-initiated)
                self._emit_bbs(self._bbs.disconnect())
        elif rng == CTL_TX_DATA_BASE:                 # $2x connected data
            self._channel = ch
            self._emit_bbs(self._bbs.data(data))

    def _handle_poll(self) -> None:
        """GG poll: nothing pending → GG-OK; otherwise the queued frame(s) are
        already in the RX buffer for the app's next read (TRM 4.4.1)."""
        with self._lock:
            pending = bool(self._rx)
        if not pending:
            self._push_frame(CTL_RX_CMD_RESP, b"GG" + bytes([CmdError.OK]))

    # ------------------------------------------------------------------
    # Host-Mode transport — outgoing frame building
    # ------------------------------------------------------------------

    def _emit_bbs(self, items: list[tuple[str, str]]) -> None:
        """Frame each BBS reply on the latched channel: 'link'→$5x, 'data'→$3x."""
        for kind, text in items:
            payload = text.encode("latin-1", "replace")
            base = CTL_RX_MSG_BASE if kind == "link" else CTL_RX_DATA_BASE
            self._push_frame(base | self._channel, payload)

    def _emit_wakeup_response(self) -> None:
        """Reply to the '*' wakeup with a banner + a GG-OK frame.

        The banner's 'PACTOR'/'PK-232' markers make has_pactor True; the GG-OK
        frame supplies the SOH byte that init_tnc uses to detect Host Mode
        (module docstring idea #2).
        """
        if self._trace:
            print("[mock-tnc] << wakeup: banner + GG-OK (Host-Mode signature)",
                  file=sys.stderr)
        with self._lock:
            self._rx.extend(b"\r\nAEA PK-232MBX  Ver. 7.1  Host Mode (mock)  "
                            b"PACTOR\r\n")
        self._push_frame(CTL_RX_CMD_RESP, b"GG" + bytes([CmdError.OK]))

    def _push_frame(self, ctl: int, payload: bytes) -> None:
        """Build a TNC→host frame and queue it for reading.

        frame.py exposes no public builder for the TNC→host CTL ranges
        ($3x/$5x), so we reuse its ``_dle_escape`` primitive plus the SOH/ETB
        constants — the exact machinery build_command()/build_data() use —
        rather than reimplementing escaping. (For $4F responses this is
        byte-identical to build_command(mnemonic, args).)
        """
        self._trace_io("<< TNC ", ctl, payload)
        frame = bytes([SOH, ctl]) + _dle_escape(payload) + bytes([ETB])
        with self._lock:
            self._rx.extend(frame)

    # ------------------------------------------------------------------
    # Tracing
    # ------------------------------------------------------------------

    def _trace_io(self, direction: str, ctl: int, payload: bytes) -> None:
        if self._trace:
            print(f"[mock-tnc] {direction}  ctl=0x{ctl:02X} ch={ctl & 0x0F} "
                  f"data={payload!r}", file=sys.stderr)


# ===========================================================================
# Dev-only entry point — launch the real app against the mock
# ===========================================================================

def _make_factory(trace: bool):
    """Return a port factory with the serial.Serial signature."""
    def factory(**kwargs):
        return LoopbackTNC(trace=trace, **kwargs)
    return factory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mock_tnc_bbs.py",
        description="Launch PK232PY against an in-process mock PK-232 running a "
                    "mini-BBS — exercise Packet connected mode (T33–T39) without "
                    "hardware. Dev-only; never shipped.",
        epilog="In the app: Connect (Host), choose port 'MOCK', switch to a "
               "Packet screen, then Connect to e.g. OE1XYZ. Type L / R 2 / D.",
    )
    parser.add_argument("--trace", action="store_true",
                        help="log every frame in/out (CTL, channel, payload) to stderr")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.trace else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    # Import the production app lazily (keeps this importable for unit tests
    # without spinning up Qt).
    from PyQt6.QtWidgets import QApplication
    from pk232py.ui.main_window import MainWindow
    from pk232py.comm.serial_manager import SerialManager

    print("[mock-tnc] Mock PK-232 + mini-BBS active.", file=sys.stderr)
    print("[mock-tnc] Connect (Host) → port 'MOCK' → Packet → Connect OE1XYZ.",
          file=sys.stderr)

    app = QApplication(sys.argv[:1])
    window = MainWindow()

    # Inject the mock transport: SerialManager.connect_port() will build a
    # LoopbackTNC instead of a real serial.Serial. SerialManager stays generic.
    window._serial.set_port_factory(_make_factory(args.trace))
    # Offer a 'MOCK' port in the connect dialog (dev convenience; any name works
    # since the factory ignores the port name).
    SerialManager.list_ports = staticmethod(lambda: ["MOCK"])

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

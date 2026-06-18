"""
tx_controller.py — TX State Machine
===================================

Pure state machine for character-ACK TX/RX logic (Baudot, ASCII, Morse, AMTOR).
No serial I/O, no Qt widgets — only signals and state.

Proven in baudot_tx_test.py (2026-05-02).
Integrated into PK232PY main project (2026-05-03).

Three-index system (see TX_STATE_MACHINE.md §13):
    _tx_sent_idx  — how far chars have been queued to TNC
    _ack_idx      — how far TNC has confirmed with DATA_ACK
    _cycle_start  — document anchor for colour_at() in TxInputWidget

Rate-limited TX (see TX_STATE_MACHINE.md §10):
    QTimer sends one character per mspeed_ms interval.
    DATA_ACKs arrive in sync with actual Baudot RF transmission.

EOT marker (see TX_STATE_MACHINE.md §11):
    char == '\\x04' → [^D] visible in TX, triggers RECEIVE when reached.

Usage in MainWindow / BaudotScreen:
    ctrl = TxController(parent=self)
    ctrl.set_mspeed(50)                    # from TNC config MSPEED
    ctrl.colour_char.connect(...)          # colour TX char green
    ctrl.show_in_rx.connect(...)           # show ACK'd char in RX
    ctrl.send_to_tnc.connect(...)          # send char to TNC
    ctrl.eot_reached.connect(do_receive)   # CTRL+D reached

    # On XM ACK from TNC:
    ctrl.on_send_start()

    # On DATA_ACK ($5F XX XX $00) from TNC:
    ctrl.on_data_ack()

    # On RECEIVE pressed:
    ctrl.on_send_stop()

    # On keystroke in TX window:
    ctrl.on_char_typed(char, display)
"""

from __future__ import annotations

import logging
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class TxController(QObject):
    """Pure TX/RX state machine for character-ACK modes (Baudot, ASCII, Morse, AMTOR).

    No serial I/O, no widget references — only signals and state.
    Communicates entirely via Qt signals.

    Signals
    -------
    colour_char(arr_idx: int, sent: bool)
        Colour one char in TX window. sent=True → inverse green (ACK'd).
    show_in_rx(display: str)
        Append one confirmed char to RX window (amber colour).
    send_to_tnc(char: str)
        Send one character to TNC via serial layer.
    warning(msg: str)
        Show warning message in RX window.
    status_msg(msg: str)
        Update status bar.
    eot_reached()
        CTRL+D EOT marker reached — switch to RECEIVE.
    timed_send_reached(n: int)
        CTRL+T timed marker reached — switch to RECEIVE, wait n sec, then SEND.
    """

    colour_char = pyqtSignal(int, bool)   # (arr_idx, sent)
    show_in_rx  = pyqtSignal(str)
    send_to_tnc = pyqtSignal(str)
    warning     = pyqtSignal(str)
    status_msg  = pyqtSignal(str)
    eot_reached = pyqtSignal()
    timed_send_reached = pyqtSignal(int)  # [^T:n] — wait n sec then SEND

    TX_MAX = 512

    # ms per character at each Baudot speed (7.5 bits/char ITA-2)
    # Formula: ms/char = 7500 / baud
    BAUD_RATES = {
        45: 167, 50: 150, 75: 100, 100: 75,
        110: 68, 150: 50, 200: 38, 300: 25,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._arr: list[dict] = []   # {char, display, sent}
        self._tx_sent_idx = 0        # next char to queue for TNC
        self._ack_idx     = 0        # next char awaiting DATA_ACK
        self._cycle_start = 0        # SEND cycle anchor for colour_at
        self._send_active = False
        self._mspeed_ms   = 150      # default 50 Baud
        self._eas_mode: bool = False  # True → colour on $2F echo, not $5F ACK
        self._echo_idx: int  = 0      # next arr index to colour on echo

        self._tx_queue: list[str] = []
        self._tx_timer = QTimer(self)
        self._tx_timer.setSingleShot(True)
        self._tx_timer.timeout.connect(self._send_next_char)

    # ── Public API ────────────────────────────────────────────────────

    def set_mspeed(self, baud: int) -> None:
        """Set TX rate from a Baud value (Baudot/ASCII). Maps via BAUD_RATES."""
        self._mspeed_ms = self.BAUD_RATES.get(baud, 150)
        logger.debug("MSPEED %d Baud → %dms/char", baud, self._mspeed_ms)

    def set_mspeed_ms(self, ms: int) -> None:
        """Set the inter-character TX interval directly in milliseconds.

        For modes without a meaningful Baud rate (e.g. CW/Morse, where the TNC
        controls WPM timing). The controller is then ACK-paced and this interval
        acts only as a buffer-overflow safety net, NOT as tempo control.
        """
        self._mspeed_ms = max(1, int(ms))
        logger.debug("MSPEED set directly → %dms/char", self._mspeed_ms)

    def set_eas_mode(self, enabled: bool) -> None:
        """Enable/disable EAS (Echo As Sent) colouring mode.

        When enabled, on_data_ack() only advances internal bookkeeping
        (for EOT tracking) but does NOT emit colour_char or show_in_rx.
        Those signals are emitted instead by on_echo_char(), which is
        called when the TNC sends a $2F ECHO frame (= character actually
        being sent over the air).
        """
        self._eas_mode = enabled
        # Initialise the echo pointer to the current cycle anchor when EAS is
        # (re)enabled at mode switch. Afterwards _echo_idx advances only in
        # on_echo_char() and resets only in clear() — it is monotonic.
        self._echo_idx = self._cycle_start

    def on_echo_char(self) -> None:
        """Called per character from $2F ECHO frame (EAS mode only).

        Colours the next uncoloured TX char and appends it to RX window.
        Mirrors the visual part of on_data_ack(), but fires at the real
        send moment, not at buffer-accept time.

        The echo stream is a faithful, in-order replay of every character the
        TNC actually transmitted. _echo_idx therefore advances **purely
        monotonically** — it is NEVER reset by on_send_start()/on_send_stop(),
        only by clear(). That is what lets a slow echo which straggles past a
        SEND → RECEIVE → SEND turnaround still colour its OWN character instead
        of a later cycle's character (the off-by-one symptom otherwise seen
        after a CTRL+D cycle). The widget's relative colour_at() formula
        (doc_offset + arr_idx − cycle_start) maps an arr_idx that now lies
        below cycle_start to the correct earlier document position.
        """
        # Leading scan — step over only the marker entries the $2F echo stream
        # genuinely omits, until _echo_idx reaches the entry this echo belongs to:
        #   \x04          an already-fired EOT marker we now pass on a straggler
        #                 echo for a post-[^D] char (skip silently, not in RX).
        #   \x1b…         timed marker — consumed on the SEND side (skip silent).
        # Space is NOT skipped here. Hardware test 2026-06-18 proved the TNC DOES
        # emit a $2F echo (payload 0x20) for a Morse word gap, so a space owns
        # its own echo call and is consumed below — skipping it here would make
        # the next real echo land on the space and desync every later char (the
        # permanent +1-per-space offset seen after b157209).
        while self._echo_idx < len(self._arr):
            mc = self._arr[self._echo_idx]['char']
            if mc == '\x04' or mc.startswith('\x1b'):
                self._echo_idx += 1
                continue
            break

        idx = self._echo_idx
        if idx >= len(self._arr):
            logger.debug("Echo idx=%d beyond arr=%d — ignored", idx, len(self._arr))
            return
        # NB: no "idx < _cycle_start" guard. With a monotonic echo pointer a
        # straggler echo legitimately addresses a char below the current cycle
        # anchor — that is exactly the case we must still colour.
        e = self._arr[idx]
        self._echo_idx += 1
        if e['char'] == ' ':
            # Space: TNC echoes the Morse word gap ($2F 0x20). _echo_idx is
            # already advanced above — just mirror it into the RX window.
            # Do NOT emit colour_char: TxInputWidget already coloured this
            # space immediately on keypress (b157209). Re-colouring would be
            # harmless visually, but advancing _echo_idx is what keeps sync.
            logger.debug("ECHO space #%d — idx advanced, no recolour", idx)
            self.show_in_rx.emit(' ')
        else:
            logger.debug("ECHO colour #%d char=%r", idx, e['char'])
            self.colour_char.emit(idx, True)
            display = '\n' if e['display'].startswith('<CR/LF>') else e['display']
            self.show_in_rx.emit(display)

        # EOT look-ahead. Timed markers (\x1b…) produce no echo, so advance over
        # them NOW to expose a following \x04. Spaces, however, ARE echoed — each
        # gets its own echo call — so a trailing space before [^D] is NOT skipped
        # here; its own echo will fire the turnaround when it consumes the space
        # and finds the \x04 next. Stop AT the \x04 (do not consume it, so a later
        # post-[^D] straggler echo can still step over it in the leading scan).
        while (self._echo_idx < len(self._arr) and
               self._arr[self._echo_idx]['char'].startswith('\x1b')):
            self._echo_idx += 1
        # EOT trigger: if the next entry is the EOT marker, the entry just echoed
        # (real char or word-gap space) was the last one before [^D] — fire
        # eot_reached now so RC is sent to the TNC only after it has finished
        # keying that entry. Monotonic _echo_idx guarantees this fires exactly
        # once per marker. on_echo_char() runs in EAS mode only.
        if self._echo_idx < len(self._arr) and self._arr[self._echo_idx]['char'] == '\x04':
            logger.debug("EAS: last char echoed, EOT next → eot_reached")
            self.status_msg.emit("EOT marker reached — switching to RECEIVE")
            self.eot_reached.emit()

    def on_char_typed(self, char: str, display: str) -> None:
        """Called on every keystroke — regardless of SEND/RECEIVE state.

        Special sentinel:
            '\\x08' (BS) — user deleted one unsent char (or one EOT marker).
            Remove the last unsent entry from _arr so doc positions stay
            in sync. Also clamp _ack_idx so it never exceeds len(_arr).

        Always appends to _arr for normal chars.
        Only queues for sending if SEND is currently active.
        """
        if char == '\x08':
            # Only remove chars beyond _tx_sent_idx (not yet sent to TNC)
            if len(self._arr) > self._tx_sent_idx:
                self._arr.pop()
            # Clamp _ack_idx — late ACKs must not address deleted positions
            if self._ack_idx > len(self._arr):
                self._ack_idx = len(self._arr)
            return

        # Only count chars not yet sent to TNC — sent chars are history.
        if (len(self._arr) - self._tx_sent_idx) >= self.TX_MAX:
            self.warning.emit("BUFFER_FULL")
            return
        self._arr.append({'char': char, 'display': display, 'sent': False})
        if self._send_active:
            self._queue_char(char)

    def on_send_start(self) -> None:
        """Called after XM ACK from TNC.

        Flushes all chars not yet sent (_tx_sent_idx onward) into the
        rate-limited queue. Chars already in TNC buffer are NOT re-sent.

        Also resets _ack_idx to _cycle_start so that ACKs from the
        previous cycle (e.g. for the EOT marker) don't interfere with
        the new cycle's ACK tracking.
        """
        self._send_active = True
        # Align _ack_idx with the new cycle start.
        # Without this, late ACKs for the previous cycle's EOT marker
        # arrive with idx=_ack_idx < _cycle_start and are all ignored,
        # meaning none of the new cycle's chars get colour_at() called.
        self._ack_idx = self._cycle_start
        # NOTE: _echo_idx is intentionally NOT reset here. In EAS mode the echo
        # stream is a continuous, in-order replay of everything sent to the TNC.
        # Resetting it would abandon pending echoes for chars sent in the
        # previous cycle (e.g. typed during a deferred-EOT window) and shift
        # every following echo by one. _echo_idx advances only in
        # on_echo_char(); it is reset only by clear(). See on_echo_char().
        unsent = self._arr[self._tx_sent_idx:]
        for e in unsent:
            self._queue_char(e['char'])
        n = len([e for e in unsent if e['char'] != '\x04'])
        logger.debug("on_send_start: queuing %d chars at %dms/char",
                     n, self._mspeed_ms)
        if n:
            self.status_msg.emit(
                f"SEND active — {n} char(s) at {7500 // self._mspeed_ms} Baud")
        else:
            self.status_msg.emit("SEND active — PTT on, ready to type")

    def on_send_stop(self) -> None:
        """Called when RECEIVE is pressed.

        Stops rate-limited timer. Chars still in queue are rolled back.
        cycle_start and _ack_idx are both advanced to _tx_sent_idx so
        the next SEND cycle starts cleanly from where we left off.
        """
        self._send_active = False
        self._tx_timer.stop()
        self._tx_sent_idx -= len(self._tx_queue)
        self._tx_queue.clear()
        self._cycle_start = self._tx_sent_idx
        # Clamp _ack_idx to _tx_sent_idx — any outstanding ACKs from the
        # previous cycle (e.g. for the EOT marker) are now irrelevant.
        # on_send_start will set _ack_idx = _cycle_start anyway, so this
        # just keeps the state consistent during RECEIVE.
        self._ack_idx = self._tx_sent_idx
        # NOTE: _echo_idx is intentionally NOT touched here — see on_send_start().
        # Echoes for already-sent chars may still be in flight after a RECEIVE;
        # abandoning them would desync the echo colouring across the turnaround.

    def on_data_ack(self) -> None:
        """Called on DATA_ACK frame ($5F XX XX $00) from TNC.

        Advances _ack_idx, colours the char green in TX,
        appends it amber to RX. Fires in order: 0, 1, 2, ...

        Late ACKs that arrive after the user has deleted the
        corresponding _arr entry (via Backspace) are silently ignored.
        """
        idx = self._ack_idx
        if idx >= len(self._arr):
            logger.debug("Spurious/late ACK idx=%d arr=%d — ignored",
                         idx, len(self._arr))
            self._ack_idx = len(self._arr)   # clamp
            return
        if idx < self._cycle_start:
            logger.debug("Late ACK ignored idx=%d cycle=%d",
                         idx, self._cycle_start)
            # Do NOT increment _ack_idx — this ACK belongs to a previous
            # cycle (e.g. the EOT marker \x04) and was already counted.
            # Incrementing here causes _ack_idx to skip one position in
            # the new cycle, resulting in the last char never being ACKd.
            return
            return
        e = self._arr[idx]
        e['sent'] = True
        self._ack_idx += 1
        logger.debug("DATA_ACK #%d char=%r", idx, e['char'])
        if not self._eas_mode:
            # Normal mode: colour immediately on ACK (Baudot/ASCII/AMTOR).
            self.colour_char.emit(idx, True)
            display = '\n' if e['display'].startswith('<CR/LF>') else e['display']
            self.show_in_rx.emit(display)
        else:
            # EAS mode (Morse): visual colouring deferred to on_echo_char().
            # ACK only advances bookkeeping; echo_idx trails behind ack_idx.
            logger.debug("EAS: ACK #%d bookkeeping only, colour deferred", idx)
        rem = len(self._arr) - self._ack_idx
        self.status_msg.emit(
            f"ACK #{idx + 1} — {rem} remaining" if rem
            else f"All {len(self._arr)} chars confirmed ✓"
        )

    def still_to_transmit(self) -> bool:
        """True if real chars (not just EOT markers) remain unsent."""
        remaining = self._arr[self._tx_sent_idx:]
        return any(
            e['char'] != '\x04' and not e['char'].startswith('\x1b')
            for e in remaining
        )

    def clear(self) -> None:
        """Reset all state — call when Host Mode becomes active."""
        self._arr.clear()
        self._tx_sent_idx = 0
        self._ack_idx     = 0
        self._cycle_start = 0
        self._echo_idx    = 0
        self._send_active = False
        self._tx_timer.stop()
        self._tx_queue.clear()

    # ── Properties ───────────────────────────────────────────────────

    @property
    def array_len(self) -> int:    return len(self._arr)

    @property
    def pending_len(self) -> int:
        """Chars typed but not yet sent — the relevant count for TX_MAX."""
        return max(0, len(self._arr) - self._tx_sent_idx)

    @property
    def tx_sent_idx(self) -> int:  return self._tx_sent_idx

    @property
    def ack_idx(self) -> int:      return self._ack_idx

    @property
    def cycle_start(self) -> int:  return self._cycle_start

    @property
    def send_active(self) -> bool: return self._send_active

    # ── Internal ─────────────────────────────────────────────────────

    def _queue_char(self, char: str) -> None:
        """Add one char to rate-limited TX queue, advance _tx_sent_idx."""
        self._tx_queue.append(char)
        self._tx_sent_idx += 1
        if not self._tx_timer.isActive() and len(self._tx_queue) == 1:
            self._tx_timer.start(self._mspeed_ms)

    def _send_next_char(self) -> None:
        """Timer callback — send next char from queue.

        EOT marker (\\x04): not sent to TNC, triggers eot_reached signal.
        _tx_queue is cleared before emit so on_send_stop sees empty queue
        and does not subtract from _tx_sent_idx.
        """
        if not self._tx_queue or not self._send_active:
            return
        char = self._tx_queue.pop(0)
        if char == '\x04':
            self._tx_queue.clear()
            self._tx_timer.stop()
            if not self._eas_mode:
                # Normal mode: the timer paces TX at the real RF rate, so the
                # EOT marker is reached exactly when the last char has been
                # sent — fire eot_reached now.
                self.status_msg.emit("EOT marker reached — switching to RECEIVE")
                self.eot_reached.emit()
            else:
                # EAS mode (Morse): the timer is only a 50 ms safety net and
                # runs far ahead of the WPM-paced $2F echoes. Defer eot_reached
                # to on_echo_char(), which fires it once the last real char's
                # echo arrives — so its colouring happens before RC is sent.
                logger.debug("EAS: EOT marker hit timer, deferring to echo")
            return
        if char.startswith('\x1b'):
            # [^T:n] timed marker — do NOT send to TNC.
            # Do NOT clear _tx_queue here — on_send_stop() will roll back
            # _tx_sent_idx by len(_tx_queue), so the chars after [^T:n]
            # are correctly re-queued when on_send_start() fires after n sec.
            try:
                n = int(char[1:])
            except ValueError:
                n = 1
            self._tx_timer.stop()
            self.status_msg.emit(
                f"[^T:{n}] — switching to RECEIVE, resuming SEND in {n}s")
            self.timed_send_reached.emit(n)
            return
        self.send_to_tnc.emit(char)
        if self._tx_queue:
            self._tx_timer.start(self._mspeed_ms)
# pk232py - Modern multimode terminal for AEA PK-232 / PK-232MBX TNC
# Copyright (C) 2026  OE3GAS  —  GPL v2
"""
packet_screen.py  –  HF Packet and VHF Packet opmode screens

Contains:
    PacketBaseScreen   shared base widget — all common UI elements
    HFPacketScreen     subclass: "HF Packet (300 Bd)", HBAUD default 300
    VHFPacketScreen    subclass: "VHF Packet (1200 Bd)", HBAUD default 1200

The two screens share all logic; the only differences are the title,
the HBAUD dropdown default, and the TNC init parameters sent on activation.

Layout (left panel via QSplitter, right panel = MHEARD):

    ┌──────────────────────────────────────────┬──────────────┐
    │  HF Packet (300 Bd)          UTC HH:MM:SS│   MHEARD     │
    ├──────────────────────────────────────────┤   Callsign   │
    │  MYCALL: [OE3GAS]  Dest:[     ]  ● STBY  │   Time       │
    ├──────────────────────────────────────────┤   ─────────  │
    │  [Connect][Disconnect][Unproto][MailDrop] │   [Refresh]  │
    │  HBAUD:[300]  Monitor:[4]                │   [Clear]    │
    ├──────────────────────────────────────────┤              │
    │  UNPROTO via:[CQ  ] [EAS][PASSALL][MRPT] │              │
    │  [MID][SQUELCH]                          │              │
    ├──────────────────────────────────────────┤              │
    │  RX window  (expands)                    │              │
    ├──────────────────────────────────────────┤              │
    │  TX window  (5 lines, block cursor)      │              │
    ├──────────────────────────────────────────┤              │
    │  [M1][M2][M3][M4][M5][M6]  [Edit Macros] │              │
    └──────────────────────────────────────────┴──────────────┘

MainWindow integration notes:
    - Registered as "HF Packet" and "VHF Packet" in _opmode_screens
    - No btn_send / btn_receive — Packet uses Connect/Disconnect instead
    - _wire_screen_buttons() calls _wire_packet_buttons(screen)
    - _make_link_handler() handles "connected"/"disconnect" text → _set_status
    - MYCALL field: set via set_mycall() on mode switch from AppConfig
    - MHEARD Refresh button wired in _wire_packet_buttons()
    - MailDrop button wired in _wire_packet_buttons()
"""

from __future__ import annotations

from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QTimer, QEvent, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QLineEdit, QPushButton,
    QComboBox, QFrame, QSizePolicy,
    QScrollArea, QSplitter,
)

from .opmode_rtty_base import (
    MacroStore, MacroEditDialog,
    make_toggle_button, add_hline,
    style_rx_widget, style_tx_widget,
    BTN_W, SPACING, MACRO_COUNT,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CALL_W = 100    # width of callsign QLineEdit fields (px)

# Status label states — dot prefix, same style as PactorScreen
STATUS_STYLES: dict[str, tuple[str, str]] = {
    "STBY":         ("●  STBY",           "#888888"),
    "CALLING":      ("●  CALLING …",      "#cc8800"),
    "CONNECTED":    ("●  CONNECTED",      "#3a9e3a"),
    "DISCONNECTED": ("●  DISCONNECTED",   "#cc4444"),
    "UNPROTO TX":   ("●  UNPROTO TX",     "#2266cc"),
}

_STYLE_CONNECT_OFF = (
    "QPushButton {"
    "  background-color: #445566; color: white;"
    "  border: 1px solid #334455; border-radius: 4px;"
    "  font-weight: bold; padding: 4px 8px;"
    "}"
    "QPushButton:hover { background-color: #556677; }"
)
_STYLE_CONNECT_ON = (
    "QPushButton {"
    "  background-color: #3a7a3a; color: white;"
    "  border: 2px solid #2a5a2a; border-radius: 4px;"
    "  font-weight: bold; padding: 4px 8px;"
    "}"
)
_STYLE_UNPROTO_OFF = (
    "QPushButton {"
    "  background-color: #445566; color: white;"
    "  border: 1px solid #334455; border-radius: 4px;"
    "  font-weight: bold; padding: 4px 8px;"
    "}"
    "QPushButton:hover { background-color: #556677; }"
)
_STYLE_UNPROTO_ON = (
    "QPushButton {"
    "  background-color: #1a4a7a; color: white;"
    "  border: 2px solid #0a2a5a; border-radius: 4px;"
    "  font-weight: bold; padding: 4px 8px;"
    "}"
)
# APRS decode toggle — amber/orange when active
_STYLE_APRS_OFF = (
    "QPushButton {"
    "  background-color: #445566; color: white;"
    "  border: 1px solid #334455; border-radius: 4px;"
    "  font-weight: bold; padding: 4px 8px;"
    "}"
    "QPushButton:hover { background-color: #556677; }"
)
_STYLE_APRS_ON = (
    "QPushButton {"
    "  background-color: #b06000; color: white;"
    "  border: 2px solid #804000; border-radius: 4px;"
    "  font-weight: bold; padding: 4px 8px;"
    "}"
)


def _no_focus_btn(text: str, width: int = BTN_W) -> QPushButton:
    """Button that never steals keyboard focus from the TX window."""
    btn = QPushButton(text)
    btn.setFixedWidth(width)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return btn


# ---------------------------------------------------------------------------
# MheardPanel
# ---------------------------------------------------------------------------

class MheardPanel(QWidget):
    """Scrollable list of heard AX.25 stations (MHEARD).

    Public API (called from MainWindow):
        add_entry(callsign, time_str, direct=False)
        clear()
        btn_refresh   — connect clicked to MainWindow._on_packet_mheard()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[tuple[str, str, bool]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        lbl = QLabel("MHEARD")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        root.addWidget(lbl)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(4, 0, 4, 0)
        hdr_c = QLabel("Callsign")
        hdr_c.setFont(QFont("Segoe UI", 8))
        hdr_t = QLabel("Time")
        hdr_t.setFont(QFont("Segoe UI", 8))
        hdr_t.setAlignment(Qt.AlignmentFlag.AlignRight)
        hdr.addWidget(hdr_c)
        hdr.addWidget(hdr_t)
        root.addLayout(hdr)

        add_hline(root)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, stretch=1)

        add_hline(root)

        lbl_legend = QLabel("* = direct (no digi)")
        lbl_legend.setFont(QFont("Segoe UI", 8))
        root.addWidget(lbl_legend)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        # Wired by MainWindow._wire_packet_buttons()
        self.btn_refresh = _no_focus_btn("Refresh", 64)
        self.btn_refresh.setToolTip("Request MHEARD list from TNC (mnemonic MH).")

        self.btn_clear = _no_focus_btn("Clear", 64)
        self.btn_clear.setToolTip("Clear the MHEARD list locally.")
        self.btn_clear.clicked.connect(self.clear)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_clear)
        root.addLayout(btn_row)

    def add_entry(self, callsign: str, time_str: str, direct: bool = False) -> None:
        """Add one entry at the top of the MHEARD list."""
        self._entries.insert(0, (callsign, time_str, direct))
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 1, 4, 1)
        rl.setSpacing(4)
        display = f"{callsign} *" if direct else callsign
        lbl_c = QLabel(display)
        lbl_c.setFont(QFont("Courier New", 9))
        # Green = direct, light blue = heard via digipeater
        lbl_c.setStyleSheet("color: #66ee66;" if direct else "color: #88ccff;")
        lbl_t = QLabel(time_str)
        lbl_t.setFont(QFont("Courier New", 9))
        lbl_t.setAlignment(Qt.AlignmentFlag.AlignRight)
        rl.addWidget(lbl_c)
        rl.addStretch()
        rl.addWidget(lbl_t)
        # Insert before trailing stretch (always last item)
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def clear(self) -> None:
        """Remove all entries from the list."""
        self._entries.clear()
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ---------------------------------------------------------------------------
# PacketBaseScreen
# ---------------------------------------------------------------------------

class PacketBaseScreen(QWidget):
    """Shared base for HF Packet and VHF Packet screens.

    Subclasses override:
        MODE_TITLE      title label text
        MODE_SUFFIX     speed annotation "(300 Bd)" / "(1200 Bd)"
        HBAUD_VALUES    HBAUD dropdown choices
        HBAUD_DEFAULT   pre-selected HBAUD value
        MONITOR_DEFAULT pre-selected Monitor level

    Attributes accessed by MainWindow:
        le_mycall, le_dest, le_unproto
        combo_hbaud, combo_monitor
        btn_connect, btn_disconnect, btn_unproto, btn_maildrop
        btn_eas, btn_passall, btn_mrpt, btn_mid, btn_squelch
        rx_display, tx_input
        macro_buttons, _macro_store
        mheard_panel
        lbl_status
    """

    MODE_TITLE      = "Packet"
    MODE_SUFFIX     = ""
    HBAUD_VALUES    = ["300", "1200"]
    HBAUD_DEFAULT   = "300"
    MONITOR_DEFAULT = "4"

    # Signals connected automatically by MainWindow._wire_mode_callbacks().
    # Declared on the base class → HF and VHF Packet inherit them.
    clear_tx_req = pyqtSignal()
    clear_rx_req = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._macro_store = MacroStore()
        err = self._macro_store.load()
        if err:
            import logging
            logging.getLogger(__name__).warning("MacroStore: %s", err)

        self._utc_timer = QTimer(self)
        self._utc_timer.setInterval(1000)
        self._utc_timer.timeout.connect(self._update_utc)
        self._utc_timer.start()

        self._build_ui()

        # ScreenFocusController: tracks focus on QLineEdit input fields.
        # ScreenFocusController: tracks focus on editable QLineEdit fields.
        # lbl_mycall is a QLabel — no focus tracking needed.
        from .screen_focus_controller import ScreenFocusController
        self.focus_ctrl = ScreenFocusController(
            fields=[self.le_dest, self.le_unproto],
            parent=self,
        )

        # Intercept Enter in tx_input → send as AX.25 DATA frame.
        # _packet_send_slot is set by MainWindow._wire_mode_callbacks().
        self.tx_input._packet_send_slot = None
        self.tx_input.installEventFilter(self)
        QTimer.singleShot(0, lambda: self.tx_input.setFocus())

    # ------------------------------------------------------------------
    # EventFilter — identical to PactorScreen / AmtorScreen
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        # Enter / Return in tx_input → send as AX.25 DATA frame
        if (event.type() == QEvent.Type.KeyPress
                and obj is getattr(self, 'tx_input', None)):
            from PyQt6.QtCore import Qt as _Qt
            if event.key() in (_Qt.Key.Key_Return, _Qt.Key.Key_Enter):
                slot = getattr(self.tx_input, '_packet_send_slot', None)
                if slot is not None:
                    slot()
                return True   # consume — do not insert newline
        if event.type() == QEvent.Type.KeyPress:
            # Walk parent chain: in an app-wide filter obj may be an
            # internal child widget, not the QLineEdit/QTextEdit itself.
            def _is_input(w):
                while w is not None:
                    if isinstance(w, (QTextEdit, QLineEdit)):
                        return True
                    w = w.parent()
                return False
            if _is_input(self.focusWidget()) or _is_input(obj):
                return super().eventFilter(obj, event)
            if hasattr(self, "tx_input") and self.tx_input is not None:
                self.tx_input.setFocus()
                QApplication.sendEvent(self.tx_input, event)
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_utc(self) -> None:
        now = datetime.now(timezone.utc)
        self.lbl_utc.setText(now.strftime("UTC  %H:%M:%S"))

    def _set_status(self, state: str) -> None:
        """Update status label. Called by MainWindow._make_link_handler()."""
        text, color = STATUS_STYLES.get(state, (f"●  {state}", "#888888"))
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 10pt;"
        )

    def set_mycall(self, callsign: str) -> None:
        """Update the MYCALL display label. Called by MainWindow on mode switch."""
        self.lbl_mycall.setText(callsign.upper() if callsign else "---")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: communication area ───────────────────────────────────
        left = QWidget()
        root = QVBoxLayout(left)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # 1. Title row ─────────────────────────────────────────────────
        title_row = QHBoxLayout()
        lbl_title = QLabel(self.MODE_TITLE)
        lbl_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_title.setTextFormat(Qt.TextFormat.PlainText)
        title_row.addWidget(lbl_title)
        title_row.addStretch()
        self.lbl_utc = QLabel()
        self.lbl_utc.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self.lbl_utc.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._update_utc()
        title_row.addWidget(self.lbl_utc)
        root.addLayout(title_row)

        add_hline(root)

        # 2. Identity row: MYCALL / Dest / Status ──────────────────────
        id_row = QHBoxLayout()
        id_row.setSpacing(8)

        lbl_mycall = QLabel("MYCALL:")
        lbl_mycall.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        id_row.addWidget(lbl_mycall)

        # Read-only — populated by MainWindow via set_mycall()
        self.lbl_mycall = QLabel("---")
        self.lbl_mycall.setFixedWidth(CALL_W)
        self.lbl_mycall.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self.lbl_mycall.setToolTip(
            "Your AX.25 callsign (MYCALL / mnemonic ML).\n"
            "Set via TNC \u2192 Configure \u2192 TNC Parameters."
        )
        id_row.addWidget(self.lbl_mycall)

        id_row.addSpacing(16)
        lbl_dest = QLabel("Dest:")
        lbl_dest.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        id_row.addWidget(lbl_dest)

        self.le_dest = QLineEdit()
        self.le_dest.setMaxLength(14)
        self.le_dest.setFixedWidth(CALL_W)
        self.le_dest.setFont(QFont("Courier New", 10))
        self.le_dest.setPlaceholderText("e.g. OE3XYZ")
        self.le_dest.setToolTip(
            "Destination callsign for AX.25 CONNECT.\n"
            "May include SSID, e.g. OE3XYZ-9 or DB0MUC-8."
        )
        id_row.addWidget(self.le_dest)
        id_row.addStretch()

        self.lbl_status = QLabel()
        self.lbl_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._set_status("STBY")
        id_row.addWidget(self.lbl_status)
        root.addLayout(id_row)

        add_hline(root)

        # 3. Action buttons + dropdowns ────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(SPACING)

        # Connect: checkable, stays pressed while connected
        self.btn_connect = _no_focus_btn("Connect", BTN_W)
        self.btn_connect.setCheckable(True)
        self.btn_connect.setStyleSheet(_STYLE_CONNECT_OFF)
        self.btn_connect.setToolTip(
            "Initiate AX.25 CONNECT to Dest callsign.\n"
            "TNC mnemonic: CO (connect channel)"
        )
        action_row.addWidget(self.btn_connect)

        # Disconnect: one-shot. Disabled until a link is up/pending — there is
        # nothing to disconnect from at startup.
        self.btn_disconnect = _no_focus_btn("Disconnect", BTN_W)
        self.btn_disconnect.setToolTip(
            "Send AX.25 DISCONNECT.\n"
            "TNC mnemonic: DI (disconnect channel)"
        )
        self.btn_disconnect.setEnabled(False)
        action_row.addWidget(self.btn_disconnect)

        # Unproto: checkable
        self.btn_unproto = _no_focus_btn("Unproto", BTN_W)
        self.btn_unproto.setCheckable(True)
        self.btn_unproto.setStyleSheet(_STYLE_UNPROTO_OFF)
        self.btn_unproto.setToolTip(
            "Send unconnected UI frames (no ARQ, no acknowledge).\n"
            "Path set in UNPROTO via field below."
        )
        action_row.addWidget(self.btn_unproto)

        # MailDrop: one-shot
        self.btn_maildrop = _no_focus_btn("MailDrop", BTN_W)
        self.btn_maildrop.setToolTip(
            "Log in to TNC MailDrop (MDCHECK).\n"
            "Only available when not connected."
        )
        action_row.addWidget(self.btn_maildrop)

        # APRS decode toggle — visible only in VHFPacketScreen.
        # getattr safe default: base class has no APRS_CAPABLE;
        # VHFPacketScreen sets it True.
        self.btn_aprs = _no_focus_btn("APRS", BTN_W)
        self.btn_aprs.setCheckable(True)
        self.btn_aprs.setStyleSheet(_STYLE_APRS_OFF)
        self.btn_aprs.setToolTip(
            "APRS decode mode.\n"
            "ON: all monitored frames (including already received)\n"
            "    are decoded into human-readable APRS format.\n"
            "OFF: restores the original raw monitor display."
        )
        action_row.addWidget(self.btn_aprs)
        self.btn_aprs.setVisible(getattr(self, "APRS_CAPABLE", False))

        action_row.addStretch()

        lbl_hbaud = QLabel("HBAUD:")
        lbl_hbaud.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        action_row.addWidget(lbl_hbaud)

        self.combo_hbaud = QComboBox()
        self.combo_hbaud.addItems(self.HBAUD_VALUES)
        self.combo_hbaud.setCurrentText(self.HBAUD_DEFAULT)
        self.combo_hbaud.setFixedWidth(68)
        self.combo_hbaud.setToolTip(
            "Host baud rate (HBAUD / mnemonic HB).\n"
            "HF Packet: 300   VHF Packet: 1200"
        )
        action_row.addWidget(self.combo_hbaud)

        action_row.addSpacing(8)
        lbl_mon = QLabel("Monitor:")
        lbl_mon.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        action_row.addWidget(lbl_mon)

        self.combo_monitor = QComboBox()
        self.combo_monitor.addItems(["0", "1", "2", "3", "4", "5", "6"])
        self.combo_monitor.setCurrentText(self.MONITOR_DEFAULT)
        self.combo_monitor.setFixedWidth(50)
        self.combo_monitor.setToolTip(
            "Monitor level (MONITOR / mnemonic MN):\n"
            "0=off  1=UI  2=+I  3=+C/D  4=default  5=+RR  6=+poll"
        )
        action_row.addWidget(self.combo_monitor)
        root.addLayout(action_row)

        # 4. UNPROTO path + toggle flags ───────────────────────────────
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(SPACING)

        lbl_unproto = QLabel("UNPROTO via:")
        lbl_unproto.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        toggle_row.addWidget(lbl_unproto)

        self.le_unproto = QLineEdit("CQ")
        self.le_unproto.setMaxLength(40)
        self.le_unproto.setFixedWidth(120)
        self.le_unproto.setFont(QFont("Courier New", 10))
        self.le_unproto.setToolTip(
            "Unproto destination and digipeater path (mnemonic UN).\n"
            "Examples: CQ   CQ VIA RELAY   CQ VIA OE3XNR-8"
        )
        toggle_row.addWidget(self.le_unproto)
        toggle_row.addSpacing(8)

        self.btn_eas      = make_toggle_button("EAS")
        self.btn_passall  = make_toggle_button("PASSALL")
        self.btn_mrpt     = make_toggle_button("MRPT")
        self.btn_mid      = make_toggle_button("MID")
        self.btn_squelch  = make_toggle_button("SQUELCH")

        self.btn_eas.setToolTip("Echo As Sent (EA) — show confirmed TX chars in RX window.")
        self.btn_passall.setToolTip("PASSALL (PA) — receive all frames regardless of CRC.")
        self.btn_mrpt.setToolTip("Monitor Repeat (MR) — show digipeated frames.")
        self.btn_mid.setToolTip("Morse ID beacon (MI) — enable periodic Morse ID.")
        self.btn_squelch.setToolTip("SQUELCH (SQ) — suppress duplicate frames.")

        for btn in (self.btn_eas, self.btn_passall, self.btn_mrpt,
                    self.btn_mid, self.btn_squelch):
            toggle_row.addWidget(btn)

        toggle_row.addStretch()
        root.addLayout(toggle_row)

        add_hline(root)

        # 5. RX window ─────────────────────────────────────────────────
        self.rx_display = QTextEdit()
        self.rx_display.setReadOnly(True)
        self.rx_display.setFont(QFont("Courier New", 10))
        self.rx_display.setPlaceholderText(
            "RX — received and monitored AX.25 frames appear here …\n\n"
            "Connected data:   $3x frames (channel data)\n"
            "Monitored frames: $3F frames (unproto / UI)"
        )
        self.rx_display.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        style_rx_widget(self.rx_display)
        root.addWidget(self.rx_display, stretch=1)

        add_hline(root)

        # 6. TX window — 5 lines, block cursor ─────────────────────────
        self.tx_input = QTextEdit()
        self.tx_input.setFont(QFont("Courier New", 10))
        self.tx_input.setPlaceholderText("TX — type here …")
        fm = self.tx_input.fontMetrics()
        mc = self.tx_input.contentsMargins()
        self.tx_input.setFixedHeight(
            fm.lineSpacing() * 5 + mc.top() + mc.bottom() + 8
        )
        style_tx_widget(self.tx_input)
        self.tx_input.setCursorWidth(
            self.tx_input.fontMetrics().averageCharWidth()
        )
        root.addWidget(self.tx_input)

        add_hline(root)

        # 7. Macro bar ──────────────────────────────────────────────────
        macro_row = QHBoxLayout()
        macro_row.setSpacing(SPACING)
        self.macro_buttons: list[QPushButton] = []
        for i in range(MACRO_COUNT):
            btn = _no_focus_btn(self._macro_store.names[i], BTN_W)
            macro_row.addWidget(btn)
            self.macro_buttons.append(btn)
        macro_row.addStretch()

        # Clear TX / Clear RX — emit signals handled by MainWindow.
        self.btn_clear_tx = _no_focus_btn("Clear TX", BTN_W)
        self.btn_clear_tx.clicked.connect(self.clear_tx_req.emit)
        macro_row.addWidget(self.btn_clear_tx)

        self.btn_clear_rx = _no_focus_btn("Clear RX", BTN_W)
        self.btn_clear_rx.clicked.connect(self.clear_rx_req.emit)
        macro_row.addWidget(self.btn_clear_rx)

        self.btn_edit_macros = _no_focus_btn("Edit Macros", BTN_W + 20)
        self.btn_edit_macros.setStyleSheet(
            "QPushButton { border: 1px solid #666; border-radius: 4px; padding: 4px; }"
        )
        self.btn_edit_macros.clicked.connect(self._on_edit_macros)
        macro_row.addWidget(self.btn_edit_macros)
        root.addLayout(macro_row)

        # ── Right: MHEARD panel ────────────────────────────────────────
        self.mheard_panel = MheardPanel()
        self.mheard_panel.setMinimumWidth(130)
        self.mheard_panel.setMaximumWidth(220)

        splitter.addWidget(left)
        splitter.addWidget(self.mheard_panel)
        splitter.setSizes([540, 160])
        outer.addWidget(splitter)

    # ------------------------------------------------------------------
    # Visual-only state updates (TNC commands sent by MainWindow)
    # ------------------------------------------------------------------

    def set_link_state(self, state: str) -> None:
        """Enable/disable the Connect/Disconnect buttons for an AX.25 link state.

        Called by MainWindow on link transitions so a second CONNECT cannot be
        sent while a link is up or pending (which would draw an
        ALREADY_CONNECTED error / undefined behaviour from a real TNC).

        state:
          'connected' / 'calling' — Connect disabled (no double CO), Disconnect
              enabled, Unproto disabled. CALLING keeps Connect pressed-but-
              disabled so it cannot be un-toggled into a half-aborted state; use
              Disconnect to abort.
          anything else (disconnected / idle) — Connect re-enabled and visually
              released, Disconnect disabled, Unproto re-enabled.

        T39: Connect and Unproto are mutually exclusive (like PTT modes) — a
        connected/pending AX.25 link must not also run UNPROTO UI frames, so the
        Unproto button is greyed while a link is up or calling and restored once
        the link is down.

        Does NOT touch the status pill (caller owns _set_status) and blocks
        signals while releasing Connect so it does not re-fire the toggle/CO.
        """
        if state.lower() in ("connected", "calling"):
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_unproto.setEnabled(False)   # T39: no UNPROTO while linked
        else:
            self.btn_connect.setEnabled(True)
            self.btn_connect.blockSignals(True)
            self.btn_connect.setChecked(False)
            self.btn_connect.blockSignals(False)
            self.btn_connect.setStyleSheet(_STYLE_CONNECT_OFF)
            self.btn_disconnect.setEnabled(False)
            self.btn_unproto.setEnabled(True)    # T39: UNPROTO available when idle

    def on_connect_toggled(self, checked: bool) -> None:
        """Visual feedback for Connect button toggle.

        Wired by MainWindow._wire_packet_buttons().
        Actual CO/DI frame is sent by MainWindow._on_packet_connect().
        """
        if checked:
            self.btn_connect.setStyleSheet(_STYLE_CONNECT_ON)
            self.btn_unproto.blockSignals(True)
            self.btn_unproto.setChecked(False)
            self.btn_unproto.blockSignals(False)
            self.btn_unproto.setStyleSheet(_STYLE_UNPROTO_OFF)
            self._set_status("CALLING")
        else:
            self.btn_connect.setStyleSheet(_STYLE_CONNECT_OFF)
            self._set_status("STBY")

    def on_unproto_toggled(self, checked: bool) -> None:
        """Visual feedback for Unproto button toggle."""
        if checked:
            self.btn_unproto.setStyleSheet(_STYLE_UNPROTO_ON)
            self.btn_connect.blockSignals(True)
            self.btn_connect.setChecked(False)
            self.btn_connect.blockSignals(False)
            self.btn_connect.setStyleSheet(_STYLE_CONNECT_OFF)
            self._set_status("UNPROTO TX")
        else:
            self.btn_unproto.setStyleSheet(_STYLE_UNPROTO_OFF)
            self._set_status("STBY")

    def on_aprs_toggled(self, checked: bool) -> None:
        """Visual feedback for APRS decode toggle.

        Only updates the button appearance — the actual re-decode
        of the RX buffer is handled by MainWindow._on_packet_aprs_toggled().
        """
        if checked:
            self.btn_aprs.setStyleSheet(_STYLE_APRS_ON)
        else:
            self.btn_aprs.setStyleSheet(_STYLE_APRS_OFF)

    # ------------------------------------------------------------------
    # Slot: Edit Macros
    # ------------------------------------------------------------------

    def _on_edit_macros(self) -> None:
        dlg = MacroEditDialog(self._macro_store, parent=self)
        dlg.exec()
        for i, btn in enumerate(self.macro_buttons):
            btn.setText(self._macro_store.names[i])


# ---------------------------------------------------------------------------
# Concrete subclasses — differ only in class attributes
# ---------------------------------------------------------------------------

class HFPacketScreen(PacketBaseScreen):
    """HF Packet — 300 Bd, VHF OFF.

    TNC init frames on activation (production — sent by HFPacketMode):
        PA     — enter Packet mode
        VH N   — VHF OFF → select 300 Bd HF FSK modem
        HB 300 — HBAUD 300
        MN Y   — Monitor ON
    """
    MODE_TITLE      = "HF Packet"
    HBAUD_VALUES    = ["300", "1200"]
    HBAUD_DEFAULT   = "300"
    MONITOR_DEFAULT = "4"


class VHFPacketScreen(PacketBaseScreen):
    """VHF Packet — 1200 Bd, VHF ON.

    TNC init frames on activation (production — sent by VHFPacketMode):
        PA      — enter Packet mode
        VH Y    — VHF ON → select Bell 202 1200 Bd modem
        HB 1200 — HBAUD 1200
        MX 4    — MAXFRAME 4
        SL 10   — SLOTTIME 10 (×10ms = 100ms)
        MN Y    — Monitor ON
    """
    MODE_TITLE      = "VHF Packet"
    HBAUD_VALUES    = ["1200", "9600"]
    HBAUD_DEFAULT   = "1200"
    MONITOR_DEFAULT = "4"
    APRS_CAPABLE    = True   # enables APRS decode button
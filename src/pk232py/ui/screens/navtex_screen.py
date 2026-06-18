"""
navtex_screen.py – NAVTEX Opmode-Screen (518 kHz, AMTOR Mode B / FEC)

NAVTEX (NAVigational TEleX) ist ein internationales System zur Übertragung
von Navigations- und Wetterwarungen an Schiffe auf 518 kHz.
In Amateurfunk-Kreisen heißt dieselbe Betriebsart AMTEX (ARRL).

Eigenschaften:
  - Nur Empfang (kein TX)
  - 518 kHz, 100 Baud, AMTOR Mode B (FEC)
  - Nachrichten beginnen immer mit ZCZC + 4-stelligem Header:
      ZCZC PA99  →  Station='P'  Klasse='A'  Seriennummer='99'
  - Nachrichtenklassen A, B, D sind PFLICHT (nicht unterdrückbar)
  - Duplikat-Unterdrückung: TNC merkt sich die letzten 200 Header
  - NAVMSG-Filter: welche Nachrichtenklassen empfangen werden
  - NAVSTN-Filter: von welchen Stationen empfangen wird

NAVTEX-Nachrichtenklassen:
  A  Navigationswarnungen        (Pflicht)
  B  Meteorologische Warnungen   (Pflicht)
  C  Eiswarnungen
  D  Such- und Rettungsinfo      (Pflicht)
  E  Wettervorhersagen
  F  Pilotendienstnachrichten
  G  DECCA System-Info
  H  LORAN-C Info
  I  Omega System-Nachrichten
  J  SATNAV-Nachrichten
  K-Z Reserviert

Standalone-Test: python navtex_screen.py
"""

import sys
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QLineEdit,
    QFrame, QSizePolicy, QGroupBox,
    QCheckBox, QGridLayout, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from .opmode_rtty_base import (
    add_hline, apply_app_style,
    style_rx_widget,
    BTN_W, SPACING,
)


# ---------------------------------------------------------------------------
# NAVTEX-Nachrichtenklassen mit Beschreibung
# ---------------------------------------------------------------------------

MSG_CLASSES = [
    ("A", "Navigational warnings",      True),   # (Buchstabe, Beschreibung, Pflicht)
    ("B", "Meteorological warnings",    True),
    ("C", "Ice warnings",               False),
    ("D", "Search & rescue info",       True),
    ("E", "Weather forecasts",          False),
    ("F", "Pilot service messages",     False),
    ("G", "DECCA system info",          False),
    ("H", "LORAN-C info",               False),
    ("I", "Omega system messages",      False),
    ("J", "SATNAV messages",            False),
]


# ---------------------------------------------------------------------------
# NavtexScreen
# ---------------------------------------------------------------------------

class NavtexScreen(QWidget):
    """NAVTEX Opmode-Screen — nur Empfang.

    Layout (von oben nach unten):
    ┌─────────────────────────────────────────────────────────┐
    │  NAVTEX                                UTC  HH:MM:SS   │
    ├─────────────────────────────────────────────────────────┤
    │  Filter-Sektion                                         │
    │  ┌─ NAVMSG (Nachrichtenklassen) ────────────────────┐  │
    │  │  ☑A ☑B ☐C ☑D ☑E ☐F ☐G ☐H ☐I ☐J  [Alle][Keine]  │  │
    │  └──────────────────────────────────────────────────┘  │
    │  ┌─ NAVSTN (Stationen) ─────────────────────────────┐  │
    │  │  ALL  [Textfeld]  [Alle][Keine]                   │  │
    │  └──────────────────────────────────────────────────┘  │
    ├─────────────────────────────────────────────────────────┤
    │  RX-Fenster (expandiert, read-only)                     │
    └─────────────────────────────────────────────────────────┘

    Hinweis: Kein TX-Fenster und keine Macro-Leiste —
             NAVTEX ist reiner Empfangsmodus ohne Sendefunktion.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._utc_timer = QTimer(self)
        self._utc_timer.setInterval(1000)
        self._utc_timer.timeout.connect(self._update_utc)
        self._utc_timer.start()

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # --- Titelzeile mit UTC ------------------------------------------
        title_row = QHBoxLayout()
        title = QLabel("NAVTEX")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_row.addWidget(title)

        # Empfangs-Status-Indikator
        self.lbl_status = QLabel("●  STANDBY")
        self.lbl_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet("color: #888888;")
        title_row.addWidget(self.lbl_status)

        title_row.addStretch()

        self.lbl_utc = QLabel()
        self.lbl_utc.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self.lbl_utc.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._update_utc()
        title_row.addWidget(self.lbl_utc)
        root.addLayout(title_row)

        add_hline(root)

        # --- Info-Zeile: Frequenz / Betriebsart --------------------------
        info_row = QHBoxLayout()
        info_row.setSpacing(20)

        for text in ("518 kHz", "100 Baud", "AMTOR Mode B / FEC", "Receive only"):
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #8aaccc;")
            info_row.addWidget(lbl)

        info_row.addStretch()
        root.addLayout(info_row)

        add_hline(root)

        # --- Filter-Sektion ----------------------------------------------
        filter_box = QGroupBox("Receive Filter")
        filter_box.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        filter_layout = QVBoxLayout(filter_box)
        filter_layout.setSpacing(6)

        # NAVMSG — Nachrichtenklassen
        navmsg_label = QLabel("NAVMSG  –  Message classes:")
        navmsg_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        filter_layout.addWidget(navmsg_label)

        msg_row = QHBoxLayout()
        msg_row.setSpacing(4)

        self._msg_checks: dict[str, QCheckBox] = {}
        for letter, desc, mandatory in MSG_CLASSES:
            cb = QCheckBox(letter)
            cb.setChecked(True)          # Default: alle AN
            cb.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            cb.setToolTip(
                f"{letter} – {desc}"
                + ("\n⚠ Mandatory class – cannot be disabled" if mandatory else "")
            )
            if mandatory:
                # Pflichtklassen: Checkbox deaktivieren (immer AN)
                cb.setEnabled(False)
                cb.setStyleSheet("QCheckBox { color: #888; }")
            self._msg_checks[letter] = cb
            msg_row.addWidget(cb)

        msg_row.addSpacing(12)

        btn_msg_all = QPushButton("All")
        btn_msg_all.setFixedWidth(50)
        btn_msg_all.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_msg_all.clicked.connect(self._on_navmsg_all)
        msg_row.addWidget(btn_msg_all)

        btn_msg_none = QPushButton("None")
        btn_msg_none.setFixedWidth(50)
        btn_msg_none.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_msg_none.clicked.connect(self._on_navmsg_none)
        msg_row.addWidget(btn_msg_none)

        msg_row.addStretch()
        filter_layout.addLayout(msg_row)

        # Legende Pflichtklassen
        legend = QLabel("  ⚠ A, B, D = mandatory classes (always active)")
        legend.setFont(QFont("Segoe UI", 8))
        legend.setStyleSheet("color: #888888;")
        filter_layout.addWidget(legend)

        # Trennlinie innerhalb der GroupBox
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        filter_layout.addWidget(sep)

        # NAVSTN — Stationsfilter
        navstn_label = QLabel("NAVSTN  –  Station filter:")
        navstn_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        filter_layout.addWidget(navstn_label)

        stn_row = QHBoxLayout()
        stn_row.setSpacing(6)

        stn_row.addWidget(QLabel("Filter:"))
        self.le_navstn = QLineEdit("ALL")
        self.le_navstn.setFont(QFont("Courier New", 10))
        self.le_navstn.setFixedWidth(200)
        self.le_navstn.setPlaceholderText("ALL  or  YES A,P,S  or  NO B")
        self.le_navstn.setToolTip(
            "ALL    – receive all stations\n"
            "NONE   – receive no station\n"
            "YES x  – only these stations (letter list)\n"
            "NO x   – exclude these stations"
        )
        stn_row.addWidget(self.le_navstn)

        btn_stn_all = QPushButton("All")
        btn_stn_all.setFixedWidth(50)
        btn_stn_all.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_stn_all.clicked.connect(lambda: self.le_navstn.setText("ALL"))
        stn_row.addWidget(btn_stn_all)

        btn_stn_none = QPushButton("None")
        btn_stn_none.setFixedWidth(50)
        btn_stn_none.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_stn_none.clicked.connect(lambda: self.le_navstn.setText("NONE"))
        stn_row.addWidget(btn_stn_none)

        stn_row.addStretch()
        filter_layout.addLayout(stn_row)

        root.addWidget(filter_box)

        add_hline(root)

        # --- RX-Fenster --------------------------------------------------
        # NAVTEX: kein TX, daher RX bekommt fast den gesamten Platz
        rx_label = QLabel("Received messages:")
        rx_label.setFont(QFont("Segoe UI", 9))
        root.addWidget(rx_label)

        self.rx_display = QTextEdit()
        self.rx_display.setReadOnly(True)
        self.rx_display.setFont(QFont("Courier New", 10))
        style_rx_widget(self.rx_display)
        self.rx_display.setPlaceholderText(
            "NAVTEX messages appear here …\n\n"
            "Format:\n"
            "ZCZC PA99\n"
            "<message text>\n"
            "NNNN"
        )
        self.rx_display.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self.rx_display, stretch=1)

        # Clear-RX row — receive-only screen clears itself.
        clear_row = QHBoxLayout()
        clear_row.addStretch()
        self.btn_clear_rx = QPushButton("Clear RX")
        self.btn_clear_rx.setFixedWidth(BTN_W)
        self.btn_clear_rx.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear_rx.clicked.connect(self._on_clear_rx)
        clear_row.addWidget(self.btn_clear_rx)
        root.addLayout(clear_row)

        add_hline(root)

        # --- RX-Fenster --------------------------------------------------

    def _on_clear_rx(self) -> None:
        """Clear the NAVTEX receive window (receive-only, local state)."""
        self.rx_display.clear()

    # ------------------------------------------------------------------
    # NAVMSG Schnell-Buttons
    # ------------------------------------------------------------------

    def _on_navmsg_all(self) -> None:
        """Alle nicht-Pflicht-Klassen einschalten."""
        for cb in self._msg_checks.values():
            if cb.isEnabled():
                cb.setChecked(True)

    def _on_navmsg_none(self) -> None:
        """Alle nicht-Pflicht-Klassen ausschalten."""
        for cb in self._msg_checks.values():
            if cb.isEnabled():
                cb.setChecked(False)

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def get_navmsg_filter(self) -> str:
        """Gibt den aktuellen NAVMSG-Filter als String zurück (für TNC-Befehl)."""
        active = [letter for letter, cb in self._msg_checks.items() if cb.isChecked()]
        if len(active) == len(self._msg_checks):
            return "ALL"
        if not any(cb.isChecked() for letter, cb in self._msg_checks.items()
                   if cb.isEnabled()):
            return "NONE"
        return "YES " + ",".join(active)

    def get_navstn_filter(self) -> str:
        """Gibt den aktuellen NAVSTN-Filter als String zurück (für TNC-Befehl)."""
        return self.le_navstn.text().strip().upper() or "ALL"

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _update_utc(self) -> None:
        now = datetime.now(timezone.utc)
        self.lbl_utc.setText(now.strftime("UTC  %H:%M:%S"))


# ---------------------------------------------------------------------------
# Standalone-Test
# ---------------------------------------------------------------------------

class _TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PK232PY – NAVTEX Screen (Test)")
        self.resize(750, 620)
        self.setCentralWidget(NavtexScreen())


def main() -> None:
    # Theme aus Kommandozeilenargument lesen (vom Launcher übergeben)
    theme = "dark"
    for arg in sys.argv[1:]:
        if arg.startswith("--theme="):
            theme = arg.split("=", 1)[1]
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_app_style(app, theme)
    win = _TestWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

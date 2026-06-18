"""
baudot_screen.py – Baudot/RTTY Opmode-Screen (ITA-2, 5-Bit)

Erbt den gesamten gemeinsamen Aufbau von RttyBaseScreen und ergänzt
die moduspezifischen Buttons in Reihe 2:

    Switch figs | Switch char | Wide Shift | RxRev | TxRev | 5Bit | 6Bit

Standalone-Test: python baudot_screen.py
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QHBoxLayout
from .opmode_rtty_base import RttyBaseScreen, apply_app_style, make_toggle_button, BTN_W, QPushButton


class BaudotScreen(RttyBaseScreen):
    """Baudot/RTTY Opmode-Screen.

    Reihe-2-Buttons (Baudot-spezifisch):
        Switch figs  – Umschalten auf Ziffern-Zeichensatz (FIGS)
        Switch char  – Zurück auf Buchstaben-Zeichensatz (LTRS)
        Wide Shift   – 850 Hz Shift ein/aus  (Toggle)
        RxRev        – RX-Polarität umkehren (Toggle)
        TxRev        – TX-Polarität umkehren (Toggle)
        5Bit         – 5-Bit-Modus           (Toggle)
        6Bit         – 6-Bit-Modus           (Toggle)
        EAS          – Echo As Sent          (Toggle)
    """

    MODE_TITLE = "Baudot"

    def _build_mode_buttons(self, layout: QHBoxLayout) -> None:
        """Baudot-spezifische Buttons in Reihe 2."""

        # Aktions-Buttons (kein Toggle — einmaliger Befehl an TNC)
        self.btn_figs  = QPushButton("Switch figs")
        self.btn_chars = QPushButton("Switch char")
        for b in (self.btn_figs, self.btn_chars):
            b.setFixedWidth(BTN_W)
            layout.addWidget(b)

        # Toggle-Buttons
        self.btn_wideshft = make_toggle_button("Wide Shift")
        self.btn_rxrev    = make_toggle_button("RxRev")
        self.btn_txrev    = make_toggle_button("TxRev")
        self.btn_5bit     = make_toggle_button("5Bit")
        self.btn_6bit     = make_toggle_button("6Bit")
        self.btn_eas      = make_toggle_button("EAS")

        self.btn_figs.setToolTip(
            "Switch the TNC to the FIGS set (digits / symbols). "
            "Sent immediately, independent of SEND/RECEIVE."
        )
        self.btn_chars.setToolTip(
            "Switch the TNC back to the LTRS set (letters). Sent immediately."
        )
        self.btn_wideshft.setToolTip(
            "Toggle 850 Hz wide shift vs. 170 Hz narrow — match the other station."
        )
        self.btn_rxrev.setToolTip("Reverse RX mark/space polarity (decode an inverted signal).")
        self.btn_txrev.setToolTip("Reverse TX mark/space polarity.")
        self.btn_5bit.setToolTip("5-bit ITA-2 character length (standard Baudot RTTY).")
        self.btn_6bit.setToolTip("6-bit character length (extended / special use).")
        self.btn_eas.setToolTip(
            "Echo As Sent — colour TX characters at the moment the TNC keys them on air."
        )

        for b in (
            self.btn_wideshft,
            self.btn_rxrev,
            self.btn_txrev,
            self.btn_5bit,
            self.btn_6bit,
            self.btn_eas,
        ):
            layout.addWidget(b)

        layout.addStretch()


# ---------------------------------------------------------------------------
# Standalone-Test
# ---------------------------------------------------------------------------

class _TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PK232PY – Baudot Screen (Test)")
        self.resize(730, 560)
        self.setCentralWidget(BaudotScreen())


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

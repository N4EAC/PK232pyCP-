"""
ascii_screen.py – ASCII-RTTY Opmode-Screen (7-Bit ASCII)

Erbt den gesamten gemeinsamen Aufbau von RttyBaseScreen und ergänzt
die moduspezifischen Buttons in Reihe 2:

    Wide Shift | RxRev | TxRev | 8Bit

Unterschiede zu Baudot:
    + 8Bit  (8BITCONV — transparenter 8-Bit-Modus)
    − Switch figs / Switch char  (ASCII hat keine Shift-Zustände)
    − 5Bit / 6Bit                (nicht relevant für ASCII)

Standalone-Test: python ascii_screen.py
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QHBoxLayout
from .opmode_rtty_base import RttyBaseScreen, apply_app_style, make_toggle_button


class AsciiScreen(RttyBaseScreen):
    """ASCII-RTTY Opmode-Screen.

    ASCII-RTTY verwendet den vollen 7-Bit-ASCII-Zeichensatz (128 Zeichen).
    Im Gegensatz zu Baudot gibt es keine Shift-Zustände (FIGS/LTRS) —
    jedes Zeichen ist selbstständig kodiert. Der optionale 8BITCONV-Modus
    erlaubt den transparenten Transfer von 8-Bit-Binärdaten.

    Reihe-2-Buttons (ASCII-spezifisch):
        Wide Shift  – 850 Hz Shift ein/aus  (Toggle)
        RxRev       – RX-Polarität umkehren (Toggle)
        TxRev       – TX-Polarität umkehren (Toggle)
        8Bit        – 8BITCONV ein/aus      (Toggle)
        EAS         – Echo As Sent          (Toggle)
    """

    MODE_TITLE  = "ASCII RTTY"
    HELP_TOPIC  = "ascii"
    BAUD_LABEL  = "ABAUD (Speed):"
    BAUD_VALUES = [
        "45", "50", "57", "75", "100", "110", "150", "200", "300",
        "400", "600", "1200", "2400", "4800", "9600",
    ]

    def _build_mode_buttons(self, layout: QHBoxLayout) -> None:
        """ASCII-spezifische Buttons in Reihe 2."""

        self.btn_wideshft = make_toggle_button("Wide Shift")
        self.btn_rxrev    = make_toggle_button("RxRev")
        self.btn_txrev    = make_toggle_button("TxRev")
        self.btn_8bit     = make_toggle_button("8Bit")
        self.btn_eas      = make_toggle_button("EAS")

        for b in (
            self.btn_wideshft,
            self.btn_rxrev,
            self.btn_txrev,
            self.btn_8bit,
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
        self.setWindowTitle("PK232PY – ASCII RTTY Screen (Test)")
        self.resize(730, 560)
        self.setCentralWidget(AsciiScreen())


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

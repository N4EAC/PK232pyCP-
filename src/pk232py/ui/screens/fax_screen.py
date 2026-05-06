"""
fax_screen.py – HF FAX / WEFAX Opmode-Screen

Der PK-232MBX empfängt HF-Wetterkarten-Faksimile (WEFAX).
Pixel-Daten kommen als $3F RX_MONITOR Frames zeilenweise vom TNC.
Das Bild wird Zeile für Zeile von oben nach unten aufgebaut.

Parameter:
  FSPEED  0–4   Scan-Geschwindigkeit (Linien/Sek):
                0 = 1.5 LPS (90 LPM)
                1 = 1   LPS (60 LPM)
                2 = 2   LPS (120 LPM)  ← Standard Wetterkarten
                3 = 3   LPS (180 LPM)
                4 = 4   LPS (240 LPM)

  ASPECT  1–6   Zeilendichte: aus 6 empfangenen werden n gedruckt
                Standard = 2 (576 lpi WEFAX)

  FAXNEG  ON/OFF  Bild invertieren (Negativ)
  RXREV   ON/OFF  Signal umkehren (anders als FAXNEG!)

Nur Empfang — kein TX, keine Macros.

Standalone-Test: python fax_screen.py
"""

import sys
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox,
    QFrame, QSizePolicy, QGroupBox,
    QScrollArea, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QPixmap, QImage, QPainter, QColor

from .opmode_rtty_base import (
    make_toggle_button, add_hline,
    apply_app_style, style_rx_widget,
    get_theme,
)


# ---------------------------------------------------------------------------
# FSPEED Tabelle
# ---------------------------------------------------------------------------

FSPEED_TABLE = [
    ("0 – 1.5 LPS  (90 LPM)",   90),
    ("1 – 1   LPS  (60 LPM)",   60),
    ("2 – 2   LPS  (120 LPM)",  120),   # Standard
    ("3 – 3   LPS  (180 LPM)",  180),
    ("4 – 4   LPS  (240 LPM)",  240),
]

# Standardbildbreite für WEFAX (Pixel pro Zeile)
FAX_IMAGE_WIDTH = 800


# ---------------------------------------------------------------------------
# FaxImageWidget – simulierter Bildaufbau
# ---------------------------------------------------------------------------

class FaxImageWidget(QLabel):
    """Zeigt das empfangene FAX-Bild an.

    Im echten Betrieb wird jede empfangene Pixelzeile per
    append_line() hinzugefügt. Im Mockup kann demo_fill()
    ein Testbild generieren.
    """

    def __init__(self, width: int = FAX_IMAGE_WIDTH, parent=None):
        super().__init__(parent)
        self._img_width  = width
        self._lines: list[bytes] = []
        self._faxneg = False
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setMinimumHeight(200)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._render_placeholder()

    def _render_placeholder(self) -> None:
        """Zeigt einen leeren grauen Platzhalter."""
        img = QImage(self._img_width, 200, QImage.Format.Format_Grayscale8)
        img.fill(180)
        self.setPixmap(QPixmap.fromImage(img))

    def clear_image(self) -> None:
        """Löscht das aktuelle Bild."""
        self._lines.clear()
        self._render_placeholder()

    def append_line(self, pixel_data: bytes) -> None:
        """Fügt eine Pixelzeile hinzu und aktualisiert die Anzeige.

        Args:
            pixel_data: Bytes mit Graustufenwerten (0=schwarz, 255=weiß).
                        Länge sollte _img_width entsprechen.
        """
        self._lines.append(pixel_data)
        self._redraw()

    def set_faxneg(self, enabled: bool) -> None:
        """Schaltet Negativ-Darstellung um und zeichnet neu."""
        self._faxneg = enabled
        if self._lines:
            self._redraw()

    def _redraw(self) -> None:
        """Baut das QImage aus allen gespeicherten Zeilen neu auf."""
        h = len(self._lines)
        if h == 0:
            return
        img = QImage(self._img_width, h, QImage.Format.Format_Grayscale8)
        for y, line in enumerate(self._lines):
            # Zeile auf Bildbreite zuschneiden / auffüllen
            row = (line[:self._img_width]).ljust(self._img_width, b'\x80')
            for x, val in enumerate(row):
                pixel = (255 - val) if self._faxneg else val
                img.setPixel(x, y, QColor(pixel, pixel, pixel).rgb())
        self.setPixmap(QPixmap.fromImage(img))
        self.setFixedHeight(max(200, h))

    def demo_fill(self, n_lines: int = 300) -> None:
        """Füllt das Bild mit einem Demo-Testmuster (Graustufenverlauf)."""
        self._lines.clear()
        import math
        for y in range(n_lines):
            row = bytes([
                int(128 + 127 * math.sin(x / 20.0 + y / 30.0))
                for x in range(self._img_width)
            ])
            self._lines.append(row)
        self._redraw()

    def save_as_png(self, path: str) -> bool:
        """Speichert das aktuelle Bild als PNG."""
        if not self._lines:
            return False
        pixmap = self.pixmap()
        if pixmap and not pixmap.isNull():
            return pixmap.save(path, "PNG")
        return False


# ---------------------------------------------------------------------------
# FaxScreen
# ---------------------------------------------------------------------------

class FaxScreen(QWidget):
    """HF FAX / WEFAX Opmode-Screen — nur Empfang, keine Macros.

    Layout (von oben nach unten):
    ┌────────────────────────────────────────────────────────┐
    │  HF FAX / WEFAX                        UTC  HH:MM:SS  │
    ├────────────────────────────────────────────────────────┤
    │  Info: Wetterkarten-Empfang · Nur Empfang              │
    ├─────────────────────────┬──────────────────────────────┤
    │  FSPEED: [Dropdown]     │  ASPECT: [-][ 2][+]         │
    │  [FAXNEG] [RXREV]       │  [Demo] [Löschen] [Speich.] │
    ├────────────────────────────────────────────────────────┤
    │  Status: ● BEREIT   Zeilen: 0                         │
    ├────────────────────────────────────────────────────────┤
    │  Bild-Scroll-Bereich (QLabel mit QPixmap)              │
    │  (wächst von oben nach unten mit jeder Zeile)          │
    └────────────────────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._utc_timer = QTimer(self)
        self._utc_timer.setInterval(1000)
        self._utc_timer.timeout.connect(self._update_utc)
        self._utc_timer.start()

        # Demo-Timer für den Mockup-Testmodus
        self._demo_timer  = QTimer(self)
        self._demo_timer.setInterval(50)   # 50ms pro Zeile ≈ 20 LPS Demo
        self._demo_timer.timeout.connect(self._on_demo_tick)
        self._demo_line   = 0
        self._demo_active = False

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # --- Titelzeile --------------------------------------------------
        title_row = QHBoxLayout()
        title = QLabel("HF FAX / WEFAX")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_row.addWidget(title)
        title_row.addStretch()
        self.lbl_utc = QLabel()
        self.lbl_utc.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        self.lbl_utc.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._update_utc()
        title_row.addWidget(self.lbl_utc)
        root.addLayout(title_row)

        add_hline(root)

        # --- Info-Zeile --------------------------------------------------
        info_row = QHBoxLayout()
        for text in (
            "Wetterkarten-Faksimile",
            "Nur Empfang",
            "LSB/USB je nach Station",
            "DCD-LED beobachten",
        ):
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #8aaccc;")
            info_row.addWidget(lbl)
        info_row.addStretch()
        root.addLayout(info_row)

        add_hline(root)

        # --- Parameter-Box -----------------------------------------------
        param_box = QGroupBox("FAX-Parameter")
        param_box.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        param_layout = QHBoxLayout(param_box)
        param_layout.setSpacing(12)

        # FSPEED Dropdown
        param_layout.addWidget(_lbl("FSPEED:"))
        self.combo_fspeed = QComboBox()
        for label, _ in FSPEED_TABLE:
            self.combo_fspeed.addItem(label)
        self.combo_fspeed.setCurrentIndex(2)   # Default: 120 LPM
        self.combo_fspeed.setFixedWidth(200)
        self.combo_fspeed.setToolTip(
            "Horizontale Scan-Geschwindigkeit.\n"
            "Wetterkarten: meist 2 LPS (120 LPM)\n"
            "Fotos/News: meist 1 LPS (60 LPM)"
        )
        param_layout.addWidget(self.combo_fspeed)

        param_layout.addSpacing(12)

        # ASPECT SpinBox
        param_layout.addWidget(_lbl("ASPECT:"))
        self.btn_asp_dn = _small_btn("−")
        param_layout.addWidget(self.btn_asp_dn)
        self.sb_aspect = QSpinBox()
        self.sb_aspect.setRange(1, 6)
        self.sb_aspect.setValue(2)
        self.sb_aspect.setFixedWidth(45)
        self.sb_aspect.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sb_aspect.setFont(QFont("Courier New", 10))
        self.sb_aspect.setToolTip(
            "Zeilendichte: aus 6 empfangenen Zeilen werden n gedruckt.\n"
            "1 = gestreckt  ·  2 = Standard WEFAX  ·  6 = gestaucht"
        )
        param_layout.addWidget(self.sb_aspect)
        self.btn_asp_up = _small_btn("+")
        param_layout.addWidget(self.btn_asp_up)
        self.btn_asp_dn.clicked.connect(
            lambda: self.sb_aspect.setValue(self.sb_aspect.value() - 1)
        )
        self.btn_asp_up.clicked.connect(
            lambda: self.sb_aspect.setValue(self.sb_aspect.value() + 1)
        )

        param_layout.addSpacing(12)

        # Toggle-Buttons
        self.btn_faxneg = make_toggle_button("FAXNEG")
        self.btn_faxneg.setToolTip(
            "FAXNEG ON: Schwarz und Weiß vertauschen.\n"
            "Nützlich bei Satellitenbildern (hauptsächlich schwarz)."
        )
        self.btn_faxneg.toggled.connect(
            lambda checked: self.fax_image.set_faxneg(checked)
        )
        param_layout.addWidget(self.btn_faxneg)

        self.btn_rxrev = make_toggle_button("RXREV")
        self.btn_rxrev.setToolTip(
            "RXREV ON: Gesamtes Signal umkehren.\n"
            "Anders als FAXNEG — betrifft auch Sync-Signale."
        )
        param_layout.addWidget(self.btn_rxrev)

        param_layout.addStretch()
        root.addWidget(param_box)

        add_hline(root)

        # --- Steuerleiste ------------------------------------------------
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        # Status
        self.lbl_status = QLabel("●  BEREIT")
        self.lbl_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet("color: #888888;")
        ctrl_row.addWidget(self.lbl_status)

        self.lbl_lines = QLabel("Zeilen: 0")
        self.lbl_lines.setFont(QFont("Segoe UI", 9))
        ctrl_row.addWidget(self.lbl_lines)

        ctrl_row.addStretch()

        # Aktions-Buttons
        self.btn_demo = QPushButton("▶  Demo")
        self.btn_demo.setFixedWidth(80)
        self.btn_demo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_demo.setToolTip("Testbild animiert aufbauen (Mockup-Demo)")
        self.btn_demo.setStyleSheet(
            "QPushButton { background-color: #2a4a6a; color: #88aadd;"
            " border: 1px solid #3a5a7a; border-radius: 4px; padding: 4px; }"
            "QPushButton:hover { background-color: #335577; }"
        )
        self.btn_demo.clicked.connect(self._on_demo)
        ctrl_row.addWidget(self.btn_demo)

        self.btn_clear = QPushButton("Löschen")
        self.btn_clear.setFixedWidth(80)
        self.btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear.setToolTip("Bild löschen und zurücksetzen")
        self.btn_clear.clicked.connect(self._on_clear)
        ctrl_row.addWidget(self.btn_clear)

        self.btn_save = QPushButton("💾  Speichern")
        self.btn_save.setFixedWidth(110)
        self.btn_save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_save.setToolTip("Bild als PNG-Datei speichern")
        self.btn_save.clicked.connect(self._on_save)
        ctrl_row.addWidget(self.btn_save)

        root.addLayout(ctrl_row)

        add_hline(root)

        # --- Bild-Scroll-Bereich -----------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )

        self.fax_image = FaxImageWidget(FAX_IMAGE_WIDTH)
        scroll.setWidget(self.fax_image)

        root.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------------
    # Demo-Modus
    # ------------------------------------------------------------------

    def _on_demo(self) -> None:
        """Startet oder stoppt den animierten Demo-Bildaufbau."""
        if self._demo_active:
            self._demo_timer.stop()
            self._demo_active = False
            self.btn_demo.setText("▶  Demo")
            self._set_status("BEREIT", "#888888")
        else:
            self.fax_image.clear_image()
            self._demo_line  = 0
            self._demo_active = True
            self.btn_demo.setText("■  Stop")
            self._set_status("EMPFANG …", "#cc8800")
            self._demo_timer.start()

    def _on_demo_tick(self) -> None:
        """Fügt pro Tick eine Demo-Zeile ein (simuliert TNC-Frame-Empfang)."""
        import math
        y = self._demo_line
        row = bytes([
            int(128 + 100 * math.sin(x / 25.0) * math.cos(y / 40.0)
                + 28 * math.sin(x / 8.0 + y / 15.0))
            for x in range(FAX_IMAGE_WIDTH)
        ])
        self.fax_image.append_line(row)
        self._demo_line += 1
        self.lbl_lines.setText(f"Zeilen: {self._demo_line}")

        if self._demo_line >= 400:
            self._demo_timer.stop()
            self._demo_active = False
            self.btn_demo.setText("▶  Demo")
            self._set_status("FERTIG", "#3a9e3a")

    # ------------------------------------------------------------------
    # Bild-Steuerung
    # ------------------------------------------------------------------

    def _on_clear(self) -> None:
        if self._demo_active:
            self._demo_timer.stop()
            self._demo_active = False
            self.btn_demo.setText("▶  Demo")
        self.fax_image.clear_image()
        self.lbl_lines.setText("Zeilen: 0")
        self._set_status("BEREIT", "#888888")

    def _on_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "FAX-Bild speichern", "fax_image.png",
            "PNG-Bild (*.png);;Alle Dateien (*)"
        )
        if path:
            ok = self.fax_image.save_as_png(path)
            if ok:
                QMessageBox.information(
                    self, "Gespeichert", f"Bild gespeichert:\n{path}"
                )
            else:
                QMessageBox.warning(
                    self, "Fehler", "Kein Bild vorhanden oder Speichern fehlgeschlagen."
                )

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str) -> None:
        self.lbl_status.setText(f"●  {text}")
        self.lbl_status.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )

    def _update_utc(self) -> None:
        now = datetime.now(timezone.utc)
        self.lbl_utc.setText(now.strftime("UTC  %H:%M:%S"))


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _small_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # kein Focus-Raub
    btn.setFixedWidth(26)
    btn.setFixedHeight(24)
    btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    btn.setStyleSheet(
        "QPushButton { background-color: #445566; color: white;"
        " border: 1px solid #334455; border-radius: 3px; }"
        "QPushButton:hover { background-color: #556677; }"
        "QPushButton:pressed { background-color: #334455; }"
    )
    return btn


# ---------------------------------------------------------------------------
# Standalone-Test
# ---------------------------------------------------------------------------

class _TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PK232PY – HF FAX / WEFAX Screen (Test)")
        self.resize(860, 680)
        self.setCentralWidget(FaxScreen())


def main() -> None:
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
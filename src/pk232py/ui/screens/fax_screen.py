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

import logging
import sys
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox,
    QFrame, QSizePolicy, QGroupBox,
    QScrollArea, QFileDialog, QMessageBox,
    QSlider,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QPixmap, QImage, QPainter, QColor

from .opmode_rtty_base import (
    make_toggle_button, add_hline,
    apply_app_style, style_rx_widget,
    get_theme, BTN_W,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FSPEED Tabelle
# ---------------------------------------------------------------------------

FSPEED_TABLE = [
    ("FSPEED 0 — 1.5 LPS  (90 LPM)",    90),
    ("FSPEED 1 — 1   LPS  (60 LPM)",    60),
    ("FSPEED 2 — 2   LPS  (120 LPM)",  120),   # Standard
    ("FSPEED 3 — 3   LPS  (180 LPM)",  180),
    ("FSPEED 4 — 4   LPS  (240 LPM)",  240),
]

# Standardbildbreite für WEFAX (Pixel pro Zeile)
# WEFAX image width: pixels/line ≈ 2 × IOC
# IOC 576 → ~1152 px  (HF weather fax standard, DWD/NOAA)
# IOC 288 → ~576 px   (older systems)
# Auto-detects from first received line — this is just the default.
FAX_IMAGE_WIDTH = 1152

# ASPECT table: (TNC value, IOC, received-to-display ratio, label)
# ratio = how many received lines are merged into one display line
# Source: AEA PK-232MBX manual (STABO edition)
ASPECT_TABLE = [
    (1, 288, 3, "ASPECT 1  —  IOC 288  —  ~576 px  —  Satellite images"),
    (2, 576, 6, "ASPECT 2  —  IOC 576  —  ~1152 px —  Weather maps (standard)"),
    (3, 550, 4, "ASPECT 3  —  IOC 550  —  ~1100 px —  Weather maps (narrow)"),
    (4, 596, 2, "ASPECT 4  —  IOC 596  —  ~1192 px —  Weather maps (wide)"),
]
# Map TNC value → ratio for quick lookup
ASPECT_RATIO: dict[int, int] = {a: r for a, _, r, _ in ASPECT_TABLE}


# ---------------------------------------------------------------------------
# FaxImageWidget – simulierter Bildaufbau
# ---------------------------------------------------------------------------

class FaxImageWidget(QLabel):
    """Zeigt das empfangene FAX-Bild an.

    Im echten Betrieb wird jede empfangene Pixelzeile per
    append_line() hinzugefügt. Im Mockup kann demo_fill()
    ein Testbild generieren.
    """

    # ── Pixel aspect ratio ──────────────────────────────────────────────
    # LERNMODUS: the TNC raster is NOT square. ESC L (double-density bit
    # image) packs 120 dots/inch HORIZONTALLY, whereas ESC A 8 (8/72" line
    # feed across an 8-pin band) yields only 72 dots/inch VERTICALLY. If we
    # render one display pixel per dot on both axes (1:1), a physical inch is
    # 120 px wide but only 72 px tall on screen — the image is squashed
    # vertically and a circle becomes a wide ("liegende") ellipse. We correct
    # this by stretching the VERTICAL axis by H_dpi / V_dpi = 120/72 at
    # display time, so the on-screen pixels become square again.
    PIXEL_ASPECT = 120 / 72   # = 5/3 ≈ 1.6667 (horizontal dpi / vertical dpi)

    # ── Non-destructive smoothing (inverse halftoning) ──────────────────
    # LERNMODUS: the TNC delivers a 1-bit BILEVEL bitmap — there is no real
    # grey, only dithered DOT DENSITY. A Gaussian blur over the bilevel image
    # turns that local dot density into perceptual grey (a crude inverse
    # halftone), which reads far better as a weather chart. This is a pure
    # DISPLAY enhancement: the received lines (_lines) and the raw bilevel
    # buffer (_buf / _qimage) are never modified, so smoothing=0 always
    # reproduces the exact original.
    SIGMA_MAX = 2.5            # Gaussian sigma at slider=100 (slider/100 * MAX)
    _SMOOTH_DEBOUNCE_MS = 200  # max recompute rate while lines keep arriving
    _SMOOTH_EVERY_LINES = 25   # force a recompute every N lines during receive

    def __init__(self, width: int = FAX_IMAGE_WIDTH, parent=None):
        super().__init__(parent)
        self._img_width  = width
        self._lines: list[bytes] = []
        self._faxneg = False
        self._zoom: float = 1.0
        # Manual vertical fine-stretch, applied ON TOP of PIXEL_ASPECT.
        # 1 = neutral → pure 120/72 aspect correction (round circle).
        self._line_height: int = 1
        self._qimage = None

        # Smoothing (display-only). 0 = off → pixel-exact raw bilevel.
        self._smoothing: int = 0
        self._smoothed = None          # cached smoothed QImage (None = dirty/off)
        self._smoothed_buf = None      # keep the smoothed buffer alive for QImage
        self._lines_since_smooth = 0   # for the every-N-lines recompute trigger
        # Throttle: recompute the (expensive) smoothed image at most every
        # _SMOOTH_DEBOUNCE_MS while lines stream in, and once more when the
        # stream rests. In between, the cheap raw buffer is shown.
        self._smooth_timer = QTimer(self)
        self._smooth_timer.setSingleShot(True)
        self._smooth_timer.timeout.connect(self._recompute_smoothed_and_show)

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
        """Löscht das aktuelle Bild und setzt Breite auf Standard zurück."""
        self._smooth_timer.stop()
        self._lines.clear()
        self._img_width = FAX_IMAGE_WIDTH   # reset for next reception
        self._qimage = None
        self._smoothed = None
        self._smoothed_buf = None
        self._lines_since_smooth = 0
        self._render_placeholder()

    def append_line(self, pixel_data: bytes) -> None:
        """Fügt eine Pixelzeile hinzu und aktualisiert die Anzeige.

        Auto-detects image width from the first received line so the
        widget adapts to whatever the TNC actually delivers.

        Args:
            pixel_data: Bytes mit Graustufenwerten (0=schwarz, 255=weiß).
        """
        if not self._lines and len(pixel_data) > 10:
            # First line: adopt its length as the image width
            self._img_width = len(pixel_data)
        self._lines.append(pixel_data)
        self._redraw()                      # cheap: raw bilevel, shown at once

        # Smoothing is expensive — never run it per line. Force a recompute
        # every _SMOOTH_EVERY_LINES, and (re)arm the debounce timer so a final
        # smooth lands shortly after the stream rests. The raw buffer is shown
        # in the meantime (set in _redraw).
        if self._smoothing > 0:
            self._lines_since_smooth += 1
            if self._lines_since_smooth >= self._SMOOTH_EVERY_LINES:
                self._recompute_smoothed_and_show()
            else:
                self._smooth_timer.start(self._SMOOTH_DEBOUNCE_MS)

    def set_faxneg(self, enabled: bool) -> None:
        """Schaltet Negativ-Darstellung um und zeichnet neu."""
        self._faxneg = enabled
        if self._lines:
            self._redraw()                  # raw buffer rebuilt post-FAXNEG
            if self._smoothing > 0:         # user action, not a stream → now
                self._recompute_smoothed_and_show()

    def set_zoom(self, factor: float) -> None:
        """Scale the displayed image by *factor* (1.0 = 100%)."""
        self._zoom = factor
        if self._qimage is not None:
            self._apply_zoom()

    def set_line_height(self, factor: int) -> None:
        """Manual vertical fine-stretch, applied ON TOP of PIXEL_ASPECT.

        1 = neutral: pure 120/72 aspect correction (the geometrically correct
            default — circles come out round).
        2-4 = extra vertical stretch, if the operator wants taller proportions.

        Only affects display scaling (not the native raster), so a re-scale of
        the existing QImage is enough — no full _redraw needed.
        """
        self._line_height = max(1, factor)
        if self._qimage is not None:
            self._apply_zoom()

    def set_smoothing(self, value: int) -> None:
        """Set smoothing strength 0..100 (display-only inverse halftoning).

        0  → pixel-exact raw bilevel (the original-preservation guarantee:
             move the slider back to 0 to get the untouched received image).
        >0 → Gaussian-blurred + smooth-scaled grey. Recomputed immediately
             here (a deliberate user action), unlike the throttled live path.
        """
        self._smoothing = max(0, min(100, int(value)))
        self._smooth_timer.stop()
        self._smoothed = None
        self._lines_since_smooth = 0
        if self._qimage is None:
            return
        if self._smoothing > 0:
            self._recompute_smoothed_and_show()
        else:
            self._apply_zoom()              # back to the raw bilevel original

    def _recompute_smoothed_and_show(self) -> None:
        """(Re)build the cached smoothed image from the raw buffer, then show."""
        self._lines_since_smooth = 0
        self._smooth_timer.stop()
        self._compute_smoothed()
        self._apply_zoom()

    def _compute_smoothed(self) -> None:
        """Gaussian-blur the POST-FAXNEG bilevel buffer into a grey QImage.

        scipy/numpy are imported lazily (only paid for when smoothing is on);
        if unavailable we leave _smoothed=None and the raw image is shown.
        """
        if self._qimage is None or self._smoothing <= 0 or not self._buf:
            self._smoothed = None
            return
        try:
            import numpy as np
            from scipy.ndimage import gaussian_filter
        except ImportError:
            logger.warning("FAX smoothing needs numpy+scipy — showing raw image")
            self._smoothed = None
            return

        w, n = self._img_width, len(self._lines)
        arr = np.frombuffer(bytes(self._buf), dtype=np.uint8).reshape(n, w)
        sigma = (self._smoothing / 100.0) * self.SIGMA_MAX
        # ANISOTROPIC sigma = (row-axis, col-axis) = (vertical, horizontal).
        # The native raster is finer horizontally (120 dpi) than vertically
        # (72 dpi), so equal pixel-blur would over-blur vertically / under-blur
        # horizontally. Scaling the horizontal sigma by PIXEL_ASPECT (120/72)
        # blurs both axes equally in PHYSICAL space.
        blurred = gaussian_filter(
            arr.astype(np.float32),
            sigma=(sigma, sigma * self.PIXEL_ASPECT),
        )
        out = np.clip(blurred, 0, 255).astype(np.uint8)
        self._smoothed_buf = out.tobytes()   # keep alive for the QImage below
        img = QImage(self._smoothed_buf, w, n, w, QImage.Format.Format_Grayscale8)
        self._smoothed = img.copy()

    def _apply_zoom(self) -> None:
        """Scale the current source to the display, correcting the pixel aspect.

        Source: the cached SMOOTHED image when smoothing>0 and it is ready,
        otherwise the raw bilevel _qimage.
        Horizontal: 1 display px per H-dot, times zoom.
        Vertical:   times zoom, times the manual line-height fine-factor, AND
                    times PIXEL_ASPECT (120/72) to undo the non-square raster.
        Scaling transform: Fast at smoothing==0 (crisp, pixel-exact original),
        Smooth at smoothing>0. The PIXEL_ASPECT vertical stretch is active in
        BOTH cases.
        """
        if self._qimage is None:
            return
        smoothing_on = self._smoothing > 0
        src = self._smoothed if (smoothing_on and self._smoothed is not None) \
            else self._qimage
        w = max(1, int(self._img_width * self._zoom))
        h = max(1, round(len(self._lines) * self._zoom
                         * self._line_height * self.PIXEL_ASPECT))
        mode = (Qt.TransformationMode.SmoothTransformation if smoothing_on
                else Qt.TransformationMode.FastTransformation)
        scaled = src.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, mode)
        self.setPixmap(QPixmap.fromImage(scaled))
        self.setFixedSize(max(w, 200), max(h, 200))

    def _redraw(self) -> None:
        """Baut das QImage aus allen gespeicherten Zeilen neu auf.

        Uses bytearray + QImage(data, w, h, bpl, format) constructor
        to avoid scanLine() which returns a voidptr with unknown size
        in PyQt6 and cannot be slice-assigned.
        """
        n = len(self._lines)
        if n == 0:
            return
        w = self._img_width

        # Build the QImage at the NATIVE raster: exactly one row per received
        # line. All vertical scaling (PIXEL_ASPECT × line_height × zoom) is done
        # later in _apply_zoom via a smooth transform — so NO integer row
        # replication here (that is what "kein integer-Replikat" means and what
        # lets the 5/3 aspect come out cleanly).
        buf = bytearray(w * n)
        for y, line in enumerate(self._lines):
            raw = (line[:w]).ljust(w, b'\x80')
            if self._faxneg:
                row = bytes(255 - v for v in raw)
            else:
                row = bytes(raw)
            buf[y * w : y * w + w] = row

        img = QImage(buf, w, n, w, QImage.Format.Format_Grayscale8)
        self._buf = buf
        self._qimage = img.copy()
        # Raw raster changed → any cached smoothed image is now stale. Show the
        # raw buffer immediately; a fresh smooth is scheduled by the caller
        # (append_line throttled / set_faxneg+set_smoothing immediate).
        self._smoothed = None
        self._apply_zoom()

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
        if self._smoothing > 0:
            self._recompute_smoothed_and_show()

    def save_as_png(self, path: str) -> bool:
        """Save the CURRENTLY DISPLAYED image as PNG.

        Saves what is on screen: the smoothed version when smoothing>0, the raw
        bilevel original when smoothing==0. The untouched original is therefore
        always reproducible by moving the smoothing slider back to 0.
        """
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
            "Weather-chart facsimile",
            "Receive only",
            "LSB/USB depending on station",
            "Watch the DCD LED",
        ):
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #8aaccc;")
            info_row.addWidget(lbl)
        info_row.addStretch()
        root.addLayout(info_row)

        add_hline(root)

        # --- Parameter-Box -----------------------------------------------
        param_box = QGroupBox("FAX Parameters")
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
            "Horizontal scan rate.\n"
            "Weather charts: usually 2 LPS (120 LPM)\n"
            "Photos/news: usually 1 LPS (60 LPM)"
        )
        param_layout.addWidget(self.combo_fspeed)

        param_layout.addSpacing(12)

        # ASPECT ComboBox — IOC-based selection
        param_layout.addWidget(_lbl("ASPECT:"))
        self.combo_aspect = QComboBox()
        for _a, _ioc, _r, _label in ASPECT_TABLE:
            self.combo_aspect.addItem(_label)
        self.combo_aspect.setCurrentIndex(1)   # default: ASPECT 2, IOC 576
        self.combo_aspect.setFont(QFont("Courier New", 9))
        self.combo_aspect.setToolTip(
            "ASPECT: line density (IOC).\n"
            "ASPECT 2 / IOC 576 = standard weather charts (DWD, NOAA).\n"
            "ASPECT 1 / IOC 288 = satellite images."
        )
        param_layout.addWidget(self.combo_aspect)
        # Keep sb_aspect as hidden compatibility shim (MainWindow wires it)
        self.sb_aspect = self.combo_aspect   # alias for compatibility

        param_layout.addSpacing(12)

        # Toggle-Buttons
        self.btn_faxneg = make_toggle_button("FAXNEG")
        self.btn_faxneg.setToolTip(
            "FAXNEG ON: swap black and white.\n"
            "Useful for satellite images (mostly black)."
        )
        self.btn_faxneg.toggled.connect(
            lambda checked: self.fax_image.set_faxneg(checked)
        )
        param_layout.addWidget(self.btn_faxneg)

        self.btn_rxrev = make_toggle_button("RXREV")
        self.btn_rxrev.setToolTip(
            "RXREV ON: invert the entire signal.\n"
            "Unlike FAXNEG — also affects the sync signals."
        )
        param_layout.addWidget(self.btn_rxrev)

        # LOCK is a one-shot ACTION (not a toggle): the PK-232 sits in
        # "FAX STBY RCVE" and emits NOTHING over Host Mode until it starts
        # printing, i.e. only after it detects a phasing sync. On the bench
        # (WAV fed in) auto-sync often fails to trigger, so LOCK (mnemonic LO)
        # forces the TNC to dump pixel data immediately as if a sync had
        # arrived. Hence a plain QPushButton, not make_toggle_button().
        self.btn_lock = QPushButton("LOCK")
        self.btn_lock.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_lock.setToolTip(
            "Force Receive (LO): TNC sofort auf Bildausgabe zwingen, ohne auf "
            "Phasing-Sync zu warten. Bild kann horizontal versetzt sein → ggf. "
            "mit JUSTIFY korrigieren."
        )
        param_layout.addWidget(self.btn_lock)

        # Stop is a one-shot ACTION too: freeze the current image and ignore
        # further incoming data (auto-sync AND LOCK) until LOCK or Clear. Lets
        # the operator keep / save a finished chart without it scrolling away.
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_stop.setToolTip(
            "Stop FAX reception: freeze the current image and ignore further "
            "data until LOCK or Clear."
        )
        param_layout.addWidget(self.btn_stop)

        param_layout.addStretch()
        root.addWidget(param_box)

        add_hline(root)

        # --- Steuerleiste ------------------------------------------------
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        # Status
        self.lbl_status = QLabel("●  READY")
        self.lbl_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet("color: #888888;")
        ctrl_row.addWidget(self.lbl_status)

        self.lbl_lines = QLabel("Lines: 0")
        self.lbl_lines.setFont(QFont("Segoe UI", 9))
        ctrl_row.addWidget(self.lbl_lines)

        ctrl_row.addStretch()

        # Aktions-Buttons
        self.btn_demo = QPushButton("▶  Demo")
        self.btn_demo.setFixedWidth(80)
        self.btn_demo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_demo.setToolTip("Animate a test image (mockup demo)")
        self.btn_demo.setStyleSheet(
            "QPushButton { background-color: #2a4a6a; color: #88aadd;"
            " border: 1px solid #3a5a7a; border-radius: 4px; padding: 4px; }"
            "QPushButton:hover { background-color: #335577; }"
        )
        self.btn_demo.clicked.connect(self._on_demo)
        ctrl_row.addWidget(self.btn_demo)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedWidth(80)
        self.btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear.setToolTip("Clear the image and reset")
        self.btn_clear.clicked.connect(self._on_clear)
        ctrl_row.addWidget(self.btn_clear)

        self.btn_save = QPushButton("💾  Save")
        self.btn_save.setFixedWidth(110)
        self.btn_save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_save.setToolTip("Save the image as a PNG file")
        self.btn_save.clicked.connect(self._on_save)
        ctrl_row.addWidget(self.btn_save)

        root.addLayout(ctrl_row)

        add_hline(root)

        # --- Zoom-Regler -------------------------------------------------
        zoom_row = QHBoxLayout()

        # Horizontal zoom
        zoom_row.addWidget(QLabel("Zoom:"))
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(100, 300)   # 100% – 300%
        self._zoom_slider.setValue(100)
        self._zoom_slider.setTickInterval(25)
        self._zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._zoom_slider.setFixedWidth(220)
        self._zoom_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._zoom_slider.setToolTip("Horizontal zoom: 100% – 300%")
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_row.addWidget(self._zoom_slider)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setFont(QFont("Courier New", 9))
        self._zoom_label.setFixedWidth(42)
        zoom_row.addWidget(self._zoom_label)

        zoom_row.addSpacing(20)

        # Vertical line height
        zoom_row.addWidget(QLabel("Line spacing:"))
        self._lh_slider = QSlider(Qt.Orientation.Horizontal)
        self._lh_slider.setRange(1, 4)    # vertical fine-stretch factor
        self._lh_slider.setValue(1)       # default: 1 = neutral (aspect-correct)
        self._lh_slider.setTickInterval(1)
        self._lh_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._lh_slider.setFixedWidth(100)
        self._lh_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._lh_slider.setToolTip(
            "Vertical fine-stretch on top of the automatic 120/72 aspect "
            "correction.\n"
            "1 = aspect-correct (standard)  ·  2–4 = extra vertical stretch"
        )
        self._lh_slider.valueChanged.connect(self._on_lh_changed)
        zoom_row.addWidget(self._lh_slider)
        self._lh_label = QLabel("1×")
        self._lh_label.setFont(QFont("Courier New", 9))
        self._lh_label.setFixedWidth(36)
        zoom_row.addWidget(self._lh_label)

        zoom_row.addSpacing(20)

        # Smoothing (inverse halftoning) — non-destructive display enhancement.
        # 0 = off → pixel-exact raw bilevel (original always reproducible).
        zoom_row.addWidget(QLabel("Smoothing:"))
        self._smooth_slider = QSlider(Qt.Orientation.Horizontal)
        self._smooth_slider.setRange(0, 100)
        self._smooth_slider.setValue(0)        # default: off (raw original)
        self._smooth_slider.setTickInterval(25)
        self._smooth_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._smooth_slider.setFixedWidth(160)
        self._smooth_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._smooth_slider.setToolTip(
            "Smoothing (inverse halftoning): blur the 1-bit dither into "
            "perceptual grey.\n"
            "0 = off → pixel-exact received image (original always reproducible "
            "by returning to 0).\nDisplay-only — the received data is never "
            "modified."
        )
        self._smooth_slider.valueChanged.connect(self._on_smoothing_changed)
        zoom_row.addWidget(self._smooth_slider)
        self._smooth_label = QLabel("Off (original)")
        self._smooth_label.setFont(QFont("Courier New", 9))
        self._smooth_label.setFixedWidth(90)
        zoom_row.addWidget(self._smooth_label)

        zoom_row.addStretch()
        root.addLayout(zoom_row)

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

        # Clear-Image row — receive-only screen clears its own image buffer.
        clear_row = QHBoxLayout()
        clear_row.addStretch()
        self.btn_clear_image = QPushButton("Clear Image")
        self.btn_clear_image.setFixedWidth(BTN_W + 20)
        self.btn_clear_image.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear_image.clicked.connect(self._on_clear_image)
        clear_row.addWidget(self.btn_clear_image)
        root.addLayout(clear_row)

    def _on_clear_image(self) -> None:
        """Clear the received FAX image and reset the line counter."""
        self.fax_image.clear_image()
        self.lbl_lines.setText("Lines: 0")

    # ------------------------------------------------------------------
    # Demo-Modus
    # ------------------------------------------------------------------

    def _on_demo(self) -> None:
        """Startet oder stoppt den animierten Demo-Bildaufbau."""
        if self._demo_active:
            self._demo_timer.stop()
            self._demo_active = False
            self.btn_demo.setText("▶  Demo")
            self._set_status("READY", "#888888")
        else:
            self.fax_image.clear_image()
            self._demo_line  = 0
            self._demo_active = True
            self.btn_demo.setText("■  Stop")
            self._set_status("RECEIVING …", "#cc8800")
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
        self.lbl_lines.setText(f"Lines: {self._demo_line}")

        if self._demo_line >= 400:
            self._demo_timer.stop()
            self._demo_active = False
            self.btn_demo.setText("▶  Demo")
            self._set_status("DONE", "#3a9e3a")

    # ------------------------------------------------------------------
    # Bild-Steuerung
    # ------------------------------------------------------------------

    def _on_clear(self) -> None:
        if self._demo_active:
            self._demo_timer.stop()
            self._demo_active = False
            self.btn_demo.setText("▶  Demo")
        self.fax_image.clear_image()
        self.lbl_lines.setText("Lines: 0")
        self._set_status("READY", "#888888")

    def _on_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save FAX image", "fax_image.png",
            "PNG image (*.png);;All files (*)"
        )
        if path:
            ok = self.fax_image.save_as_png(path)
            if ok:
                QMessageBox.information(
                    self, "Saved", f"Image saved:\n{path}"
                )
            else:
                QMessageBox.warning(
                    self, "Error", "No image present or saving failed."
                )

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _on_zoom_changed(self, value: int) -> None:
        """Zoom slider moved — rescale the FAX image display."""
        factor = value / 100.0
        self._zoom_label.setText(f"{value}%")
        self.fax_image.set_zoom(factor)

    def _on_lh_changed(self, value: int) -> None:
        """Line-spacing slider moved — change the vertical fine-stretch factor."""
        self._lh_label.setText(f"{value}×")
        self.fax_image.set_line_height(value)

    def _on_smoothing_changed(self, value: int) -> None:
        """Smoothing slider moved — set display-only inverse-halftone strength."""
        self._smooth_label.setText("Off (original)" if value == 0 else f"{value}%")
        self.fax_image.set_smoothing(value)

    def set_receiving(self, active: bool) -> None:
        """Called by MainWindow when FAX mode is activated/deactivated.

        Disables the Demo button while Host Mode is active so that
        demo data cannot interfere with real TNC data.
        """
        self.btn_demo.setEnabled(not active)
        if active:
            self.btn_demo.setToolTip(
                "Demo unavailable while the TNC is connected."
            )
        else:
            self.btn_demo.setToolTip(
                "Animate a test image (mockup demo)"
            )

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
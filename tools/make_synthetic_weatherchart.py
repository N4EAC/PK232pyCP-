#!/usr/bin/env python3
"""
make_synthetic_weatherchart.py — deterministic synthetic WEFAX test chart.

Generates a copyright-free, weather-chart-LOOKING grayscale image and writes it
to ``tools/synthetic_weatherchart.png`` (1152 x 600 px, mode "L"). It exists so
the FAX closed-loop test T66 has a committable reference image: the real DWD
chart (``tools/Wetterkarte.jpg``, © Deutscher Wetterdienst) cannot go into a
public repo, so we synthesise an equivalent that stresses the same decoder
features — smooth grayscale gradients, fine closed contour lines (isobars),
short curved strokes (coastline), and crisp text glyphs (H / T markers, title).

It is NOT meant to be meteorologically meaningful or photoreal — only
structurally rich enough that a correct decode is visually obvious and a
geometry regression (slant / shear / aspect error) is easy to spot.

Dependencies: numpy + Pillow only (same lean footprint as fax_wav_generator.py).

Usage:
    python tools/make_synthetic_weatherchart.py        # writes the PNG
    python tools/make_synthetic_weatherchart.py --show  # also opens a preview

------------------------------------------------------------------------------
LERNMODUS — why this file is built the way it is
------------------------------------------------------------------------------

1. DETERMINISM (fixed seed, no run-to-run variance)
   A test fixture must be byte-stable: if two people regenerate it they MUST get
   the same PNG, otherwise "the decode looks different" becomes ambiguous
   (decoder bug? or just a different input?). Every source of variation is
   pinned: the Gaussian pressure centres are hard-coded coordinates, and the
   only randomness (scattered station plots) draws from a SEEDED generator
   (``np.random.default_rng(SEED)``) — never the global, unseeded RNG.

2. ISOBARS FROM A SCALAR FIELD (the cheap contour trick)
   Real isobars are level curves of a pressure field. We build such a field as a
   sum of 2-D Gaussian "pressure centres", then we do NOT run a contouring
   algorithm. We QUANTISE the field into N bands (``np.digitize``) and mark
   every pixel where its band differs from the neighbour to the right or below.
   Those band boundaries ARE the contour lines — automatically closed, nested,
   and 1 px thin, with zero geometry library. Smooth field in -> clean concentric
   loops out.

3. PATH ANCHORING (__file__, not the CWD)
   Same lesson as fax_wav_generator.py: the output path is resolved relative to
   this script's location, so it lands in tools/ whether you launch from the
   repo root or from inside tools/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - clear guidance instead of a traceback
    sys.exit("Pillow is required: pip install Pillow")


# ===========================================================================
# CONSTANTS
# ===========================================================================

_SCRIPT_DIR = Path(__file__).resolve().parent          # .../pk232py_repo/tools
OUTPUT_PATH = _SCRIPT_DIR / "synthetic_weatherchart.png"

WIDTH  = 1152          # = fax_wav_generator.IMG_WIDTH
HEIGHT = 600           # = fax_wav_generator.NUM_LINES
SEED   = 20260615      # fixed -> reproducible station scatter

# Pressure centres: (cx, cy, amplitude, sigma). amplitude > 0 = High ("H"),
# amplitude < 0 = Low / "Tief" ("T"). Coordinates are hard-coded -> deterministic.
PRESSURE_CENTRES = [
    (250, 170, +1.00, 150),   # H
    (840, 150, -1.15, 135),   # T
    (560, 430, +0.85, 200),   # H
    (980, 470, -0.70, 120),   # T
    (130, 470, -0.55, 110),   # T
    (700, 330, +0.45, 90),    # H (weak, fills the centre with extra rings)
]

N_ISOBAR_BANDS = 26          # number of quantisation bands -> isobar density
BG_GRAY_LIGHT  = 255         # field minimum -> white
BG_GRAY_DARK   = 232         # field maximum -> faint gray (keeps gradients subtle)


# ===========================================================================
# FONT
# ===========================================================================

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ===========================================================================
# FIELD + ISOBARS
# ===========================================================================

def _pressure_field() -> np.ndarray:
    """Sum of 2-D Gaussians -> a smooth scalar field, shape (HEIGHT, WIDTH)."""
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float64)
    field = np.zeros((HEIGHT, WIDTH), dtype=np.float64)
    for cx, cy, amp, sigma in PRESSURE_CENTRES:
        field += amp * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma ** 2)))
    return field


def _field_to_grayscale_bg(field: np.ndarray) -> np.ndarray:
    """Map the field to a faint light-gray background (exercises grayscale)."""
    lo, hi = float(field.min()), float(field.max())
    norm = (field - lo) / (hi - lo) if hi > lo else np.zeros_like(field)
    gray = BG_GRAY_LIGHT - norm * (BG_GRAY_LIGHT - BG_GRAY_DARK)
    return gray.astype(np.uint8)


def _isobar_edges(field: np.ndarray) -> np.ndarray:
    """Boolean mask of contour pixels: where the quantisation band changes
    versus the right or the bottom neighbour (see LERNMODUS idea #2)."""
    levels = np.linspace(field.min(), field.max(), N_ISOBAR_BANDS)
    band = np.digitize(field, levels)
    edges = np.zeros_like(band, dtype=bool)
    edges[:, :-1] |= band[:, :-1] != band[:, 1:]   # horizontal neighbour
    edges[:-1, :] |= band[:-1, :] != band[1:, :]   # vertical neighbour
    return edges


# ===========================================================================
# OVERLAYS (coastline, graticule, markers, station plots, title)
# ===========================================================================

def _draw_graticule(d: ImageDraw.ImageDraw) -> None:
    """Faint mid-gray lat/long grid — extra fine straight lines so a vertical
    or horizontal shear in the decode is immediately visible."""
    for x in range(96, WIDTH, 96):
        d.line([(x, 0), (x, HEIGHT - 1)], fill=205, width=1)
    for y in range(75, HEIGHT, 75):
        d.line([(0, y), (WIDTH - 1, y)], fill=205, width=1)
    d.rectangle([0, 0, WIDTH - 1, HEIGHT - 1], outline=0, width=2)   # frame


def _draw_coastline(d: ImageDraw.ImageDraw) -> None:
    """Two deterministic sinusoidal strokes standing in for coastlines."""
    t = np.linspace(0, WIDTH - 1, 600)
    coast_a = 250 + 90 * np.sin(t / 170.0) + 30 * np.sin(t / 43.0)
    coast_b = 470 + 50 * np.sin(t / 130.0 + 1.2) + 18 * np.sin(t / 29.0)
    for coast in (coast_a, coast_b):
        d.line(list(zip(t.tolist(), coast.tolist())), fill=0, width=2)


def _draw_centre_markers(d: ImageDraw.ImageDraw) -> None:
    """H (high) / T (Tief = low) glyph at each pressure centre."""
    font = _font(34)
    for cx, cy, amp, _sigma in PRESSURE_CENTRES:
        letter = "H" if amp > 0 else "T"
        bbox = d.textbbox((0, 0), letter, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((cx - w / 2 - bbox[0], cy - h / 2 - bbox[1]), letter, fill=0, font=font)


def _draw_station_plots(d: ImageDraw.ImageDraw) -> None:
    """Scattered station circles + short wind barbs. Seeded -> deterministic."""
    rng = np.random.default_rng(SEED)
    n = 45
    xs = rng.integers(30, WIDTH - 30, n)
    ys = rng.integers(30, HEIGHT - 30, n)
    angles = rng.uniform(0, 2 * np.pi, n)
    for x, y, ang in zip(xs.tolist(), ys.tolist(), angles.tolist()):
        d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=0, width=1)
        bx, by = x + 14 * np.cos(ang), y + 14 * np.sin(ang)   # wind-barb shaft
        d.line([(x, y), (bx, by)], fill=0, width=1)


def _draw_title(d: ImageDraw.ImageDraw) -> None:
    """Title bar text — crisp glyphs to confirm text legibility after decode."""
    font = _font(20)
    label = "SYNTHETIC WEFAX TEST CHART  -  IOC 576  120 LPM  (not for navigation)"
    d.rectangle([0, 0, WIDTH - 1, 34], fill=255)
    d.text((12, 8), label, fill=0, font=font)
    d.line([(0, 34), (WIDTH - 1, 34)], fill=0, width=2)


# ===========================================================================
# COMPOSE + MAIN
# ===========================================================================

def make_chart() -> Image.Image:
    """Build the full synthetic chart as a Pillow "L" image."""
    field = _pressure_field()
    canvas = _field_to_grayscale_bg(field)      # faint gray gradients
    canvas[_isobar_edges(field)] = 0            # crisp black isobars
    img = Image.fromarray(canvas, mode="L")

    d = ImageDraw.Draw(img)
    _draw_graticule(d)
    _draw_coastline(d)
    _draw_station_plots(d)
    _draw_centre_markers(d)
    _draw_title(d)
    return img


def main(argv: list[str]) -> int:
    img = make_chart()
    img.save(OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH}  ({img.size[0]}x{img.size[1]}, mode {img.mode})")
    print(f"  size on disk: {OUTPUT_PATH.stat().st_size / 1024:.1f} kB")
    if "--show" in argv:
        img.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
fax_wav_generator.py — WEFAX test-WAV generator for PK232PY.

Generates three self-contained WEFAX (HF weather-fax) WAV files that can be
fed into the PK232PY FAX decoder or the standalone WEFAX audio-decoder tool
(``fax_decoder_test.py``) to verify the full receive/decode chain WITHOUT any
TNC, radio or live audio:

    fax_test_wetterkarte.wav   real reference weather chart
    fax_test_pattern.wav       synthetic geometry / resolution test pattern
    fax_test_text.wav          Lorem-Ipsum text page (Arial 16 pt)

Each file is a complete WEFAX transmission:

    [ APT start tone ] [ phasing lines ] [ image lines ] [ stop tone ] [ black ]

Dependencies: numpy + Pillow + the stdlib ``wave`` module. (No scipy, no Qt —
deliberately kept dependency-light so the tool runs in a bare venv.)

Usage:
    cd E:\\PK232\\pk232py_repo
    python tools/fax_wav_generator.py

------------------------------------------------------------------------------
LERNMODUS — the two non-obvious ideas in this file
------------------------------------------------------------------------------

1. PHASE ACCUMULATOR (continuous-phase FM / DDS)
   We do NOT build the signal by concatenating little sine snippets, one per
   pixel:  sin(2*pi*f1*t) ++ sin(2*pi*f2*t) ++ ...
   Each snippet starts its sine at phase 0, so at every pixel boundary the
   waveform jumps. Those discontinuities are audible clicks and — far worse —
   they put broadband energy into the spectrum that confuses an FM
   demodulator (it sees a phantom frequency spike at every join).

   Instead we build ONE instantaneous-frequency array f[n] for the whole
   transmission and integrate it once:

       phase[n] = 2*pi/fs * cumsum(f[0..n])      (the "accumulator")
       signal[n] = sin(phase[n])

   Because phase is the running integral of frequency, it is continuous by
   construction even though f[n] is a staircase — no clicks anywhere, not even
   between the framing tones and the image. This is exactly how a real
   FSK/FM modulator (a DDS chip) works.

2. PIXEL -> FREQUENCY MAPPING (white = HIGH tone)
   International WEFAX convention (the one decoders expect):
       black pixel (0)   -> 1500 Hz   (low tone)
       white pixel (255) -> 2300 Hz   (high tone)
   so:   f = F_BLACK + (pixel/255) * (F_WHITE - F_BLACK)

   GOTCHA: the original task text wrote this as
       f = white + (pixel/255)*(black - white)
   which actually maps pixel 0 -> 2300 and 255 -> 1500 (inverted!). That
   contradicts the task's own parenthetical ("pixel 0 = black = 1500 Hz") and
   the existing project encoder (fax_encoder_test.py). We implement the
   correct, decoder-compatible mapping below and keep the convention in one
   place (``pixel_to_freq``) so a FAXNEG/inverted test is a one-line change.
"""

from __future__ import annotations

import os
import sys
import wave
from pathlib import Path

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - clear guidance instead of a traceback
    sys.exit("Pillow is required: pip install Pillow")


# ===========================================================================
# PATH ANCHORS  — resolve data files relative to THIS SCRIPT, not the CWD
# ===========================================================================
# LERNMODUS: a plain "Wetterkarte.jpg" candidate is interpreted relative to the
# current working directory. That works when you launch from the repo root
# (`python tools/fax_wav_generator.py`) but silently fails when you `cd tools`
# first — the same relative name then points at tools/tools/... which does not
# exist, and the generator either falls back to the decoded PNG or aborts.
# Anchoring on __file__ makes the lookup independent of where you start from:
# the script always knows where it lives on disk, so the candidate list below
# resolves to the SAME absolute paths regardless of the CWD.
_SCRIPT_DIR = Path(__file__).resolve().parent      # .../pk232py_repo/tools
_REPO_ROOT  = _SCRIPT_DIR.parent                   # .../pk232py_repo


# ===========================================================================
# CONSTANTS  — every WEFAX / audio parameter lives here and is editable
# ===========================================================================

# --- Audio format ----------------------------------------------------------
SAMPLE_RATE   = 11025        # Hz. Nyquist 5512 Hz >> 2300 Hz tone -> plenty of
                             # headroom, and keeps the files compact. Set to
                             # 8000 / 16000 if a decoder insists on it.
BITS_PER_SAMPLE = 16         # 16-bit PCM
AMPLITUDE     = 0.8          # peak fraction of full scale (headroom vs clipping)

# --- WEFAX tone frequencies -------------------------------------------------
F_BLACK       = 1500.0       # Hz — black pixel  (low tone)
F_WHITE       = 2300.0       # Hz — white pixel  (high tone)
# Centre 1900 Hz, shift +/-400 Hz. (The PK-232 internally uses a 1.7 kHz /
# 1000 Hz wide-shift filter, but 1500/2300 Hz is the on-air WEFAX convention
# that file decoders expect — see module docstring.)

F_APT_START   = 300.0        # Hz — APT start keying rate for IOC 576
F_STOP        = 450.0        # Hz — WEFAX stop tone

# --- Timing -----------------------------------------------------------------
LPM           = 120          # lines per minute (FSPEED 2 = 2 lines/s)
T_LINE        = 60.0 / LPM   # seconds per image line -> 0.5 s at 120 LPM
T_APT_START   = 5.0          # s of APT start tone
N_PHASING_LINES = 20         # phasing lines (each T_LINE long)
T_STOP        = 5.0          # s of stop tone
T_TRAILING_BLACK = 2.0       # s of solid black after the stop tone

PHASING_BLACK_FRAC = 0.05    # narrow black sync pulse at the start of each
                             # phasing line; the rest of the line is white

# --- Image geometry ---------------------------------------------------------
IMG_WIDTH     = 1152         # pixels per line (~2 * IOC for IOC 576)
NUM_LINES     = 600          # image height in lines.
                             # 600 lines = 300 s of image at 120 LPM = full-spec
                             # WEFAX chart. Must be >= IMG_WIDTH//2 (the test
                             # pattern's circle diameter) or the circle gets
                             # clipped top/bottom. Set to 300 only for quick
                             # smoke tests where geometry fidelity is irrelevant.

# --- Text rendering (WAV 3) -------------------------------------------------
TEXT_DPI      = 96           # assumed display DPI for pt -> px conversion
FONT_PT       = 16           # Arial point size requested
# 16 pt @ 96 DPI = 16 * 96/72 = ~21 px
FONT_PX       = round(FONT_PT * TEXT_DPI / 72)

# Candidate Arial paths (first hit wins); metric-compatible fallbacks after.
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    # --- fallbacks (a WARNING is printed if one of these is used) ---
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]
_PREFERRED_FONTS = {"arial.ttf"}   # lower-cased basenames we treat as "Arial"

# --- Reference weather chart (WAV 1) ----------------------------------------
# The committed, copyright-free fixture is FIRST so T66 is reproducible for
# everyone: tools/synthetic_weatherchart.png is generated deterministically by
# make_synthetic_weatherchart.py (regenerate with `python
# tools/make_synthetic_weatherchart.py`). The real DWD chart
# (tools/Wetterkarte.jpg, © Deutscher Wetterdienst) is NOT in the repo for
# copyright reasons — it stays as a lower-priority local fallback, as does the
# decoded reference PNG and the Claude project-knowledge path.
# All in-repo candidates are anchored on _SCRIPT_DIR / _REPO_ROOT (absolute),
# so the lookup works whether you start from the repo root or from tools/.
WEATHER_IMAGE_CANDIDATES = [
    _SCRIPT_DIR / "synthetic_weatherchart.png",  # committed, copyright-free (T66)
    _SCRIPT_DIR / "Wetterkarte.jpg",         # real DWD chart, local only (gitignored)
    _REPO_ROOT  / "Wetterkarte.jpg",
    _REPO_ROOT  / "docs" / "Wetterkarte.jpg",
    _SCRIPT_DIR / "wetterkarte_decoded.png", # in-repo decoded reference chart
    _REPO_ROOT  / "wetterkarte_decoded.png",
    Path("/mnt/project/Wetterkarte.jpg"),    # Claude project-knowledge path
]

# Lorem Ipsum source text (WAV 3)
LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat. Duis aute irure dolor in reprehenderit in voluptate "
    "velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint "
    "occaecat cupidatat non proident, sunt in culpa qui officia deserunt "
    "mollit anim id est laborum."
)


# ===========================================================================
# FM ENCODER  — instantaneous-frequency arrays + one phase accumulator
# ===========================================================================

def pixel_to_freq(pixel: np.ndarray | int) -> np.ndarray | float:
    """Map grayscale value(s) 0..255 to WEFAX tone frequency in Hz.

    0   (black) -> F_BLACK (1500 Hz, low tone)
    255 (white) -> F_WHITE (2300 Hz, high tone)

    See module docstring (idea #2) for why white is the HIGH tone and why the
    task's inline formula was inverted.
    """
    return F_BLACK + (np.asarray(pixel, dtype=np.float64) / 255.0) * (F_WHITE - F_BLACK)


def _integrate(freq: np.ndarray) -> np.ndarray:
    """Turn an instantaneous-frequency array (Hz, per sample) into a
    phase-continuous, normalised float32 audio array in [-1, 1].

    This *is* the phase accumulator: phase = 2*pi/fs * running-sum(freq).
    cumsum guarantees continuity regardless of how the frequency jumps.
    """
    phase = (2.0 * np.pi / SAMPLE_RATE) * np.cumsum(freq.astype(np.float64))
    return np.sin(phase).astype(np.float32)


def _const_freq(freq_hz: float, seconds: float) -> np.ndarray:
    """A flat instantaneous-frequency segment of the given duration."""
    n = int(round(seconds * SAMPLE_RATE))
    return np.full(n, freq_hz, dtype=np.float64)


# --- Framing-tone frequency builders ---------------------------------------

def apt_start_freq() -> np.ndarray:
    """APT start: black/white keyed at F_APT_START (300 Hz) for T_APT_START s.

    A square wave that toggles between the black and white tones 300 times a
    second. A decoder's start-detector locks onto this 300 Hz keying rate.
    """
    n = int(round(T_APT_START * SAMPLE_RATE))
    # fractional phase of the 300 Hz keying square wave at each sample
    keying_phase = (np.arange(n) * F_APT_START / SAMPLE_RATE) % 1.0
    return np.where(keying_phase < 0.5, F_BLACK, F_WHITE).astype(np.float64)


def phasing_freq() -> np.ndarray:
    """Phasing lines: each T_LINE long, a narrow black pulse at the line start
    then white for the rest. Gives the decoder a repeating, unambiguous
    line-start marker so it can lock horizontal phase before the image."""
    n_line  = int(round(T_LINE * SAMPLE_RATE))
    n_black = max(1, int(round(n_line * PHASING_BLACK_FRAC)))
    one_line = np.concatenate([
        np.full(n_black,          F_BLACK, dtype=np.float64),
        np.full(n_line - n_black, F_WHITE, dtype=np.float64),
    ])
    return np.tile(one_line, N_PHASING_LINES)


def stop_freq() -> np.ndarray:
    """WEFAX stop tone (450 Hz) followed by trailing solid black."""
    return np.concatenate([
        _const_freq(F_STOP,  T_STOP),
        _const_freq(F_BLACK, T_TRAILING_BLACK),
    ])


def image_freq(img: np.ndarray) -> np.ndarray:
    """Instantaneous-frequency array for one image (uint8, shape (H, W)).

    Each line lasts T_LINE seconds; the W pixels of the line are spread evenly
    across that time. We compute the source (line, column) for *every* output
    sample by vectorised arithmetic — no Python loop over pixels.

    GOTCHA: T_LINE * fs = 5512.5 samples is non-integer at 120 LPM / 11025 Hz.
    Building from a fixed integer samples-per-line would drift by half a sample
    each line and slowly skew the image. We instead map global sample time
    -> fractional line position, so the line length self-corrects and the
    total length is exactly round(NUM_LINES * T_LINE * fs).
    """
    h, w = img.shape
    total = int(round(h * T_LINE * SAMPLE_RATE))
    samples_per_line = T_LINE * SAMPLE_RATE

    # global position in "line units": 0.0 .. h (fractional)
    pos        = np.arange(total, dtype=np.float64) / samples_per_line
    line_idx   = np.clip(pos.astype(np.int64), 0, h - 1)
    frac       = pos - np.floor(pos)                       # 0..1 within the line
    col_idx    = np.clip((frac * w).astype(np.int64), 0, w - 1)

    pixels = img[line_idx, col_idx]
    return pixel_to_freq(pixels)


def image_to_fax_signal(img: np.ndarray) -> np.ndarray:
    """Public convenience: encode an image (uint8 2-D array) to normalised
    float32 audio with the phase accumulator. Phase-continuous across all
    pixels and lines. (main() assembles the full transmission from the
    *frequency* builders above and integrates ONCE, so even the framing/image
    boundaries are click-free — see main().)"""
    return _integrate(image_freq(img))


# ===========================================================================
# TEST-IMAGE GENERATORS  — each returns uint8 ndarray, shape (NUM_LINES, IMG_WIDTH)
# ===========================================================================

def _fit_to_canvas(src: Image.Image) -> np.ndarray:
    """Scale a grayscale PIL image to IMG_WIDTH, then bring its height to
    NUM_LINES (shrink if taller, white-pad at the bottom if shorter)."""
    src = src.convert("L")
    w, h = src.size
    new_h = max(1, round(h * IMG_WIDTH / w))
    src = src.resize((IMG_WIDTH, new_h), Image.LANCZOS)

    if new_h == NUM_LINES:
        return np.asarray(src, dtype=np.uint8)
    if new_h > NUM_LINES:
        # squash to fit — keeps the whole chart visible for geometry checks
        src = src.resize((IMG_WIDTH, NUM_LINES), Image.LANCZOS)
        return np.asarray(src, dtype=np.uint8)
    # shorter than the canvas: pad below with white (255)
    canvas = np.full((NUM_LINES, IMG_WIDTH), 255, dtype=np.uint8)
    canvas[:new_h, :] = np.asarray(src, dtype=np.uint8)
    return canvas


def make_weather_image() -> np.ndarray:
    """WAV 1 source: the real reference weather chart from the repo/project.

    Candidates are absolute Paths anchored on the script location, so the
    first existing one wins regardless of the current working directory. On
    failure we list the ABSOLUTE paths we actually probed — the old message
    printed CWD-relative names, which were useless for diagnosing the very
    "launched from the wrong directory" problem this resolution scheme fixes.
    """
    searched = []
    for cand in WEATHER_IMAGE_CANDIDATES:
        cand = Path(cand)
        searched.append(str(cand))
        if cand.exists():
            print(f"  weather chart: using '{cand}'")
            return _fit_to_canvas(Image.open(cand))
    raise FileNotFoundError(
        "Reference weather chart not found. Searched these absolute paths:\n  - "
        + "\n  - ".join(searched)
        + "\nPlace a grayscale weather chart at one of these paths and retry."
    )


def make_pattern_image() -> np.ndarray:
    """WAV 2 source: synthetic geometry / resolution test pattern.

    Top third    : horizontal black lines on white, varying spacing.
    Middle band  : vertical black lines on white.
    Centre       : circle outline, diameter = 50% of width (576 px).
    Bottom third : horizontal bars of increasing thickness (1,2,4,8,16,32 px)
                   to expose IOC/ASPECT (vertical) distortion.
    """
    img = Image.new("L", (IMG_WIDTH, NUM_LINES), color=255)  # white background
    d = ImageDraw.Draw(img)
    third = NUM_LINES // 3

    # --- top third: horizontal lines, spacing grows left->right via gaps ----
    y = 4
    gap = 4
    while y < third - 2:
        d.line([(0, y), (IMG_WIDTH - 1, y)], fill=0, width=1)
        y += gap
        gap += 1                       # progressively wider spacing

    # --- middle band: vertical lines ---------------------------------------
    mid_top, mid_bot = third + 4, 2 * third - 4
    x = 4
    vgap = 6
    while x < IMG_WIDTH - 2:
        d.line([(x, mid_top), (x, mid_bot)], fill=0, width=1)
        x += vgap

    # --- centre: circle outline, diameter = 50% of width --------------------
    # Clamp to NUM_LINES so the circle is never clipped top/bottom and stays
    # round even on a short canvas. At NUM_LINES=600 this is the full 576 px.
    diameter = min(IMG_WIDTH // 2, NUM_LINES - 8)   # 8 px breathing room
    cx, cy = IMG_WIDTH // 2, NUM_LINES // 2
    r = diameter // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=2)

    # --- bottom third: bars of increasing thickness ------------------------
    y = 2 * third + 6
    for thickness in (1, 2, 4, 8, 16, 32):
        if y + thickness >= NUM_LINES:
            break
        d.rectangle([40, y, IMG_WIDTH - 40, y + thickness - 1], fill=0)
        y += thickness + 6             # bar + gap

    return np.asarray(img, dtype=np.uint8)


def _load_font():
    """Return (ImageFont, name_used, is_fallback)."""
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            base = os.path.basename(path).lower()
            is_fallback = base not in _PREFERRED_FONTS
            return ImageFont.truetype(path, FONT_PX), os.path.basename(path), is_fallback
    return ImageFont.load_default(), "PIL-default-bitmap", True


def _wrap(text: str, font, draw: ImageDraw.ImageDraw, max_w: int) -> list[str]:
    """Greedy word-wrap to pixel width using the font's real metrics."""
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_text_image() -> np.ndarray:
    """WAV 3 source: Lorem-Ipsum text page, black on white, Arial 16 pt."""
    font, name, is_fallback = _load_font()
    if is_fallback:
        print(f"  WARNING: Arial not found — using fallback font '{name}' "
              f"(metrics differ slightly from Arial).")
    else:
        print(f"  text font: '{name}' @ {FONT_PT}pt ({FONT_PX}px, {TEXT_DPI} DPI)")

    img = Image.new("L", (IMG_WIDTH, NUM_LINES), color=255)
    d = ImageDraw.Draw(img)
    margin = 24
    line_h = round(FONT_PX * 1.35)     # 1.35x leading

    # wrap a few paragraphs, repeat until the page is full
    wrapped = _wrap(LOREM, font, d, IMG_WIDTH - 2 * margin)
    y = margin
    para = 0
    while y < NUM_LINES - line_h:
        for ln in wrapped:
            if y >= NUM_LINES - line_h:
                break
            d.text((margin, y), ln, fill=0, font=font)
            y += line_h
        y += line_h // 2               # blank line between paragraphs
        para += 1
        if para > 50:                  # safety stop
            break

    return np.asarray(img, dtype=np.uint8)


# ===========================================================================
# WAV OUTPUT
# ===========================================================================

def write_wav(path: Path, signal: np.ndarray, sample_rate: int) -> None:
    """Write a normalised float32 signal in [-1, 1] as 16-bit PCM mono WAV,
    scaled to AMPLITUDE of full scale."""
    peak = float(np.max(np.abs(signal))) or 1.0
    scaled = signal / peak * AMPLITUDE          # normalise then apply headroom
    pcm = np.clip(scaled * 32767.0, -32768, 32767).astype("<i2")  # little-endian int16

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(BITS_PER_SAMPLE // 8)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


# ===========================================================================
# ASSEMBLY + SANITY CHECK + MAIN
# ===========================================================================

def build_transmission(img: np.ndarray) -> np.ndarray:
    """Assemble a full WEFAX transmission as ONE phase-continuous signal.

    We concatenate the instantaneous-FREQUENCY arrays of every section and
    integrate exactly once. That single cumsum means there is no phase jump
    even at the start/phasing/image/stop boundaries — the whole file is
    click-free.
    """
    full_freq = np.concatenate([
        apt_start_freq(),     # 1. APT start tone
        phasing_freq(),       # 2. phasing lines
        image_freq(img),      # 3. image
        stop_freq(),          # 4. stop tone + trailing black
    ])
    return _integrate(full_freq)


def _dominant_freq(signal: np.ndarray, fs: int) -> float:
    """Crude dominant-frequency estimate of a slice via FFT magnitude peak."""
    n = len(signal)
    if n < 2:
        return 0.0
    win = signal * np.hanning(n)
    spec = np.abs(np.fft.rfft(win))
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    return float(freqs[int(np.argmax(spec))])


def sanity_check(label: str, signal: np.ndarray, fs: int) -> None:
    """Print duration, sample count, amplitude range and a rough dominant
    frequency taken from a slice inside the image region."""
    dur = len(signal) / fs
    # a 0.25 s slice well inside the IMAGE region (past start tone + phasing),
    # so the dominant frequency reflects actual picture content
    img_start_s = T_APT_START + N_PHASING_LINES * T_LINE + 5.0
    s0 = int(img_start_s * fs)
    s1 = min(len(signal), s0 + int(0.25 * fs))
    dom = _dominant_freq(signal[s0:s1], fs) if s1 > s0 else 0.0
    print(f"  [{label}] duration={dur:6.1f}s  samples={len(signal):,}  "
          f"min/max={signal.min():+.3f}/{signal.max():+.3f}  "
          f"dom~{dom:5.0f}Hz (band {F_BLACK:.0f}-{F_WHITE:.0f}Hz)")


def main() -> int:
    out_dir = Path.cwd()
    jobs = [
        ("fax_test_wetterkarte.wav", "weather", make_weather_image),
        ("fax_test_pattern.wav",     "pattern", make_pattern_image),
        ("fax_test_text.wav",        "text",    make_text_image),
    ]

    print(f"WEFAX test-WAV generator — {LPM} LPM, IOC 576, {IMG_WIDTH}px/line, "
          f"{NUM_LINES} lines, {SAMPLE_RATE} Hz\n")

    for filename, label, make_image in jobs:
        print(f"* {filename}")
        try:
            img = make_image()
        except FileNotFoundError as exc:
            print(f"  ERROR: {exc}")
            return 2
        signal = build_transmission(img)
        path = out_dir / filename
        write_wav(path, signal, SAMPLE_RATE)
        size_mb = path.stat().st_size / (1024 * 1024)
        sanity_check(label, signal, SAMPLE_RATE)
        print(f"  wrote {path}  ({size_mb:.2f} MB)\n")

    print("Done. Feed a WAV into the decoder:")
    print("  - GUI:  python fax_decoder_test.py  ->  'Open WAV'  -> pick the file")
    print("  - or play it into the PK232PY FAX screen via an audio loopback "
          "(VB-CABLE / 'Stereo Mix') routed to the TNC/soundcard input.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

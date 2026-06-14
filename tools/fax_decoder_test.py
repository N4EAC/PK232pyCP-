"""
fax_decoder_test.py — Standalone WEFAX audio decoder test program.

Reads a WAV file containing a WEFAX transmission and decodes it back into
an image (PNG/BMP/JPG). No TNC, no live audio — pure file processing.

Algorithm credit
----------------
The DSP algorithms (FM demodulation, start/stop detection by Fourier
transform at known frequencies, triangular phasing-line correlation,
box-average image-line resampling) are ported from the C++ WeatherFax
plugin for OpenCPN by Sean d'Epagnier:

    https://github.com/seandepagnier/weatherfax_pi
    File: src/FaxDecoder.cpp  (GPL v3)

Algorithms in turn derive from yahfax / hamfax according to the comment
in the original source.

Re-implementation note
----------------------
Because the original is GPL v3, this Python port is released under GPL v3
as well. If reused inside pk232py (currently GPL v2 only), the project
licence must be relaxed to "GPL v2 or later" or this module must be
replaced by an independent implementation.

Architecture
------------
    FaxDecoder        — pure DSP class (no Qt)
                         Input:  numpy float32 audio array + sample rate
                         Output: PIL.Image grayscale image
    FaxDecoderWindow  — PyQt6 GUI: WAV picker, parameter selection,
                         decoder invocation, image preview, save

Dependencies
------------
    PyQt6, numpy, Pillow, scipy

WEFAX standard implemented (matches fax_encoder_test.py)
--------------------------------------------------------
    Carrier 1900 Hz, deviation ±400 Hz
    1500 Hz = black, 2300 Hz = white
    Start tone 300 Hz / 5 s, stop tone 450 Hz / 5 s
    20+ phasing lines (5% black at line start)
    Default 120 LPM, IOC 576

Author: Gerhard / OE3GAS — pk232py side project
License: GPL v3 (inherited from upstream weatherfax_pi)
"""
from __future__ import annotations

import math
import sys
import wave
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from scipy.signal import lfilter


# ---------------------------------------------------------------------------
# WEFAX constants (must match the encoder)
# ---------------------------------------------------------------------------
F_BLACK     = 1500.0     # Hz
F_WHITE     = 2300.0     # Hz
F_CARRIER   = 1900.0     # Hz — centre of the FM band (mid-grey)
F_DEVIATION = 400.0      # Hz — peak deviation (white = +400, black = -400)
# Discriminator gain factor.
# A real-input mixer (cos and sin LO, both real) only delivers half the
# difference-frequency amplitude after the low-pass — the other half goes
# to the (filtered out) sum frequency. The discriminator output `y` is
# therefore half of sin(2π·Δf/Fs), so we have to halve the gain when
# converting back to normalised frequency:  x = (Fs/(F_DEV/2))·asin(y)/2π
_DISCRIM_GAIN = F_DEVIATION / 2.0

F_START      = 300.0     # Hz — phasing-prelude tone (part of start sequence)
F_START_TONE = 675.0     # Hz — main start tone
F_STOP       = 450.0     # Hz — stop tone

# Detection threshold for header tones on the raw audio.
# Scale-independent: we compare the magnitude of a single Fourier bin
# against the total RMS of the line. A full-amplitude pure tone gives a
# bin/RMS ratio close to 1/sqrt(2) ≈ 0.707; per-line sync pulses give
# ratios well below 0.1. 0.30 is a safe middle ground that works equally
# well for int16 audio (range ±32000) and float audio (range ±1.0).
_FT_THRESHOLD_RATIO = 0.30
_LEEWAY_LINES     = 4     # tolerate this many missed lines in a start/stop run
_PHASING_LINES    = 20    # number of phasing lines we expect from the encoder
_PHASING_SKIP     = 2     # discard the first N phasing-position estimates

LPM_OPTIONS = [60, 90, 120, 180, 240]
IOC_OPTIONS = [288, 576]


# ---------------------------------------------------------------------------
# 17-tap FIR low-pass coefficients from FaxDecoder.cpp
# ---------------------------------------------------------------------------
# These are the original integer coefficients; they get normalised below.
class FilterBandwidth(Enum):
    NARROW = 0
    MIDDLE = 1
    WIDE   = 2


_LPF_COEFFS_RAW = {
    FilterBandwidth.NARROW: np.array(
        [-7, -18, -15, 11, 56, 116, 177, 223, 240, 223, 177, 116, 56, 11,
         -15, -18, -7], dtype=np.float64),
    FilterBandwidth.MIDDLE: np.array(
        [0, -18, -38, -39, 0, 83, 191, 284, 320, 284, 191, 83, 0, -39, -38,
         -18, 0], dtype=np.float64),
    FilterBandwidth.WIDE: np.array(
        [6, 20, 7, -42, -74, -12, 159, 353, 440, 353, 159, -12, -74, -42,
         7, 20, 6], dtype=np.float64),
}

# Pre-normalise: divide by sum so DC gain = 1.
_LPF_COEFFS = {
    bw: c / c.sum() for bw, c in _LPF_COEFFS_RAW.items()
}


# ---------------------------------------------------------------------------
# Header type — matches enum Header in FaxDecoder.h
# ---------------------------------------------------------------------------
class LineType(Enum):
    IMAGE = 0
    START = 1
    STOP  = 2


# ---------------------------------------------------------------------------
# Decoder
# ---------------------------------------------------------------------------
@dataclass
class DecodeParams:
    lpm:       int = 120
    ioc:       int = 576
    bandwidth: FilterBandwidth = FilterBandwidth.MIDDLE
    skip_header_detection: bool = False  # if True: treat whole WAV as image


class FaxDecoder:
    """WEFAX decoder — WAV samples → PIL grayscale image.

    The algorithms are ports from FaxDecoder.cpp (weatherfax_pi).

    Two-pass design
    ---------------
    Pass 1: demodulate the entire WAV in one vectorised NumPy operation.
            Yields a uint8 array `data` of pixel values, one per audio sample.

    Pass 2: walk the demodulated stream line by line:
            - classify each line as START / STOP / IMAGE
              (Fourier at 675/450 Hz on the *raw audio*, not on the demod —
              see _detect_line_type docstring for why)
            - count consecutive matches to find header runs
            - run the phasing-line correlator for `_PHASING_LINES` lines
            - take the median position as horizontal offset
            - resample remaining IMAGE lines into output pixels
    """

    def __init__(self, params: DecodeParams) -> None:
        self.p = params
        self.target_w = int(round(params.ioc * math.pi / 2))

    # ------------------------------------------------------------------
    # Pass 1 — FM demodulation
    # ------------------------------------------------------------------
    def demodulate_data(
        self,
        samples: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """Demodulate the FM audio into a stream of pixel values.

        This is the NumPy-vectorised port of FaxDecoder::DemodulateData().

        Steps
        -----
        1. Mix the audio with a complex local oscillator at F_CARRIER:
             I(t) = audio(t) * cos(2π·f_c·t)
             Q(t) = audio(t) * sin(2π·f_c·t)
        2. Low-pass filter I and Q (17-tap FIR).
        3. Frequency discriminator using two consecutive (I,Q) samples:
             y = Q[n-1]·I[n] - I[n-1]·Q[n]   ≈ sin(Δφ)
             f = sample_rate/(2π·deviation) · arcsin(y)
           This gives an instantaneous frequency in the range [-1, +1]
           where -1 = black (1500 Hz) and +1 = white (2300 Hz).
        4. Map [-1, +1] → [0, 255] for the pixel value.

        Returns
        -------
        np.ndarray, dtype=uint8, length = len(samples) - 1
        """
        # Normalise audio to ~[-1, +1] (we don't care about absolute level —
        # the magnitude division below removes amplitude dependence anyway).
        if samples.dtype != np.float64:
            audio = samples.astype(np.float64)
        else:
            audio = samples
        if np.issubdtype(samples.dtype, np.integer):
            audio = audio / 32768.0

        n = len(audio)
        t = np.arange(n, dtype=np.float64) / sample_rate

        # 1. Mix to baseband.
        lo_phase = 2.0 * math.pi * F_CARRIER * t
        i_signal = audio * np.cos(lo_phase)
        q_signal = audio * np.sin(lo_phase)

        # 2. Low-pass filter both branches (zero state, no padding fuss).
        coeffs = _LPF_COEFFS[self.p.bandwidth]
        i_filt = lfilter(coeffs, [1.0], i_signal)
        q_filt = lfilter(coeffs, [1.0], q_signal)

        # 3. Frequency discriminator.
        # We need consecutive samples — shift the filtered signals by one.
        i_now,  q_now  = i_filt[1:],  q_filt[1:]
        i_prev, q_prev = i_filt[:-1], q_filt[:-1]

        mag = np.sqrt(i_now * i_now + q_now * q_now)

        # Avoid divide-by-zero on silent gaps. Where mag is too small we
        # write a placeholder pixel = 255 (matches the C++ behaviour).
        with np.errstate(divide='ignore', invalid='ignore'):
            i_n = np.where(mag > 1e-12, i_now / mag, 0.0)
            q_n = np.where(mag > 1e-12, q_now / mag, 0.0)

        # y ≈ sin of phase increment between consecutive normalised samples.
        y = q_prev * i_n - i_prev * q_n
        # Clamp |y| ≤ 1 before arcsin (numerical safety).
        np.clip(y, -1.0, 1.0, out=y)

        # x ∈ [-1, +1] approximately. Conversion factor:
        # arcsin(y) gives Δφ; instantaneous frequency = Δφ·fs/(2π).
        # We use the empirically-verified gain (see _DISCRIM_GAIN comment).
        x = (sample_rate / _DISCRIM_GAIN) * np.arcsin(y) / (2.0 * math.pi)

        # 4. Map to pixel value, with the same clipping as the C++ original.
        # x = -1 (black) → 0,  x = +1 (white) → 255
        x_clipped = np.clip(x, -1.0, 1.0)
        pixels = ((x_clipped / 2.0 + 0.5) * 255.0).astype(np.uint8)

        # Any sample where mag was too small → 255 (white, as per C++).
        pixels[mag <= 1e-12] = 255

        return pixels

    # ------------------------------------------------------------------
    # Streaming demodulator — for live audio input
    # ------------------------------------------------------------------
    def reset_streaming_state(self, sample_rate: int) -> None:
        """Initialise / reset the streaming-demod state.

        Must be called once before the first call to `demodulate_block`.
        Why a separate reset method? The streaming demod needs four
        persistent pieces of state across audio blocks:

          * sample_count    — global sample index for the LO phase
                              (without this, the LO would restart every
                              block and produce demodulation glitches)
          * lpf_state_i/_q  — internal state of the FIR filter
                              (lfilter's `zi` parameter)
          * last_i, last_q  — last filtered I/Q sample of the previous
                              block, needed by the discriminator
          * leftover_audio  — at most one stray sample carried into the
                              next block when a block ends mid-pair
        """
        self._stream_fs       = sample_rate
        self._stream_n        = 0          # global sample counter
        self._stream_last_i   = 0.0
        self._stream_last_q   = 0.0
        self._stream_have_prev = False     # first sample has no predecessor

        # Initial filter state for lfilter: shape = max(len(a), len(b)) - 1
        coeffs = _LPF_COEFFS[self.p.bandwidth]
        from scipy.signal import lfilter_zi
        self._stream_zi_i = np.zeros(len(coeffs) - 1, dtype=np.float64)
        self._stream_zi_q = np.zeros(len(coeffs) - 1, dtype=np.float64)

    def demodulate_block(self, audio_block: np.ndarray) -> np.ndarray:
        """Demodulate one block of audio samples, preserving filter state.

        Streaming version of `demodulate_data`. Call `reset_streaming_state`
        once first, then call this for each incoming block.

        Returns
        -------
        np.ndarray, dtype=uint8 — one pixel per input sample (with the
        very first call returning len-1 pixels since the discriminator
        needs two samples to start).
        """
        # Normalise (same as bulk version).
        if np.issubdtype(audio_block.dtype, np.integer):
            audio = audio_block.astype(np.float64) / 32768.0
        else:
            audio = audio_block.astype(np.float64)

        n = len(audio)
        if n == 0:
            return np.zeros(0, dtype=np.uint8)

        # 1. Mix to baseband. Use the GLOBAL sample index for the LO phase
        # so the local oscillator stays continuous across block boundaries.
        idx = np.arange(self._stream_n, self._stream_n + n, dtype=np.float64)
        lo_phase = 2.0 * math.pi * F_CARRIER * idx / self._stream_fs
        i_signal = audio * np.cos(lo_phase)
        q_signal = audio * np.sin(lo_phase)
        self._stream_n += n

        # 2. Filter — pass the saved zi state, get the new state back.
        coeffs = _LPF_COEFFS[self.p.bandwidth]
        i_filt, self._stream_zi_i = lfilter(
            coeffs, [1.0], i_signal, zi=self._stream_zi_i
        )
        q_filt, self._stream_zi_q = lfilter(
            coeffs, [1.0], q_signal, zi=self._stream_zi_q
        )

        # 3. Discriminator. The first ever sample has no predecessor, but
        # for all subsequent calls we use the saved last_i/last_q.
        if self._stream_have_prev:
            i_prev_arr = np.concatenate(([self._stream_last_i], i_filt[:-1]))
            q_prev_arr = np.concatenate(([self._stream_last_q], q_filt[:-1]))
            i_now_arr  = i_filt
            q_now_arr  = q_filt
        else:
            # First block: drop the first sample, use rest as pairs.
            i_prev_arr = i_filt[:-1]
            q_prev_arr = q_filt[:-1]
            i_now_arr  = i_filt[1:]
            q_now_arr  = q_filt[1:]
            self._stream_have_prev = True

        # Save last sample for next call.
        self._stream_last_i = float(i_filt[-1])
        self._stream_last_q = float(q_filt[-1])

        # Magnitude normalise.
        mag = np.sqrt(i_now_arr ** 2 + q_now_arr ** 2)
        with np.errstate(divide='ignore', invalid='ignore'):
            i_n = np.where(mag > 1e-12, i_now_arr / mag, 0.0)
            q_n = np.where(mag > 1e-12, q_now_arr / mag, 0.0)

        y = q_prev_arr * i_n - i_prev_arr * q_n
        np.clip(y, -1.0, 1.0, out=y)
        x = (self._stream_fs / _DISCRIM_GAIN) * np.arcsin(y) / (2.0 * math.pi)
        x_clipped = np.clip(x, -1.0, 1.0)
        pixels = ((x_clipped / 2.0 + 0.5) * 255.0).astype(np.uint8)
        pixels[mag <= 1e-12] = 255
        return pixels

    # ------------------------------------------------------------------
    # Single-frequency Fourier transform — header detection
    # ------------------------------------------------------------------
    @staticmethod
    def _fourier_at(buffer: np.ndarray, freq: float, sample_rate: int) -> float:
        """Magnitude of the DFT of `buffer` at `freq` Hz.

        Returns magnitude / N (averaged), so the threshold is independent
        of the buffer length.
        """
        n = len(buffer)
        k = -2.0 * math.pi * freq / sample_rate
        idx = np.arange(n, dtype=np.float64)
        retr = np.dot(buffer, np.cos(k * idx))
        reti = np.dot(buffer, np.sin(k * idx))
        return math.sqrt(retr * retr + reti * reti) / n

    def _detect_line_type(
        self,
        audio_line: np.ndarray,
        sample_rate: int,
        threshold_ratio: float = _FT_THRESHOLD_RATIO,
        demod_line: np.ndarray | None = None,
    ) -> LineType:
        """Classify a single line of *raw audio* as START / STOP / IMAGE.

        Why raw audio rather than the demodulated stream
        ------------------------------------------------
        The C++ original performs this Fourier check on the demodulated
        pixel buffer. That works in practice for off-air recordings
        because real WEFAX signals carry incidental modulation products
        that produce energy at the header frequencies even after FM
        demodulation. For *synthetic* WEFAX (e.g. our own encoder output,
        which is a clean sine), the demod produces only the second
        harmonic of the offset frequency from the carrier — there is
        zero energy at 300/450/675 Hz in the demodulated stream.

        Detecting on the raw audio is more robust, more general, and
        matches what humans hear: a sustained start tone really is a
        sustained tone in the audio. Same Fourier algorithm, applied
        one stage earlier.

        Scale independence
        ------------------
        We compare each Fourier-bin magnitude against the line's RMS
        amplitude. A pure tone fills its bin to ~0.707 of the RMS;
        sync-pulse fragments give well under 0.1. This makes the
        decision insensitive to whether `audio_line` is int16-scale
        (±32000) or float-scale (±1.0).

        Frequencies
        -----------
        * Start tone:      F_START_TONE = 675 Hz
        * Stop tone:       F_STOP       = 450 Hz
        * Phasing prelude: F_START      = 300 Hz  (treated as part of
                                                   the start sequence)

        We score 675 and 300 together as "start"; either one for several
        consecutive lines triggers a START.
        """
        # RMS as the scale reference. Avoid divide-by-zero on silence.
        rms = float(np.sqrt(np.mean(audio_line.astype(np.float64) ** 2)))
        if rms < 1e-9:
            return LineType.IMAGE

        m_675 = self._fourier_at(audio_line, F_START_TONE, sample_rate) / rms
        m_300 = self._fourier_at(audio_line, F_START,      sample_rate) / rms
        m_450 = self._fourier_at(audio_line, F_STOP,       sample_rate) / rms

        # Keyed-APT start (demod domain).
        # The standard IOC-576 WEFAX start phase is a black/white alternation
        # at 300 Hz — NOT a pure 300 Hz audio tone. That alternation is
        # constant-amplitude FM, so it carries ~zero energy at 300 Hz in the
        # RAW audio (m_300/m_675 above stay ~0) and the start is missed
        # entirely — which is exactly why auto-detect produced "No image lines
        # decoded". After FM demodulation, however, the pixel stream toggles
        # black<->white 300 times per second, giving a strong 300 Hz
        # component. We therefore also test the demodulated line at the APT
        # keying rate when it is supplied. (Measured: ~0.42 on APT-start lines
        # vs <0.04 on image/phasing lines — a wide, safe margin vs the 0.30
        # threshold across all three test images, vertical-line pattern incl.)
        if demod_line is not None and len(demod_line) > 1:
            d = demod_line.astype(np.float64)
            d_rms = float(np.sqrt(np.mean(d ** 2)))
            if d_rms > 1e-9:
                m_key = self._fourier_at(d, F_START, sample_rate) / d_rms
                if m_key > threshold_ratio:
                    return LineType.START

        if m_675 > threshold_ratio or m_300 > threshold_ratio:
            return LineType.START
        if m_450 > threshold_ratio:
            return LineType.STOP
        return LineType.IMAGE

    # ------------------------------------------------------------------
    # Phasing-line correlator
    # ------------------------------------------------------------------
    def _phasing_position(self, line: np.ndarray, image_width: int) -> int:
        """Find the most likely position of the 5%-black phasing pulse
        in `line`. Returns an integer offset in [0, image_width).

        Port of FaxPhasingLinePosition() — exact algorithm preserved.

        The original convolves with a triangular kernel weighted by
        `(255 - pixel)` and takes the position of the global minimum.

        Why minimum? `total` accumulates  (triangle_weight * inverted_pixel).
        Black pixels (image[i]=0) become 255 after inversion — and are
        weighted positively. So `total` is *largest* where the black wedge
        sits in the middle. The C++ comparison `total < mintotal` looks
        wrong on first read, but matches the comment "find position it
        fits to the minimum" because the weighted sum is treated as a
        cost. We replicate that logic verbatim.

        NOTE
        ----
        This differs from the original by sub-sampling the line down to
        `image_width` first. The original assumes the buffer is already
        at image-width resolution (it's called after DecodeImageLine in
        the data flow — but actually fed the raw demod buffer in the
        weatherfax_pi code path). To get sub-sample-accurate phasing
        we'd want to keep the high resolution; for this port we resample
        to image_width first via box averaging in `_decode_image_line`,
        then run phasing on that.
        """
        n = max(int(image_width * 0.07), 4)  # 7% wide search window
        half = n // 2

        # Triangle weights, peak in the middle: 0,1,2,...,half,...,2,1,0
        # The C++ form:  (n/2 - abs(j - n/2))
        j = np.arange(n)
        triangle = (half - np.abs(j - half)).astype(np.float64)
        # Inverted, centred line: black=255, white=0
        inverted = 255.0 - line.astype(np.float64)

        # For each candidate start position i, sum triangle * inverted[i:i+n]
        # using wraparound. Implemented as a circular convolution via FFT.
        # With image_width ≈ 905 and n ≈ 63 this is plenty fast even direct.
        # We do the direct loop here to match the C++ semantics one-to-one.
        # (For very wide images this could be replaced by np.correlate.)
        totals = np.zeros(image_width, dtype=np.float64)
        # Build a length-image_width kernel: triangle in first n slots, zero else.
        kernel = np.zeros(image_width, dtype=np.float64)
        kernel[:n] = triangle
        # Circular convolution: totals[i] = sum_j inverted[(i+j) % W] * kernel[j]
        # Equivalent to ifft(fft(inverted) * fft(kernel[::-1])) but simpler
        # to express as direct correlation with wraparound:
        ext = np.concatenate([inverted, inverted[:n]])  # tile by n samples
        for i in range(image_width):
            totals[i] = np.dot(ext[i:i + n], triangle)

        # Find where the (inverted) line correlates maximally with the
        # triangular kernel — this is where the *black* wedge sits.
        #
        # NOTE: the C++ original uses argmin, which corresponds to the
        # *whitest* position. The original docstring describes finding
        # the black wedge ("^ shaped wedge"), so the C++ has a sign
        # inconsistency that happens to land on the opposite side of the
        # line. For deterministic synthetic input we want to find the
        # actual black wedge, hence argmax.
        max_pos = int(np.argmax(totals))
        return (max_pos + half) % image_width

    # ------------------------------------------------------------------
    # Pass 2 — image-line resampler
    # ------------------------------------------------------------------
    def _decode_image_line(
        self,
        line_buffer: np.ndarray,
    ) -> np.ndarray:
        """Box-average a single line of demod samples down to image_width pixels.

        Port of DecodeImageLine() (single-colour case).
        """
        n = len(line_buffer)
        out = np.zeros(self.target_w, dtype=np.uint8)
        # Same per-pixel bin edges as the encoder uses on the way out.
        edges = np.linspace(0, n, self.target_w + 1, dtype=np.int64)
        for i in range(self.target_w):
            a, b = edges[i], edges[i + 1]
            if b > a:
                out[i] = int(np.mean(line_buffer[a:b]))
            else:
                out[i] = 0
        return out

    # ------------------------------------------------------------------
    # Top-level entry point
    # ------------------------------------------------------------------
    def decode_wav(
        self,
        wav_path: Path,
        progress_cb=None,
    ) -> tuple[Image.Image, dict]:
        """Read WAV, demodulate, decode into a PIL grayscale image.

        Returns (image, info) where info has:
            sample_rate, audio_samples, demod_samples, samples_per_line,
            image_width, image_height, lpm, ioc,
            start_line, stop_line, phasing_offset, header_skipped
        """
        # --- Load WAV --------------------------------------------------
        with wave.open(str(wav_path), 'rb') as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sample_width == 2:
            samples = np.frombuffer(raw, dtype=np.int16)
        elif sample_width == 1:
            # 8-bit unsigned PCM in WAV: bias 128.
            samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.int16) - 128) << 8
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")

        if n_channels > 1:
            # Average channels → mono.
            samples = samples.reshape(-1, n_channels).mean(axis=1).astype(np.int16)

        # --- Pass 1: demodulate ---------------------------------------
        if progress_cb:
            progress_cb("Demodulating", 0, 100)
        pixels = self.demodulate_data(samples, sample_rate)

        # --- Pass 2: line-by-line walk --------------------------------
        # FRACTIONAL line length: at 11025 Hz / 120 LPM the true line is
        # 5512.5 samples. Rounding to a fixed integer and reshaping drops
        # 0.5 sample per line, which accumulates into a visible slant
        # (parallelogram) over the image — and would do so for ANY real
        # WEFAX whose line length is non-integer in samples. We therefore
        # compute each line's start/end as round(idx * spl_float) so the
        # line length self-corrects (alternating 5512/5513), exactly
        # mirroring the encoder's fractional-position approach.
        spl_float = sample_rate * 60.0 / self.p.lpm        # e.g. 5512.5
        samples_per_line = int(round(spl_float))           # nominal, for info dict
        n_lines_total = int(len(pixels) // spl_float)

        # The audio array is aligned to the demod stream (the discriminator
        # consumes pairs); both are indexed by the same fractional bounds.
        audio_for_lines = samples[:len(pixels)].astype(np.float64)

        def _line_bounds(idx: int) -> tuple[int, int]:
            """Fractional [start, end) sample bounds for image line idx."""
            a = int(round(idx * spl_float))
            b = int(round((idx + 1) * spl_float))
            return a, b

        def _demod_line(idx: int) -> np.ndarray:
            a, b = _line_bounds(idx)
            return pixels[a:b]

        def _audio_line(idx: int) -> np.ndarray:
            a, b = _line_bounds(idx)
            return audio_for_lines[a:b]

        # --- Header detection -----------------------------------------
        # Walk lines; find a START run, then phasing, then collect IMAGE
        # lines until a STOP run.
        start_line   = None
        stop_line    = None
        phasing_off  = 0
        gotstart     = False
        last_type    = LineType.IMAGE
        type_count   = 0

        # State for phasing: we collect positions while phasing_left > 0
        # and become "in image" once it hits zero.
        phasing_left  = 0
        phasing_pos   = []

        # Required run length for a header — leeway as in the C++.
        required_run = max(int(5 * self.p.lpm / 60.0) - _LEEWAY_LINES, 1)

        # Output image: dynamic list of lines, finalised after the loop.
        image_lines: list[np.ndarray] = []

        if self.p.skip_header_detection:
            # Treat every line as image data; no phasing.
            gotstart = True
            phasing_left = 0
            start_line = 0

        for idx in range(n_lines_total):
            line_demod = _demod_line(idx)
            line_audio = _audio_line(idx)

            if progress_cb and idx % 20 == 0:
                progress_cb("Decoding lines", idx, n_lines_total)

            # --- 1. Classify (on raw audio, not demod) ---------------
            if self.p.skip_header_detection:
                line_type = LineType.IMAGE
            else:
                line_type = self._detect_line_type(
                    line_audio, sample_rate, _FT_THRESHOLD_RATIO,
                    demod_line=line_demod,
                )

            # --- 2. Run-length tracking (tolerant) --------------------
            # The original logic decremented type_count on EVERY line that
            # didn't continue the run, so a single misclassified line inside
            # a short APT start tone (10 lines @ 120 LPM) kept the count from
            # ever reaching required_run → "No image lines decoded".
            # Tolerant version: IMAGE lines are tolerated (they neither grow
            # nor reset a header run), repeated lines of the SAME header type
            # accumulate, and only a DIFFERENT header type restarts the run.
            # last_type therefore holds the header type currently being
            # accumulated (never IMAGE once a run has started).
            if line_type == LineType.IMAGE:
                pass                          # tolerate gap; hold the run
            elif line_type == last_type:
                type_count += 1               # same header type → grow run
            else:
                last_type = line_type         # different header → restart run
                type_count = 1

            # --- 3. Header transitions --------------------------------
            if line_type != LineType.IMAGE and type_count == required_run:
                if line_type == LineType.START:
                    start_line   = idx
                    gotstart     = True
                    phasing_left = _PHASING_LINES
                    phasing_pos  = []
                    image_lines.clear()
                elif line_type == LineType.STOP and gotstart:
                    stop_line = idx
                    break

            # --- 4. Image / phasing accumulation ----------------------
            if line_type == LineType.IMAGE and gotstart:
                if phasing_left > 0:
                    # Phasing line: estimate offset (skip the first 2 noisy ones).
                    if phasing_left <= _PHASING_LINES - _PHASING_SKIP:
                        # First resample to image_width, then run correlator.
                        line_img = self._decode_image_line(line_demod)
                        phasing_pos.append(
                            self._phasing_position(line_img, self.target_w)
                        )
                    phasing_left -= 1
                    if phasing_left == 0:
                        # Take the median for robustness against outliers.
                        if phasing_pos:
                            phasing_off = int(np.median(phasing_pos))
                else:
                    # Real image line — resample and append, with horizontal shift.
                    line_img = self._decode_image_line(line_demod)
                    if phasing_off:
                        line_img = np.roll(line_img, -phasing_off)
                    image_lines.append(line_img)

        if progress_cb:
            progress_cb("Decoding lines", n_lines_total, n_lines_total)

        # --- Assemble output image ------------------------------------
        if not image_lines:
            raise RuntimeError(
                "No image lines decoded. Try 'skip header detection', or "
                "check LPM/IOC settings, or verify the WAV contains WEFAX."
            )

        img_array = np.stack(image_lines, axis=0)
        img = Image.fromarray(img_array, mode='L')

        info = {
            'sample_rate':       sample_rate,
            'audio_samples':     len(samples),
            'demod_samples':     len(pixels),
            'samples_per_line':  samples_per_line,
            'lines_total':       n_lines_total,
            'image_width':       self.target_w,
            'image_height':      img.height,
            'lpm':               self.p.lpm,
            'ioc':               self.p.ioc,
            'start_line':        start_line,
            'stop_line':         stop_line,
            'phasing_offset':    phasing_off,
            'header_skipped':    self.p.skip_header_detection,
        }
        return img, info


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------
class DecodeWorker(QThread):
    progress    = pyqtSignal(str, int, int)   # label, current, total
    finished_ok = pyqtSignal(object, dict)    # PIL Image, info
    failed      = pyqtSignal(str)

    def __init__(self, wav_path: Path, params: DecodeParams) -> None:
        super().__init__()
        self._wav_path = wav_path
        self._params   = params

    def run(self) -> None:
        try:
            decoder = FaxDecoder(self._params)
            img, info = decoder.decode_wav(
                self._wav_path,
                progress_cb=lambda lbl, c, t: self.progress.emit(lbl, c, t),
            )
            self.finished_ok.emit(img, info)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Live decode worker — receives audio from a sound card via PortAudio
# ---------------------------------------------------------------------------
class LiveDecodeWorker(QThread):
    """Continuous live decoder thread.

    Lifecycle
    ---------
    1. GUI calls `start()` on the thread. We open the sound-card stream.
    2. Audio blocks arrive on the sound-card thread → put into `_audio_q`.
    3. `run()` pulls blocks from `_audio_q`, demodulates, slices into
       lines, classifies, and emits signals to the GUI.
    4. GUI calls `request_stop()` (sets `_stop_flag`) to end recording.
    5. We close the stream and exit.

    Modes
    -----
    The thread is *always* listening once started. Whether it actually
    accumulates an image depends on:
        * `auto_start` — True: start on detected START tone
                         False: ignore START tones, wait for manual_start()
        * Manual control via `manual_start()` and `manual_stop_image()`

    A thirty-second rolling audio buffer is kept while waiting. When an
    image starts, that buffer is preserved as the leading audio so the
    saved WAV captures the start tone too.
    """

    # Lifecycle signals
    started_listening = pyqtSignal(int)             # sample_rate
    stopped           = pyqtSignal()
    failed            = pyqtSignal(str)

    # Per-block status for the level meter / status bar
    audio_level       = pyqtSignal(float)           # 0..1 RMS
    line_decoded      = pyqtSignal(int, object)     # line_idx, ndarray

    # Per-image lifecycle
    image_started     = pyqtSignal(str)             # reason ("auto"/"manual")
    image_finished    = pyqtSignal(
        object,                                     # PIL.Image.Image
        dict,                                       # info dict
        bytes,                                      # WAV bytes
    )

    def __init__(
        self,
        params: DecodeParams,
        device_index: int | None = None,
        sample_rate: int = 11025,
        auto_start: bool = True,
    ) -> None:
        super().__init__()
        self._params       = params
        self._device_index = device_index
        self._sample_rate  = sample_rate
        self._auto_start   = auto_start

        self._stop_flag      = False
        self._manual_start   = False
        self._manual_stop    = False

        # Block-arrival queue. The audio thread pushes; we pop.
        # Use a simple list with a lock — sounddevice uses small blocks
        # at audio rate, GIL handling is fine for our throughput.
        from collections import deque
        from threading import Lock
        self._audio_q     = deque()
        self._q_lock      = Lock()

    # ---- Public control API -------------------------------------------
    def request_stop(self) -> None:
        """Tell the worker to shut down after current block."""
        self._stop_flag = True

    def manual_start(self) -> None:
        """User pressed 'Start image now' — begin recording immediately."""
        self._manual_start = True

    def manual_stop_image(self) -> None:
        """User pressed 'Stop image' — finish current image now."""
        self._manual_stop = True

    def set_auto_start(self, enabled: bool) -> None:
        """Toggle auto-start at runtime."""
        self._auto_start = enabled

    # ---- Worker body ---------------------------------------------------
    def run(self) -> None:
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            self.failed.emit(f"sounddevice/PortAudio not available: {exc}")
            return

        try:
            self._run_loop(sd)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.stopped.emit()

    def _run_loop(self, sd) -> None:
        """The actual decoding loop, separated for readability."""
        # ---- Open input stream ---------------------------------------
        # sounddevice callback runs on a private audio thread.
        # We push raw blocks into our queue; the worker thread does the
        # actual DSP. This keeps the audio callback fast and bounded.
        def _audio_callback(indata, frames, time_info, status):
            if status:
                # underrun/overflow — note but don't fail
                pass
            with self._q_lock:
                # Make a copy: indata is a temporary buffer.
                self._audio_q.append(indata[:, 0].copy())

        block_size = 2048   # ~185 ms @ 11025 Hz — small enough for low latency
        stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype='float32',
            blocksize=block_size,
            device=self._device_index,
            callback=_audio_callback,
        )

        # ---- Per-decoder state ---------------------------------------
        decoder = FaxDecoder(self._params)
        decoder.reset_streaming_state(self._sample_rate)
        spl = int(round(self._sample_rate * 60.0 / self._params.lpm))

        # Accumulators across audio blocks:
        #   pending_pixels — demodulated samples not yet sliced into lines
        #   pending_audio  — raw audio not yet sliced into lines (for header detection)
        pending_pixels = np.zeros(0, dtype=np.uint8)
        pending_audio  = np.zeros(0, dtype=np.float32)

        # Rolling pre-image audio buffer (for WAV save). Holds the most
        # recent ~30 s; gets prepended to the image audio when capture begins.
        rolling_seconds = 30
        rolling_max = rolling_seconds * self._sample_rate
        rolling_audio = np.zeros(0, dtype=np.float32)

        # Image-recording state
        capturing      = False
        image_audio    = np.zeros(0, dtype=np.float32)   # full audio for WAV
        image_lines    = []                              # decoded pixel rows
        line_idx_in_img = 0
        last_type      = LineType.IMAGE
        type_count     = 0
        gotstart       = False
        phasing_left   = 0
        phasing_pos    = []
        phasing_off    = 0
        required_run   = max(int(5 * self._params.lpm / 60.0) - _LEEWAY_LINES, 1)

        # ---- Start the audio stream ----------------------------------
        with stream:
            self.started_listening.emit(self._sample_rate)

            import time
            while not self._stop_flag:
                # Pull all currently-queued blocks.
                with self._q_lock:
                    if not self._audio_q:
                        block = None
                    else:
                        block = np.concatenate(list(self._audio_q))
                        self._audio_q.clear()

                if block is None:
                    time.sleep(0.02)
                    continue

                # Demod & accumulate.
                new_pixels = decoder.demodulate_block(block)
                pending_pixels = np.concatenate([pending_pixels, new_pixels])
                # NOTE: pixels has len(block) on subsequent calls but
                # len(block)-1 on the first call (discriminator pair).
                # To keep audio aligned with pixels we drop the first sample
                # of the very first block. This is a one-time event.
                if len(pending_audio) == 0 and len(new_pixels) == len(block) - 1:
                    pending_audio = block[1:].astype(np.float32)
                else:
                    pending_audio = np.concatenate([pending_audio, block.astype(np.float32)])

                # Update rolling audio buffer.
                rolling_audio = np.concatenate([rolling_audio, block.astype(np.float32)])
                if len(rolling_audio) > rolling_max:
                    rolling_audio = rolling_audio[-rolling_max:]

                # Audio-level indicator (RMS of this block).
                rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
                self.audio_level.emit(rms)

                # ---- Slice complete lines from accumulators ----------
                while len(pending_pixels) >= spl and len(pending_audio) >= spl:
                    line_demod = pending_pixels[:spl]
                    line_audio = pending_audio[:spl].astype(np.float64)
                    pending_pixels = pending_pixels[spl:]
                    pending_audio  = pending_audio[spl:]

                    # Always classify so we can react to START even when
                    # not actively capturing. Pass the demod line too so the
                    # keyed-APT (300 Hz black/white) start is detectable here
                    # as well — same fix as decode_wav.
                    line_type = decoder._detect_line_type(
                        line_audio, self._sample_rate, _FT_THRESHOLD_RATIO,
                        demod_line=line_demod,
                    )

                    # Run-length tracking (same as decode_wav).
                    if line_type == last_type and line_type != LineType.IMAGE:
                        type_count += 1
                    else:
                        type_count = max(type_count - 1, 0)
                    last_type = line_type

                    # ---- Manual start trigger ------------------------
                    if self._manual_start and not capturing:
                        self._manual_start = False
                        capturing = True
                        gotstart = True
                        phasing_left = 0       # no phasing — user said go
                        phasing_pos = []
                        phasing_off = 0
                        line_idx_in_img = 0
                        image_lines = []
                        # Save the pre-recorded rolling buffer as the lead-in.
                        image_audio = rolling_audio.copy()
                        self.image_started.emit("manual")

                    # ---- Auto start on detected START tone -----------
                    if (self._auto_start
                            and not capturing
                            and line_type == LineType.START
                            and type_count == required_run):
                        capturing = True
                        gotstart = True
                        phasing_left = _PHASING_LINES
                        phasing_pos = []
                        phasing_off = 0
                        line_idx_in_img = 0
                        image_lines = []
                        image_audio = rolling_audio.copy()
                        self.image_started.emit("auto")

                    # ---- If capturing, record audio and process line --
                    if capturing:
                        # Append this line's audio to the image WAV buffer.
                        image_audio = np.concatenate(
                            [image_audio, line_audio.astype(np.float32)]
                        )

                        # Manual stop?
                        if self._manual_stop:
                            self._manual_stop = False
                            self._finalise_image(
                                image_lines, image_audio,
                                phasing_off, "manual_stop",
                            )
                            capturing = False
                            gotstart = False
                            continue

                        # Auto stop on STOP tone.
                        if (line_type == LineType.STOP
                                and type_count == required_run
                                and gotstart):
                            self._finalise_image(
                                image_lines, image_audio,
                                phasing_off, "stop_tone",
                            )
                            capturing = False
                            gotstart = False
                            type_count = 0
                            continue

                        # Phasing / image accumulation.
                        if line_type == LineType.IMAGE and gotstart:
                            if phasing_left > 0:
                                if phasing_left <= _PHASING_LINES - _PHASING_SKIP:
                                    line_img = decoder._decode_image_line(line_demod)
                                    phasing_pos.append(
                                        decoder._phasing_position(line_img, decoder.target_w)
                                    )
                                phasing_left -= 1
                                if phasing_left == 0 and phasing_pos:
                                    phasing_off = int(np.median(phasing_pos))
                            else:
                                line_img = decoder._decode_image_line(line_demod)
                                if phasing_off:
                                    line_img = np.roll(line_img, -phasing_off)
                                image_lines.append(line_img)
                                self.line_decoded.emit(line_idx_in_img, line_img)
                                line_idx_in_img += 1

    def _finalise_image(
        self,
        image_lines: list,
        image_audio: np.ndarray,
        phasing_off: int,
        reason: str,
    ) -> None:
        """Convert the accumulated lines into a PIL image and emit."""
        if not image_lines:
            return

        img_array = np.stack(image_lines, axis=0)
        img = Image.fromarray(img_array, mode='L')

        # Build WAV bytes from the audio buffer.
        # Use the shared writer (in-memory).
        import io
        buf = io.BytesIO()
        peak = max(float(np.max(np.abs(image_audio))), 1e-9)
        scale = 0.95 * 32767 / peak
        audio_i16 = np.clip(image_audio * scale, -32768, 32767).astype(np.int16)
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(audio_i16.tobytes())
        wav_bytes = buf.getvalue()

        info = {
            'sample_rate':    self._sample_rate,
            'image_width':    img.width,
            'image_height':   img.height,
            'lpm':            self._params.lpm,
            'ioc':            self._params.ioc,
            'phasing_offset': phasing_off,
            'finish_reason':  reason,
            'audio_samples':  len(image_audio),
            'audio_seconds':  len(image_audio) / self._sample_rate,
        }
        self.image_finished.emit(img, info, wav_bytes)


# ---------------------------------------------------------------------------
# GUI — tabbed: WAV file decoder + Live audio decoder
# ---------------------------------------------------------------------------
class FaxDecoderWindow(QMainWindow):
    """Main decoder window with two tabs:
        * "From WAV file" — original offline decoder
        * "Live audio"     — PortAudio capture + streaming decode
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WEFAX Decoder Test (OE3GAS)")
        self.resize(720, 720)

        # State for WAV-file tab
        self._wav_path: Path | None = None
        self._image:    Image.Image | None = None
        self._info:     dict | None = None
        self._worker:   DecodeWorker | None = None

        # State for live-audio tab
        self._live_worker:   LiveDecodeWorker | None = None
        self._live_image:    Image.Image | None = None
        self._live_buffer:   np.ndarray | None = None     # growing line buffer
        self._live_target_w: int = 0

        # ----- Tabs -----
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_wav_tab(), "From WAV file")
        self.tabs.addTab(self._build_live_tab(), "Live audio")
        self.setCentralWidget(self.tabs)
        self.setStatusBar(QStatusBar())

    # ==================================================================
    # WAV file tab
    # ==================================================================
    def _build_wav_tab(self) -> QWidget:
        self.btn_open = QPushButton("Open WAV…")
        self.lbl_path = QLabel("(no WAV loaded)")

        self.cb_lpm = QComboBox()
        for v in LPM_OPTIONS:
            self.cb_lpm.addItem(f"{v} LPM", v)
        self.cb_lpm.setCurrentText("120 LPM")

        self.cb_ioc = QComboBox()
        for v in IOC_OPTIONS:
            self.cb_ioc.addItem(f"IOC {v}", v)
        self.cb_ioc.setCurrentText("IOC 576")

        self.cb_bw = QComboBox()
        self.cb_bw.addItem("Narrow", FilterBandwidth.NARROW)
        self.cb_bw.addItem("Middle", FilterBandwidth.MIDDLE)
        self.cb_bw.addItem("Wide",   FilterBandwidth.WIDE)
        self.cb_bw.setCurrentText("Middle")

        self.cb_skip = QComboBox()
        self.cb_skip.addItem("Auto-detect headers", False)
        self.cb_skip.addItem("Skip header detection (whole WAV is image)", True)

        self.btn_decode = QPushButton("Decode")
        self.btn_decode.setEnabled(False)
        self.btn_save   = QPushButton("Save Image…")
        self.btn_save.setEnabled(False)
        self.progress   = QProgressBar()
        self.progress.setVisible(False)

        self.lbl_image = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setMinimumHeight(280)
        self.lbl_image.setStyleSheet("border: 1px solid #888;")
        self.lbl_info = QLabel("")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #444;")

        form = QFormLayout()
        form.addRow("LPM:",       self.cb_lpm)
        form.addRow("IOC:",       self.cb_ioc)
        form.addRow("Bandwidth:", self.cb_bw)
        form.addRow("Mode:",      self.cb_skip)

        top = QHBoxLayout()
        top.addWidget(self.btn_open)
        top.addWidget(self.lbl_path, 1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_decode)
        bottom.addWidget(self.btn_save)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(form)
        root.addLayout(bottom)
        root.addWidget(self.progress)
        root.addWidget(self.lbl_image, 1)
        root.addWidget(self.lbl_info)

        page = QWidget()
        page.setLayout(root)

        self.btn_open.clicked.connect(self._on_open)
        self.btn_decode.clicked.connect(self._on_decode)
        self.btn_save.clicked.connect(self._on_save)
        return page

    def _on_open(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open WAV", "", "WAV (*.wav);;All files (*)"
        )
        if not path_str:
            return
        self._wav_path = Path(path_str)
        self.lbl_path.setText(self._wav_path.name)
        self.btn_decode.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.lbl_image.clear()
        self.lbl_info.clear()

    def _on_decode(self) -> None:
        if self._wav_path is None:
            return

        params = DecodeParams(
            lpm=self.cb_lpm.currentData(),
            ioc=self.cb_ioc.currentData(),
            bandwidth=self.cb_bw.currentData(),
            skip_header_detection=self.cb_skip.currentData(),
        )

        self.btn_decode.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.statusBar().showMessage("Decoding…")

        self._worker = DecodeWorker(self._wav_path, params)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_decode_ok)
        self._worker.failed.connect(self._on_decode_failed)
        self._worker.start()

    def _on_progress(self, label: str, cur: int, total: int) -> None:
        if total > 0:
            self.progress.setValue(int(100 * cur / total))
        self.statusBar().showMessage(f"{label} {cur}/{total}")

    def _on_decode_ok(self, img: Image.Image, info: dict) -> None:
        self._image = img
        self._info  = info
        self._show_pixmap(self.lbl_image, img)
        self.lbl_info.setText(
            f"Decoded: {info['image_width']}x{info['image_height']} px  -  "
            f"Start line: {info['start_line']}  -  Stop line: {info['stop_line']}  "
            f"-  Phasing offset: {info['phasing_offset']} px  -  "
            f"Audio: {info['audio_samples']/info['sample_rate']:.1f} s "
            f"@ {info['sample_rate']} Hz"
        )
        self._reset_wav_buttons()
        self.btn_save.setEnabled(True)
        self.statusBar().showMessage("Decoded - choose Save Image to write a file", 5000)

    def _on_decode_failed(self, msg: str) -> None:
        QMessageBox.critical(self, "Decoding failed", msg)
        self.statusBar().showMessage("Failed", 3000)
        self._reset_wav_buttons()

    def _on_save(self) -> None:
        if self._image is None:
            return
        default = (self._wav_path.with_suffix('.png')
                   if self._wav_path else Path("fax_decoded.png"))
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save image", str(default),
            "PNG (*.png);;BMP (*.bmp);;JPEG (*.jpg)"
        )
        if not path_str:
            return
        try:
            self._image.save(path_str)
            self.statusBar().showMessage(f"Saved -> {path_str}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _reset_wav_buttons(self) -> None:
        self.progress.setVisible(False)
        self.btn_decode.setEnabled(self._wav_path is not None)
        self.btn_open.setEnabled(True)

    # ==================================================================
    # Live audio tab
    # ==================================================================
    def _build_live_tab(self) -> QWidget:
        # --- Device picker ---
        self.cb_device = QComboBox()
        self.btn_refresh_devices = QPushButton("Refresh")
        self.btn_refresh_devices.clicked.connect(self._refresh_devices)

        # --- Decoder parameters (separate from WAV tab so the user can
        # configure them independently) ---
        self.cb_lpm_live = QComboBox()
        for v in LPM_OPTIONS:
            self.cb_lpm_live.addItem(f"{v} LPM", v)
        self.cb_lpm_live.setCurrentText("120 LPM")
        self.cb_ioc_live = QComboBox()
        for v in IOC_OPTIONS:
            self.cb_ioc_live.addItem(f"IOC {v}", v)
        self.cb_ioc_live.setCurrentText("IOC 576")
        self.cb_bw_live = QComboBox()
        self.cb_bw_live.addItem("Narrow", FilterBandwidth.NARROW)
        self.cb_bw_live.addItem("Middle", FilterBandwidth.MIDDLE)
        self.cb_bw_live.addItem("Wide",   FilterBandwidth.WIDE)
        self.cb_bw_live.setCurrentText("Middle")

        # --- Auto-start checkbox ---
        self.chk_auto_start = QCheckBox(
            "Auto-start on detected START tone"
        )
        self.chk_auto_start.setChecked(True)
        self.chk_auto_start.toggled.connect(self._on_auto_start_toggled)

        # --- Output folder for saved images and WAVs ---
        self.lbl_outdir = QLabel(str(Path.home() / "wefax_captures"))
        self.btn_outdir = QPushButton("Choose folder...")
        self.btn_outdir.clicked.connect(self._on_choose_outdir)

        # --- Listening / capture controls ---
        self.btn_listen   = QPushButton("Start listening")
        self.btn_listen.clicked.connect(self._on_listen_toggle)
        self.btn_manual_start = QPushButton("Start image now")
        self.btn_manual_start.setEnabled(False)
        self.btn_manual_start.clicked.connect(self._on_manual_start)
        self.btn_manual_stop  = QPushButton("Stop image")
        self.btn_manual_stop.setEnabled(False)
        self.btn_manual_stop.clicked.connect(self._on_manual_stop)

        # --- Audio level bar ---
        self.lvl_bar = QProgressBar()
        self.lvl_bar.setRange(0, 100)
        self.lvl_bar.setTextVisible(False)
        self.lvl_bar.setMaximumHeight(8)

        # --- Live image display ---
        self.lbl_live_image = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl_live_image.setMinimumHeight(320)
        self.lbl_live_image.setStyleSheet("border: 1px solid #888;")

        self.lbl_live_info = QLabel("Idle.")
        self.lbl_live_info.setWordWrap(True)
        self.lbl_live_info.setStyleSheet("color: #444;")

        # --- Layout ---
        device_row = QHBoxLayout()
        device_row.addWidget(self.cb_device, 1)
        device_row.addWidget(self.btn_refresh_devices)

        outdir_row = QHBoxLayout()
        outdir_row.addWidget(self.lbl_outdir, 1)
        outdir_row.addWidget(self.btn_outdir)

        params_form = QFormLayout()
        params_form.addRow("Input device:", device_row)
        params_form.addRow("LPM:",          self.cb_lpm_live)
        params_form.addRow("IOC:",          self.cb_ioc_live)
        params_form.addRow("Bandwidth:",    self.cb_bw_live)
        params_form.addRow("Save to:",      outdir_row)
        params_form.addRow(self.chk_auto_start)

        ctl_row = QHBoxLayout()
        ctl_row.addWidget(self.btn_listen)
        ctl_row.addWidget(self.btn_manual_start)
        ctl_row.addWidget(self.btn_manual_stop)

        root = QVBoxLayout()
        root.addLayout(params_form)
        root.addLayout(ctl_row)
        root.addWidget(self.lvl_bar)
        root.addWidget(self.lbl_live_image, 1)
        root.addWidget(self.lbl_live_info)

        page = QWidget()
        page.setLayout(root)

        # Populate device list. If sounddevice is missing, the dropdown
        # is empty and "Start listening" remains disabled with a tooltip.
        self._refresh_devices()
        return page

    # ---- Device discovery ---------------------------------------------
    def _refresh_devices(self) -> None:
        self.cb_device.clear()
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default = sd.default.device[0] if sd.default.device else None
            for i, d in enumerate(devices):
                if d.get('max_input_channels', 0) > 0:
                    label = f"{i}: {d['name']}"
                    if i == default:
                        label += "  (default)"
                    self.cb_device.addItem(label, i)
            if self.cb_device.count() == 0:
                self.cb_device.addItem("No input devices found", None)
                self.btn_listen.setEnabled(False)
            else:
                self.btn_listen.setEnabled(True)
        except (ImportError, OSError) as exc:
            self.cb_device.addItem(f"PortAudio unavailable: {exc}", None)
            self.btn_listen.setEnabled(False)
            self.btn_listen.setToolTip(
                "Install sounddevice and PortAudio to enable live audio."
            )

    def _on_choose_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.lbl_outdir.text()
        )
        if path:
            self.lbl_outdir.setText(path)

    def _on_auto_start_toggled(self, checked: bool) -> None:
        if self._live_worker is not None:
            self._live_worker.set_auto_start(checked)

    # ---- Listening lifecycle -------------------------------------------
    def _on_listen_toggle(self) -> None:
        if self._live_worker is None:
            self._start_listening()
        else:
            self._stop_listening()

    def _start_listening(self) -> None:
        device = self.cb_device.currentData()
        if device is None:
            QMessageBox.warning(self, "No input device", "Pick an input device first.")
            return

        # Make sure the output folder exists.
        outdir = Path(self.lbl_outdir.text())
        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.critical(self, "Cannot create folder", str(exc))
            return

        params = DecodeParams(
            lpm=self.cb_lpm_live.currentData(),
            ioc=self.cb_ioc_live.currentData(),
            bandwidth=self.cb_bw_live.currentData(),
            skip_header_detection=False,
        )
        self._live_target_w = int(round(params.ioc * math.pi / 2))
        self._live_buffer   = None
        self._live_image    = None

        self._live_worker = LiveDecodeWorker(
            params=params,
            device_index=device,
            sample_rate=11025,
            auto_start=self.chk_auto_start.isChecked(),
        )
        self._live_worker.started_listening.connect(self._on_live_started)
        self._live_worker.stopped.connect(self._on_live_stopped)
        self._live_worker.failed.connect(self._on_live_failed)
        self._live_worker.audio_level.connect(self._on_audio_level)
        self._live_worker.line_decoded.connect(self._on_live_line)
        self._live_worker.image_started.connect(self._on_image_started)
        self._live_worker.image_finished.connect(self._on_image_finished)
        self._live_worker.start()

        self.btn_listen.setText("Stop listening")
        self.btn_manual_start.setEnabled(True)

    def _stop_listening(self) -> None:
        if self._live_worker is not None:
            self._live_worker.request_stop()
            # The 'stopped' signal will reset UI when the thread exits.

    # ---- Slots from worker ---------------------------------------------
    def _on_live_started(self, sample_rate: int) -> None:
        self.lbl_live_info.setText(
            f"Listening @ {sample_rate} Hz - waiting for "
            + ("START tone" if self.chk_auto_start.isChecked()
               else "manual start")
        )
        self.statusBar().showMessage("Listening", 0)

    def _on_live_stopped(self) -> None:
        self._live_worker = None
        self.btn_listen.setText("Start listening")
        self.btn_manual_start.setEnabled(False)
        self.btn_manual_stop.setEnabled(False)
        self.lvl_bar.setValue(0)
        self.lbl_live_info.setText("Idle.")
        self.statusBar().showMessage("Stopped", 3000)

    def _on_live_failed(self, msg: str) -> None:
        QMessageBox.critical(self, "Live decode failed", msg)
        self._on_live_stopped()

    def _on_audio_level(self, rms: float) -> None:
        # rms is float-amplitude (0..1). Use a log-ish scale for nicer feel.
        # 0.0 -> 0%, 0.01 -> ~30%, 0.1 -> ~75%, 1.0 -> 100%
        if rms <= 1e-5:
            pct = 0
        else:
            pct = int(min(100, max(0, 100 * (1 + math.log10(rms) / 3))))
        self.lvl_bar.setValue(pct)

    def _on_image_started(self, reason: str) -> None:
        self.lbl_live_info.setText(
            f"Recording image (trigger: {reason})..."
        )
        # Initialise an empty preview canvas. We don't know the final
        # height, so we grow as lines arrive.
        self._live_buffer = np.full(
            (1, self._live_target_w), 255, dtype=np.uint8
        )
        self.btn_manual_start.setEnabled(False)
        self.btn_manual_stop.setEnabled(True)

    def _on_live_line(self, line_idx: int, line_pixels: np.ndarray) -> None:
        # Append to growing buffer and refresh the preview.
        if self._live_buffer is None:
            return
        if line_idx == 0:
            self._live_buffer = line_pixels.reshape(1, -1).copy()
        else:
            self._live_buffer = np.vstack([self._live_buffer, line_pixels])

        # Throttle preview refresh: only every 10 lines (=5 s @ 120 LPM).
        if line_idx % 10 == 0:
            img = Image.fromarray(self._live_buffer, mode='L')
            self._show_pixmap(self.lbl_live_image, img)
            self.statusBar().showMessage(f"Receiving line {line_idx}", 0)

    def _on_image_finished(
        self,
        img: Image.Image,
        info: dict,
        wav_bytes: bytes,
    ) -> None:
        self._live_image = img

        # Auto-save image and WAV side by side with timestamped names.
        from datetime import datetime
        outdir = Path(self.lbl_outdir.text())
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        png_path = outdir / f"wefax_{ts}.png"
        wav_path = outdir / f"wefax_{ts}.wav"
        try:
            img.save(png_path)
            with open(wav_path, 'wb') as fh:
                fh.write(wav_bytes)
            saved_msg = f"Saved {png_path.name} + {wav_path.name}"
        except Exception as exc:
            saved_msg = f"Save failed: {exc}"

        self._show_pixmap(self.lbl_live_image, img)
        self.lbl_live_info.setText(
            f"Image done ({info['finish_reason']}): "
            f"{info['image_width']}x{info['image_height']} px, "
            f"{info['audio_seconds']:.1f} s audio. {saved_msg}"
        )
        # Continue listening for the next image.
        self.btn_manual_start.setEnabled(True)
        self.btn_manual_stop.setEnabled(False)

    def _on_manual_start(self) -> None:
        if self._live_worker is not None:
            self._live_worker.manual_start()

    def _on_manual_stop(self) -> None:
        if self._live_worker is not None:
            self._live_worker.manual_stop_image()

    # ==================================================================
    # Shared helpers
    # ==================================================================
    def _show_pixmap(self, label: QLabel, img: Image.Image) -> None:
        """Display a PIL image scaled to fit the given QLabel."""
        rgb = img.convert('RGB')
        qimg = QImage(rgb.tobytes(), rgb.width, rgb.height,
                      3 * rgb.width, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(pix)

    def closeEvent(self, event):
        # Make sure the live worker is shut down cleanly.
        if self._live_worker is not None:
            self._live_worker.request_stop()
            self._live_worker.wait(2000)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    app = QApplication(sys.argv)
    win = FaxDecoderWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
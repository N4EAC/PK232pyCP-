# HF FAX (WEFAX)

HF FAX, also called WEFAX (Weather FAX), is a receive-only mode for decoding
facsimile images transmitted on HF. It is used primarily by meteorological
services to broadcast weather charts, satellite images, and sea state maps.

The PK-232MBX decodes the FAX audio signal and streams the image data to
PK232PY, which assembles and displays the image in real time.

---

## Typical FAX Frequencies (USB, kHz)

| Station | Frequencies |
|---------|-------------|
| Deutscher Wetterdienst (DWD) | 3855, 7880, 13882 |
| Meteo France | 3855, 7882 |
| Northwood (UK MET) | 2618.5, 4610, 8040, 11086.5 |
| US Coast Guard (NMF) | 4235, 6340.5, 9110, 12750 |

Tune the radio to the listed frequency in **USB** mode. The FAX signal
appears as two audio tones (black and white) within the passband.

---

## Receiving a FAX Image

1. Tune the radio to the FAX frequency in USB mode.
2. Switch to HF FAX from the Mode dropdown.
3. Click **Start**. The TNC begins decoding the audio.
4. The image builds up line by line in the display area. Reception is
   automatic once the signal is present.
5. Click **Stop** to freeze the current image.

Most FAX transmissions begin with a phasing signal (alternating black/white
lines) which the TNC uses to synchronise. Reception starts automatically
when the image data begins.

---

## Controls

| Control | Function |
|---------|----------|
| **Start / LOCK** | Start reception or force synchronisation. LOCK is a one-shot command that forces the decoder to lock onto the current signal phase — useful when automatic sync fails. |
| **Stop** | Freeze the current image. The image stays on screen for viewing. Press Start or LOCK to resume. |
| **Clear Image** | Erase the current image and re-enable reception. |
| **FAXNEG** | Invert the displayed image (black/white swap). Display-only — does not affect reception. Use when the image appears as a white-on-black negative. |
| **RXREV** | Reverse signal polarity on receive. Use when the image is consistently inverted and FAXNEG does not help (this changes the actual decoding, FAXNEG only the display). |
| **FSPEED** | FAX drum speed in lines per minute (LPM). Standard weather FAX: 120 LPM. Some stations use 60 LPM or 240 LPM. |

---

## Image Quality Adjustments
Be aware that the original output is Dedicated to Epson line Printers via parallel port. PK232py converts the TNC-Output dot a bi-Level Bitmap as intended by the makers of the PK232, so if you receive a grayscale Picture, grayscale Information will be lost and converted to simple black or white points.

### Line spacing slider

Fine-tunes the vertical pixel aspect ratio. Adjusts the displayed line height
to compensate for slight differences between the TNC's internal clock and the
transmitting station's drum speed. The default (centre position) applies the
standard 120/72 dpi correction automatically. Adjust if the image appears
stretched or compressed vertically.

### Smoothing slider

Applies a non-destructive anti-halftoning filter to the image. FAX images
are transmitted as bilevel (black/white) but the smoothing filter produces
a grayscale appearance that is easier to read.

- Slider at 0: raw bilevel image (no processing)
- Slider at maximum: strong smoothing

The slider position does not affect the saved image — the currently displayed
version is saved, including any smoothing applied.

---

## Troubleshooting

**Image is received but appears as a negative (white on black).**
Click **FAXNEG** to invert the display. If this happens consistently, toggle
**RXREV** to permanently correct the polarity at the decoder level.

**Image is slanted (parallelogram shape).**
The line timing is slightly off. Adjust the **Line spacing** slider until
the image is rectangular. This compensates for a small mismatch between the
TNC clock and the transmitting station's drum speed.

**Image shows horizontal banding or skips.**
The TNC lost synchronisation mid-image. Click **LOCK** to force
re-synchronisation. This can happen with poor signal quality or QSB.

**No image appears despite signal on the radio.**
Check audio level from the radio to the TNC. The audio should be at a
level that drives the TNC's demodulator without clipping. Also verify
that FSPEED matches the station (120 LPM for most weather FAX).

---

## See Also

- [AMTOR](amtor) — AMTOR Mode B is the basis for NAVTEX
- [NAVTEX](navtex) — another receive-only HF mode

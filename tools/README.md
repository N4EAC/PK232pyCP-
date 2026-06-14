# tools/

Development and test tooling for PK232PY. **These tools are not part of the
shipped application** and may carry their own licences (see the table below).

## Tools

| File | Purpose | Licence |
|------|---------|---------|
| `fax_wav_generator.py` | Generates three WEFAX test WAVs (weather chart, geometry/resolution pattern, Arial-16 pt text page) for closed-loop FAX decode testing without hardware. | GPL v2 (project) |
| `fax_decoder_test.py` | Standalone WEFAX audio decoder (PyQt6 GUI + live audio) used ONLY to verify generated WAVs. Never integrated into pk232py. | GPL v3 (ported from weatherfax_pi) |

## Scope / licence note

PK232PY **never decodes FAX audio itself.** In real operation the AEA
PK-232MBX performs the FAX demodulation in hardware and delivers ready-made
pixel bytes (Epson ESC L column format) to pk232py over Host Mode. The
application only renders those pixels.

These tools are therefore pure **test scaffolding** for a closed loop
(`fax_wav_generator.py` → WAV → `fax_decoder_test.py`), exercised without any
TNC, radio or live audio.

Because `fax_decoder_test.py` ports DSP algorithms from the GPL-v3
[weatherfax_pi](https://github.com/seandepagnier/weatherfax_pi) project, it is
itself GPL v3. This is **uncritical**: it is a separate standalone tool and is
never linked into or shipped with the GPL-v2 main application, so there is no
licence conflict. (Were it ever reused inside pk232py — it will not be — the
project licence would have to be relaxed to "GPL v2 or later".)

## Usage

Run from the repository root:

```bash
python tools/fax_wav_generator.py        # generates the 3 test WAVs
python tools/fax_decoder_test.py [wav]   # GUI; optional WAV path as argument
```

The generated WAVs are gitignored (regenerable artefacts).

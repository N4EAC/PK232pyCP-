# Signal / SIAM

The Signal / SIAM screen provides automatic signal analysis. The TNC analyses
the incoming audio and identifies the most likely digital mode.

SIAM stands for **Signal Identification and Analysis Mode** — an AEA feature
of the PK-232MBX firmware.

---

## How It Works

1. Tune the radio to a signal you want to identify.
2. Switch to Signal (Select SIAM from the Mode Dropdown)
3. Click **Analyse**. The TNC captures a signal sample and analyses it.
4. The result shows the identified mode, baud rate, shift, and polarity.
5. Click **OK — Switch to identified mode** to switch PK232PY directly to
   the identified mode and begin receiving.

---

## What SIAM Can Identify

SIAM can identify the following modes and parameters:

- Baudot RTTY (various baud rates and shifts)
- ASCII RTTY
- AMTOR / SITOR
- PACTOR

For each identified signal, SIAM reports:

- **Mode**: Baudot, ASCII, AMTOR, or PACTOR
- **Baud rate**: the detected symbol rate
- **Shift**: the detected FSK frequency shift (Hz)
- **Polarity**: normal or reversed (RXREV)
- **Confidence**: how certain the TNC is of the result in percent (from 0 to 1,00, where 1 = 100%)

---

## Limitations

SIAM works best with clean, strong signals. The following factors reduce
identification accuracy:

- Weak signals or high QRM level
- Signals that are not in SIAM's list (e.g. PSK31, FT8, JS8)
- Overlapping signals on the same frequency
- Very short transmissions (not enough data to analyse)

SIAM cannot identify Packet Radio (AX.25), NAVTEX, or FAX signals.

---

## See Also

- [Baudot RTTY](baudot)
- [AMTOR](amtor)
- [PACTOR I](pactor)

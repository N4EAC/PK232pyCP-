# AMTOR

AMTOR (AMateur Teleprinting Over Radio) is an error-correcting HF mode derived
from the commercial SITOR system. It runs at 100 Bd FSK with 170 Hz shift and
comes in two flavours:

- **ARQ (Mode A)** — a connected, two-way mode with automatic repeat request.
  The two stations hand the link back and forth and every block is acknowledged,
  so errors are detected and re-sent.
- **FEC / SELFEC (Mode B)** — a one-way broadcast mode with forward error
  correction (each character is sent twice). Used for CQ calls and bulletins
  where there is no return path.

AMTOR is available on every PK-232MBX — it does **not** require the PACTOR
firmware option.

---

## Before You Start

Set your **SELCAL** (selective-calling code) in the parameters. The SELCAL is a
4-character code derived from your callsign and is how ARQ stations address each
other. Your MYSELCAL is announced when you are called.

AMTOR runs at a fixed 100 Bd and a fixed shift, so there is no RBAUD or WIDESHFT
control on this screen (those belong to Baudot/ASCII RTTY).

---

## Connecting (ARQ)

1. Enter the destination station's SELCAL in the **Dest** field.
2. Click **ARQ**. The TNC starts the ARQ calling sequence.
3. When the link is up, the status indicator shows **● CONNECTED**.
4. Type text in the TX window — it is sent block-by-block with error correction.
5. Use **ACHG** (changeover) to hand the link to the other station so it can
   reply, or type `[^D]` (EOT) to send the polite over-to-you turnaround.
6. Click **STBY** to drop the link and return to standby.

---

## Broadcasting (FEC / SELFEC)

- **FEC** — broadcast to anyone listening (no connection). Click **FEC**, type
  your text, then **STBY** when finished. Typing `[^D]` also ends the broadcast.
- **SELFEC** — selective FEC to a single SELCAL (still one-way, but addressed).
  Enter the Dest SELCAL first, then click **SELFEC**.

---

## Buttons

| Button | Function |
|---|---|
| **ARQ** | Start an ARQ (Mode A) connection to the Dest SELCAL. |
| **FEC** | Start an FEC (Mode B) broadcast — no acknowledge. |
| **SELFEC** | Selective FEC broadcast addressed to one SELCAL. |
| **ALIST** | Listen mode — monitor AMTOR traffic without transmitting. |
| **Pactor Listen** | Auto-detect and monitor PACTOR signals (PACTOR firmware only). |
| **ACHG** | Changeover — take over / hand over the ARQ link (break-in). |
| **HOLD** | Hold the TX buffer instead of releasing it on changeover. |
| **STBY** | Standby — drop the link / stop transmitting and reset. |

---

## Toggle Buttons

| Toggle | Function |
|---|---|
| **ARXTOR** | Auto-detect incoming AMTOR/PACTOR and switch the receiver accordingly. |
| **RxRev** | Reverse the received mark/space polarity if text is garbled. |
| **TxRev** | Reverse the transmitted mark/space polarity. |
| **RFEC** | Request-FEC mode. |
| **SRxAll** | Receive all SELCALs, not just your own. |
| **EAS** | Echo As Sent — show confirmed TX characters in the RX window. |
| **Switch figs / Switch char** | Force the FIGS / LTRS shift, like Baudot RTTY. |

---

## Troubleshooting

**ARQ connect attempt never links up.**
Check that the Dest SELCAL is correct and that the other station is in AMTOR
standby/listen. ARQ needs a clean two-way path; a one-way or very weak signal
will not sync.

**Received text is all garbage.**
Try toggling **RxRev** — the mark/space tones may be swapped for your radio's
sideband.

**I hear PACTOR but cannot decode it.**
PACTOR requires the PACTOR firmware option. Without it, only AMTOR is available.
See [PACTOR I](pactor).

---

## See Also

- [PACTOR I](pactor) — faster HF data mode (requires PACTOR firmware)
- [Baudot RTTY](baudot) — the classic FSK teleprinter mode
- [Keyboard Shortcuts](shortcuts)
- [Control Characters](controls)

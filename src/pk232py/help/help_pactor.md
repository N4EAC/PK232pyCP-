# PACTOR I

PACTOR is an HF data mode which combines elements of AMTOR (ARQ error correction) 
and Packet Radio (data packets) for robust, efficient HF file transfer. 
PACTOR operates at 200 Bd FSK with 200 Hz shift.

**PACTOR requires the PACTOR firmware option.** The TNC firmware banner shown
after connecting indicates whether PACTOR is available. If the firmware version
does not mention PACTOR, only AMTOR and the other basic modes are available.
The PK232 does not decode PACTOR > Version 2!

---

## Before You Start

Set your callsign in the **MYPTCALL** field (Parameters → PACTOR Parameters).
This is the callsign announced during PACTOR connects — normally the same as
your regular callsign.

---

## Connecting to a PACTOR Station

1. Enter the destination callsign in the **Dest** field.
2. Click **Connect**. The TNC begins the PACTOR ARQ handshake.
3. When connected, the status indicator shows **● CONNECTED**.
4. Type text in the TX window — it is sent as PACTOR data packets.
5. To end the session, use **Disconnect** or type `[^D]` (EOT) in the TX window.

PACTOR connects are faster to establish than AMTOR ARQ because PACTOR uses a
fixed calling sequence without the slow AMTOR sync phase.

---

## PTLIST and PTSEND

These buttons interact with PACTOR BBS (mailbox) nodes:

- **PTLIST**: request the message list from the connected BBS. The BBS returns
  a list of available messages.
- **PTSEND**: send a message or file to the connected BBS. The BBS stores it
  for later retrieval.

These functions only make sense when connected to a PACTOR BBS node.

---

## PACTOR Parameters

| Button/Field | Function |
|---|---|
| **PT200** | Enable PACTOR Level 2 (200 Bd FSK). When ON, the TNC negotiates PACTOR-2 with compatible stations for higher throughput. Requires PACTOR firmware. |
| **PTHUFF** | Huffman compression. Compresses ASCII text before transmission. Effective for plain text, less so for binary data. Requires PACTOR firmware. |
| **PTROUND** | Round-trip time optimisation for long-path HF links where propagation delay is significant. |
| **MYPTCALL** | My PACTOR callsign — announced during PACTOR connects. |

---

## Receiving PACTOR (PTLIST / Listen)

To monitor incoming PACTOR transmissions without connecting, the TNC must be
in PACTOR listen mode. This is handled via the **ARXTOR** toggle on the AMTOR
screen — when ARXTOR is ON, the TNC automatically detects and switches to
PACTOR when it hears a PACTOR signal.

---

## Troubleshooting

**Connect attempt fails immediately.**
Check that the destination callsign is correct and that the other station is
in PACTOR standby. Also verify that PACTOR firmware is available (check the
firmware version shown after connecting).

**Connection established but data transfer is slow.**
On poor HF paths, PACTOR falls back to shorter packet sizes and more retries.
This is normal ARQ behaviour. PT200 (PACTOR-2) may help on marginally good paths.

**PTHUFF is ON but throughput does not improve.**
Huffman compression is only effective for ASCII text. Binary data or already-
compressed content will not benefit and may even be slightly slower.

---

## See Also

- [AMTOR](amtor) — similar HF data mode, available without PACTOR firmware
- [Keyboard Shortcuts](shortcuts)
- [Control Characters](controls)

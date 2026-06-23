# Packet Radio (HF and VHF)

Packet Radio uses the AX.25 protocol — the same protocol used in amateur radio
networks worldwide. The PK-232MBX handles all AX.25 framing internally; PK232PY
sends and receives complete data frames.

Two Packet modes are available:

- **HF Packet**: 300 Bd, Bell 103 modem, shift 200 Hz. Used on HF bands.
- **VHF Packet**: 1200 Bd, Bell 202 modem, shift 1000 Hz. Used on VHF (144.800 MHz in Europe
  for APRS; other frequencies for connected operation).

---

## Before You Start

Set your callsign in **MYCALL** (Parameters → Packet Parameters).

Check the **HBAUD** setting matches the network you want to use:
- HF: 300 Bd (default for HF Packet screen)
- VHF: 1200 Bd (default for VHF Packet screen)

Set **Monitor** level to 4 for normal use (shows all frame types including
connect requests and disconnects).

---

## Monitor Mode (Unconnected)

Without connecting, the TNC monitors all AX.25 traffic on the frequency.
Received frames appear in the RX window with a UTC timestamp.

On 144.800 MHz (European APRS frequency), you will see APRS beacons from
nearby stations. Click the **APRS** button to decode these frames and display
position, weather, telemetry, and other APRS data in a structured format.

The **Monitor** level dropdown controls which frame types are shown:

| Level | Shown |
|-------|-------|
| 0 | Nothing |
| 1 | UI frames only (beacons, APRS) |
| 2 | + I frames (connected data) |
| 3 | + connect/disconnect requests |
| 4 | + acknowledgements |
| 5 | + raw frames |
| 6 | All frames |

---

## Connecting to a Station or BBS

1. Enter the destination callsign in the **Dest** field (with optional SSID,
   e.g. `OE3XYZ` or `OE3XYZ-9`).
2. Click **Connect**. The TNC sends a SABM frame and the status shows
   **● CALLING …**
3. When the other station accepts the connection, the status changes to
   **● CONNECTED**.
4. Type in the TX window and press Enter to send. Each Enter sends one
   AX.25 data frame.
5. When done, click **Disconnect** or type `D` if connected to a BBS.

---

## Unproto (Beacon / CQ)

Click **Unproto** to send AX.25 UI frames without establishing a connection.
Set the path in the **UNPROTO via** field (e.g. `CQ` or `CQ VIA OE3XNR-8`).

Unproto and Connect are mutually exclusive — the Connect button is disabled
while Unproto is active, and vice versa.

---

## APRS 

The **APRS** button toggles APRS decode mode for received UI frames.

- **APRS OFF**: raw AX.25 frame display with UTC timestamp.
- **APRS ON**: decoded APRS data cards, colour-coded by frame type:
  - Orange: Mic-E position report
  - Blue: standard position report
  - Green: weather data
  - Yellow: telemetry
  - Pink: message / bulletin

All received frames are buffered — switching between raw and APRS mode
re-renders the full history without losing data.

---

## MHEARD

The MHEARD panel (right side of the screen) shows recently heard stations.

- **\*** after a callsign = heard directly (no digipeater).
- No **\*** = heard via a digipeater — direct connect may not be possible.
- **Refresh**: requests the MHEARD list from the TNC (up to 18 stations).
- **Clear**: clears the MHEARD display locally (does not affect the TNC list).

---

## Toggle Buttons

| Button | Function |
|--------|----------|
| **EAS** | Echo As Sent — shows TX characters in RX window after confirmed send. |
| **PASSALL** | Receive all frames regardless of CRC errors (monitoring only). |
| **MRPT** | Monitor Repeat — also show digipeated frames. |
| **MID** | Morse ID beacon at set interval. |
| **SQUELCH** | Suppress duplicate frames in the monitor display. |

---

## MailDrop

The **MailDrop** button connects to the TNC's built-in mailbox node. The TNC
acts as a simple BBS that can store and forward messages.

---

## Troubleshooting

**Connect attempt is never acknowledged.**
Check frequency, HBAUD setting, and that the other station is listening.
On HF, 300 Bd requires very clean audio and good propagation — QRM or a
wrong audio level will prevent decoding.

**Monitor shows frames but Connect fails.**
The station may be busy or not accepting connections. Check the Dest callsign
and SSID. On VHF, ensure your audio level and PTT are correctly configured.

**APRS positions look wrong or missing.**
Some APRS frame types (Mic-E in particular) require correct longitude decoding.
If positions appear garbled, check that the raw frame in non-APRS mode shows
a valid AX.25 UI frame with APRS-ID in the path.

---

## See Also

- [AMTOR](amtor) — HF data mode without AX.25
- [PACTOR I](pactor) — HF data mode with higher throughput

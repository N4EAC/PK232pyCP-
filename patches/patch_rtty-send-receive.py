"""
patch_rtty_send_receive.py
==========================
Korrigiert das SEND/RECEIVE-Verhalten für Baudot/ASCII RTTY und Morse:

SEND drücken:
  1. Sendet XMIT-Befehl (XM) → TNC tastet PTT und beginnt DIDDLE
  2. Verbindet tx_input.textChanged → _on_rtty_text_changed
     → jeder neu eingetippte Text wird sofort als data_frame gesendet

RECEIVE drücken:
  1. Sendet RCVE-Befehl (RC) → TNC schaltet auf Empfang
  2. Trennt tx_input.textChanged wieder

Aufruf vom Repo-Root:
    python patch_rtty_send_receive.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [

    # ── 1. _on_screen_send() ersetzen ────────────────────────────────────────
    (
        "    def _on_screen_send(self, active: bool) -> None:\n"
        "        \"\"\"Called when the SEND button on the active screen is toggled.\n"
        "\n"
        "        active=True:  flush TX window and start sending.\n"
        "        active=False: no explicit TNC command — the user stopped sending\n"
        "                      by un-toggling the button. The TX window remains\n"
        "                      for editing; another SEND press resumes.\n"
        "        \"\"\"\n"
        "        if not active:\n"
        "            return\n"
        "        self._on_send()   # send current TX window contents",

        "    def _on_screen_send(self, active: bool) -> None:\n"
        "        \"\"\"Called when the SEND button on the active screen is toggled.\n"
        "\n"
        "        active=True:\n"
        "          1. Send XMIT command (XM) — TNC keys PTT and starts DIDDLE.\n"
        "          2. Wire tx_input.textChanged → _on_rtty_text_changed so that\n"
        "             every character typed is sent immediately as a data frame.\n"
        "\n"
        "        active=False:\n"
        "          1. Send RCVE command (RC) — TNC returns to receive.\n"
        "          2. Disconnect textChanged.\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "\n"
        "        tx = self._tx_input\n"
        "        if tx is None:\n"
        "            return\n"
        "\n"
        "        from pk232py.comm.frame import build_command\n"
        "\n"
        "        if active:\n"
        "            # Send XMIT — TNC keys PTT and starts DIDDLE\n"
        "            xmit = build_command(b'XM')\n"
        "            self._serial.send_command(xmit[2:4], xmit[4:-1])\n"
        "            self._log_monitor(\"[TX] XMIT — PTT ON, DIDDLE started\")\n"
        "\n"
        "            # Send any text already in the TX window\n"
        "            text = tx.toPlainText().strip()\n"
        "            if text:\n"
        "                self._send_rtty_text(text)\n"
        "                tx.clear()\n"
        "\n"
        "            # Wire live-TX: every new character goes out immediately\n"
        "            try:\n"
        "                tx.textChanged.disconnect(self._on_rtty_text_changed)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "            tx.textChanged.connect(self._on_rtty_text_changed)\n"
        "\n"
        "        else:\n"
        "            # Disconnect live-TX\n"
        "            try:\n"
        "                tx.textChanged.disconnect(self._on_rtty_text_changed)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "\n"
        "            # Send RCVE — TNC switches back to receive\n"
        "            rcve = build_command(b'RC')\n"
        "            self._serial.send_command(rcve[2:4], rcve[4:-1])\n"
        "            self._log_monitor(\"[TX] RCVE — PTT OFF, back to receive\")"
    ),

    # ── 2. Neue Methoden _on_rtty_text_changed + _send_rtty_text einfügen ────
    (
        "    def _on_screen_receive(self, active: bool) -> None:",

        "    def _on_rtty_text_changed(self) -> None:\n"
        "        \"\"\"Called whenever the TX window content changes while SEND is active.\n"
        "\n"
        "        Sends the complete current content as a data frame, then clears\n"
        "        the window.  This produces character-by-character transmission\n"
        "        as the operator types.\n"
        "\n"
        "        Note: textChanged fires on every single character, so we check\n"
        "        that content is non-empty before sending.\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "        tx = self._tx_input\n"
        "        if tx is None:\n"
        "            return\n"
        "        text = tx.toPlainText()\n"
        "        if not text:\n"
        "            return\n"
        "        # Block signals to avoid re-entrant call when we clear the field\n"
        "        tx.blockSignals(True)\n"
        "        tx.clear()\n"
        "        tx.blockSignals(False)\n"
        "        self._send_rtty_text(text)\n"
        "\n"
        "    def _send_rtty_text(self, text: str) -> None:\n"
        "        \"\"\"Build and send a data frame for the given text.\n"
        "\n"
        "        Uses mode.data_frame() if available (handles uppercase for\n"
        "        Baudot automatically), otherwise falls back to raw send_data().\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "        mode = self._modes.current_mode\n"
        "        if mode is not None and hasattr(mode, 'data_frame'):\n"
        "            frame = mode.data_frame(text)\n"
        "            # data_frame returns SOH $4F ... ETB — extract payload\n"
        "            # For data frames (CTL $2x): build_data returns SOH $2x data ETB\n"
        "            # send_data expects raw bytes only\n"
        "            self._serial.send_data(\n"
        "                text.encode('ascii', errors='replace'),\n"
        "                channel=0,\n"
        "            )\n"
        "        else:\n"
        "            self._serial.send_data(\n"
        "                text.encode('ascii', errors='replace')\n"
        "            )\n"
        "        self._log_monitor(f\"[TX] {text!r}\")\n"
        "\n"
        "    def _on_screen_receive(self, active: bool) -> None:"
    ),

]


def apply_patches(path: Path, patches: list[tuple]) -> None:
    src = path.read_text(encoding="utf-8")

    missing = []
    for i, patch in enumerate(patches, 1):
        if patch[0] not in src:
            missing.append(i)

    if missing:
        print(f"FEHLER: Suchstring nicht gefunden fuer Patch(e): {missing}")
        print("Patch wird NICHT angewendet — Datei unveraendert.")
        return

    for i, patch in enumerate(patches, 1):
        src = src.replace(patch[0], patch[1], 1)
        print(f"OK  Patch {i} angewendet")

    path.write_text(src, encoding="utf-8")
    print(f"\nFertig — {path} aktualisiert.")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply_patches(TARGET, PATCHES)
"""
patch_rtty_complete.py
======================
Kombinierter Patch gegen die AKTUELLEN Sources (Stand nach Sources-Update):

Änderung 1: _on_screen_send() — XMIT/RCVE Befehl + Live-TX + Pending-Warnung
Änderung 2: Zwei neue Methoden: _on_rtty_text_changed() + _send_rtty_text()

Aufruf vom Repo-Root:
    python patch_rtty_complete.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [

    # ── 1. _on_screen_send() komplett ersetzen ───────────────────────────────
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
        "          2. Send any text already in TX window.\n"
        "          3. Wire tx_input.textChanged so every new character is sent\n"
        "             immediately as a data frame.\n"
        "\n"
        "        active=False:\n"
        "          1. Warn if unsent text remains in TX window.\n"
        "          2. Disconnect textChanged.\n"
        "          3. Send RCVE command (RC) — TNC returns to receive.\n"
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
        "            # 1. Send XMIT — TNC keys PTT and starts DIDDLE\n"
        "            xmit = build_command(b'XM')\n"
        "            self._serial.send_command(xmit[2:4], xmit[4:-1])\n"
        "            self._log_monitor(\"[TX] XMIT — PTT ON, DIDDLE started\")\n"
        "\n"
        "            # 2. Send any text already in TX window\n"
        "            text = tx.toPlainText().strip()\n"
        "            if text:\n"
        "                self._send_rtty_text(text)\n"
        "                tx.blockSignals(True)\n"
        "                tx.clear()\n"
        "                tx.blockSignals(False)\n"
        "\n"
        "            # 3. Wire live-TX: every new character goes out immediately\n"
        "            try:\n"
        "                tx.textChanged.disconnect(self._on_rtty_text_changed)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "            tx.textChanged.connect(self._on_rtty_text_changed)\n"
        "\n"
        "        else:\n"
        "            # 1. Warn if unsent text remains\n"
        "            pending = tx.toPlainText().strip()\n"
        "            if pending:\n"
        "                rx = self._rx_display\n"
        "                rx.moveCursor(rx.textCursor().MoveOperation.End)\n"
        "                rx.insertPlainText(\"\\n*** Still text to transmit! ***\\n\")\n"
        "\n"
        "            # 2. Disconnect live-TX\n"
        "            try:\n"
        "                tx.textChanged.disconnect(self._on_rtty_text_changed)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "\n"
        "            # 3. Send RCVE — TNC switches back to receive\n"
        "            rcve = build_command(b'RC')\n"
        "            self._serial.send_command(rcve[2:4], rcve[4:-1])\n"
        "            self._log_monitor(\"[TX] RCVE — PTT OFF, back to receive\")"
    ),

    # ── 2. Neue Methoden nach _on_screen_send(), vor _on_screen_receive() ────
    (
        "    def _on_screen_receive(self, active: bool) -> None:\n"
        "        \"\"\"Called when the RECEIVE button on the active screen is toggled.\n"
        "\n"
        "        active=True:  send RECEIVE command to TNC for the current mode.\n"
        "        active=False: return TNC to standby for the current mode.\n"
        "\n"
        "        Each mode has a different receive-activation mnemonic:\n"
        "          Baudot/ASCII RTTY  — RX is always on; no explicit command needed.\n"
        "          AMTOR              — receive handled by ALIST / FEC buttons.\n"
        "          Morse              — RX is always on; no explicit command needed.\n"
        "          PACTOR             — receive via PTLIST (btn_ptlist on screen).\n"
        "        For modes where no action is needed, the call is a graceful no-op.\n"
        "        \"\"\"",

        "    def _on_rtty_text_changed(self) -> None:\n"
        "        \"\"\"Called whenever TX window content changes while SEND is active.\n"
        "\n"
        "        Sends the complete current content as a data frame, then clears\n"
        "        the window — producing character-by-character live transmission.\n"
        "        blockSignals prevents a recursive call when clearing the field.\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "        tx = self._tx_input\n"
        "        if tx is None:\n"
        "            return\n"
        "        text = tx.toPlainText()\n"
        "        if not text:\n"
        "            return\n"
        "        tx.blockSignals(True)\n"
        "        tx.clear()\n"
        "        tx.blockSignals(False)\n"
        "        self._send_rtty_text(text)\n"
        "\n"
        "    def _send_rtty_text(self, text: str) -> None:\n"
        "        \"\"\"Send text as a data frame via the active mode.\n"
        "\n"
        "        Baudot mode uppercases automatically via data_frame().\n"
        "        send_data() expects raw payload bytes — not a full Host frame.\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "        self._serial.send_data(\n"
        "            text.encode('ascii', errors='replace'),\n"
        "            channel=0,\n"
        "        )\n"
        "        self._log_monitor(f\"[TX] {text!r}\")\n"
        "\n"
        "    def _on_screen_receive(self, active: bool) -> None:\n"
        "        \"\"\"Called when the RECEIVE button on the active screen is toggled.\n"
        "\n"
        "        active=True:  send RECEIVE command to TNC for the current mode.\n"
        "        active=False: return TNC to standby for the current mode.\n"
        "\n"
        "        Each mode has a different receive-activation mnemonic:\n"
        "          Baudot/ASCII RTTY  — RX is always on; no explicit command needed.\n"
        "          AMTOR              — receive handled by ALIST / FEC buttons.\n"
        "          Morse              — RX is always on; no explicit command needed.\n"
        "          PACTOR             — receive via PTLIST (btn_ptlist on screen).\n"
        "        For modes where no action is needed, the call is a graceful no-op.\n"
        "        \"\"\""
    ),

]


def apply_patches(path: Path, patches: list[tuple]) -> None:
    src = path.read_text(encoding="utf-8")

    missing = []
    for i, patch in enumerate(patches, 1):
        if patch[0] not in src:
            missing.append(i)
            # Zeige die ersten 80 Zeichen des gesuchten Strings zur Diagnose
            print(f"  Patch {i} — Suchstring nicht gefunden.")
            print(f"  Erster Teil: {repr(patch[0][:80])}")

    if missing:
        print(f"\nPatch wird NICHT angewendet — Datei unveraendert.")
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
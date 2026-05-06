"""
patch_rtty_final.py
===================
Robuster Patch mit zwei Änderungen:

1. _on_screen_send() — ersetzt die alte Version durch XMIT/RCVE/Live-TX
   + "Still text to transmit!" Warnung
2. Zwei neue Methoden: _on_rtty_text_changed() + _send_rtty_text()
3. _switch_opmode() — setzt btn_receive initial auf grün für RTTY-Modi

Der Patch sucht zuerst nach dem alten String, dann nach einem
alternativen Muster falls der erste nicht passt.
Gibt bei Fehler den exakten gefundenen Kontext aus.

Aufruf vom Repo-Root:
    python patch_rtty_final.py
"""

from pathlib import Path
import re

TARGET = Path("src/pk232py/ui/main_window.py")


def find_and_show(src: str, needle: str, label: str) -> bool:
    """Suche needle in src. Zeige Kontext wenn nicht gefunden."""
    if needle in src:
        return True
    # Zeige was tatsächlich um die ersten 40 chars steht
    first_line = needle.splitlines()[0][:60]
    idx = src.find(first_line[:30])
    if idx >= 0:
        print(f"  HINWEIS: Erste Zeile gefunden ab Position {idx}:")
        print(f"  {repr(src[idx:idx+120])}")
    else:
        print(f"  Erste Zeile von {label} nicht gefunden: {repr(first_line)}")
    return False


def patch_on_screen_send(src: str) -> str:
    """Ersetze _on_screen_send() — suche nach beiden möglichen Varianten."""

    # Variante A: alter Stand (self._on_send())
    old_a = (
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
        "        self._on_send()   # send current TX window contents"
    )

    new = (
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
    )

    if old_a in src:
        print("OK  Patch 1a: _on_screen_send (alte Variante) ersetzt")
        return src.replace(old_a, new, 1)

    # Variante B: bereits teilweise gepatcht aber ohne pending-warning
    if "self._serial.send_command(xmit[2:4], xmit[4:-1])" in src:
        if "Still text to transmit" not in src:
            # Füge nur die Pending-Warnung ein
            old_b = (
                "        else:\n"
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
            )
            new_b = (
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
            )
            if old_b in src:
                print("OK  Patch 1b: Pending-Warnung ergänzt")
                return src.replace(old_b, new_b, 1)
            print("FEHLER: Variante B — else-Block nicht gefunden")
            return src
        else:
            print("OK  Patch 1: _on_screen_send bereits aktuell (kein Patch nötig)")
            return src

    print("FEHLER: _on_screen_send — kein passender Suchstring gefunden")
    # Diagnose: zeige was vorhanden ist
    idx = src.find("def _on_screen_send")
    if idx >= 0:
        print(f"  Gefundene Version:\n  {repr(src[idx:idx+200])}")
    return src


def patch_new_methods(src: str) -> str:
    """Füge _on_rtty_text_changed + _send_rtty_text ein falls noch nicht vorhanden."""

    if "_on_rtty_text_changed" in src:
        print("OK  Patch 2: _on_rtty_text_changed bereits vorhanden")
        return src

    # Einfügen vor _on_screen_receive
    anchor = "    def _on_screen_receive(self, active: bool) -> None:"
    if anchor not in src:
        print("FEHLER: Anker _on_screen_receive nicht gefunden")
        return src

    insert = (
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
        "        Baudot mode uppercases automatically via mode.data_frame().\n"
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
    )
    print("OK  Patch 2: _on_rtty_text_changed + _send_rtty_text eingefügt")
    return src.replace(anchor, insert + anchor, 1)


def patch_initial_receive(src: str) -> str:
    """Setze btn_receive initial auf grün wenn Baudot/ASCII/Morse Screen."""

    if "btn_receive.setChecked(True)" in src:
        print("OK  Patch 3: Initial-RECEIVE bereits vorhanden")
        return src

    # Einfügen am Ende von _switch_opmode(), nach dem setCurrentWidget-Aufruf
    old = (
        "        self._opmode_stack.setCurrentWidget(screen)\n"
        "        logger.debug(\"Opmode screen switched to: %s\", name)\n"
        "        # Focus the TX window of the new screen immediately\n"
        "        QTimer.singleShot(0, self._focus_active_tx)"
    )
    new = (
        "        self._opmode_stack.setCurrentWidget(screen)\n"
        "        logger.debug(\"Opmode screen switched to: %s\", name)\n"
        "\n"
        "        # For RTTY/Morse screens: set RECEIVE button green on entry\n"
        "        # because the TNC starts in receive mode.\n"
        "        _rx_modes = (\"Baudot RTTY\", \"ASCII RTTY\", \"CW / Morse\")\n"
        "        if name in _rx_modes and hasattr(screen, \"btn_receive\"):\n"
        "            screen.btn_receive.blockSignals(True)\n"
        "            screen.btn_receive.setChecked(True)\n"
        "            screen.btn_receive.blockSignals(False)\n"
        "            # Trigger visual update directly (signals blocked above)\n"
        "            screen._on_receive_toggled(True)\n"
        "\n"
        "        # Focus the TX window of the new screen immediately\n"
        "        QTimer.singleShot(0, self._focus_active_tx)"
    )
    if old not in src:
        print("FEHLER: Anker in _switch_opmode nicht gefunden")
        idx = src.find("def _switch_opmode")
        if idx >= 0:
            print(f"  Gefundene Version:\n  {repr(src[idx:idx+300])}")
        return src

    print("OK  Patch 3: Initial-RECEIVE grün in _switch_opmode eingefügt")
    return src.replace(old, new, 1)


def apply(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    original = src

    src = patch_on_screen_send(src)
    src = patch_new_methods(src)
    src = patch_initial_receive(src)

    if src == original:
        print("\nKeine Änderungen vorgenommen.")
        return

    path.write_text(src, encoding="utf-8")
    print(f"\nFertig — {path} aktualisiert.")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply(TARGET)
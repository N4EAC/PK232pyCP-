"""
patch_rtty_pending_text_warning.py
===================================
Ergänzt eine Warnung im RX-Fenster wenn RECEIVE gedrückt wird
während noch Text im TX-Fenster steht.

Aufruf vom Repo-Root:
    python patch_rtty_pending_text_warning.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [
    (
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
        "            self._log_monitor(\"[TX] RCVE — PTT OFF, back to receive\")",

        "        else:\n"
        "            # Warn user if unsent text remains in the TX window\n"
        "            pending = tx.toPlainText().strip()\n"
        "            if pending:\n"
        "                rx = self._rx_display\n"
        "                rx.moveCursor(rx.textCursor().MoveOperation.End)\n"
        "                rx.insertPlainText(\"\\n*** Still text to transmit! ***\\n\")\n"
        "\n"
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
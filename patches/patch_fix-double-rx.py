"""
patch_fix_double_rx.py
======================
Behebt die doppelte Anzeige empfangener Zeichen.

Ursache: _on_frame_received() schreibt RX_DATA/RX_MONITOR/ECHO
direkt in _log_terminal() UND gleichzeitig ruft ModeManager den
on_data_received-Callback auf, der ebenfalls _log_terminal() aufruft.

Fix: den direkten Schreibpfad in _on_frame_received() entfernen.
Die Mode-Callbacks sind der korrekte und einzige Weg für RX-Daten.

Aufruf vom Repo-Root:
    python patch_fix_double_rx.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [
    (
        "        # Terminal: show received text for data frames\n"
        "        if frame.kind in (FrameKind.RX_DATA, FrameKind.RX_MONITOR,\n"
        "                          FrameKind.ECHO):\n"
        "            text = frame.text.strip()\n"
        "            if text:\n"
        "                self._log_terminal(text)\n",

        "        # RX_DATA / RX_MONITOR / ECHO are routed to the active\n"
        "        # screen's rx_display via the mode's on_data_received callback\n"
        "        # (_wire_mode_callbacks → _on_mode_data_received).\n"
        "        # Writing here as well would produce duplicate output.\n"
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
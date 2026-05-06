"""
patch_button_guard.py
=====================
Verhindert dass ein aktiver SEND oder RECEIVE Button durch erneuten
Klick deaktiviert werden kann.

Lösung: am Anfang von _on_send_toggled und _on_receive_toggled:
    if not checked: return

Damit wird checked=False (= Klick auf aktiven Button) ignoriert.
Der Button bleibt optisch und logisch aktiv.

Zieldatei: src/pk232py/ui/screens/opmode_rtty_base.py

Aufruf vom Repo-Root:
    python patch_button_guard.py
"""

from pathlib import Path
import ast

TARGET = Path("src/pk232py/ui/screens/opmode_rtty_base.py")

PATCHES = [
    (
        "    def _on_send_toggled(self, checked: bool) -> None:\n"
        "        if checked:\n"
        "            self.btn_receive.blockSignals(True)\n",

        "    def _on_send_toggled(self, checked: bool) -> None:\n"
        "        if not checked:\n"
        "            return   # already active — ignore re-click\n"
        "        if checked:\n"
        "            self.btn_receive.blockSignals(True)\n",
    ),
    (
        "    def _on_receive_toggled(self, checked: bool) -> None:\n"
        "        if checked:\n"
        "            self._blink_timer.stop()\n",

        "    def _on_receive_toggled(self, checked: bool) -> None:\n"
        "        if not checked:\n"
        "            return   # already active — ignore re-click\n"
        "        if checked:\n"
        "            self._blink_timer.stop()\n",
    ),
]


def apply(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    for i, (old, new) in enumerate(PATCHES, 1):
        if old in src:
            src = src.replace(old, new, 1)
            print(f"OK  Patch {i} angewendet")
            fixes += 1
        else:
            # Prüfe ob Guard bereits vorhanden
            guard = "if not checked:\n            return   # already active"
            if guard in src:
                print(f"OK  Patch {i}: Guard bereits vorhanden")
                fixes += 1
            else:
                print(f"WARN Patch {i}: Suchstring nicht gefunden")

    if src == original:
        print("Keine Änderungen nötig.")
        return

    try:
        ast.parse(src)
        print("Syntax OK")
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e} — Datei nicht geschrieben")
        return

    path.write_text(src, encoding="utf-8")
    print(f"Fertig — {path} aktualisiert "
          f"({len(src.splitlines())} Zeilen, {fixes} Fix(e))")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply(TARGET)
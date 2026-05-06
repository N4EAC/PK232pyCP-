"""
patch_wire_char_ready.py
========================
Verdrahtet das char_ready Signal des Screens in _wire_screen_buttons().

char_ready wird vom Screen emittiert wenn SEND aktiv ist und eine
Taste gedrückt wird. MainWindow._on_rtty_char_ready() sendet das
Zeichen und zeigt es im RX-Fenster an.

Ohne diese Verdrahtung kommt das Signal an aber niemand empfängt es.

Aufruf:
  python patch_wire_char_ready.py
  python "%USERPROFILE%\\Downloads\\patch_wire_char_ready.py"
"""

from pathlib import Path
import ast, sys

TARGET = Path("src/pk232py/ui/main_window.py")


def apply(path: Path) -> None:
    print(f"Arbeitsverzeichnis : {Path.cwd()}")
    print(f"Zieldatei          : {path.resolve()}")
    print(f"Datei gefunden     : {path.exists()}")
    print()

    if not path.exists():
        print("FEHLER: Datei nicht gefunden.")
        sys.exit(1)

    src = path.read_text(encoding="utf-8")

    # Prüfe ob bereits verdrahtet
    if "char_ready.connect(self._on_rtty_char_ready)" in src:
        print("OK  char_ready bereits verdrahtet — kein Patch nötig.")
        return

    # Suchstring: Ende von _wire_screen_buttons, nach _wire_navtex_filters
    old = (
        "        # Phase 3 — identity fields, spinboxes, toggles, NAVTEX filters\n"
        "        self._wire_identity_fields(screen)\n"
        "        self._wire_morse_params(screen)\n"
        "        self._wire_toggle_buttons(screen)\n"
        "        self._wire_navtex_filters(screen)"
    )
    new = (
        "        # Phase 3 — identity fields, spinboxes, toggles, NAVTEX filters\n"
        "        self._wire_identity_fields(screen)\n"
        "        self._wire_morse_params(screen)\n"
        "        self._wire_toggle_buttons(screen)\n"
        "        self._wire_navtex_filters(screen)\n"
        "\n"
        "        # char_ready: emitted by screen eventFilter per keypress\n"
        "        # while SEND is active → _on_rtty_char_ready sends + RX echo\n"
        "        if hasattr(screen, \"char_ready\"):\n"
        "            try:\n"
        "                screen.char_ready.disconnect(self._on_rtty_char_ready)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "            screen.char_ready.connect(self._on_rtty_char_ready)"
    )

    if old not in src:
        print("FEHLER: Suchstring nicht gefunden.")
        idx = src.find("_wire_navtex_filters")
        if idx >= 0:
            print(f"  Kontext: {repr(src[idx:idx+120])}")
        sys.exit(1)

    src2 = src.replace(old, new, 1)

    try:
        ast.parse(src2)
        print("Syntax OK")
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e}")
        sys.exit(1)

    path.write_text(src2, encoding="utf-8")
    print("OK  char_ready in _wire_screen_buttons verdrahtet")
    print(f"Fertig — {path} aktualisiert ({len(src2.splitlines())} Zeilen)")


if __name__ == "__main__":
    apply(TARGET)
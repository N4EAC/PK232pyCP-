"""
patch_fix_cursor.py
===================
Ergänzt Block-Cursor auf allen TX-Fenstern in _apply_appearance().

Aufruf vom Repo-Root:
    python patch_fix_cursor.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")


def apply(path: Path) -> None:
    src = path.read_text(encoding="utf-8")

    old = (
        "            if hasattr(screen, \"tx_input\"):\n"
        "                screen.tx_input.setFont(font)\n"
        "                screen.tx_input.setStyleSheet(style_tx)\n"
        "        # Verbose terminal view"
    )
    new = (
        "            if hasattr(screen, \"tx_input\"):\n"
        "                screen.tx_input.setFont(font)\n"
        "                screen.tx_input.setStyleSheet(style_tx)\n"
        "                # Block cursor: width = one average character\n"
        "                char_w = screen.tx_input.fontMetrics().averageCharWidth()\n"
        "                screen.tx_input.setCursorWidth(char_w)\n"
        "        # Verbose terminal view"
    )

    if old not in src:
        print("FEHLER: Suchstring nicht gefunden")
        print(f"Suche nach: {repr(old[:80])}")
        # Diagnose
        idx = src.find("screen.tx_input.setStyleSheet(style_tx)")
        if idx >= 0:
            print(f"Kontext gefunden:\n{repr(src[idx-20:idx+120])}")
        return

    import ast
    src2 = src.replace(old, new, 1)
    try:
        ast.parse(src2)
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e}")
        return

    path.write_text(src2, encoding="utf-8")
    print("OK  Block-Cursor in _apply_appearance() ergänzt")
    print(f"Fertig — {path} aktualisiert ({len(src2.splitlines())} Zeilen)")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply(TARGET)
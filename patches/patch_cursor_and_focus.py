"""
patch_cursor_and_focus.py
=========================
Fix 1: Block-Cursor auch auf _vt_input im Verbose Terminal
Fix 2: Nach SEND-Klick Focus zurück ins TX-Fenster setzen

Aufruf vom Repo-Root:
    python patch_cursor_and_focus.py
"""

from pathlib import Path
import ast

TARGET = Path("src/pk232py/ui/main_window.py")


def apply(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    # ── Fix 1: Block-Cursor auf _vt_input ────────────────────────────────────
    old1 = (
        "        self._vt_input.setFont(font)\n"
        "        self._vt_input.setStyleSheet(\n"
        "            f\"background-color:{a.bg_color}; \"\n"
        "            f\"color:{a.fg_color}; border:none;\"\n"
        "        )\n"
        "        logger.debug(\"Appearance applied: %s %dpt bg=%s fg=%s\","
    )
    new1 = (
        "        self._vt_input.setFont(font)\n"
        "        self._vt_input.setStyleSheet(\n"
        "            f\"background-color:{a.bg_color}; \"\n"
        "            f\"color:{a.fg_color}; border:none;\"\n"
        "        )\n"
        "        # Block cursor on verbose terminal input\n"
        "        char_w_vt = self._vt_input.fontMetrics().averageCharWidth()\n"
        "        self._vt_input.setCursorWidth(char_w_vt)\n"
        "        logger.debug(\"Appearance applied: %s %dpt bg=%s fg=%s\","
    )
    if old1 in src:
        src = src.replace(old1, new1, 1)
        print("OK  Fix 1: Block-Cursor auf _vt_input")
        fixes += 1
    else:
        print("WARN Fix 1: Suchstring nicht gefunden")
        idx = src.find("self._vt_input.setCursorWidth")
        if idx >= 0:
            print("     → Block-Cursor bereits vorhanden")
            fixes += 1  # schon drin, zählt als OK

    # ── Fix 2: Focus zurück ins TX-Fenster nach SEND ─────────────────────────
    old2 = (
        "            # 3. Wire live-TX: every new character goes out immediately\n"
        "            try:\n"
        "                tx.textChanged.disconnect(self._on_rtty_text_changed)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "            tx.textChanged.connect(self._on_rtty_text_changed)"
    )
    new2 = (
        "            # 3. Wire live-TX: every new character goes out immediately\n"
        "            try:\n"
        "                tx.textChanged.disconnect(self._on_rtty_text_changed)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "            tx.textChanged.connect(self._on_rtty_text_changed)\n"
        "\n"
        "            # 4. Return keyboard focus to TX window\n"
        "            #    (btn_send has NoFocus but focus may have drifted)\n"
        "            QTimer.singleShot(0, tx.setFocus)"
    )
    if old2 in src:
        src = src.replace(old2, new2, 1)
        print("OK  Fix 2: Focus nach SEND zurück ins TX-Fenster")
        fixes += 1
    else:
        print("WARN Fix 2: Suchstring nicht gefunden")
        if "QTimer.singleShot(0, tx.setFocus)" in src:
            print("     → Focus-Rückgabe bereits vorhanden")
            fixes += 1

    # ── Syntaxcheck + Schreiben ───────────────────────────────────────────────
    if src == original:
        print(f"\nKeine Änderungen vorgenommen.")
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
"""
patch_tx_final.py
=================
Zwei verbleibende Fixes für das TX-Keypressevent System:

Fix 1: _on_screen_send(True) — zeichenweiser Buffer-Flush statt
       _send_rtty_text + textChanged

Fix 2: char_ready Signal in _wire_screen_buttons verdrahten

Aufruf:
  python patch_tx_final.py
  python "%USERPROFILE%\\Downloads\\patch_tx_final.py"
"""

from pathlib import Path
import ast, sys

TARGET = Path("src/pk232py/ui/main_window.py")


def apply(path):
    print(f"Arbeitsverzeichnis : {Path.cwd()}")
    print(f"Zieldatei          : {path.resolve()}")
    print(f"Datei gefunden     : {path.exists()}")
    print()

    if not path.exists():
        print("FEHLER: Datei nicht gefunden.")
        sys.exit(1)

    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    # ── Fix 1: _on_screen_send(True) — Buffer-Flush zeichenweise ─────────────
    old1 = (
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
        "            # 4. Return keyboard focus to TX window\n"
        "            #    (btn_send has NoFocus but focus may have drifted)\n"
        "            QTimer.singleShot(0, tx.setFocus)"
    )
    new1 = (
        "            # 2. Flush buffered TX content char by char.\n"
        "            #    TX window shrinks from front as each char is sent.\n"
        "            #    RX window shows each char as TX echo (yellow).\n"
        "            buffered = tx.toPlainText()\n"
        "            if buffered:\n"
        "                from PyQt6.QtGui import QTextCursor\n"
        "                for ch in buffered:\n"
        "                    tx.blockSignals(True)\n"
        "                    c = tx.textCursor()\n"
        "                    c.movePosition(QTextCursor.MoveOperation.Start)\n"
        "                    c.deleteChar()\n"
        "                    tx.setTextCursor(c)\n"
        "                    tx.blockSignals(False)\n"
        "                    self._on_rtty_char_ready(ch)\n"
        "\n"
        "            # 3. Return keyboard focus to TX window\n"
        "            QTimer.singleShot(0, tx.setFocus)"
    )
    if old1 in src:
        src = src.replace(old1, new1, 1)
        print("OK  Fix 1: Buffer-Flush zeichenweise in _on_screen_send")
        fixes += 1
    elif "c.movePosition(QTextCursor.MoveOperation.Start)" in src:
        print("OK  Fix 1: Buffer-Flush bereits vorhanden")
        fixes += 1
    else:
        print("FEHLER Fix 1: Suchstring nicht gefunden")
        idx = src.find("# 2. Send any text already in TX window")
        if idx >= 0:
            print(f"  Kontext: {repr(src[idx:idx+400])}")

    # ── Fix 2: _on_screen_send(False) — alten textChanged disconnect entfernen
    old2 = (
        "            # 2. Disconnect live-TX\n"
        "            try:\n"
        "                tx.textChanged.disconnect(self._on_rtty_text_changed)\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "\n"
        "            # 3. Send RCVE — TNC switches back to receive\n"
        "            rcve = build_command(b'RC')"
    )
    new2 = (
        "            # 2. Send RCVE — TNC switches back to receive.\n"
        "            #    Unsent chars remain in TX window as buffer.\n"
        "            rcve = build_command(b'RC')"
    )
    if old2 in src:
        src = src.replace(old2, new2, 1)
        print("OK  Fix 2: textChanged disconnect aus else-Zweig entfernt")
        fixes += 1
    else:
        print("OK  Fix 2: textChanged disconnect bereits entfernt")
        fixes += 1

    # ── Fix 3: char_ready in _wire_screen_buttons verdrahten ─────────────────
    if "char_ready" not in src:
        old3 = (
            "        # SEND button — toggled ON: activate TX; toggled OFF: no-op\n"
            "        if hasattr(screen, \"btn_send\"):\n"
            "            try:\n"
            "                screen.btn_send.toggled.disconnect(self._on_screen_send)\n"
            "            except (RuntimeError, TypeError):\n"
            "                pass   # not connected yet — harmless\n"
            "            screen.btn_send.toggled.connect(self._on_screen_send)"
        )
        new3 = (
            "        # SEND button — toggled ON: activate TX; toggled OFF: no-op\n"
            "        if hasattr(screen, \"btn_send\"):\n"
            "            try:\n"
            "                screen.btn_send.toggled.disconnect(self._on_screen_send)\n"
            "            except (RuntimeError, TypeError):\n"
            "                pass   # not connected yet — harmless\n"
            "            screen.btn_send.toggled.connect(self._on_screen_send)\n"
            "\n"
            "        # char_ready: emitted by screen eventFilter per keypress\n"
            "        # while SEND is active → _on_rtty_char_ready sends + echoes\n"
            "        if hasattr(screen, \"char_ready\"):\n"
            "            try:\n"
            "                screen.char_ready.disconnect(self._on_rtty_char_ready)\n"
            "            except (RuntimeError, TypeError):\n"
            "                pass\n"
            "            screen.char_ready.connect(self._on_rtty_char_ready)"
        )
        if old3 in src:
            src = src.replace(old3, new3, 1)
            print("OK  Fix 3: char_ready in _wire_screen_buttons verdrahtet")
            fixes += 1
        else:
            print("FEHLER Fix 3: _wire_screen_buttons Anker nicht gefunden")
            idx = src.find("btn_send.toggled.connect(self._on_screen_send)")
            if idx >= 0:
                print(f"  Kontext: {repr(src[max(0,idx-200):idx+100])}")
    else:
        print("OK  Fix 3: char_ready bereits verdrahtet")
        fixes += 1

    # ── Syntaxcheck + Schreiben ───────────────────────────────────────────────
    if src == original:
        print("\nKeine Aenderungen vorgenommen.")
        return

    try:
        ast.parse(src)
        print("Syntax OK")
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e} — Datei nicht geschrieben")
        sys.exit(1)

    path.write_text(src, encoding="utf-8")
    print(f"Fertig — {path} aktualisiert "
          f"({len(src.splitlines())} Zeilen, {fixes} Fix(e))")


if __name__ == "__main__":
    apply(TARGET)
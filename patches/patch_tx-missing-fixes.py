"""
patch_tx_missing_fixes.py
=========================
Nachpatch für die 3 WARN-Fixes aus patch_tx_keypressevent.py:

  WARN Fix 3 (screen):   eventFilter in opmode_rtty_base.py
  WARN Fix 1 (main):     _on_screen_send Buffer-Flush
  WARN Fix 3 (main):     char_ready in _wire_screen_buttons

Aufruf:
  python patch_tx_missing_fixes.py
  python "%USERPROFILE%\\Downloads\\patch_tx_missing_fixes.py"
"""

from pathlib import Path
import ast, sys

TARGET_SCREEN = Path("src/pk232py/ui/screens/opmode_rtty_base.py")
TARGET_MAIN   = Path("src/pk232py/ui/main_window.py")


def patch_screen(path):
    print(f"\n--- {path} ---")
    src = path.read_text(encoding="utf-8")
    original = src

    # eventFilter: exakter Suchstring aus aktuellen Sources
    old = (
        "    def eventFilter(self, obj, event) -> bool:\n"
        "        \"\"\"Sicherheitsnetz: jeder Tastendruck landet im TX-Fenster.\n"
        "\n"
        "        Wird ein KeyPress-Event von einem Widget ausgelöst, das KEIN\n"
        "        Texteingabe-Widget ist (QTextEdit / QLineEdit), leiten wir das\n"
        "        Event direkt ans TX-Fenster weiter.\n"
        "\n"
        "        Das greift auch dann, wenn ein Button versehentlich doch Focus\n"
        "        bekommen hat (z.B. per Tab-Taste).\n"
        "        \"\"\"\n"
        "        if event.type() == QEvent.Type.KeyPress:\n"
        "            focused = self.focusWidget()\n"
        "            # Wenn der Focus bereits in einem Eingabefeld ist → normal weiter\n"
        "            if isinstance(focused, (QTextEdit, QLineEdit)):\n"
        "                return super().eventFilter(obj, event)\n"
        "            # Sonst: Event ans TX-Fenster schicken, falls vorhanden\n"
        "            if hasattr(self, \"tx_input\") and self.tx_input is not None:\n"
        "                self.tx_input.setFocus()\n"
        "                # Event an das TX-Fenster weiterleiten\n"
        "                from PyQt6.QtWidgets import QApplication\n"
        "                QApplication.sendEvent(self.tx_input, event)\n"
        "                return True   # Event als behandelt markieren\n"
        "        return super().eventFilter(obj, event)"
    )
    new = (
        "    def eventFilter(self, obj, event) -> bool:\n"
        "        \"\"\"Route keypresses depending on SEND/RECEIVE state.\n"
        "\n"
        "        RECEIVE active:\n"
        "          Keypresses go to tx_input normally (editable, Backspace OK).\n"
        "\n"
        "        SEND active:\n"
        "          Printable chars + Enter are written to tx_input (display)\n"
        "          AND emitted via char_ready(char) for sending + RX echo.\n"
        "          Backspace/Delete/arrows are ignored while SEND is active.\n"
        "        \"\"\"\n"
        "        from PyQt6.QtCore import QEvent\n"
        "        from PyQt6.QtWidgets import QApplication\n"
        "\n"
        "        if event.type() == QEvent.Type.KeyPress:\n"
        "            send_active = (\n"
        "                hasattr(self, 'btn_send') and self.btn_send.isChecked()\n"
        "            )\n"
        "\n"
        "            if send_active and hasattr(self, 'tx_input'):\n"
        "                key  = event.key()\n"
        "                text = event.text()\n"
        "                # Enter/Return -> CR/LF: show in TX + emit\n"
        "                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):\n"
        "                    self.tx_input.insertPlainText('\\n')\n"
        "                    self.char_ready.emit('\\r\\n')\n"
        "                    return True\n"
        "                # Printable char: show in TX + emit for send/RX echo\n"
        "                if text and text.isprintable():\n"
        "                    self.tx_input.insertPlainText(text)\n"
        "                    self.char_ready.emit(text)\n"
        "                    return True\n"
        "                # Backspace, Delete, arrows: ignore while SEND active\n"
        "                return True\n"
        "\n"
        "            # RECEIVE active: redirect to tx_input if focus is elsewhere\n"
        "            focused = self.focusWidget()\n"
        "            if isinstance(focused, (QTextEdit, QLineEdit)):\n"
        "                return super().eventFilter(obj, event)\n"
        "            if hasattr(self, 'tx_input') and self.tx_input is not None:\n"
        "                self.tx_input.setFocus()\n"
        "                QApplication.sendEvent(self.tx_input, event)\n"
        "                return True\n"
        "\n"
        "        return super().eventFilter(obj, event)"
    )

    if old in src:
        src = src.replace(old, new, 1)
        print("OK  eventFilter ersetzt")
    elif "char_ready.emit" in src:
        print("OK  eventFilter bereits aktuell")
    else:
        print("FEHLER: eventFilter Suchstring nicht gefunden")
        # Diagnose
        idx = src.find("def eventFilter")
        if idx >= 0:
            print(f"  Gefunden ab Pos {idx}: {repr(src[idx:idx+120])}")
        return False

    if src != original:
        try:
            ast.parse(src)
        except SyntaxError as e:
            print(f"FEHLER Syntax: {e}"); return False
        path.write_text(src, encoding="utf-8")
        print(f"Syntax OK — {path} aktualisiert ({len(src.splitlines())} Zeilen)")
    return True


def patch_main(path):
    print(f"\n--- {path} ---")
    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    # Fix 1: _on_screen_send(True) — aktueller Stand aus Sources
    old1 = (
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
        "            # 3. Return keyboard focus to TX window\n"
        "            QTimer.singleShot(0, tx.setFocus)"
    )
    new1 = (
        "        if active:\n"
        "            # 1. Send XMIT — TNC keys PTT and starts DIDDLE\n"
        "            xmit = build_command(b'XM')\n"
        "            self._serial.send_command(xmit[2:4], xmit[4:-1])\n"
        "            self._log_monitor(\"[TX] XMIT — PTT ON, DIDDLE started\")\n"
        "\n"
        "            # 2. Flush buffered TX content char by char.\n"
        "            #    TX window shrinks from front as each char is sent.\n"
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
        print("OK  Fix 1: Buffer-Flush in _on_screen_send")
        fixes += 1
    elif "c.movePosition(QTextCursor.MoveOperation.Start)" in src:
        print("OK  Fix 1: Buffer-Flush bereits vorhanden")
        fixes += 1
    else:
        print("WARN Fix 1: Suchstring nicht gefunden")
        idx = src.find("# 1. Send XMIT")
        if idx >= 0:
            print(f"  Kontext: {repr(src[idx:idx+300])}")

    # Fix 3: char_ready in _wire_screen_buttons
    if "char_ready" not in src:
        old3 = (
            "        # SEND button — toggled ON: activate TX; toggled OFF: stop TX\n"
            "        if hasattr(screen, \"btn_send\"):\n"
            "            try:\n"
            "                screen.btn_send.toggled.disconnect(self._on_screen_send)\n"
            "            except (RuntimeError, TypeError):\n"
            "                pass   # not connected yet — harmless\n"
            "            screen.btn_send.toggled.connect(self._on_screen_send)"
        )
        new3 = (
            "        # SEND button — toggled ON: activate TX; toggled OFF: stop TX\n"
            "        if hasattr(screen, \"btn_send\"):\n"
            "            try:\n"
            "                screen.btn_send.toggled.disconnect(self._on_screen_send)\n"
            "            except (RuntimeError, TypeError):\n"
            "                pass   # not connected yet — harmless\n"
            "            screen.btn_send.toggled.connect(self._on_screen_send)\n"
            "\n"
            "        # char_ready: screen emits per keypress while SEND active\n"
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
            print("WARN Fix 3: _wire_screen_buttons Anker nicht gefunden")
            idx = src.find("btn_send.toggled.connect(self._on_screen_send)")
            if idx >= 0:
                print(f"  Kontext: {repr(src[idx-200:idx+100])}")
    else:
        print("OK  Fix 3: char_ready bereits verdrahtet")
        fixes += 1

    if src == original:
        print("Keine Aenderungen."); return True

    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e}"); return False

    path.write_text(src, encoding="utf-8")
    print(f"Syntax OK — {path} aktualisiert ({len(src.splitlines())} Zeilen, {fixes} Fix(e))")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("patch_tx_missing_fixes.py")
    print("=" * 60)
    print(f"Arbeitsverzeichnis: {Path.cwd()}")
    ok1 = patch_screen(TARGET_SCREEN)
    ok2 = patch_main(TARGET_MAIN)
    print()
    print("Abgeschlossen." if (ok1 and ok2) else "Fehler — bitte Ausgabe pruefen.")
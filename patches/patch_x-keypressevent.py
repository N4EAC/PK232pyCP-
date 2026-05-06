"""
patch_tx_keypressevent.py  v2
==============================
SEND aktiv — Tastendruck:
  → Zeichen ins TX-Fenster (anzeigen)
  → char_ready.emit(char) → senden + RX-Fenster gelb

RECEIVE aktiv — Tastendruck:
  → Zeichen ins TX-Fenster (editierbar, Backspace OK)
  → nichts senden

RECEIVE → SEND:
  → TX-Puffer zeichenweise senden
  → TX-Fenster leert sich zeichenweise von vorne
  → jedes Zeichen im RX-Fenster

SEND → RECEIVE:
  → Aussendung stoppen (RC)
  → nicht gesendete Zeichen bleiben im TX-Fenster als Puffer

Aufruf:
  python patch_tx_keypressevent.py
  python "%USERPROFILE%\\Downloads\\patch_tx_keypressevent.py"
"""

from pathlib import Path
import ast, sys

TARGET_SCREEN = Path("src/pk232py/ui/screens/opmode_rtty_base.py")
TARGET_MAIN   = Path("src/pk232py/ui/main_window.py")


def patch_screen(path):
    print(f"\n--- {path} ---")
    if not path.exists():
        print("FEHLER: Datei nicht gefunden"); return False

    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    # Fix 1: pyqtSignal Import
    if "pyqtSignal" not in src:
        old = "from PyQt6.QtCore import"
        new = "from PyQt6.QtCore import pyqtSignal, "
        if old in src:
            src = src.replace(old, new, 1)
            print("OK  Fix 1: pyqtSignal Import ergaenzt"); fixes += 1
        else:
            print("WARN Fix 1: QtCore Import nicht gefunden")
    else:
        print("OK  Fix 1: pyqtSignal bereits vorhanden"); fixes += 1

    # Fix 2: char_ready Signal
    if "char_ready = pyqtSignal(str)" not in src:
        old = (
            "    BAUD_VALUES:  list[str] = RBAUD_VALUES   "
            "# Default = Baudot-Werte aus Modul-Konstante\n"
            "\n"
            "    def __init__(self, parent=None):"
        )
        new = (
            "    BAUD_VALUES:  list[str] = RBAUD_VALUES   "
            "# Default = Baudot-Werte aus Modul-Konstante\n"
            "\n"
            "    # Emitted when SEND is active and user presses a printable key.\n"
            "    # Connected by MainWindow to _on_rtty_char_ready().\n"
            "    char_ready = pyqtSignal(str)\n"
            "\n"
            "    def __init__(self, parent=None):"
        )
        if old in src:
            src = src.replace(old, new, 1)
            print("OK  Fix 2: char_ready Signal hinzugefuegt"); fixes += 1
        else:
            print("WARN Fix 2: Anker nicht gefunden")
    else:
        print("OK  Fix 2: char_ready bereits vorhanden"); fixes += 1

    # Fix 3: eventFilter ersetzen
    # Suche nach der bestehenden eventFilter-Methode — beide bekannten Varianten
    EF_OLD_A = (
        "    def eventFilter(self, obj, event) -> bool:\n"
        "        \"\"\"\n"
        "        Wird ein KeyPress-Event von einem Widget ausgeloest, das KEIN\n"
    )
    EF_OLD_B = (
        "    def eventFilter(self, obj, event) -> bool:\n"
        "        \"\"\"\n"
        "        Wird ein KeyPress-Event von einem Widget ausgelöst, das KEIN\n"
    )
    EF_OLD_C = (
        "    def eventFilter(self, obj, event) -> bool:\n"
        "        \"\"\"Route keypresses to TX window or emit char_ready when SEND active.\n"
    )
    EF_NEW = (
        "    def eventFilter(self, obj, event) -> bool:\n"
        "        \"\"\"Route keypresses correctly depending on SEND/RECEIVE state.\n"
        "\n"
        "        RECEIVE active:\n"
        "          Keypresses go to tx_input normally (editable, Backspace OK).\n"
        "\n"
        "        SEND active:\n"
        "          Printable chars and Enter are written to tx_input (display)\n"
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
        "                # Enter/Return -> CR/LF\n"
        "                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):\n"
        "                    self.tx_input.insertPlainText('\\n')\n"
        "                    self.char_ready.emit('\\r\\n')\n"
        "                    return True\n"
        "                # Printable character: show in TX + emit for send/RX\n"
        "                if text and text.isprintable():\n"
        "                    self.tx_input.insertPlainText(text)\n"
        "                    self.char_ready.emit(text)\n"
        "                    return True\n"
        "                # Backspace, Delete, arrows -> ignore while SEND active\n"
        "                return True\n"
        "\n"
        "            # RECEIVE active: redirect to tx_input if focus elsewhere\n"
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

    found_ef = False
    for marker in (EF_OLD_A, EF_OLD_B, EF_OLD_C):
        if marker in src:
            # Finde vollständige Methode: von marker bis zur nächsten def
            idx = src.find(marker)
            end = src.find("\n    def ", idx + len(marker))
            if end >= 0:
                old_ef = src[idx:end]
                src = src.replace(old_ef, EF_NEW, 1)
                print("OK  Fix 3: eventFilter ersetzt"); fixes += 1
                found_ef = True
                break
    if not found_ef:
        if "char_ready.emit" in src:
            print("OK  Fix 3: eventFilter bereits korrekt"); fixes += 1
        else:
            print("WARN Fix 3: eventFilter nicht gefunden")

    if src == original:
        print("Keine Aenderungen."); return True

    try:
        ast.parse(src)
        print("Syntax OK")
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e}"); return False

    path.write_text(src, encoding="utf-8")
    print(f"Fertig ({len(src.splitlines())} Zeilen, {fixes} Fix(e))")
    return True


def patch_main(path):
    print(f"\n--- {path} ---")
    if not path.exists():
        print("FEHLER: Datei nicht gefunden"); return False

    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    # Fix 1: _on_screen_send(True) — Buffer-Flush zeichenweise
    SEND_TRUE_MARKERS = [
        # Variante A: original
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
        "            # Track how many chars have already been sent\n"
        "            # so _on_rtty_text_changed only sends the new tail.\n"
        "            self._rtty_tx_pos = len(tx.toPlainText())\n"
        "            tx.textChanged.connect(self._on_rtty_text_changed)\n"
        "\n"
        "            # 4. Return keyboard focus to TX window\n"
        "            #    (btn_send has NoFocus but focus may have drifted)\n"
        "            QTimer.singleShot(0, tx.setFocus)",
        # Variante B: v1-patch (simpler flush)
        "            # 2. Flush buffered TX content char by char\n"
        "            #    (text typed while RECEIVE was active)\n"
        "            buffered = tx.toPlainText()\n"
        "            if buffered:\n"
        "                tx.blockSignals(True)\n"
        "                tx.clear()\n"
        "                tx.blockSignals(False)\n"
        "                for ch in buffered:\n"
        "                    self._on_rtty_char_ready(ch)\n"
        "\n"
        "            # 3. Return keyboard focus to TX window\n"
        "            #    Screen's eventFilter now intercepts keys directly.\n"
        "            QTimer.singleShot(0, tx.setFocus)",
    ]
    SEND_TRUE_NEW = (
        "            # 2. Flush buffered TX content char by char.\n"
        "            #    Each char: TX window shrinks from front, RX shows echo.\n"
        "            buffered = tx.toPlainText()\n"
        "            if buffered:\n"
        "                from PyQt6.QtGui import QTextCursor\n"
        "                for ch in buffered:\n"
        "                    # Remove first char from TX window\n"
        "                    tx.blockSignals(True)\n"
        "                    c = tx.textCursor()\n"
        "                    c.movePosition(QTextCursor.MoveOperation.Start)\n"
        "                    c.deleteChar()\n"
        "                    tx.setTextCursor(c)\n"
        "                    tx.blockSignals(False)\n"
        "                    # Send + RX echo\n"
        "                    self._on_rtty_char_ready(ch)\n"
        "\n"
        "            # 3. Return keyboard focus to TX window\n"
        "            QTimer.singleShot(0, tx.setFocus)"
    )
    found = False
    for marker in SEND_TRUE_MARKERS:
        if marker in src:
            src = src.replace(marker, SEND_TRUE_NEW, 1)
            print("OK  Fix 1: _on_screen_send Buffer-Flush zeichenweise"); fixes += 1
            found = True; break
    if not found:
        if "c.movePosition(QTextCursor.MoveOperation.Start)" in src:
            print("OK  Fix 1: Buffer-Flush bereits vorhanden"); fixes += 1
        else:
            print("WARN Fix 1: _on_screen_send if-Zweig nicht gefunden")

    # Fix 2: textChanged disconnect aus else-Zweig entfernen
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
        "            #    Unsent chars remain in TX window as buffer for next SEND.\n"
        "            rcve = build_command(b'RC')"
    )
    if old2 in src:
        src = src.replace(old2, new2, 1)
        print("OK  Fix 2: textChanged disconnect entfernt"); fixes += 1
    else:
        print("OK  Fix 2: textChanged disconnect bereits entfernt"); fixes += 1

    # Fix 3: char_ready verdrahten
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
            "        # char_ready: screen emits this on each keypress while SEND active\n"
            "        if hasattr(screen, \"char_ready\"):\n"
            "            try:\n"
            "                screen.char_ready.disconnect(self._on_rtty_char_ready)\n"
            "            except (RuntimeError, TypeError):\n"
            "                pass\n"
            "            screen.char_ready.connect(self._on_rtty_char_ready)"
        )
        if old3 in src:
            src = src.replace(old3, new3, 1)
            print("OK  Fix 3: char_ready verdrahtet"); fixes += 1
        else:
            print("WARN Fix 3: _wire_screen_buttons Anker nicht gefunden")
    else:
        print("OK  Fix 3: char_ready bereits verdrahtet"); fixes += 1

    # Fix 4: _on_rtty_char_ready einfuegen
    if "_on_rtty_char_ready" not in src:
        old4 = "    def _on_rtty_text_changed(self) -> None:"
        new4 = (
            "    def _on_rtty_char_ready(self, char: str) -> None:\n"
            "        \"\"\"Send one character and echo it in the RX window.\n"
            "\n"
            "        Called from screen eventFilter (live typing while SEND active)\n"
            "        and from _on_screen_send(True) when flushing the TX buffer.\n"
            "        CR/LF is shown as '<CR/LF>' in the RX window.\n"
            "        \"\"\"\n"
            "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
            "            return\n"
            "\n"
            "        if char in ('\\r\\n', '\\n'):\n"
            "            display = '<CR/LF>\\n'\n"
            "            wire    = b'\\r\\n'\n"
            "        elif char == '\\r':\n"
            "            display = '<CR>\\n'\n"
            "            wire    = b'\\r'\n"
            "        else:\n"
            "            display = char\n"
            "            wire    = char.encode('ascii', errors='replace')\n"
            "\n"
            "        self._serial.send_data(wire, channel=0)\n"
            "\n"
            "        from PyQt6.QtGui import QTextCursor, QColor\n"
            "        rx = self._rx_display\n"
            "        cursor = rx.textCursor()\n"
            "        cursor.movePosition(QTextCursor.MoveOperation.End)\n"
            "        fmt = cursor.charFormat()\n"
            "        fmt.setForeground(QColor('#ffee88'))  # TX yellow\n"
            "        cursor.setCharFormat(fmt)\n"
            "        cursor.insertText(display)\n"
            "        fmt.setForeground(QColor('#88ccff'))  # reset RX blue\n"
            "        cursor.setCharFormat(fmt)\n"
            "        rx.setTextCursor(cursor)\n"
            "        rx.ensureCursorVisible()\n"
            "        self._log_monitor(f'[TX] {char!r}')\n"
            "\n"
            "    def _on_rtty_text_changed(self) -> None:"
        )
        if old4 in src:
            src = src.replace(old4, new4, 1)
            print("OK  Fix 4: _on_rtty_char_ready eingefuegt"); fixes += 1
        else:
            print("WARN Fix 4: Anker _on_rtty_text_changed nicht gefunden")
    else:
        print("OK  Fix 4: _on_rtty_char_ready bereits vorhanden"); fixes += 1

    # Fix 5: alten TX-Echo Block aus _send_rtty_text entfernen
    old5 = (
        "        # Local TX echo: show sent chars in RX window in TX colour\n"
        "        rx = self._rx_display\n"
        "        from PyQt6.QtGui import QTextCursor, QColor\n"
        "        cursor = rx.textCursor()\n"
        "        cursor.movePosition(QTextCursor.MoveOperation.End)\n"
        "        fmt = cursor.charFormat()\n"
        "        fmt.setForeground(QColor(\"#ffee88\"))   # TX yellow\n"
        "        cursor.setCharFormat(fmt)\n"
        "        cursor.insertText(text)\n"
        "        # Reset colour to RX blue for subsequent received text\n"
        "        fmt.setForeground(QColor(\"#88ccff\"))   # RX blue\n"
        "        cursor.setCharFormat(fmt)\n"
        "        rx.setTextCursor(cursor)\n"
        "        rx.ensureCursorVisible()\n"
        "        self._log_monitor(f\"[TX] {text!r}\")"
    )
    new5 = "        self._log_monitor(f\"[TX] {text!r}\")"
    if old5 in src:
        src = src.replace(old5, new5, 1)
        print("OK  Fix 5: Alter TX-Echo aus _send_rtty_text entfernt"); fixes += 1
    else:
        print("OK  Fix 5: Kein alter TX-Echo in _send_rtty_text"); fixes += 1

    if src == original:
        print("Keine Aenderungen."); return True

    try:
        ast.parse(src)
        print("Syntax OK")
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e}"); return False

    path.write_text(src, encoding="utf-8")
    print(f"Fertig ({len(src.splitlines())} Zeilen, {fixes} Fix(e))")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("patch_tx_keypressevent.py  v2")
    print("=" * 60)
    print(f"Arbeitsverzeichnis: {Path.cwd()}")
    ok1 = patch_screen(TARGET_SCREEN)
    ok2 = patch_main(TARGET_MAIN)
    print()
    if ok1 and ok2:
        print("Alle Patches abgeschlossen.")
    else:
        print("Ein oder mehrere Patches fehlgeschlagen.")
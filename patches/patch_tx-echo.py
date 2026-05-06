"""
patch_tx_echo.py
================
Gesendete Zeichen werden im RX-Fenster als lokales Echo angezeigt.

_send_rtty_text() schreibt den Text zusätzlich in das RX-Fenster
mit TX-Farbe (#ffee88 gelb) damit der Operator sieht welche Zeichen
gesendet wurden. Farbe wird danach auf RX-Blau zurückgesetzt.

Aufruf vom Repo-Root:
    python patch_tx_echo.py
"""

from pathlib import Path
import ast
import sys

TARGET = Path("src/pk232py/ui/main_window.py")

OLD = (
    "    def _send_rtty_text(self, text: str) -> None:\n"
    "        \"\"\"Send text as a data frame via the active mode.\n"
    "\n"
    "        Baudot mode uppercases automatically via data_frame().\n"
    "        send_data() expects raw payload bytes — not a full Host frame.\n"
    "        \"\"\"\n"
    "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
    "            return\n"
    "        self._serial.send_data(\n"
    "            text.encode('ascii', errors='replace'),\n"
    "            channel=0,\n"
    "        )\n"
    "        self._log_monitor(f\"[TX] {text!r}\")"
)

NEW = (
    "    def _send_rtty_text(self, text: str) -> None:\n"
    "        \"\"\"Send text as a data frame via the active mode.\n"
    "\n"
    "        Baudot mode uppercases automatically via data_frame().\n"
    "        send_data() expects raw payload bytes — not a full Host frame.\n"
    "        Also echoes sent text to RX window (local TX echo) in TX colour\n"
    "        so the operator can see what was transmitted.\n"
    "        \"\"\"\n"
    "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
    "            return\n"
    "        self._serial.send_data(\n"
    "            text.encode('ascii', errors='replace'),\n"
    "            channel=0,\n"
    "        )\n"
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
    "        fmt.setForeground(QColor(\"#88ccff\"))\n"
    "        cursor.setCharFormat(fmt)\n"
    "        rx.setTextCursor(cursor)\n"
    "        rx.ensureCursorVisible()\n"
    "        self._log_monitor(f\"[TX] {text!r}\")"
)


def apply(path: Path) -> None:
    print(f"Arbeitsverzeichnis : {Path.cwd()}")
    print(f"Zieldatei          : {path.resolve()}")
    print(f"Datei gefunden     : {path.exists()}")
    print()

    if not path.exists():
        print("FEHLER: Datei nicht gefunden.")
        print("Bitte aus dem Repo-Root aufrufen:")
        print("  cd E:\\PK232\\pk232py_repo")
        print("  python patch_tx_echo.py")
        sys.exit(1)

    src = path.read_text(encoding="utf-8")

    if OLD not in src:
        print("FEHLER: Suchstring nicht gefunden.")
        idx = src.find("def _send_rtty_text")
        if idx >= 0:
            lines = src[:idx].count('\n') + 1
            print(f"  Vorhandene Version ab Zeile {lines}:")
            print(f"  {repr(src[idx:idx+200])}")
        else:
            print("  _send_rtty_text nicht gefunden.")
        sys.exit(1)

    src2 = src.replace(OLD, NEW, 1)

    try:
        ast.parse(src2)
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e} — Datei nicht geschrieben")
        sys.exit(1)

    path.write_text(src2, encoding="utf-8")
    print("OK  TX-Echo in _send_rtty_text() ergaenzt")
    print("Syntax OK")
    print(f"Fertig — {path} aktualisiert ({len(src2.splitlines())} Zeilen)")


if __name__ == "__main__":
    apply(TARGET)
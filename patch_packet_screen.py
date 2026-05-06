#!/usr/bin/env python3
"""
patch_ctrl_s.py — PK232PY v13: Implement CTRL+S [^S] SOS marker

Applies all changes for the [^S] control character to the live source files.

Usage:
    cd E:\\PK232\\pk232py_repo
    python patch_ctrl_s.py

The script:
  1. Verifies the repo root (looks for src/pk232py).
  2. Creates .bak backups of all touched files.
  3. Applies each patch via exact string replacement.
  4. Reports success or failure for every change.
  5. Exits with code 0 on full success, 1 if any patch failed.
"""

import sys
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[32m  OK\033[0m"
FAIL = "\033[31m FAIL\033[0m"


def patch(path: Path, old: str, new: str, label: str) -> bool:
    """Replace `old` with `new` in `path`. Returns True on success."""
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{FAIL}  [{label}] — search string NOT FOUND in {path.name}")
        return False
    count = text.count(old)
    if count > 1:
        print(f"{FAIL}  [{label}] — search string found {count}x (expected 1) in {path.name}")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{PASS}  [{label}]")
    return True


def backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    print(f"       backup → {bak.name}")


# ---------------------------------------------------------------------------
# Locate repo root
# ---------------------------------------------------------------------------

repo = Path.cwd()
if not (repo / "src" / "pk232py").is_dir():
    print("ERROR: Run this script from the pk232py repo root.")
    print(f"       Current directory: {repo}")
    sys.exit(1)

src = repo / "src" / "pk232py"
print(f"\nRepo root : {repo}")
print(f"Source    : {src}\n")

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

F_CTRL    = src / "ui" / "screens" / "baudot_tx_controller.py"
F_RTTY    = src / "ui" / "screens" / "opmode_rtty_base.py"
F_MAIN    = src / "ui" / "main_window.py"
F_MACRO   = src / "ui" / "screens" / "macro_store.py"
F_HELP    = src / "help" / "help_baudot.md"

for f in [F_CTRL, F_RTTY, F_MAIN, F_MACRO, F_HELP]:
    if not f.exists():
        print(f"ERROR: File not found: {f}")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

print("Creating backups ...")
for f in [F_CTRL, F_RTTY, F_MAIN, F_MACRO, F_HELP]:
    backup(f)
print()

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------

results = []

print("=" * 60)
print("FILE 1: baudot_tx_controller.py")
print("=" * 60)

# 1a — new signal sos_reached
results.append(patch(F_CTRL,
    old='    eot_reached = pyqtSignal()',
    new='    eot_reached = pyqtSignal()\n'
        '    sos_reached = pyqtSignal()   # [^S] marker reached — switch to SEND',
    label="1a  sos_reached signal declaration"
))

# 1b — docstring update
results.append(patch(F_CTRL,
    old='    eot_reached()\n'
        '        CTRL+D EOT marker reached — switch to RECEIVE.\n'
        '    """',
    new='    eot_reached()\n'
        '        CTRL+D EOT marker reached — switch to RECEIVE.\n'
        '    sos_reached()\n'
        '        CTRL+S SOS marker reached — switch to SEND.\n'
        '    """',
    label="1b  docstring: add sos_reached"
))

# 1c — _send_next_char: handle \x13 sentinel after \x04 block
results.append(patch(F_CTRL,
    old='        if char == \'\\x04\':\n'
        '            self._tx_queue.clear()\n'
        '            self._tx_timer.stop()\n'
        '            self.status_msg.emit("EOT marker reached — switching to RECEIVE")\n'
        '            self.eot_reached.emit()\n'
        '            return\n'
        '        self.send_to_tnc.emit(char)',
    new='        if char == \'\\x04\':\n'
        '            self._tx_queue.clear()\n'
        '            self._tx_timer.stop()\n'
        '            self.status_msg.emit("EOT marker reached — switching to RECEIVE")\n'
        '            self.eot_reached.emit()\n'
        '            return\n'
        '        if char == \'\\x13\':\n'
        '            # [^S] SOS marker — do NOT send to TNC, trigger SEND\n'
        '            self.status_msg.emit("[^S] marker reached — switching to SEND")\n'
        '            self.sos_reached.emit()\n'
        '            return\n'
        '        self.send_to_tnc.emit(char)',
    label="1c  _send_next_char: handle \\x13 sentinel"
))

# 1d — still_to_transmit: treat \x13 like \x04
results.append(patch(F_CTRL,
    old="        return any(e['char'] != '\\x04' for e in remaining)",
    new="        return any(e['char'] not in ('\\x04', '\\x13') for e in remaining)",
    label="1d  still_to_transmit: exclude \\x13 from count"
))

print()
print("=" * 60)
print("FILE 2: opmode_rtty_base.py")
print("=" * 60)

# 2a — TxInputWidget.keyPressEvent: add CTRL+S block after CTRL+D block
results.append(patch(F_RTTY,
    old='        # CTRL+D: insert [^D] EOT marker\n'
        '        if mods == Ctrl and key == Qt.Key.Key_D:\n'
        '            f_eot = QTextCharFormat()\n'
        '            f_eot.setForeground(QColor("#ffffff"))\n'
        '            f_eot.setBackground(QColor("#cc4400"))\n'
        '            f_eot.setFontWeight(700)\n'
        '            c = self.textCursor()\n'
        '            eot_doc_pos = c.position()\n'
        '            c.setCharFormat(f_eot)\n'
        '            c.insertText("[^D]")\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            if not hasattr(self, "_eot_positions"):\n'
        '                self._eot_positions: list[int] = []\n'
        '            self._eot_positions.append(eot_doc_pos)\n'
        '            # [^D] = 4 doc chars but 1 _arr entry → 3 extra doc positions\n'
        '            self._doc_extra += 3\n'
        '            self.char_typed.emit("\\x04", "[^D]")\n'
        '            return',
    new='        # CTRL+D: insert [^D] EOT marker (switch to RECEIVE when reached)\n'
        '        if mods == Ctrl and key == Qt.Key.Key_D:\n'
        '            f_eot = QTextCharFormat()\n'
        '            f_eot.setForeground(QColor("#ffffff"))\n'
        '            f_eot.setBackground(QColor("#cc4400"))\n'
        '            f_eot.setFontWeight(700)\n'
        '            c = self.textCursor()\n'
        '            eot_doc_pos = c.position()\n'
        '            c.setCharFormat(f_eot)\n'
        '            c.insertText("[^D]")\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            if not hasattr(self, "_eot_positions"):\n'
        '                self._eot_positions: list[int] = []\n'
        '            self._eot_positions.append(eot_doc_pos)\n'
        '            # [^D] = 4 doc chars but 1 _arr entry → 3 extra doc positions\n'
        '            self._doc_extra += 3\n'
        '            self.char_typed.emit("\\x04", "[^D]")\n'
        '            return\n'
        '\n'
        '        # CTRL+S: insert [^S] SOS marker (switch to SEND when reached)\n'
        '        if mods == Ctrl and key == Qt.Key.Key_S:\n'
        '            f_sos = QTextCharFormat()\n'
        '            f_sos.setForeground(QColor("#ffffff"))\n'
        '            f_sos.setBackground(QColor("#0044cc"))\n'
        '            f_sos.setFontWeight(700)\n'
        '            c = self.textCursor()\n'
        '            sos_doc_pos = c.position()\n'
        '            c.setCharFormat(f_sos)\n'
        '            c.insertText("[^S]")\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            if not hasattr(self, "_eot_positions"):\n'
        '                self._eot_positions: list[int] = []\n'
        '            self._eot_positions.append(sos_doc_pos)\n'
        '            # [^S] = 4 doc chars but 1 _arr entry → 3 extra doc positions\n'
        '            self._doc_extra += 3\n'
        '            self.char_typed.emit("\\x13", "[^S]")\n'
        '            return',
    label="2a  TxInputWidget: CTRL+S block"
))

# 2b — TxInputWidget docstring
results.append(patch(F_RTTY,
    old='    - CTRL+D            — inserts [^D] EOT marker (char = \\x04)',
    new='    - CTRL+D            — inserts [^D] EOT marker (char = \\x04)\n'
        '    - CTRL+S            — inserts [^S] SOS marker (char = \\x13)',
    label="2b  TxInputWidget docstring: add CTRL+S"
))

print()
print("=" * 60)
print("FILE 3: main_window.py")
print("=" * 60)

# 3a — connect sos_reached signal (after eot_reached connect block)
results.append(patch(F_MAIN,
    old='            self._baudot_ctrl.eot_reached.connect(self._on_baudot_eot)',
    new='            self._baudot_ctrl.eot_reached.connect(self._on_baudot_eot)\n'
        '            try:\n'
        '                self._baudot_ctrl.sos_reached.disconnect()\n'
        '            except (RuntimeError, TypeError):\n'
        '                pass\n'
        '            self._baudot_ctrl.sos_reached.connect(self._on_baudot_sos)',
    label="3a  connect sos_reached signal"
))

# 3b — add _on_baudot_sos handler after _on_baudot_eot
results.append(patch(F_MAIN,
    old='    def _on_baudot_eot(self) -> None:\n'
        '        """CTRL+D EOT marker reached — switch to RECEIVE."""\n'
        '        screen = self._opmode_stack.currentWidget()\n'
        '        if hasattr(screen, \'btn_receive\') and not screen.btn_receive.isChecked():\n'
        '            screen.btn_receive.setChecked(True)',
    new='    def _on_baudot_eot(self) -> None:\n'
        '        """CTRL+D EOT marker reached — switch to RECEIVE."""\n'
        '        screen = self._opmode_stack.currentWidget()\n'
        '        if hasattr(screen, \'btn_receive\') and not screen.btn_receive.isChecked():\n'
        '            screen.btn_receive.setChecked(True)\n'
        '\n'
        '    def _on_baudot_sos(self) -> None:\n'
        '        """[^S] SOS marker reached — switch to SEND.\n'
        '\n'
        '        Only activates if we are currently in RECEIVE mode (btn_send not\n'
        '        already checked). Setting btn_send.setChecked(True) fires the\n'
        '        toggled signal, which calls _on_screen_send(True) — same path\n'
        '        as pressing the SEND button manually.\n'
        '        """\n'
        '        screen = self._opmode_stack.currentWidget()\n'
        '        if hasattr(screen, \'btn_send\') and not screen.btn_send.isChecked():\n'
        '            screen.btn_send.setChecked(True)',
    label="3b  add _on_baudot_sos handler"
))

# 3c — _on_macro_clicked: [^S] lookahead (insert elif after [^D] block)
results.append(patch(F_MAIN,
    old="            if text[i:i+4] == '[^D]':\n"
        "                # EOT marker — emit sentinel, insert visual marker in TX\n"
        "                from PyQt6.QtGui import QTextCharFormat as _TCF, QColor as _QC\n"
        "                f_eot = _TCF()\n"
        "                f_eot.setForeground(_QC(\"#ffffff\"))\n"
        "                f_eot.setBackground(_QC(\"#cc4400\"))\n"
        "                f_eot.setFontWeight(700)\n"
        "                tx.setCurrentCharFormat(f_eot)\n"
        "                tx.textCursor().insertText('[^D]')\n"
        "                tx.setCurrentCharFormat(f)\n"
        "                # [^D] = 4 doc chars, 1 _arr entry → track discrepancy\n"
        "                tx._doc_extra = getattr(tx, '_doc_extra', 0) + 3\n"
        "                tx.char_typed.emit('\\x04', '[^D]')\n"
        "                i += 4\n"
        "            elif text[i] == '\\n':",
    new="            if text[i:i+4] == '[^D]':\n"
        "                # EOT marker — emit sentinel, insert visual marker in TX\n"
        "                from PyQt6.QtGui import QTextCharFormat as _TCF, QColor as _QC\n"
        "                f_eot = _TCF()\n"
        "                f_eot.setForeground(_QC(\"#ffffff\"))\n"
        "                f_eot.setBackground(_QC(\"#cc4400\"))\n"
        "                f_eot.setFontWeight(700)\n"
        "                tx.setCurrentCharFormat(f_eot)\n"
        "                tx.textCursor().insertText('[^D]')\n"
        "                tx.setCurrentCharFormat(f)\n"
        "                # [^D] = 4 doc chars, 1 _arr entry → track discrepancy\n"
        "                tx._doc_extra = getattr(tx, '_doc_extra', 0) + 3\n"
        "                tx.char_typed.emit('\\x04', '[^D]')\n"
        "                i += 4\n"
        "            elif text[i:i+4] == '[^S]':\n"
        "                # SOS marker — emit sentinel, insert visual marker in TX\n"
        "                from PyQt6.QtGui import QTextCharFormat as _TCF, QColor as _QC\n"
        "                f_sos = _TCF()\n"
        "                f_sos.setForeground(_QC(\"#ffffff\"))\n"
        "                f_sos.setBackground(_QC(\"#0044cc\"))\n"
        "                f_sos.setFontWeight(700)\n"
        "                tx.setCurrentCharFormat(f_sos)\n"
        "                tx.textCursor().insertText('[^S]')\n"
        "                tx.setCurrentCharFormat(f)\n"
        "                # [^S] = 4 doc chars, 1 _arr entry → track discrepancy\n"
        "                tx._doc_extra = getattr(tx, '_doc_extra', 0) + 3\n"
        "                tx.char_typed.emit('\\x13', '[^S]')\n"
        "                i += 4\n"
        "            elif text[i] == '\\n':",
    label="3c  _on_macro_clicked: [^S] lookahead"
))

print()
print("=" * 60)
print("FILE 4: macro_store.py")
print("=" * 60)

# 4a — MacroTextEdit docstring
results.append(patch(F_MACRO,
    old='class MacroTextEdit(QTextEdit):\n'
        '    """QTextEdit for macro text with CTRL+D support.\n'
        '\n'
        '    CTRL+D inserts "[^D]" (4 visible ASCII chars) with orange inverse\n'
        '    styling. Backspace detects cursor right after "[^D]" and deletes\n'
        '    all 4 chars atomically — same approach as TxInputWidget._eot_positions.\n'
        '\n'
        '    No private-use Unicode — works on all Windows fonts.\n'
        '    Stored as "[^D]" in Macro.txt (human-readable).\n'
        '    """',
    new='class MacroTextEdit(QTextEdit):\n'
        '    """QTextEdit for macro text with CTRL+D and CTRL+S support.\n'
        '\n'
        '    CTRL+D inserts "[^D]" (4 visible ASCII chars) with orange inverse styling.\n'
        '    CTRL+S inserts "[^S]" (4 visible ASCII chars) with blue inverse styling.\n'
        '    Backspace detects cursor right after either marker and deletes\n'
        '    all 4 chars atomically — same approach as TxInputWidget._eot_positions.\n'
        '\n'
        '    No private-use Unicode — works on all Windows fonts.\n'
        '    Stored as "[^D]" / "[^S]" in Macro.txt (human-readable).\n'
        '    """',
    label="4a  MacroTextEdit docstring"
))

# 4b — MacroTextEdit.keyPressEvent: add CTRL+S block after CTRL+D block
results.append(patch(F_MACRO,
    old='        # CTRL+D — insert [^D] orange marker\n'
        '        if mods == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_D:\n'
        '            f_eot = QTextCharFormat()\n'
        '            f_eot.setForeground(QColor("#ffffff"))\n'
        '            f_eot.setBackground(QColor("#cc4400"))\n'
        '            f_eot.setFontWeight(700)\n'
        '            f_normal = QTextCharFormat()\n'
        '            c = self.textCursor()\n'
        '            pos = c.position()\n'
        '            c.setCharFormat(f_eot)\n'
        '            c.insertText("[^D]")\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            self._eot_positions.append(pos)\n'
        '            return',
    new='        # CTRL+D — insert [^D] orange marker (switch to RECEIVE when reached)\n'
        '        if mods == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_D:\n'
        '            f_eot = QTextCharFormat()\n'
        '            f_eot.setForeground(QColor("#ffffff"))\n'
        '            f_eot.setBackground(QColor("#cc4400"))\n'
        '            f_eot.setFontWeight(700)\n'
        '            f_normal = QTextCharFormat()\n'
        '            c = self.textCursor()\n'
        '            pos = c.position()\n'
        '            c.setCharFormat(f_eot)\n'
        '            c.insertText("[^D]")\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            self._eot_positions.append(pos)\n'
        '            return\n'
        '\n'
        '        # CTRL+S — insert [^S] blue marker (switch to SEND when reached)\n'
        '        if mods == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_S:\n'
        '            f_sos = QTextCharFormat()\n'
        '            f_sos.setForeground(QColor("#ffffff"))\n'
        '            f_sos.setBackground(QColor("#0044cc"))\n'
        '            f_sos.setFontWeight(700)\n'
        '            f_normal = QTextCharFormat()\n'
        '            c = self.textCursor()\n'
        '            pos = c.position()\n'
        '            c.setCharFormat(f_sos)\n'
        '            c.insertText("[^S]")\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            self._eot_positions.append(pos)\n'
        '            return',
    label="4b  MacroTextEdit.keyPressEvent: CTRL+S block"
))

# 4c — _set_formatted_text: add f_sos format and [^S] branch
results.append(patch(F_MACRO,
    old='        i = 0\n'
        '        while i < len(text):\n'
        '            if text[i:i+4] == \'[^D]\':\n'
        '                cursor.setCharFormat(f_eot)\n'
        '                cursor.insertText(\'[^D]\')   # 4 orange chars\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                i += 4\n'
        '            elif text[i] == \'\\n\':\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                cursor.insertBlock()\n'
        '                i += 1\n'
        '            else:\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                cursor.insertText(text[i])\n'
        '                i += 1',
    new='        f_sos = QTextCharFormat()\n'
        '        f_sos.setForeground(QColor("#ffffff"))\n'
        '        f_sos.setBackground(QColor("#0044cc"))\n'
        '        f_sos.setFontWeight(700)\n'
        '        i = 0\n'
        '        while i < len(text):\n'
        '            if text[i:i+4] == \'[^D]\':\n'
        '                cursor.setCharFormat(f_eot)\n'
        '                cursor.insertText(\'[^D]\')   # 4 orange chars\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                i += 4\n'
        '            elif text[i:i+4] == \'[^S]\':\n'
        '                cursor.setCharFormat(f_sos)\n'
        '                cursor.insertText(\'[^S]\')   # 4 blue chars\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                i += 4\n'
        '            elif text[i] == \'\\n\':\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                cursor.insertBlock()\n'
        '                i += 1\n'
        '            else:\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                cursor.insertText(text[i])\n'
        '                i += 1',
    label="4c  _set_formatted_text: [^S] display on load"
))

print()
print("=" * 60)
print("FILE 5: help_baudot.md")
print("=" * 60)

# 5a — control characters table: remove "(planned)" from [^S] row
results.append(patch(F_HELP,
    old='| `CTRL+S` | `[^S]` | Blue | Switch to SEND when this position is reached *(planned)* |',
    new='| `CTRL+S` | `[^S]` | Blue | Switch to SEND when this position is reached during TX |',
    label="5a  help: remove (planned) from [^S] table row"
))

# 5b — keyboard shortcuts table: add CTRL+S entry
results.append(patch(F_HELP,
    old='| `CTRL+D` | Insert `[^D]` EOT marker (auto-switch to RECEIVE) |',
    new='| `CTRL+D` | Insert `[^D]` EOT marker (auto-switch to RECEIVE) |\n'
        '| `CTRL+S` | Insert `[^S]` SOS marker (auto-switch to SEND) |',
    label="5b  help: add CTRL+S to keyboard shortcuts table"
))

# 5c — tips section: mention [^S] in macro tip
results.append(patch(F_HELP,
    old='- **Pre-type your CQ:** Type the full CQ call ending with `[^D]` while in RECEIVE, then press SEND — the TNC will transmit and automatically return to RECEIVE',
    new='- **Pre-type your CQ:** Type the full CQ call ending with `[^D]` while in RECEIVE, then press SEND — the TNC will transmit and automatically return to RECEIVE\n'
        '- **Auto-repeat CQ:** Use `[^S]` after `[^D]` to automatically switch back to SEND after a listening pause — e.g. `CQ DE OE3GAS[^D][^S]` for continuous CQ',
    label="5c  help: add [^S] usage tip"
))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("=" * 60)
total  = len(results)
passed = sum(results)
failed = total - passed

if failed == 0:
    print(f"\033[32mAll {total} patches applied successfully.\033[0m")
    print("\nNext steps:")
    print("  1. Run the application:  python -m pk232py")
    print("  2. Open Baudot screen, type CTRL+S → [^S] blue marker should appear")
    print("  3. Test with a macro containing [^S]")
    print("  4. git add -A && git commit -m 'feat: CTRL+S [^S] SOS marker (v13)'")
    sys.exit(0)
else:
    print(f"\033[31m{failed} patch(es) FAILED — {passed}/{total} applied.\033[0m")
    print("\nThe .bak files contain the original content.")
    print("Check the FAIL messages above and verify pk232py_sources.txt is up to date.")
    sys.exit(1)
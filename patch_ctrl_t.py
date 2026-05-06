#!/usr/bin/env python3
"""
patch_ctrl_t.py — PK232PY v13: Implement CTRL+T [^T:n] timed marker

[^T:n] means: switch to RECEIVE, wait n seconds, switch back to SEND.
n is 1..10 (entered via a small QInputDialog when CTRL+T is pressed).

Marker format:  [^T:1] = 6 chars,  [^T:10] = 7 chars
Sentinel char:  ESC + decimal digits, e.g. "\\x1b1" .. "\\x1b10"
  (ESC = 0x1B, safe: never transmitted to TNC, handled entirely in controller)

Affected files (5):
  baudot_tx_controller.py   — new signal + timer + sentinel handling
  opmode_rtty_base.py       — CTRL+T keyPressEvent, Backspace (variable length)
  main_window.py            — connect signal, handler, macro lookahead
  macro_store.py            — CTRL+T in MacroTextEdit, _set_formatted_text
  help/help_baudot.md       — remove "(planned)", add usage tip

Usage:
    cd E:\\PK232\\pk232py_repo
    python patch_ctrl_t.py
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
        print(f"{FAIL}  [{label}] — search string found {count}x (ambiguous) in {path.name}")
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

F_CTRL  = src / "ui" / "screens" / "baudot_tx_controller.py"
F_RTTY  = src / "ui" / "screens" / "opmode_rtty_base.py"
F_MAIN  = src / "ui" / "main_window.py"
F_MACRO = src / "ui" / "screens" / "macro_store.py"
F_HELP  = src / "help" / "help_baudot.md"

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

results = []

# ===========================================================================
# FILE 1 — baudot_tx_controller.py
# ===========================================================================
print("=" * 60)
print("FILE 1: baudot_tx_controller.py")
print("=" * 60)

# ── 1a  New signal timed_send_reached(n: int) ─────────────────────────────
# The signal carries n so MainWindow knows how long to wait.
results.append(patch(F_CTRL,
    old='    eot_reached = pyqtSignal()',
    new='    eot_reached = pyqtSignal()\n'
        '    timed_send_reached = pyqtSignal(int)  # [^T:n] — wait n sec then SEND',
    label="1a  timed_send_reached signal"
))

# ── 1b  Docstring ──────────────────────────────────────────────────────────
results.append(patch(F_CTRL,
    old='    eot_reached()\n'
        '        CTRL+D EOT marker reached — switch to RECEIVE.\n'
        '    """',
    new='    eot_reached()\n'
        '        CTRL+D EOT marker reached — switch to RECEIVE.\n'
        '    timed_send_reached(n: int)\n'
        '        CTRL+T timed marker reached — switch to RECEIVE, wait n sec, then SEND.\n'
        '    """',
    label="1b  docstring: add timed_send_reached"
))

# ── 1c  _send_next_char: handle ESC-prefixed sentinel ─────────────────────
# Sentinel encoding: '\x1b' + str(n)  e.g. '\x1b3' for n=3, '\x1b10' for n=10.
# ESC (0x1B) is never a printable RTTY char, so it is safe as a sentinel prefix.
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
        '        if char.startswith(\'\\x1b\'):\n'
        '            # [^T:n] timed marker — do NOT send to TNC\n'
        '            try:\n'
        '                n = int(char[1:])\n'
        '            except ValueError:\n'
        '                n = 1\n'
        '            self._tx_queue.clear()\n'
        '            self._tx_timer.stop()\n'
        '            self.status_msg.emit(\n'
        '                f"[^T:{n}] — switching to RECEIVE, resuming SEND in {n}s")\n'
        '            self.timed_send_reached.emit(n)\n'
        '            return\n'
        '        self.send_to_tnc.emit(char)',
    label="1c  _send_next_char: handle \\x1b sentinel"
))

# ── 1d  still_to_transmit: treat ESC-prefixed sentinels like \x04 ──────────
results.append(patch(F_CTRL,
    old="        return any(e['char'] != '\\x04' for e in remaining)",
    new="        return any(\n"
        "            e['char'] != '\\x04' and not e['char'].startswith('\\x1b')\n"
        "            for e in remaining\n"
        "        )",
    label="1d  still_to_transmit: exclude \\x1b sentinels"
))

# ===========================================================================
# FILE 2 — opmode_rtty_base.py
# ===========================================================================
print()
print("=" * 60)
print("FILE 2: opmode_rtty_base.py")
print("=" * 60)

# ── 2a  TxInputWidget: add QInputDialog import note in docstring ───────────
# We need QInputDialog for the n-input dialog.  It comes from PyQt6.QtWidgets
# which is already imported in opmode_rtty_base.py.  We just add CTRL+T to
# the docstring and the keyPressEvent.

results.append(patch(F_RTTY,
    old='    - CTRL+D            — inserts [^D] EOT marker (char = \\x04)',
    new='    - CTRL+D            — inserts [^D] EOT marker (char = \\x04)\n'
        '    - CTRL+T            — opens n dialog, inserts [^T:n] timed marker (char = \\x1b + str(n))',
    label="2a  TxInputWidget docstring: add CTRL+T"
))

# ── 2b  TxInputWidget keyPressEvent: add CTRL+T block ─────────────────────
# Key design decisions:
#
#   1. _eot_positions is extended to a list of dicts:
#        {'pos': int, 'len': int}
#      so Backspace can delete the right number of chars for variable-length
#      markers.  [^D] uses len=4; [^T:n] uses len=6 or 7.
#
#      IMPORTANT: existing code reads _eot_positions as a list of ints.
#      We migrate it to dicts here; the Backspace block below is replaced
#      entirely to handle both old int entries (safety) and new dict entries.
#
#   2. _doc_extra increment = marker_len - 1
#      because 1 entry goes into _arr but marker_len chars go into the doc.

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
        '                self._eot_positions: list[dict] = []\n'
        '            self._eot_positions.append({\'pos\': eot_doc_pos, \'len\': 4})\n'
        '            # [^D] = 4 doc chars but 1 _arr entry → 3 extra doc positions\n'
        '            self._doc_extra += 3\n'
        '            self.char_typed.emit("\\x04", "[^D]")\n'
        '            return\n'
        '\n'
        '        # CTRL+T: open n-dialog, insert [^T:n] timed marker\n'
        '        # (RECEIVE, wait n seconds, SEND)\n'
        '        if mods == Ctrl and key == Qt.Key.Key_T:\n'
        '            from PyQt6.QtWidgets import QInputDialog\n'
        '            n, ok = QInputDialog.getInt(\n'
        '                self, "Timed Marker",\n'
        '                "Wait time in seconds (1–10):",\n'
        '                value=5, min=1, max=10\n'
        '            )\n'
        '            if not ok:\n'
        '                return\n'
        '            marker = f"[^T:{n}]"          # e.g. "[^T:5]" = 6 chars\n'
        '            marker_len = len(marker)       # 6 for n=1..9, 7 for n=10\n'
        '            f_tmr = QTextCharFormat()\n'
        '            f_tmr.setForeground(QColor("#ffffff"))\n'
        '            f_tmr.setBackground(QColor("#8800cc"))\n'
        '            f_tmr.setFontWeight(700)\n'
        '            c = self.textCursor()\n'
        '            tmr_doc_pos = c.position()\n'
        '            c.setCharFormat(f_tmr)\n'
        '            c.insertText(marker)\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            if not hasattr(self, "_eot_positions"):\n'
        '                self._eot_positions: list[dict] = []\n'
        '            self._eot_positions.append({\'pos\': tmr_doc_pos, \'len\': marker_len})\n'
        '            # marker_len doc chars but 1 _arr entry → (marker_len-1) extra\n'
        '            self._doc_extra += marker_len - 1\n'
        '            # Sentinel: ESC + decimal n  (e.g. "\\x1b5" or "\\x1b10")\n'
        '            self.char_typed.emit(f"\\x1b{n}", marker)\n'
        '            return',
    label="2b  TxInputWidget: CTRL+T block + migrate _eot_positions to dicts"
))

# ── 2c  Backspace: replace int-based lookup with dict-based ───────────────
# The old code used:  pos == eot_pos + 4  (hardcoded 4)
# New code uses:      pos == entry['pos'] + entry['len']
# This handles [^D] (len=4), [^T:1]..[^T:9] (len=6), [^T:10] (len=7).
results.append(patch(F_RTTY,
    old='            eot_positions = getattr(self, "_eot_positions", [])\n'
        '            # Check if cursor is right after a [^D] marker (4 chars).\n'
        '            # EOT marker at doc_pos p occupies chars p..p+3, cursor at p+4.\n'
        '            eot_hit = None\n'
        '            for eot_pos in eot_positions:\n'
        '                if pos == eot_pos + 4:\n'
        '                    eot_hit = eot_pos\n'
        '                    break\n'
        '            if eot_hit is not None:\n'
        '                # Delete all 4 chars of [^D] atomically\n'
        '                c.setPosition(eot_hit)\n'
        '                c.setPosition(eot_hit + 4, QTextCursor.MoveMode.KeepAnchor)\n'
        '                c.removeSelectedText()\n'
        '                self._eot_positions.remove(eot_hit)\n'
        '                # Adjust tracked positions of EOT markers that come after\n'
        '                self._eot_positions = [\n'
        '                    p - 4 if p > eot_hit else p\n'
        '                    for p in self._eot_positions\n'
        '                ]\n'
        '                # Restore the 3 extra doc positions\n'
        '                self._doc_extra = max(0, self._doc_extra - 3)\n'
        '                # Notify controller: BS sentinel for the whole EOT (1 _arr entry)\n'
        '                self.char_typed.emit(\'\\x08\', \'\')\n'
        '            else:\n'
        '                # Normal backspace — notify controller then delete\n'
        '                self.char_typed.emit(\'\\x08\', \'\')\n'
        '                super().keyPressEvent(ev)\n'
        '                # Adjust EOT positions after cursor\n'
        '                self._eot_positions = [\n'
        '                    p - 1 if p >= pos else p\n'
        '                    for p in getattr(self, "_eot_positions", [])\n'
        '                ]',
    new='            eot_positions = getattr(self, "_eot_positions", [])\n'
        '            # Check if cursor is right after any marker.\n'
        '            # Each entry: {\'pos\': int, \'len\': int}\n'
        '            # Marker at doc_pos p with length L occupies p..p+L-1,\n'
        '            # cursor sits at p+L after the marker.\n'
        '            eot_hit = None\n'
        '            for entry in eot_positions:\n'
        '                # Support both old int entries and new dict entries\n'
        '                if isinstance(entry, dict):\n'
        '                    p, mlen = entry[\'pos\'], entry[\'len\']\n'
        '                else:\n'
        '                    p, mlen = entry, 4   # legacy: [^D] was always 4\n'
        '                if pos == p + mlen:\n'
        '                    eot_hit = (p, mlen, entry)\n'
        '                    break\n'
        '            if eot_hit is not None:\n'
        '                p, mlen, entry_ref = eot_hit\n'
        '                # Delete all marker chars atomically\n'
        '                c.setPosition(p)\n'
        '                c.setPosition(p + mlen, QTextCursor.MoveMode.KeepAnchor)\n'
        '                c.removeSelectedText()\n'
        '                self._eot_positions.remove(entry_ref)\n'
        '                # Shift positions of markers that come after this one\n'
        '                new_list = []\n'
        '                for e in self._eot_positions:\n'
        '                    if isinstance(e, dict):\n'
        '                        if e[\'pos\'] > p:\n'
        '                            new_list.append({\'pos\': e[\'pos\'] - mlen, \'len\': e[\'len\']})\n'
        '                        else:\n'
        '                            new_list.append(e)\n'
        '                    else:\n'
        '                        new_list.append(e - mlen if e > p else e)\n'
        '                self._eot_positions = new_list\n'
        '                # Restore the extra doc positions for this marker\n'
        '                self._doc_extra = max(0, self._doc_extra - (mlen - 1))\n'
        '                # Notify controller: BS sentinel — 1 _arr entry removed\n'
        '                self.char_typed.emit(\'\\x08\', \'\')\n'
        '            else:\n'
        '                # Normal backspace — notify controller then delete\n'
        '                self.char_typed.emit(\'\\x08\', \'\')\n'
        '                super().keyPressEvent(ev)\n'
        '                # Shift marker positions after the deleted char\n'
        '                new_list = []\n'
        '                for e in getattr(self, "_eot_positions", []):\n'
        '                    if isinstance(e, dict):\n'
        '                        if e[\'pos\'] >= pos:\n'
        '                            new_list.append({\'pos\': e[\'pos\'] - 1, \'len\': e[\'len\']})\n'
        '                        else:\n'
        '                            new_list.append(e)\n'
        '                    else:\n'
        '                        new_list.append(e - 1 if e >= pos else e)\n'
        '                self._eot_positions = new_list',
    label="2c  Backspace: variable-length marker delete"
))

# ===========================================================================
# FILE 3 — main_window.py
# ===========================================================================
print()
print("=" * 60)
print("FILE 3: main_window.py")
print("=" * 60)

# ── 3a  Connect timed_send_reached signal ─────────────────────────────────
results.append(patch(F_MAIN,
    old='            self._baudot_ctrl.eot_reached.connect(self._on_baudot_eot)',
    new='            self._baudot_ctrl.eot_reached.connect(self._on_baudot_eot)\n'
        '            try:\n'
        '                self._baudot_ctrl.timed_send_reached.disconnect()\n'
        '            except (RuntimeError, TypeError):\n'
        '                pass\n'
        '            self._baudot_ctrl.timed_send_reached.connect(self._on_baudot_timed_send)',
    label="3a  connect timed_send_reached signal"
))

# ── 3b  Add _on_baudot_timed_send handler ─────────────────────────────────
# Logic:
#   1. Already in RECEIVE (eot_reached fires just before this via TX flow,
#      OR we were already receiving).
#   2. Make sure btn_receive is checked (force RECEIVE state).
#   3. After n*1000 ms, fire btn_send.setChecked(True) via QTimer.singleShot.
#
# We do NOT need to manage a persistent timer — QTimer.singleShot is fire-
# and-forget.  If the user manually presses SEND before the timer fires the
# setChecked(True) call is a no-op (already checked).
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
        '    def _on_baudot_timed_send(self, n: int) -> None:\n'
        '        """[^T:n] timed marker reached — RECEIVE, wait n seconds, then SEND.\n'
        '\n'
        '        Step 1: force RECEIVE mode (PTT off).\n'
        '        Step 2: after n seconds, activate SEND (PTT on) via QTimer.\n'
        '        The timer is fire-and-forget; if the user presses SEND manually\n'
        '        before the timer fires, setChecked(True) on an already-checked\n'
        '        button is a harmless no-op.\n'
        '        """\n'
        '        screen = self._opmode_stack.currentWidget()\n'
        '        # Step 1 — switch to RECEIVE\n'
        '        if hasattr(screen, \'btn_receive\') and not screen.btn_receive.isChecked():\n'
        '            screen.btn_receive.setChecked(True)\n'
        '        # Show countdown in status bar\n'
        '        self.statusBar().showMessage(\n'
        '            f"[^T:{n}] — RECEIVE for {n}s, then auto-SEND …", n * 1000)\n'
        '        # Step 2 — schedule SEND after n seconds\n'
        '        def _auto_send():\n'
        '            s = self._opmode_stack.currentWidget()\n'
        '            if hasattr(s, \'btn_send\') and not s.btn_send.isChecked():\n'
        '                s.btn_send.setChecked(True)\n'
        '        QTimer.singleShot(n * 1000, _auto_send)',
    label="3b  add _on_baudot_timed_send handler"
))

# ── 3c  _on_macro_clicked: add [^T:n] lookahead ───────────────────────────
# Pattern e.g. [^T:5] or [^T:10] — we detect '[^T:' and read digits until ']'
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
        "            elif text[i:i+4] == '[^T:':\n"
        "                # Timed marker [^T:n] — read digits up to ']'\n"
        "                j = i + 4\n"
        "                while j < len(text) and text[j].isdigit():\n"
        "                    j += 1\n"
        "                if j < len(text) and text[j] == ']':\n"
        "                    marker = text[i:j+1]          # e.g. '[^T:5]'\n"
        "                    marker_len = len(marker)\n"
        "                    try:\n"
        "                        n_val = int(text[i+4:j])\n"
        "                        n_val = max(1, min(10, n_val))\n"
        "                    except ValueError:\n"
        "                        n_val = 1\n"
        "                    from PyQt6.QtGui import QTextCharFormat as _TCF, QColor as _QC\n"
        "                    f_tmr = _TCF()\n"
        "                    f_tmr.setForeground(_QC(\"#ffffff\"))\n"
        "                    f_tmr.setBackground(_QC(\"#8800cc\"))\n"
        "                    f_tmr.setFontWeight(700)\n"
        "                    tx.setCurrentCharFormat(f_tmr)\n"
        "                    tx.textCursor().insertText(marker)\n"
        "                    tx.setCurrentCharFormat(f)\n"
        "                    tx._doc_extra = getattr(tx, '_doc_extra', 0) + (marker_len - 1)\n"
        "                    tx.char_typed.emit(f'\\x1b{n_val}', marker)\n"
        "                    i = j + 1\n"
        "                else:\n"
        "                    # Malformed — insert as plain text\n"
        "                    tx.setCurrentCharFormat(f)\n"
        "                    tx.textCursor().insertText(text[i])\n"
        "                    tx.char_typed.emit(text[i], text[i])\n"
        "                    i += 1\n"
        "            elif text[i] == '\\n':",
    label="3c  _on_macro_clicked: [^T:n] lookahead"
))

# ===========================================================================
# FILE 4 — macro_store.py
# ===========================================================================
print()
print("=" * 60)
print("FILE 4: macro_store.py")
print("=" * 60)

# ── 4a  MacroTextEdit docstring ───────────────────────────────────────────
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
        '    """QTextEdit for macro text with CTRL+D and CTRL+T support.\n'
        '\n'
        '    CTRL+D inserts "[^D]" (4 chars) with orange inverse styling.\n'
        '    CTRL+T opens a dialog for n (1–10), inserts "[^T:n]" (6–7 chars)\n'
        '    with purple inverse styling.\n'
        '    Backspace detects cursor right after any marker and deletes it\n'
        '    atomically — _eot_positions stores {pos, len} dicts.\n'
        '\n'
        '    No private-use Unicode — works on all Windows fonts.\n'
        '    Stored as "[^D]" / "[^T:n]" in Macro.txt (human-readable).\n'
        '    """',
    label="4a  MacroTextEdit docstring"
))

# ── 4b  MacroTextEdit.__init__: change list type annotation ───────────────
results.append(patch(F_MACRO,
    old='        self._eot_positions: list[int] = []',
    new='        self._eot_positions: list[dict] = []  # {\'pos\': int, \'len\': int}',
    label="4b  MacroTextEdit.__init__: dict list"
))

# ── 4c  MacroTextEdit.keyPressEvent: add CTRL+T, update CTRL+D and Backspace
results.append(patch(F_MACRO,
    old='    def keyPressEvent(self, ev: QKeyEvent) -> None:\n'
        '        key  = ev.key()\n'
        '        mods = ev.modifiers()\n'
        '\n'
        '        # CTRL+D — insert [^D] orange marker\n'
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
        '        # Backspace — atomic delete of [^D] if cursor is right after it\n'
        '        if key == Qt.Key.Key_Backspace:\n'
        '            c = self.textCursor()\n'
        '            pos = c.position()\n'
        '            for eot_pos in list(self._eot_positions):\n'
        '                if pos == eot_pos + 4:\n'
        '                    c.setPosition(eot_pos)\n'
        '                    c.setPosition(eot_pos + 4,\n'
        '                                  QTextCursor.MoveMode.KeepAnchor)\n'
        '                    c.removeSelectedText()\n'
        '                    self._eot_positions.remove(eot_pos)\n'
        '                    self._eot_positions = [\n'
        '                        p - 4 if p > eot_pos else p\n'
        '                        for p in self._eot_positions\n'
        '                    ]\n'
        '                    return\n'
        '            # Normal backspace — shift tracked positions\n'
        '            if not c.hasSelection():\n'
        '                self._eot_positions = [\n'
        '                    p - 1 if p >= pos else p\n'
        '                    for p in self._eot_positions\n'
        '                ]\n'
        '            super().keyPressEvent(ev)\n'
        '            return\n'
        '\n'
        '        super().keyPressEvent(ev)',
    new='    def keyPressEvent(self, ev: QKeyEvent) -> None:\n'
        '        key  = ev.key()\n'
        '        mods = ev.modifiers()\n'
        '\n'
        '        # CTRL+D — insert [^D] orange marker (switch to RECEIVE)\n'
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
        '            self._eot_positions.append({\'pos\': pos, \'len\': 4})\n'
        '            return\n'
        '\n'
        '        # CTRL+T — open n dialog, insert [^T:n] purple marker (timed RECEIVE)\n'
        '        if mods == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_T:\n'
        '            from PyQt6.QtWidgets import QInputDialog\n'
        '            n, ok = QInputDialog.getInt(\n'
        '                self, "Timed Marker",\n'
        '                "Wait time in seconds (1–10):",\n'
        '                value=5, min=1, max=10\n'
        '            )\n'
        '            if not ok:\n'
        '                return\n'
        '            marker = f"[^T:{n}]"\n'
        '            marker_len = len(marker)\n'
        '            f_tmr = QTextCharFormat()\n'
        '            f_tmr.setForeground(QColor("#ffffff"))\n'
        '            f_tmr.setBackground(QColor("#8800cc"))\n'
        '            f_tmr.setFontWeight(700)\n'
        '            f_normal = QTextCharFormat()\n'
        '            c = self.textCursor()\n'
        '            pos = c.position()\n'
        '            c.setCharFormat(f_tmr)\n'
        '            c.insertText(marker)\n'
        '            c.setCharFormat(f_normal)\n'
        '            self.setTextCursor(c)\n'
        '            self._eot_positions.append({\'pos\': pos, \'len\': marker_len})\n'
        '            return\n'
        '\n'
        '        # Backspace — atomic delete of any marker if cursor is right after it\n'
        '        if key == Qt.Key.Key_Backspace:\n'
        '            c = self.textCursor()\n'
        '            pos = c.position()\n'
        '            for entry in list(self._eot_positions):\n'
        '                p   = entry[\'pos\']\n'
        '                mlen = entry[\'len\']\n'
        '                if pos == p + mlen:\n'
        '                    c.setPosition(p)\n'
        '                    c.setPosition(p + mlen, QTextCursor.MoveMode.KeepAnchor)\n'
        '                    c.removeSelectedText()\n'
        '                    self._eot_positions.remove(entry)\n'
        '                    self._eot_positions = [\n'
        '                        {\'pos\': e[\'pos\'] - mlen, \'len\': e[\'len\']}\n'
        '                        if e[\'pos\'] > p else e\n'
        '                        for e in self._eot_positions\n'
        '                    ]\n'
        '                    return\n'
        '            # Normal backspace — shift tracked positions\n'
        '            if not c.hasSelection():\n'
        '                self._eot_positions = [\n'
        '                    {\'pos\': e[\'pos\'] - 1, \'len\': e[\'len\']}\n'
        '                    if e[\'pos\'] >= pos else e\n'
        '                    for e in self._eot_positions\n'
        '                ]\n'
        '            super().keyPressEvent(ev)\n'
        '            return\n'
        '\n'
        '        super().keyPressEvent(ev)',
    label="4c  MacroTextEdit: CTRL+T + dict-based Backspace"
))

# ── 4d  _set_formatted_text: render [^T:n] in purple on load ─────────────
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
    new='        f_tmr = QTextCharFormat()\n'
        '        f_tmr.setForeground(QColor("#ffffff"))\n'
        '        f_tmr.setBackground(QColor("#8800cc"))\n'
        '        f_tmr.setFontWeight(700)\n'
        '        i = 0\n'
        '        while i < len(text):\n'
        '            if text[i:i+4] == \'[^D]\':\n'
        '                cursor.setCharFormat(f_eot)\n'
        '                cursor.insertText(\'[^D]\')   # 4 orange chars\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                i += 4\n'
        '            elif text[i:i+4] == \'[^T:\':\n'
        '                # Read [^T:n] or [^T:10]\n'
        '                j = i + 4\n'
        '                while j < len(text) and text[j].isdigit():\n'
        '                    j += 1\n'
        '                if j < len(text) and text[j] == \']\':\n'
        '                    marker = text[i:j+1]\n'
        '                    cursor.setCharFormat(f_tmr)\n'
        '                    cursor.insertText(marker)   # purple chars\n'
        '                    cursor.setCharFormat(f_normal)\n'
        '                    i = j + 1\n'
        '                else:\n'
        '                    cursor.setCharFormat(f_normal)\n'
        '                    cursor.insertText(text[i])\n'
        '                    i += 1\n'
        '            elif text[i] == \'\\n\':\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                cursor.insertBlock()\n'
        '                i += 1\n'
        '            else:\n'
        '                cursor.setCharFormat(f_normal)\n'
        '                cursor.insertText(text[i])\n'
        '                i += 1',
    label="4d  _set_formatted_text: render [^T:n] purple on load"
))

# ===========================================================================
# FILE 5 — help/help_baudot.md
# ===========================================================================
print()
print("=" * 60)
print("FILE 5: help_baudot.md")
print("=" * 60)

# ── 5a  Control characters table ──────────────────────────────────────────
results.append(patch(F_HELP,
    old='| `CTRL+T:n` | `[^T:5]` | Purple | Switch to RECEIVE, wait n seconds, then switch back to SEND *(planned)* |',
    new='| `CTRL+T` | `[^T:5]` | Purple | Switch to RECEIVE, wait n seconds, then switch back to SEND |',
    label="5a  help: remove (planned) from [^T:n] row"
))

# ── 5b  Keyboard shortcuts table ──────────────────────────────────────────
results.append(patch(F_HELP,
    old='| `CTRL+D` | Insert `[^D]` EOT marker (auto-switch to RECEIVE) |',
    new='| `CTRL+D` | Insert `[^D]` EOT marker (auto-switch to RECEIVE) |\n'
        '| `CTRL+T` | Insert `[^T:n]` timed marker (RECEIVE n seconds, then auto-SEND) |',
    label="5b  help: add CTRL+T to shortcuts table"
))

# ── 5c  Update macro control-char note ────────────────────────────────────
results.append(patch(F_HELP,
    old='Control characters (`[^D]`, `[^S]`, `[^T:n]`) can also be used in\n'
        'macro texts to automate TX/RX switching. *(CTRL+S and CTRL+T planned)*',
    new='Control characters (`[^D]`, `[^T:n]`) can also be used in\n'
        'macro texts to automate TX/RX switching.',
    label="5c  help: update macro ctrl-char note"
))

# ── 5d  Tips section: add [^T:n] example ─────────────────────────────────
results.append(patch(F_HELP,
    old='- **Pre-type your CQ:** Type the full CQ call ending with `[^D]` while in RECEIVE, then press SEND — the TNC will transmit and automatically return to RECEIVE',
    new='- **Pre-type your CQ:** Type the full CQ call ending with `[^D]` while in RECEIVE, then press SEND — the TNC will transmit and automatically return to RECEIVE\n'
        '- **Timed CQ loop:** Use `[^T:n]` to listen for n seconds and automatically resume sending — e.g. `CQ DE OE3GAS K[^D][^T:5]` transmits the CQ, listens 5 seconds, then keys up again',
    label="5d  help: add [^T:n] tip"
))

# ===========================================================================
# Summary
# ===========================================================================
print()
print("=" * 60)
total  = len(results)
passed = sum(results)
failed = total - passed

if failed == 0:
    print(f"\033[32mAll {total} patches applied successfully.\033[0m")
    print("\nNext steps:")
    print("  1. Run:   python -m pk232py")
    print("  2. Open Baudot screen, CTRL+T → dialog → [^T:5] purple marker")
    print("  3. Test: type text, CTRL+T, more text, press SEND")
    print("     → TX first part → RECEIVE 5s → auto-SEND rest")
    print("  4. git add -A && git commit -m 'feat: CTRL+T [^T:n] timed marker (v13)'")
    sys.exit(0)
else:
    print(f"\033[31m{failed} patch(es) FAILED — {passed}/{total} applied.\033[0m")
    print("\nThe .bak files contain the original content.")
    sys.exit(1)
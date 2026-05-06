#!/usr/bin/env python3
"""
fix_ctrl_t_queue.py — Bugfix: [^T:n] text nach dem Marker wird nicht gesendet

Problem:
    In _send_next_char() wird beim [^T:n] Sentinel _tx_queue.clear() aufgerufen
    BEVOR timed_send_reached emittiert wird. Dadurch sind die Chars nach dem
    Marker bereits aus der Queue gelöscht. on_send_stop() sieht eine leere Queue
    und macht keinen Rollback von _tx_sent_idx. on_send_start() nach den n
    Sekunden findet _arr[_tx_sent_idx:] leer vor — nichts zu senden.

Fix:
    _tx_queue.clear() entfernen. on_send_stop() macht den Rollback korrekt
    selbst via:  self._tx_sent_idx -= len(self._tx_queue)
    Damit zeigt _tx_sent_idx nach dem RECEIVE wieder auf den ersten Char
    nach [^T:n], und on_send_start() flusht den Rest korrekt.

Betrifft nur: src/pk232py/ui/screens/baudot_tx_controller.py
"""

import sys
import shutil
from pathlib import Path

PASS = "\033[32m  OK\033[0m"
FAIL = "\033[31m FAIL\033[0m"

def patch(path, old, new, label):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{FAIL}  [{label}] — NOT FOUND in {path.name}")
        return False
    if text.count(old) > 1:
        print(f"{FAIL}  [{label}] — found {text.count(old)}x (ambiguous)")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{PASS}  [{label}]")
    return True

repo = Path.cwd()
if not (repo / "src" / "pk232py").is_dir():
    print(f"ERROR: Run from repo root. Current: {repo}")
    sys.exit(1)

f = repo / "src" / "pk232py" / "ui" / "screens" / "baudot_tx_controller.py"
bak = f.with_suffix(".py.fix_bak")
shutil.copy2(f, bak)
print(f"Backup → {bak.name}\n")

result = patch(f,
    old=(
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
        '            return'
    ),
    new=(
        '        if char.startswith(\'\\x1b\'):\n'
        '            # [^T:n] timed marker — do NOT send to TNC.\n'
        '            # Do NOT clear _tx_queue here — on_send_stop() will roll back\n'
        '            # _tx_sent_idx by len(_tx_queue), so the chars after [^T:n]\n'
        '            # are correctly re-queued when on_send_start() fires after n sec.\n'
        '            try:\n'
        '                n = int(char[1:])\n'
        '            except ValueError:\n'
        '                n = 1\n'
        '            self._tx_timer.stop()\n'
        '            self.status_msg.emit(\n'
        '                f"[^T:{n}] — switching to RECEIVE, resuming SEND in {n}s")\n'
        '            self.timed_send_reached.emit(n)\n'
        '            return'
    ),
    label="remove _tx_queue.clear() before timed_send_reached.emit()"
)

print()
if result:
    print("\033[32mFix applied.\033[0m")
    print("\nTest:")
    print("  Typ: 'Test[^T:3]Danach' → SEND")
    print("  → 'Test' wird gesendet → 3s RECEIVE → 'Danach' wird gesendet")
    print("\ngit add -A && git commit -m 'fix: [^T:n] send text after marker (v13)'")
else:
    print("\033[31mFix FAILED.\033[0m")
    sys.exit(1)
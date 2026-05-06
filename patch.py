#!/usr/bin/env python3
"""
patch.py — PK232PY Bug Fix Patcher  (v22)
==========================================

Bug: Chars typed during RECEIVE appear GREEN instead of WHITE.

Root cause:
  _on_rtty_data_ack() uses cursor.setCharFormat() to colour confirmed
  chars GREEN directly in the document. This sets the document's
  character format at those positions, but also leaves the
  tx_input.currentCharFormat() pointing to the GREEN format.

  When new chars are typed during RECEIVE, the eventFilter RECEIVE
  branch does QApplication.sendEvent(tx, event) which inserts the
  char using Qt's normal key handling. Qt uses tx.currentCharFormat()
  for the new char — which is still GREEN from the last ACK.

Fix:
  In the RECEIVE branch of eventFilter, before calling sendEvent,
  reset tx.currentCharFormat() to WHITE (#ffffff) so that newly
  typed chars always appear white (unsent).

  Also reset currentCharFormat in _on_screen_receive() so that
  switching back to RECEIVE always resets the colour for new input.

Usage:
    python patch.py [--repo PATH] [--dry-run] [--check]
"""

import argparse
import shutil
import sys
from pathlib import Path


PATCHES = [
    # ------------------------------------------------------------------
    # FIX 1: Reset currentCharFormat to WHITE in RECEIVE eventFilter branch
    # ------------------------------------------------------------------
    {
        "file": "src/pk232py/ui/main_window.py",
        "description": (
            "Reset tx.currentCharFormat to WHITE before sendEvent "
            "in RECEIVE branch so new chars appear white not green"
        ),
        "search": (
            "                                self._in_event_filter = True\n"
            "                                try:\n"
            "                                    tx.setFocus()\n"
            "                                    QApplication.sendEvent(tx, event)\n"
            "                                finally:\n"
            "                                    self._in_event_filter = False\n"
            "                                return True"
        ),
        "replace": (
            "                                # Reset char format to WHITE so new\n"
            "                                # chars are not coloured green from\n"
            "                                # the last ACK operation.\n"
            "                                from PyQt6.QtGui import QTextCharFormat, QColor\n"
            "                                _w = QTextCharFormat()\n"
            "                                _w.setForeground(QColor('#ffffff'))\n"
            "                                tx.setCurrentCharFormat(_w)\n"
            "                                self._in_event_filter = True\n"
            "                                try:\n"
            "                                    tx.setFocus()\n"
            "                                    QApplication.sendEvent(tx, event)\n"
            "                                finally:\n"
            "                                    self._in_event_filter = False\n"
            "                                return True"
        ),
    },

    # ------------------------------------------------------------------
    # FIX 2: Also reset currentCharFormat when switching to RECEIVE
    # ------------------------------------------------------------------
    {
        "file": "src/pk232py/ui/main_window.py",
        "description": (
            "Reset tx.currentCharFormat to WHITE when entering RECEIVE "
            "so format is clean for next input session"
        ),
        "search": (
            "            if self._send_active:\n"
            "                self._on_screen_send(False)   # \u2190 clears _send_active + PTT logic\n"
            "                # Also reset visual state of SEND button."
        ),
        "replace": (
            "            if self._send_active:\n"
            "                self._on_screen_send(False)   # \u2190 clears _send_active + PTT logic\n"
            "                # Also reset visual state of SEND button.\n"
            "\n"
            "            # Reset tx_input char format to WHITE so next typed\n"
            "            # chars appear white (unsent), not green from last ACK.\n"
            "            _screen = self._opmode_stack.currentWidget()\n"
            "            _tx = getattr(_screen, 'tx_input', None)\n"
            "            if _tx is not None:\n"
            "                from PyQt6.QtGui import QTextCharFormat, QColor\n"
            "                _wfmt = QTextCharFormat()\n"
            "                _wfmt.setForeground(QColor('#ffffff'))\n"
            "                _tx.setCurrentCharFormat(_wfmt)"
        ),
    },
]


# ---------------------------------------------------------------------------
# Patcher logic
# ---------------------------------------------------------------------------

def find_repo(given) -> Path:
    root = Path(given).resolve() if given else Path.cwd()
    if not root.exists():
        print(f"ERROR: path does not exist: {root}")
        sys.exit(1)
    return root


def apply_patch(patch: dict, root: Path, dry_run: bool, check: bool) -> bool:
    rel     = patch["file"]
    desc    = patch["description"]
    search  = patch["search"]
    replace = patch["replace"]

    target = root / rel
    if not target.exists():
        print(f"  SKIP  {rel}  (file not found)")
        return False

    content = target.read_text(encoding="utf-8")

    if search not in content:
        if replace in content:
            print(f"  OK    {rel}  (already patched)")
        else:
            print(f"  WARN  {rel}  (search string not found)")
            print(f"        First 80 chars: {repr(search[:80])}")
        return False

    if dry_run or check:
        print(f"  PATCH {rel}")
        print(f"        {desc}")
        return True

    bak = target.with_suffix(target.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(target, bak)
        print(f"  BAK   {bak.name}")

    target.write_text(content.replace(search, replace, 1), encoding="utf-8")
    print(f"  DONE  {rel}")
    print(f"        {desc}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="PK232PY patch v22")
    parser.add_argument("--repo", metavar="PATH", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check",   action="store_true")
    args = parser.parse_args()

    root = find_repo(args.repo)
    print(f"Repository : {root}")
    print(f"Patch      : v22  ({len(PATCHES)} patches)")
    print()

    if args.dry_run:
        print("=== DRY RUN ===")
        print()

    changes = 0
    for i, patch in enumerate(PATCHES, 1):
        print(f"[{i}/{len(PATCHES)}] {patch['description'][:72]}")
        if apply_patch(patch, root, args.dry_run, args.check):
            changes += 1
        print()

    if args.check:
        sys.exit(1 if changes > 0 else 0)

    if args.dry_run:
        print(f"Dry run: {changes} patch(es) would be applied.")
    else:
        print(f"Done: {changes} patch(es) applied.")
        if changes > 0:
            print()
            print("Expected:")
            print("  RECEIVE → type chars → WHITE in TX")
            print("  SEND → chars sent, turn GREEN on ACK")
            print("  RECEIVE → type more chars → WHITE again")
            print()
            print("  git add src/pk232py/ui/main_window.py")
            print("  git commit -m 'fix: reset char format to white on RECEIVE'")


if __name__ == "__main__":
    main()
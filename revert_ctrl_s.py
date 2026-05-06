#!/usr/bin/env python3
"""
revert_ctrl_s.py — Undo patch_ctrl_s.py by restoring .bak files

Restores the 5 files that patch_ctrl_s.py modified:
  baudot_tx_controller.py
  opmode_rtty_base.py
  main_window.py
  macro_store.py
  help/help_baudot.md

Usage:
    cd E:\\PK232\\pk232py_repo
    python revert_ctrl_s.py
"""

import sys
import shutil
from pathlib import Path

PASS = "\033[32m  OK\033[0m"
FAIL = "\033[31m FAIL\033[0m"

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
# Files to restore
# ---------------------------------------------------------------------------

files = [
    src / "ui" / "screens" / "baudot_tx_controller.py",
    src / "ui" / "screens" / "opmode_rtty_base.py",
    src / "ui" / "main_window.py",
    src / "ui" / "screens" / "macro_store.py",
    src / "help" / "help_baudot.md",
]

# ---------------------------------------------------------------------------
# Restore from .bak
# ---------------------------------------------------------------------------

results = []
print("Restoring from .bak files ...")
for f in files:
    bak = f.with_suffix(f.suffix + ".bak")
    if not bak.exists():
        print(f"{FAIL}  {f.name} — .bak file not found: {bak}")
        results.append(False)
        continue
    shutil.copy2(bak, f)
    print(f"{PASS}  {f.name} restored from {bak.name}")
    results.append(True)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
total  = len(results)
passed = sum(results)
failed = total - passed

if failed == 0:
    print(f"\033[32mAll {total} files restored successfully.\033[0m")
    print("\nNext step — apply the CTRL+T patch:")
    print("    python patch_ctrl_t.py")
    sys.exit(0)
else:
    print(f"\033[31m{failed} restore(s) FAILED — {passed}/{total} completed.\033[0m")
    print("\nFor missing .bak files, use git to restore the originals:")
    print("    git checkout -- src/pk232py/ui/screens/baudot_tx_controller.py")
    print("    git checkout -- src/pk232py/ui/screens/opmode_rtty_base.py")
    print("    git checkout -- src/pk232py/ui/main_window.py")
    print("    git checkout -- src/pk232py/ui/screens/macro_store.py")
    print("    git checkout -- src/pk232py/help/help_baudot.md")
    sys.exit(1)
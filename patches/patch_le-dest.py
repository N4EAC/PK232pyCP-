"""
patch_fix_le_dest.py
====================
Korrigiert den Widget-Namen für das Ziel-SELCAL-Feld im AMTOR-Screen.

Problem: _on_amtor_arq() und _on_amtor_selfec() suchen nach
         screen.le_dest_selcal — das Feld heißt aber le_dest.

Aufruf vom Repo-Root:
    python patch_fix_le_dest.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [

    # _on_amtor_arq: le_dest_selcal → le_dest
    (
        "    def _on_amtor_arq(self) -> None:\n"
        "        \"\"\"ARQ button — call the destination SELCAL (mnemonic AC).\"\"\"\n"
        "        screen = self._opmode_stack.currentWidget()\n"
        "        selcal = getattr(screen, \"le_dest_selcal\", None)\n"
        "        if selcal is None:\n"
        "            return\n"
        "        dest = selcal.text().strip().upper()\n"
        "        if not dest:\n"
        "            from PyQt6.QtWidgets import QMessageBox\n"
        "            QMessageBox.warning(self, \"ARQ Call\",\n"
        "                                \"Please enter a destination SELCAL.\")\n"
        "            return\n"
        "        from pk232py.modes.amtor import AMTORMode\n"
        "        frame = AMTORMode.arq_call_frame(dest)\n"
        "        if self._amtor_send(frame):\n"
        "            self._log_monitor(f\"[AMTOR] ARQ call → {dest}\")",

        "    def _on_amtor_arq(self) -> None:\n"
        "        \"\"\"ARQ button — call the destination SELCAL (mnemonic AC).\"\"\"\n"
        "        screen = self._opmode_stack.currentWidget()\n"
        "        selcal = getattr(screen, \"le_dest\", None)\n"
        "        if selcal is None:\n"
        "            return\n"
        "        dest = selcal.text().strip().upper()\n"
        "        if not dest:\n"
        "            from PyQt6.QtWidgets import QMessageBox\n"
        "            QMessageBox.warning(self, \"ARQ Call\",\n"
        "                                \"Please enter a destination SELCAL.\")\n"
        "            return\n"
        "        from pk232py.modes.amtor import AMTORMode\n"
        "        frame = AMTORMode.arq_call_frame(dest)\n"
        "        if self._amtor_send(frame):\n"
        "            self._log_monitor(f\"[AMTOR] ARQ call → {dest}\")"
    ),

    # _on_amtor_selfec: le_dest_selcal → le_dest
    (
        "        selcal = getattr(screen, \"le_dest_selcal\", None)\n"
        "        dest = selcal.text().strip().upper() if selcal else \"\"",

        "        selcal = getattr(screen, \"le_dest\", None)\n"
        "        dest = selcal.text().strip().upper() if selcal else \"\""
    ),

]


def apply_patches(path: Path, patches: list[tuple]) -> None:
    src = path.read_text(encoding="utf-8")

    missing = []
    for i, patch in enumerate(patches, 1):
        if patch[0] not in src:
            missing.append(i)

    if missing:
        print(f"FEHLER: Suchstring nicht gefunden fuer Patch(e): {missing}")
        print("Patch wird NICHT angewendet — Datei unveraendert.")
        return

    for i, patch in enumerate(patches, 1):
        src = src.replace(patch[0], patch[1], 1)
        print(f"OK  Patch {i} angewendet")

    path.write_text(src, encoding="utf-8")
    print(f"\nFertig — {path} aktualisiert.")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply_patches(TARGET, PATCHES)
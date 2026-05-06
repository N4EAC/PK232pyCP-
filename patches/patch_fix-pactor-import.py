"""
patch_fix_pactor_import.py
==========================
Korrigiert den absoluten Import in pactor_screen.py auf einen
relativen Package-Import — nötig damit das Modul als Teil des
pk232py-Packages geladen werden kann.

Aufruf vom Repo-Root:
    python patch_fix_pactor_import.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/screens/pactor_screen.py")

PATCHES = [
    (
        "from opmode_rtty_base import (\n"
        "    MacroStore, MacroEditDialog,\n"
        "    make_toggle_button, add_hline,\n"
        "    apply_app_style, style_rx_widget, style_tx_widget,\n"
        "    BTN_W, SPACING, MACRO_COUNT,\n"
        "    STYLE_PROM_INACTIVE, STYLE_SEND_ON, STYLE_SEND_BLINK, STYLE_RECEIVE_ON,\n"
        ")",

        "from .opmode_rtty_base import (\n"
        "    MacroStore, MacroEditDialog,\n"
        "    make_toggle_button, add_hline,\n"
        "    apply_app_style, style_rx_widget, style_tx_widget,\n"
        "    BTN_W, SPACING, MACRO_COUNT,\n"
        "    STYLE_PROM_INACTIVE, STYLE_SEND_ON, STYLE_SEND_BLINK, STYLE_RECEIVE_ON,\n"
        ")"
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
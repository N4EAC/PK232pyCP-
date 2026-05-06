"""
patch_rbaud.py
==============
Verdrahtet den RBAUD-Dropdown der Opmode-Screens mit dem TNC.

Änderung:
  _wire_screen_buttons() — RBAUD-Dropdown verbinden

Aufruf vom Repo-Root:
    python patch_rbaud.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [

    # Ergänze RBAUD-Verdrahtung am Ende von _wire_screen_buttons()
    (
        "        # RECEIVE button — toggled ON: put TNC into receive; OFF: standby\n"
        "        if hasattr(screen, \"btn_receive\"):\n"
        "            try:\n"
        "                screen.btn_receive.toggled.disconnect(self._on_screen_receive)\n"
        "            except RuntimeError:\n"
        "                pass\n"
        "            screen.btn_receive.toggled.connect(self._on_screen_receive)\n",

        "        # RECEIVE button — toggled ON: put TNC into receive; OFF: standby\n"
        "        if hasattr(screen, \"btn_receive\"):\n"
        "            try:\n"
        "                screen.btn_receive.toggled.disconnect(self._on_screen_receive)\n"
        "            except RuntimeError:\n"
        "                pass\n"
        "            screen.btn_receive.toggled.connect(self._on_screen_receive)\n"
        "\n"
        "        # RBAUD dropdown — currentIndexChanged: send RB frame to TNC\n"
        "        if hasattr(screen, \"combo_rbaud\"):\n"
        "            try:\n"
        "                screen.combo_rbaud.currentIndexChanged.disconnect(\n"
        "                    self._on_screen_rbaud_changed\n"
        "                )\n"
        "            except RuntimeError:\n"
        "                pass\n"
        "            screen.combo_rbaud.currentIndexChanged.connect(\n"
        "                self._on_screen_rbaud_changed\n"
        "            )\n"
    ),

    # Neue Methode _on_screen_rbaud_changed() nach _on_screen_receive() einfügen
    (
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Display decoded data from active mode in RX panel.\"\"\"",

        "    def _on_screen_rbaud_changed(self, index: int) -> None:\n"
        "        \"\"\"Called when the RBAUD dropdown on the active screen changes.\n"
        "\n"
        "        Reads the selected baud-rate string from the dropdown,\n"
        "        converts it to an integer and sends an RB command frame.\n"
        "\n"
        "        Only sent when Host Mode is active — silently ignored\n"
        "        otherwise (e.g. when the screen is first built and the\n"
        "        dropdown is populated programmatically).\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "\n"
        "        mode = self._modes.current_mode\n"
        "        if mode is None or not hasattr(mode, \"rbaud_frame\"):\n"
        "            return\n"
        "\n"
        "        # Read baud value from the dropdown text (e.g. \"45\", \"100\")\n"
        "        screen = self._opmode_stack.currentWidget()\n"
        "        if not hasattr(screen, \"combo_rbaud\"):\n"
        "            return\n"
        "        text = screen.combo_rbaud.currentText().strip()\n"
        "        try:\n"
        "            baud = int(text)\n"
        "        except ValueError:\n"
        "            logger.warning(\"RBAUD: invalid value %r\", text)\n"
        "            return\n"
        "\n"
        "        # Update mode instance so get_init_frames() stays in sync\n"
        "        mode.rbaud = baud\n"
        "\n"
        "        # Send RB frame to TNC\n"
        "        frame = mode.rbaud_frame(baud)\n"
        "        self._serial.send_command(\n"
        "            frame[2:4],   # mnemonic bytes\n"
        "            frame[4:-1],  # argument bytes\n"
        "        )\n"
        "        logger.info(\"RBAUD set to %d Bd\", baud)\n"
        "        self._log_monitor(f\"[PARAM] RBAUD → {baud} Bd\")\n"
        "\n"
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Display decoded data from active mode in RX panel.\"\"\""
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
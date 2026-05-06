"""
patch_send_receive.py
=====================
Verdrahtet die SEND- und RECEIVE-Buttons aller Opmode-Screens mit den
entsprechenden MainWindow-Methoden.

Aufruf vom Repo-Root:
    python patch_send_receive.py

Was geändert wird:
  1. _wire_mode_callbacks() — ruft neu am Ende _wire_screen_buttons() auf
  2. Neue Methode _wire_screen_buttons() nach _make_link_handler() einfügen
  3. Neue Methode _on_receive_mode() nach _on_send() einfügen
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")


PATCHES = [

    # ── 1. _wire_mode_callbacks(): am Ende _wire_screen_buttons() aufrufen ──
    (
        "        logger.debug(\"Mode callbacks wired for: %s\", mode.name)",

        "        # Wire screen buttons (SEND, RECEIVE) to MainWindow slots\n"
        "        self._wire_screen_buttons()\n"
        "\n"
        "        logger.debug(\"Mode callbacks wired for: %s\", mode.name)"
    ),

    # ── 2. _wire_screen_buttons() nach _make_link_handler() einfügen ────────
    (
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Display decoded data from active mode in RX panel.\"\"\"",

        "    def _wire_screen_buttons(self) -> None:\n"
        "        \"\"\"Connect SEND and RECEIVE buttons of the active screen\n"
        "        to MainWindow slots.\n"
        "\n"
        "        Called from _wire_mode_callbacks() whenever the mode changes.\n"
        "        Safe to call multiple times — Qt ignores duplicate connections\n"
        "        only if the same signal+slot pair is connected again, but we\n"
        "        explicitly disconnect first to avoid stacking signals.\n"
        "        \"\"\"\n"
        "        screen = self._opmode_stack.currentWidget()\n"
        "        if screen is None:\n"
        "            return\n"
        "\n"
        "        # SEND button — toggled ON: activate TX; toggled OFF: no-op\n"
        "        if hasattr(screen, \"btn_send\"):\n"
        "            try:\n"
        "                screen.btn_send.toggled.disconnect(self._on_screen_send)\n"
        "            except RuntimeError:\n"
        "                pass   # not connected yet — harmless\n"
        "            screen.btn_send.toggled.connect(self._on_screen_send)\n"
        "\n"
        "        # RECEIVE button — toggled ON: put TNC into receive; OFF: standby\n"
        "        if hasattr(screen, \"btn_receive\"):\n"
        "            try:\n"
        "                screen.btn_receive.toggled.disconnect(self._on_screen_receive)\n"
        "            except RuntimeError:\n"
        "                pass\n"
        "            screen.btn_receive.toggled.connect(self._on_screen_receive)\n"
        "\n"
        "    def _on_screen_send(self, active: bool) -> None:\n"
        "        \"\"\"Called when the SEND button on the active screen is toggled.\n"
        "\n"
        "        active=True:  flush TX window and start sending.\n"
        "        active=False: no explicit TNC command — the user stopped sending\n"
        "                      by un-toggling the button. The TX window remains\n"
        "                      for editing; another SEND press resumes.\n"
        "        \"\"\"\n"
        "        if not active:\n"
        "            return\n"
        "        self._on_send()   # send current TX window contents\n"
        "\n"
        "    def _on_screen_receive(self, active: bool) -> None:\n"
        "        \"\"\"Called when the RECEIVE button on the active screen is toggled.\n"
        "\n"
        "        active=True:  send RECEIVE command to TNC for the current mode.\n"
        "        active=False: return TNC to standby for the current mode.\n"
        "\n"
        "        Each mode has a different receive-activation mnemonic:\n"
        "          Baudot/ASCII RTTY  — RX is always on; no explicit command needed.\n"
        "          AMTOR              — receive handled by ALIST / FEC buttons.\n"
        "          Morse              — RX is always on; no explicit command needed.\n"
        "          PACTOR             — receive via PTLIST (btn_ptlist on screen).\n"
        "        For modes where no action is needed, the call is a graceful no-op.\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "\n"
        "        mode = self._modes.current_mode\n"
        "        if mode is None:\n"
        "            return\n"
        "\n"
        "        mode_name = mode.name\n"
        "\n"
        "        if active:\n"
        "            # Mode-specific receive activation\n"
        "            if mode_name in (\"Baudot RTTY\", \"ASCII RTTY\", \"CW / Morse\"):\n"
        "                # These modes receive continuously — no command needed.\n"
        "                # The button is purely visual feedback for the operator.\n"
        "                logger.debug(\"RECEIVE: %s — continuous RX, no TNC command\",\n"
        "                             mode_name)\n"
        "\n"
        "            elif mode_name == \"NAVTEX\":\n"
        "                # NAVTEX receives automatically — no command needed.\n"
        "                logger.debug(\"RECEIVE: NAVTEX — auto RX\")\n"
        "\n"
        "            else:\n"
        "                # Unknown mode — log and do nothing.\n"
        "                logger.debug(\"RECEIVE: %s — no specific receive command\",\n"
        "                             mode_name)\n"
        "        else:\n"
        "            # RECEIVE toggled OFF — no explicit TNC command for most modes.\n"
        "            logger.debug(\"RECEIVE OFF: %s\", mode_name)\n"
        "\n"
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Display decoded data from active mode in RX panel.\"\"\""
    ),

]


# ---------------------------------------------------------------------------
# Patch anwenden
# ---------------------------------------------------------------------------

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
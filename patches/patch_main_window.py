"""
patch_main_window.py
====================
Wendet die 5 Änderungen für PactorScreen + verbessertes Callback-Routing
auf src/pk232py/ui/main_window.py an.

Aufruf vom Repo-Root:
    python patch_main_window.py

Das Skript prüft vor der Ausführung ob alle Suchstrings gefunden werden,
und bricht ab wenn etwas nicht passt — keine halben Änderungen.
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")


# ---------------------------------------------------------------------------
# Die 5 Änderungen als (SEARCH, REPLACE) Paare
# ---------------------------------------------------------------------------

PATCHES = [

    # ── 1. Import PactorScreen ──────────────────────────────────────────────
    (
        "from .screens.fax_screen     import FaxScreen",
        "from .screens.fax_screen     import FaxScreen\n"
        "from .screens.pactor_screen  import PactorScreen   # added"
    ),

    # ── 2. PactorScreen in _opmode_screens Dict ─────────────────────────────
    (
        '            "AMTOR FEC":     _amtor,       # same screen, different sub-mode\n'
        '            "CW / Morse":    MorseScreen(),',
        '            "AMTOR FEC":     _amtor,       # same screen, different sub-mode\n'
        '            "PACTOR":        PactorScreen(),   # added\n'
        '            "CW / Morse":    MorseScreen(),'
    ),

    # ── 3 + 4. _wire_mode_callbacks() erweitern ──────────────────────────────
    # Ersetze die komplette Methode durch die neue Version mit
    # on_fec_received und _make_link_handler.
    (
        "    def _wire_mode_callbacks(self) -> None:\n"
        "        \"\"\"Connect the active mode's data callbacks to the RX display.\"\"\"\n"
        "        mode = self._modes.current_mode\n"
        "        if mode is None:\n"
        "            return\n"
        " # Generic: on_data_received RX display\n"
        "        if hasattr(mode, \"on_data_received\"):\n"
        "            mode.on_data_received = self._on_mode_data_received\n"
        "        # Echo ($2F): show in RX display too\n"
        "        if hasattr(mode, \"on_echo_received\"):\n"
        "            mode.on_echo_received = self._on_mode_echo_received\n"
        " # Link messages RX display\n"
        "        if hasattr(mode, \"on_link_message\"):\n"
        "            mode.on_link_message = self._on_mode_link_message\n"
        "        logger.debug(\"Mode callbacks wired for: %s\", mode.name)",

        "    def _wire_mode_callbacks(self) -> None:\n"
        "        \"\"\"Connect the active mode's data callbacks to the UI.\"\"\"\n"
        "        mode = self._modes.current_mode\n"
        "        if mode is None:\n"
        "            return\n"
        "\n"
        "        # ARQ / general received data\n"
        "        if hasattr(mode, \"on_data_received\"):\n"
        "            mode.on_data_received = self._on_mode_data_received\n"
        "\n"
        "        # PACTOR FEC / Unproto data ($3F) — same handler as ARQ data\n"
        "        if hasattr(mode, \"on_fec_received\"):\n"
        "            mode.on_fec_received = self._on_mode_data_received\n"
        "\n"
        "        # Echo ($2F)\n"
        "        if hasattr(mode, \"on_echo_received\"):\n"
        "            mode.on_echo_received = self._on_mode_echo_received\n"
        "\n"
        "        # Link messages → log + screen status label\n"
        "        if hasattr(mode, \"on_link_message\"):\n"
        "            screen = self._opmode_screens.get(mode.name)\n"
        "            if screen is not None and hasattr(screen, \"_set_status\"):\n"
        "                mode.on_link_message = self._make_link_handler(screen)\n"
        "            else:\n"
        "                mode.on_link_message = self._on_mode_link_message\n"
        "\n"
        "        logger.debug(\"Mode callbacks wired for: %s\", mode.name)"
    ),

    # ── 5. _make_link_handler() als neue Methode einfügen ───────────────────
    # Eingefügt direkt nach _wire_mode_callbacks(), vor _on_mode_data_received
    (
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Display decoded data from active mode in RX panel.\"\"\"",

        "    def _make_link_handler(self, screen):\n"
        "        \"\"\"Return a link-message handler that updates both the\n"
        "        monitor log and the screen's _set_status label.\n"
        "\n"
        "        Maps TNC link-message text to the status keys used by\n"
        "        AmtorScreen and PactorScreen.\n"
        "        \"\"\"\n"
        "        def handler(msg: str) -> None:\n"
        "            # 1. General log / monitor\n"
        "            self._on_mode_link_message(msg)\n"
        "            # 2. Update screen status label\n"
        "            m = msg.lower()\n"
        "            if \"connected\" in m and \"disconnect\" not in m:\n"
        "                status = \"CONNECTED\"\n"
        "            elif \"disconnect\" in m:\n"
        "                status = \"DISCONN\"\n"
        "            elif \"calling\" in m or \"connect request\" in m:\n"
        "                status = \"CALLING\"\n"
        "            elif \"fec\" in m:\n"
        "                status = \"FEC TX\"\n"
        "            else:\n"
        "                status = \"STBY\"\n"
        "            screen._set_status(status)\n"
        "        return handler\n"
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

    # Vorab prüfen ob alle Suchstrings vorhanden sind
    missing = []
    for i, patch in enumerate(patches, 1):
        search = patch[0]
        if search not in src:
            missing.append(i)

    if missing:
        print(f"FEHLER: Suchstrings nicht gefunden fuer Patch(e): {missing}")
        print("Patch wird NICHT angewendet — Datei unveraendert.")
        return

    # Alle Patches anwenden
    for i, patch in enumerate(patches, 1):
        search, replace = patch[0], patch[1]
        src = src.replace(search, replace, 1)
        print(f"OK  Patch {i} angewendet")

    path.write_text(src, encoding="utf-8")
    print(f"\nFertig — {path} wurde aktualisiert.")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply_patches(TARGET, PATCHES)
"""
patch_fix_duplicates.py
=======================
Entfernt Duplikate die durch frühere Patches entstanden sind:

1. Doppelter Aufruf _wire_screen_buttons() in _wire_mode_callbacks()
2. Erste (alte, unvollständige) Definition von _wire_screen_buttons()
3. Erste (alte) Definition von _on_screen_receive() die nach der alten
   _wire_screen_buttons steht

Aufruf vom Repo-Root:
    python patch_fix_duplicates.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")


def apply(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    # ── 1. Doppelter Aufruf in _wire_mode_callbacks() ────────────────────────
    old_double_call = (
        "        # Wire screen buttons (SEND, RECEIVE) to MainWindow slots\n"
        "        self._wire_screen_buttons()\n"
        "\n"
        "        # Wire screen buttons (SEND, RECEIVE) to MainWindow slots\n"
        "        self._wire_screen_buttons()\n"
    )
    new_single_call = (
        "        # Wire screen buttons (SEND, RECEIVE) to MainWindow slots\n"
        "        self._wire_screen_buttons()\n"
    )
    if old_double_call in src:
        src = src.replace(old_double_call, new_single_call, 1)
        print("OK  Fix 1: Doppelter _wire_screen_buttons()-Aufruf entfernt")
        fixes += 1
    else:
        print("OK  Fix 1: Kein doppelter Aufruf gefunden (bereits bereinigt)")

    # ── 2. Alte (unvollständige) _wire_screen_buttons() entfernen ────────────
    # Die alte Version hat nur SEND/RECEIVE und verwendet "except RuntimeError:"
    # Die neue hat AMTOR/PACTOR/RBAUD/Phase3 und "except (RuntimeError, TypeError):"
    old_wire_buttons = (
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
    )
    if old_wire_buttons in src:
        src = src.replace(old_wire_buttons, "", 1)
        print("OK  Fix 2: Alte _wire_screen_buttons()-Definition entfernt")
        fixes += 1
    else:
        print("OK  Fix 2: Alte _wire_screen_buttons() nicht gefunden (bereits bereinigt)")

    # ── 3. Alte _on_screen_send() + _on_screen_receive() entfernen ───────────
    # Diese folgte direkt nach der alten _wire_screen_buttons.
    # Nach Fix 2 sollte sie nicht mehr vorhanden sein — prüfen trotzdem.
    old_send_receive = (
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
    )
    if old_send_receive in src:
        src = src.replace(old_send_receive, "", 1)
        print("OK  Fix 3: Alte _on_screen_send + _on_screen_receive entfernt")
        fixes += 1
    else:
        print("OK  Fix 3: Alte Versionen nicht gefunden (bereits bereinigt)")

    # ── Ergebnis ─────────────────────────────────────────────────────────────
    if src == original:
        print("\nKeine Änderungen nötig — Datei unverändert.")
        return

    # Syntax-Check vor dem Schreiben
    import ast
    try:
        ast.parse(src)
        print(f"\nSyntax OK")
    except SyntaxError as e:
        print(f"\nFEHLER: Syntaxfehler nach Patch: {e}")
        print("Datei wird NICHT geschrieben.")
        return

    path.write_text(src, encoding="utf-8")
    lines = len(src.splitlines())
    print(f"Fertig — {path} aktualisiert ({lines} Zeilen, {fixes} Fix(e) angewendet).")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply(TARGET)
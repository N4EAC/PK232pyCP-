"""
patch_three_fixes.py
====================
Fix 1: Startup zeigt Verbose Terminal (nicht Baudot Screen)
Fix 2: Block-Cursor auf TX-Fenstern nach _apply_appearance()
Fix 3: _on_mode_data_received schreibt im Verbose-Modus in _vt_display

Aufruf vom Repo-Root:
    python patch_three_fixes.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")


def apply(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    original = src
    fixes = 0

    # ── Fix 1: Startup auf Verbose Terminal umstellen ────────────────────────
    old1 = (
        "        self.setCentralWidget(main_container)\n"
        "        self._stack.setCurrentIndex(0)     # start in Host Mode view\n"
        "        self._wire_mode_callbacks()\n"
        "        # Focus goes to the active screen's TX window (if it has one)\n"
        "        QTimer.singleShot(0, self._focus_active_tx)"
    )
    new1 = (
        "        self.setCentralWidget(main_container)\n"
        "        self._stack.setCurrentIndex(1)     # start in Verbose Terminal view\n"
        "        self._wire_mode_callbacks()\n"
        "        # Focus goes to verbose terminal input on startup\n"
        "        QTimer.singleShot(0, lambda: self._vt_input.setFocus())"
    )
    if old1 in src:
        src = src.replace(old1, new1, 1)
        print("OK  Fix 1: Startup → Verbose Terminal")
        fixes += 1
    else:
        print("WARN Fix 1: Suchstring nicht gefunden")

    # ── Fix 2: Block-Cursor in _apply_appearance() ───────────────────────────
    old2 = (
        "    def _apply_appearance(self) -> None:\n"
        "        \"\"\"Apply saved appearance settings to RX/TX displays.\"\"\"\n"
        "        try:\n"
        "            cfg = self._app_config.appearance\n"
        "            font = QFont(cfg.font_family, cfg.font_size)\n"
        "            style = (\n"
        "                f\"background-color:{cfg.bg_color}; color:{cfg.fg_color};\"\n"
        "            )\n"
        "            # Apply to all screen rx_display and tx_input widgets\n"
        "            for screen in set(self._opmode_screens.values()):\n"
        "                if hasattr(screen, \"rx_display\"):\n"
        "                    screen.rx_display.setFont(font)\n"
        "                    screen.rx_display.setStyleSheet(style)\n"
        "                if hasattr(screen, \"tx_input\"):\n"
        "                    screen.tx_input.setFont(font)\n"
        "                    screen.tx_input.setStyleSheet(style)\n"
        "            self._vt_display.setFont(font)\n"
        "            self._vt_display.setStyleSheet(style)\n"
        "        except Exception as exc:\n"
        "            logger.warning(\"Could not apply appearance: %s\", exc)"
    )
    new2 = (
        "    def _apply_appearance(self) -> None:\n"
        "        \"\"\"Apply saved appearance settings to RX/TX displays.\"\"\"\n"
        "        try:\n"
        "            cfg = self._app_config.appearance\n"
        "            font = QFont(cfg.font_family, cfg.font_size)\n"
        "            style = (\n"
        "                f\"background-color:{cfg.bg_color}; color:{cfg.fg_color};\"\n"
        "            )\n"
        "            # Apply to all screen rx_display and tx_input widgets\n"
        "            for screen in set(self._opmode_screens.values()):\n"
        "                if hasattr(screen, \"rx_display\"):\n"
        "                    screen.rx_display.setFont(font)\n"
        "                    screen.rx_display.setStyleSheet(style)\n"
        "                if hasattr(screen, \"tx_input\"):\n"
        "                    screen.tx_input.setFont(font)\n"
        "                    screen.tx_input.setStyleSheet(style)\n"
        "                    # Block cursor on TX window\n"
        "                    char_w = screen.tx_input.fontMetrics().averageCharWidth()\n"
        "                    screen.tx_input.setCursorWidth(char_w)\n"
        "            self._vt_display.setFont(font)\n"
        "            self._vt_display.setStyleSheet(style)\n"
        "        except Exception as exc:\n"
        "            logger.warning(\"Could not apply appearance: %s\", exc)"
    )
    if old2 in src:
        src = src.replace(old2, new2, 1)
        print("OK  Fix 2: Block-Cursor in _apply_appearance()")
        fixes += 1
    else:
        print("WARN Fix 2: Suchstring nicht gefunden")

    # ── Fix 3: _on_mode_data_received — im Verbose-Modus in _vt_display ──────
    # Im Verbose-Modus (stack index 1) landen Daten im _vt_display,
    # nicht im opmode screen rx_display.
    old3 = (
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Route decoded TNC data to the active screen's RX window.\"\"\"\n"
        "        try:\n"
        "            text = data.decode(\"ascii\", errors=\"replace\")\n"
        "        except Exception:\n"
        "            text = repr(data)\n"
        "\n"
        "        # Primary path: write directly into the active screen's rx_display.\n"
        "        # _rx_display is a property — always points to the correct widget.\n"
        "        rx = self._rx_display\n"
        "        rx.moveCursor(rx.textCursor().MoveOperation.End)\n"
        "        rx.insertPlainText(text)\n"
        "\n"
        "        # Monitor panel (always, if visible)\n"
        "        if self._monitor_container.isVisible():\n"
        "            if self._mon_btn_decoded.isChecked():\n"
        "                self._log_monitor(f\"[DATA] {text.rstrip()}\")\n"
        "            else:\n"
        "                self._monitor_raw(\"rx\", data)"
    )
    new3 = (
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Route decoded TNC data to the correct display widget.\n"
        "\n"
        "        In Host Mode (stack index 0): write to active opmode screen's\n"
        "        rx_display via the _rx_display property.\n"
        "        In Verbose Mode (stack index 1): write to _vt_display so the\n"
        "        operator sees the decoded data in the terminal.\n"
        "        \"\"\"\n"
        "        try:\n"
        "            text = data.decode(\"ascii\", errors=\"replace\")\n"
        "        except Exception:\n"
        "            text = repr(data)\n"
        "\n"
        "        if self._stack.currentIndex() == 0:\n"
        "            # Host Mode: write to active opmode screen's rx_display\n"
        "            rx = self._rx_display\n"
        "            rx.moveCursor(rx.textCursor().MoveOperation.End)\n"
        "            rx.insertPlainText(text)\n"
        "        else:\n"
        "            # Verbose Mode: show decoded data in verbose terminal\n"
        "            self._vt_append(text, color=\"#88ccff\")\n"
        "\n"
        "        # Monitor panel (always, if visible)\n"
        "        if self._monitor_container.isVisible():\n"
        "            if self._mon_btn_decoded.isChecked():\n"
        "                self._log_monitor(f\"[DATA] {text.rstrip()}\")\n"
        "            else:\n"
        "                self._monitor_raw(\"rx\", data)"
    )
    if old3 in src:
        src = src.replace(old3, new3, 1)
        print("OK  Fix 3: _on_mode_data_received → Verbose/Host routing")
        fixes += 1
    else:
        # Versuche alternative Version (aus _log_terminal Pfad)
        old3b = (
            "    def _on_mode_data_received(self, data: bytes) -> None:\n"
            "        \"\"\"Display decoded data from active mode in RX panel.\"\"\"\n"
            "        try:\n"
            "            text = data.decode(\"ascii\", errors=\"replace\")\n"
            "        except Exception:\n"
            "            text = repr(data)\n"
            "        # Show in RX display\n"
            "        self._log_terminal(text)\n"
            "        # Show in monitor (decoded mode)\n"
            "        if self._monitor_container.isVisible():\n"
            "            if self._mon_btn_decoded.isChecked():\n"
            "                self._log_monitor(f\"[DATA] {text.rstrip()}\")\n"
            "            elif not self._mon_btn_decoded.isChecked():\n"
            "                self._monitor_raw(\"rx\", data)"
        )
        new3b = (
            "    def _on_mode_data_received(self, data: bytes) -> None:\n"
            "        \"\"\"Route decoded TNC data to the correct display widget.\n"
            "\n"
            "        Host Mode (stack index 0): active opmode screen's rx_display.\n"
            "        Verbose Mode (stack index 1): verbose terminal _vt_display.\n"
            "        \"\"\"\n"
            "        try:\n"
            "            text = data.decode(\"ascii\", errors=\"replace\")\n"
            "        except Exception:\n"
            "            text = repr(data)\n"
            "\n"
            "        if self._stack.currentIndex() == 0:\n"
            "            # Host Mode: write to active opmode screen's rx_display\n"
            "            self._log_terminal(text)\n"
            "        else:\n"
            "            # Verbose Mode: show decoded data in verbose terminal\n"
            "            self._vt_append(text, color=\"#88ccff\")\n"
            "\n"
            "        # Monitor panel (always, if visible)\n"
            "        if self._monitor_container.isVisible():\n"
            "            if self._mon_btn_decoded.isChecked():\n"
            "                self._log_monitor(f\"[DATA] {text.rstrip()}\")\n"
            "            elif not self._mon_btn_decoded.isChecked():\n"
            "                self._monitor_raw(\"rx\", data)"
        )
        if old3b in src:
            src = src.replace(old3b, new3b, 1)
            print("OK  Fix 3b: _on_mode_data_received → Verbose/Host routing")
            fixes += 1
        else:
            print("WARN Fix 3: Suchstring nicht gefunden (beide Varianten)")

    # ── Syntaxcheck + Schreiben ───────────────────────────────────────────────
    if src == original:
        print(f"\nKeine Änderungen ({fixes} Fixes angewendet).")
        return

    import ast
    try:
        ast.parse(src)
        print("Syntax OK")
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e} — Datei nicht geschrieben")
        return

    path.write_text(src, encoding="utf-8")
    print(f"Fertig — {path} aktualisiert "
          f"({len(src.splitlines())} Zeilen, {fixes} Fix(e))")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply(TARGET)
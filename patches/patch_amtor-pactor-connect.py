"""
patch_amtor_pactor_connect.py
=============================
Verdrahtet die Connect/Disconnect/Mode-Buttons von AMTOR und PACTOR
mit den entsprechenden TNC-Befehlen.

AMTOR (AmtorScreen):
  btn_arq       → arq_call_frame(dest_selcal)  — ARQ call (AC)
  btn_fec       → fec_frame()                  — FEC broadcast (FE)
  btn_selfec    → selfec_frame(dest_selcal)     — SELFEC (SE)
  btn_alist     → alist_frame()                 — ALIST listen (AL)
  btn_stby      → stby_frame() [AM]             — AMTOR standby
  btn_achg      → achg_frame()                  — ARQ changeover (AG)

PACTOR (PactorScreen):
  btn_connect   → connect ARQ (PT + AC call)
  btn_ptlist    → ptlist_frame()                — PTLIST listen (PN)
  btn_ptsend    → ptsend_frame()                — PTSEND FEC (PD)
  btn_disconnect→ disconnect: PT standby (PT mnemonic)
  btn_stby      → stby: PT standby

Aufruf vom Repo-Root:
    python patch_amtor_pactor_connect.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [

    # ── 1. _wire_screen_buttons(): AMTOR + PACTOR Mode-Buttons verbinden ────
    (
        "        # RBAUD dropdown — currentIndexChanged: send RB frame to TNC\n",

        "        # AMTOR mode buttons\n"
        "        self._wire_amtor_buttons(screen)\n"
        "\n"
        "        # PACTOR mode buttons\n"
        "        self._wire_pactor_buttons(screen)\n"
        "\n"
        "        # RBAUD dropdown — currentIndexChanged: send RB frame to TNC\n"
    ),

    # ── 2. Neue Methoden nach _on_screen_rbaud_changed() einfügen ───────────
    (
        "    def _on_mode_data_received(self, data: bytes) -> None:\n"
        "        \"\"\"Display decoded data from active mode in RX panel.\"\"\"",

        # ── _wire_amtor_buttons ──────────────────────────────────────────────
        "    def _wire_amtor_buttons(self, screen) -> None:\n"
        "        \"\"\"Connect AMTOR mode buttons to TNC commands.\n"
        "\n"
        "        Only wires buttons that exist on the screen — safe to call\n"
        "        for non-AMTOR screens (all hasattr guards).\n"
        "        \"\"\"\n"
        "        def _conn(btn_name: str, slot) -> None:\n"
        "            btn = getattr(screen, btn_name, None)\n"
        "            if btn is None:\n"
        "                return\n"
        "            try:\n"
        "                btn.clicked.disconnect(slot)\n"
        "            except RuntimeError:\n"
        "                pass\n"
        "            btn.clicked.connect(slot)\n"
        "\n"
        "        _conn(\"btn_arq\",        self._on_amtor_arq)\n"
        "        _conn(\"btn_fec\",        self._on_amtor_fec)\n"
        "        _conn(\"btn_selfec\",     self._on_amtor_selfec)\n"
        "        _conn(\"btn_alist\",      self._on_amtor_alist)\n"
        "        _conn(\"btn_stby\",       self._on_amtor_stby)\n"
        "        _conn(\"btn_achg\",       self._on_amtor_achg)\n"
        "\n"
        "    def _wire_pactor_buttons(self, screen) -> None:\n"
        "        \"\"\"Connect PACTOR mode buttons to TNC commands.\"\"\"\n"
        "        def _conn(btn_name: str, slot) -> None:\n"
        "            btn = getattr(screen, btn_name, None)\n"
        "            if btn is None:\n"
        "                return\n"
        "            try:\n"
        "                btn.clicked.disconnect(slot)\n"
        "            except RuntimeError:\n"
        "                pass\n"
        "            btn.clicked.connect(slot)\n"
        "\n"
        "        _conn(\"btn_connect\",    self._on_pactor_connect)\n"
        "        _conn(\"btn_ptlist\",     self._on_pactor_ptlist)\n"
        "        _conn(\"btn_ptsend\",     self._on_pactor_ptsend)\n"
        "        _conn(\"btn_disconnect\", self._on_pactor_disconnect)\n"
        "        _conn(\"btn_stby\",       self._on_pactor_stby)\n"
        "\n"
        "    # ------------------------------------------------------------------\n"
        "    # AMTOR slots\n"
        "    # ------------------------------------------------------------------\n"
        "\n"
        "    def _amtor_send(self, frame: bytes) -> bool:\n"
        "        \"\"\"Send a pre-built AMTOR command frame. Returns True on success.\"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return False\n"
        "        return self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "\n"
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
        "            self._log_monitor(f\"[AMTOR] ARQ call → {dest}\")\n"
        "\n"
        "    def _on_amtor_fec(self) -> None:\n"
        "        \"\"\"FEC button — start Mode B broadcast (mnemonic FE).\"\"\"\n"
        "        from pk232py.modes.amtor import AMTORMode\n"
        "        frame = AMTORMode.fec_frame()\n"
        "        if self._amtor_send(frame):\n"
        "            self._log_monitor(\"[AMTOR] FEC broadcast started\")\n"
        "\n"
        "    def _on_amtor_selfec(self) -> None:\n"
        "        \"\"\"SELFEC button — selective FEC (mnemonic SE).\"\"\"\n"
        "        screen = self._opmode_stack.currentWidget()\n"
        "        selcal = getattr(screen, \"le_dest_selcal\", None)\n"
        "        dest = selcal.text().strip().upper() if selcal else \"\"\n"
        "        if not dest:\n"
        "            from PyQt6.QtWidgets import QMessageBox\n"
        "            QMessageBox.warning(self, \"SELFEC\",\n"
        "                                \"Please enter a destination SELCAL.\")\n"
        "            return\n"
        "        from pk232py.modes.amtor import AMTORMode\n"
        "        frame = AMTORMode.selfec_frame(dest)\n"
        "        if self._amtor_send(frame):\n"
        "            self._log_monitor(f\"[AMTOR] SELFEC → {dest}\")\n"
        "\n"
        "    def _on_amtor_alist(self) -> None:\n"
        "        \"\"\"ALIST button — Mode A listen (mnemonic AL).\"\"\"\n"
        "        from pk232py.modes.amtor import AMTORMode\n"
        "        frame = AMTORMode.alist_frame()\n"
        "        if self._amtor_send(frame):\n"
        "            self._log_monitor(\"[AMTOR] ALIST — listening\")\n"
        "\n"
        "    def _on_amtor_stby(self) -> None:\n"
        "        \"\"\"STBY button — return to AMTOR standby (mnemonic AM).\"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "        from pk232py.comm.frame import build_command\n"
        "        frame = build_command(b'AM')\n"
        "        self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "        self._log_monitor(\"[AMTOR] Standby\")\n"
        "\n"
        "    def _on_amtor_achg(self) -> None:\n"
        "        \"\"\"ACHG button — ARQ changeover / break-in (mnemonic AG).\"\"\"\n"
        "        if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "            return\n"
        "        from pk232py.comm.frame import build_command\n"
        "        frame = build_command(b'AG')\n"
        "        self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "        self._log_monitor(\"[AMTOR] ACHG — changeover sent\")\n"
        "\n"
        "    # ------------------------------------------------------------------\n"
        "    # PACTOR slots\n"
        "    # ------------------------------------------------------------------\n"
        "\n"
        "    def _pactor_send(self, frame: bytes) -> bool:\n"
        "        \"\"\"Send a pre-built PACTOR command frame.\"\"\"\n"
        "        if not self._serial.is_connected:\n"
        "            return False\n"
        "        return self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "\n"
        "    def _on_pactor_connect(self) -> None:\n"
        "        \"\"\"Connect button — initiate PACTOR ARQ call.\n"
        "\n"
        "        Sends PACTOR standby (PT) then ARQ call (AC {callsign}).\n"
        "        MYPTCALL must already be set via get_init_frames().\n"
        "        \"\"\"\n"
        "        screen = self._opmode_stack.currentWidget()\n"
        "        le_dest = getattr(screen, \"le_dest\", None)\n"
        "        if le_dest is None:\n"
        "            return\n"
        "        dest = le_dest.text().strip().upper()\n"
        "        if not dest:\n"
        "            from PyQt6.QtWidgets import QMessageBox\n"
        "            QMessageBox.warning(self, \"PACTOR Connect\",\n"
        "                                \"Please enter a destination callsign.\")\n"
        "            return\n"
        "        if not self._serial.is_connected:\n"
        "            return\n"
        "        from pk232py.comm.frame import build_command\n"
        "        # 1. Enter PACTOR standby\n"
        "        stby = build_command(b'PT')\n"
        "        self._serial.send_command(stby[2:4], stby[4:-1])\n"
        "        # 2. Initiate ARQ call (mnemonic AC, same as AMTOR but for PACTOR)\n"
        "        call = build_command(b'AC', dest.encode('ascii'))\n"
        "        self._serial.send_command(call[2:4], call[4:-1])\n"
        "        self._log_monitor(f\"[PACTOR] Connecting → {dest}\")\n"
        "\n"
        "    def _on_pactor_ptlist(self) -> None:\n"
        "        \"\"\"PTLIST button — enter PACTOR listen mode (mnemonic PN).\"\"\"\n"
        "        from pk232py.modes.pactor import PACTORMode\n"
        "        frame = PACTORMode.ptlist_frame()\n"
        "        if self._pactor_send(frame):\n"
        "            self._log_monitor(\"[PACTOR] PTLIST — listening\")\n"
        "\n"
        "    def _on_pactor_ptsend(self) -> None:\n"
        "        \"\"\"PTSEND button — start PACTOR FEC unproto transmission (mnemonic PD).\n"
        "\n"
        "        Sends TX window contents as PTSEND unproto.\n"
        "        \"\"\"\n"
        "        if not self._serial.is_connected:\n"
        "            return\n"
        "        from pk232py.comm.frame import build_command\n"
        "        # PD 1,2 = 100 baud, 2 repetitions (sensible default)\n"
        "        frame = build_command(b'PD', b'1,2')\n"
        "        self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "        self._log_monitor(\"[PACTOR] PTSEND started (100 Bd, 2x)\")\n"
        "\n"
        "    def _on_pactor_disconnect(self) -> None:\n"
        "        \"\"\"Disconnect button — terminate PACTOR ARQ (DI then PT standby).\"\"\"\n"
        "        if not self._serial.is_connected:\n"
        "            return\n"
        "        from pk232py.comm.frame import build_command\n"
        "        di = build_command(b'DI')\n"
        "        self._serial.send_command(di[2:4], di[4:-1])\n"
        "        self._log_monitor(\"[PACTOR] Disconnect sent\")\n"
        "\n"
        "    def _on_pactor_stby(self) -> None:\n"
        "        \"\"\"STBY button — return to PACTOR standby (mnemonic PT).\"\"\"\n"
        "        if not self._serial.is_connected:\n"
        "            return\n"
        "        from pk232py.comm.frame import build_command\n"
        "        frame = build_command(b'PT')\n"
        "        self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "        self._log_monitor(\"[PACTOR] Standby\")\n"
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
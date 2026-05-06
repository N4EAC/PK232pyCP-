"""
patch_fix_toggle_disconnect.py
===============================
Behebt den Bug in _wire_toggle_buttons():

  btn.toggled.disconnect()   ← trennt ALLE Connections, auch screen-interne

Das reisst _on_send_toggled und _on_receive_toggled vom Screen ab →
  - SEND-Button blinkt nicht mehr
  - Keine Eingabe im TX-Fenster möglich
  - RECEIVE-Button reagiert nicht mehr visuell

Fix: disconnect() nur aufrufen wenn wir wissen welchen Slot wir trennen.
Da wir dynamische Closures verwenden können wir nicht disconnect(slot) 
aufrufen. Stattdessen: beim zweiten Aufruf einfach einen neuen Slot 
hinzufügen — Qt hat kein Problem damit solange wir nicht stapeln.

Loesung: Wir speichern die erzeugten Slots in einem Dict auf der
MainWindow-Instanz und disconnecten nur unseren eigenen Slot.

Aufruf vom Repo-Root:
    python patch_fix_toggle_disconnect.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")

PATCHES = [
    (
        # Altes disconnect() ohne Argument + reconnect
        "        for btn_name, (frame_fn, inst_attr) in toggle_map.items():\n"
        "            btn = getattr(screen, btn_name, None)\n"
        "            if btn is None or frame_fn is None:\n"
        "                continue\n"
        "            # Build a closure capturing frame_fn and inst_attr\n"
        "            def _make_slot(fn, attr):\n"
        "                def slot(checked: bool) -> None:\n"
        "                    if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "                        return\n"
        "                    frame = fn(checked)\n"
        "                    self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "                    if attr:\n"
        "                        m = self._modes.current_mode\n"
        "                        if m and hasattr(m, attr):\n"
        "                            setattr(m, attr, checked)\n"
        "                    self._log_monitor(\n"
        "                        f\"[PARAM] {btn_name.replace('btn_', '').upper()}\"\n"
        "                        f\" → {'ON' if checked else 'OFF'}\"\n"
        "                    )\n"
        "                return slot\n"
        "            try:\n"
        "                btn.toggled.disconnect()\n"
        "            except (RuntimeError, TypeError):\n"
        "                pass\n"
        "            # Reconnect screen-internal slot first (visual only)\n"
        "            # then the TNC slot\n"
        "            btn.toggled.connect(_make_slot(frame_fn, inst_attr))",

        # Neues Muster: Slot in _toggle_slots speichern und nur unseren trennen
        "        # _toggle_slots: Dict btn_name → letzter verbundener TNC-Slot\n"
        "        # Wird auf der Instanz gespeichert um bei erneutem Aufruf\n"
        "        # nur unseren Slot zu trennen — nicht den screen-internen.\n"
        "        if not hasattr(self, '_toggle_slots'):\n"
        "            self._toggle_slots = {}\n"
        "\n"
        "        for btn_name, (frame_fn, inst_attr) in toggle_map.items():\n"
        "            btn = getattr(screen, btn_name, None)\n"
        "            if btn is None or frame_fn is None:\n"
        "                continue\n"
        "\n"
        "            # Nur unseren eigenen Slot trennen (nicht screen-interne!)\n"
        "            old_slot = self._toggle_slots.get(btn_name)\n"
        "            if old_slot is not None:\n"
        "                try:\n"
        "                    btn.toggled.disconnect(old_slot)\n"
        "                except (RuntimeError, TypeError):\n"
        "                    pass\n"
        "\n"
        "            # Neuen Slot erzeugen und speichern\n"
        "            def _make_slot(fn, attr, bname):\n"
        "                def slot(checked: bool) -> None:\n"
        "                    if not self._serial.is_connected or not self._serial.is_host_mode:\n"
        "                        return\n"
        "                    frame = fn(checked)\n"
        "                    self._serial.send_command(frame[2:4], frame[4:-1])\n"
        "                    if attr:\n"
        "                        m = self._modes.current_mode\n"
        "                        if m and hasattr(m, attr):\n"
        "                            setattr(m, attr, checked)\n"
        "                    self._log_monitor(\n"
        "                        f\"[PARAM] {bname.replace('btn_', '').upper()}\"\n"
        "                        f\" → {'ON' if checked else 'OFF'}\"\n"
        "                    )\n"
        "                return slot\n"
        "\n"
        "            new_slot = _make_slot(frame_fn, inst_attr, btn_name)\n"
        "            self._toggle_slots[btn_name] = new_slot\n"
        "            btn.toggled.connect(new_slot)"
    ),
]


def apply_patches(path: Path, patches: list[tuple]) -> None:
    src = path.read_text(encoding="utf-8")

    missing = []
    for i, patch in enumerate(patches, 1):
        if patch[0] not in src:
            missing.append(i)
            print(f"  Patch {i} — Suchstring nicht gefunden")
            print(f"  Erste 80 Zeichen: {repr(patch[0][:80])}")

    if missing:
        print("Patch wird NICHT angewendet.")
        return

    for i, patch in enumerate(patches, 1):
        src = src.replace(patch[0], patch[1], 1)
        print(f"OK  Patch {i} angewendet")

    import ast
    try:
        ast.parse(src)
        print("Syntax OK")
    except SyntaxError as e:
        print(f"FEHLER Syntax: {e} — Datei nicht geschrieben")
        return

    path.write_text(src, encoding="utf-8")
    print(f"Fertig — {path} aktualisiert ({len(src.splitlines())} Zeilen)")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply_patches(TARGET, PATCHES)
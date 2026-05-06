"""
patch_fix_disconnect.py
=======================
PyQt6 wirft TypeError (nicht RuntimeError) wenn ein Signal-Slot-Paar
noch nicht verbunden war und disconnect() aufgerufen wird.

Fix: alle except RuntimeError → except (RuntimeError, TypeError)

Aufruf vom Repo-Root:
    python patch_fix_disconnect.py
"""

from pathlib import Path

TARGET = Path("src/pk232py/ui/main_window.py")


def apply_fix(path: Path) -> None:
    src = path.read_text(encoding="utf-8")

    # Ersetze alle except RuntimeError in disconnect-Blöcken
    # durch except (RuntimeError, TypeError)
    old = "            except RuntimeError:\n                pass   # not connected yet — harmless"
    new = "            except (RuntimeError, TypeError):\n                pass   # not connected yet — harmless"

    count = src.count(old)
    if count == 0:
        # Versuche die zweite Variante (ohne Kommentar)
        old2 = "            except RuntimeError:\n                pass\n"
        new2 = "            except (RuntimeError, TypeError):\n                pass\n"
        count2 = src.count(old2)
        if count2 == 0:
            print("FEHLER: Kein passender except-Block gefunden.")
            return
        src = src.replace(old2, new2)
        print(f"OK  {count2} except-Bloecke korrigiert (Variante 2)")
    else:
        src = src.replace(old, new)
        print(f"OK  {count} except-Block(e) korrigiert (Variante 1)")

    # Ersetze alle verbleibenden except RuntimeError in disconnect-Kontexten
    # (genereller Sweep für alle pass-Blöcke nach disconnect)
    import re
    src_new = re.sub(
        r'(\.disconnect\([^)]*\)\s*\n\s*)except RuntimeError:(\s*\n\s*pass)',
        r'\1except (RuntimeError, TypeError):\2',
        src
    )
    changed = src_new != src
    src = src_new

    path.write_text(src, encoding="utf-8")
    if changed:
        print("OK  Weitere except-Bloecke per regex korrigiert")
    print(f"\nFertig — {path} aktualisiert.")


if __name__ == "__main__":
    if not TARGET.exists():
        print(f"Datei nicht gefunden: {TARGET}")
    else:
        apply_fix(TARGET)
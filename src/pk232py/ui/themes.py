# pk232py - Modern multimode terminal for AEA PK-232 / PK-232MBX TNC
# Copyright (C) 2026  OE3GAS  —  GPL v2
"""Theme presets and QPalette construction for the appearance system.

A *theme* is a named bundle of font + colours. Three of the four presets
(Dark / Mono / Retro) drive a full custom :class:`QPalette`; the fourth
(Air) keeps the native system look.

------------------------------------------------------------------------------
LERNMODUS — why a QPalette, and why a style switch
------------------------------------------------------------------------------

1. WHY A PALETTE AT ALL.
   PK232PY styles its RX/TX text panels directly with stylesheets, but
   everything Qt draws for us — menus, dialogs, message boxes, the OK/Cancel
   buttons, spin boxes, combo-box popups — takes its colours from the
   *application* QPalette. If we only set the panel stylesheets and leave the
   palette at the OS default, a dark window gets dark dialogs with *dark*
   button text → unreadable. Setting every relevant ColorRole fixes that.

2. WHY THE STYLE MATTERS (native vs Fusion).
   The native Windows style ("windowsvista") draws push-buttons via the OS
   theme engine and largely IGNORES QPalette.ButtonText — so a custom palette
   alone does NOT fix the unreadable-button bug. The Fusion style honours the
   palette completely. So themed presets switch the app to Fusion; Air switches
   back to the captured system style so it looks truly native.

3. WHY AIR USES system_palette INSTEAD OF LIGHT COLOURS.
   We could fake a light theme by setting white-ish palette roles, but native
   widgets (scrollbars, buttons, the menu chrome) would still be drawn by
   Fusion and look subtly foreign. Restoring the system style + its
   standardPalette() keeps those widgets 100 % native — no visual break.

------------------------------------------------------------------------------
How the ColorRoles map (Dark / Mono / Retro)
------------------------------------------------------------------------------
  Window / WindowText        = bg          / fg
  Base / Text                = bg darker   / fg     (text-entry backgrounds)
  AlternateBase              = bg lighter           (alternating rows)
  Button / ButtonText        = bg lighter  / fg     (push buttons — the fix)
  ToolTipBase / ToolTipText  = bg lighter  / fg
  Highlight / HighlightedText= accent      / bg     (selection)
  PlaceholderText            = fg/bg blend
  Disabled {Text,ButtonText,WindowText} = greyed fg/bg blend
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette


@dataclass(frozen=True)
class Theme:
    """A named appearance preset.

    Attributes:
        key:            stable INI/identifier key ("dark", "mono", ...).
        name:           human-readable menu label ("Dark", "Mono", ...).
        font_family:    display font family.
        font_size:      display font point size.
        bg / fg:        background / foreground hex colours. Ignored for the
                        palette when ``system_palette`` is True, but still used
                        for the RX/TX text panels.
        system_palette: True → keep the native system palette/style (Air).
                        False → build and apply a full custom QPalette (Fusion).
    """
    key:            str
    name:           str
    font_family:    str
    font_size:      int
    bg:             str
    fg:             str
    system_palette: bool


THEMES: dict[str, Theme] = {
    "dark": Theme(
        key="dark", name="Dark",
        font_family="Cascadia Mono SemiBold", font_size=14,
        bg="#1e1e1e", fg="#ffffff", system_palette=False,
    ),
    # Mono = classic black/white/grey terminal — deliberately NO colour.
    # fg is light grey (not pure white) so it is a touch softer on the eyes;
    # build_palette derives every other role as a grey shade of bg/fg.
    "mono": Theme(
        key="mono", name="Mono",
        font_family="Courier New", font_size=14,
        bg="#000000", fg="#e0e0e0", system_palette=False,
    ),
    "retro": Theme(
        key="retro", name="Retro",
        font_family="Courier New", font_size=14,
        bg="#0d0800", fg="#ffb000", system_palette=False,
    ),
    # Air keeps the native look; bg/fg are light values used ONLY for the
    # RX/TX text panels (the global palette stays the system default).
    "air": Theme(
        key="air", name="Air",
        font_family="Segoe UI", font_size=11,
        bg="#ffffff", fg="#1a1a1a", system_palette=True,
    ),
}

# Order shown in the Configure → Appearance submenu.
THEME_ORDER: tuple[str, ...] = ("dark", "mono", "retro", "air")


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _shift(c: QColor, delta: int) -> QColor:
    """Lighten (delta>0) / darken (delta<0) by an ADDITIVE per-channel offset.

    Additive (not QColor.lighter()) so it still works on pure black: a
    multiplicative lighten leaves #000000 black, whereas Mono's button needs to
    be visibly lighter than its black background.
    """
    def clamp(v: int) -> int:
        return max(0, min(255, v))
    return QColor(clamp(c.red() + delta), clamp(c.green() + delta),
                  clamp(c.blue() + delta))


def _blend(a: QColor, b: QColor, t: float) -> QColor:
    """Linear blend: t=0 → a, t=1 → b."""
    return QColor(
        round(a.red()   * (1 - t) + b.red()   * t),
        round(a.green() * (1 - t) + b.green() * t),
        round(a.blue()  * (1 - t) + b.blue()  * t),
    )


def build_palette(theme: Theme) -> QPalette | None:
    """Return a full custom QPalette for *theme*, or None for a system theme.

    None signals the caller to restore the native style + standardPalette()
    (Air). For Dark/Mono/Retro, every ColorRole that Qt-drawn widgets read is
    set explicitly so dialogs, menus and push-buttons are readable.
    """
    if theme.system_palette:
        return None

    bg = QColor(theme.bg)
    fg = QColor(theme.fg)

    base      = _shift(bg, -8)      # text-entry background, slightly darker
    alt_base  = _shift(bg, +6)
    button    = _shift(bg, +28)     # push-button face, clearly lighter
    tip_bg    = _shift(bg, +28)
    highlight = _blend(fg, bg, 0.45)   # selection: accent toward fg
    disabled  = _blend(fg, bg, 0.55)   # greyed-out text

    pal = QPalette()
    R = QPalette.ColorRole
    G = QPalette.ColorGroup

    pal.setColor(R.Window,          bg)
    pal.setColor(R.WindowText,      fg)
    pal.setColor(R.Base,            base)
    pal.setColor(R.AlternateBase,   alt_base)
    pal.setColor(R.Text,            fg)
    pal.setColor(R.Button,          button)
    pal.setColor(R.ButtonText,      fg)        # ← the unreadable-button fix
    pal.setColor(R.BrightText,      QColor("#ff5555"))
    pal.setColor(R.ToolTipBase,     tip_bg)
    pal.setColor(R.ToolTipText,     fg)
    pal.setColor(R.PlaceholderText, _blend(fg, bg, 0.5))
    pal.setColor(R.Highlight,       highlight)
    pal.setColor(R.HighlightedText, bg)
    pal.setColor(R.Link,            highlight)

    # Disabled group: dim the text-ish roles so inactive widgets read greyed.
    for role in (R.Text, R.ButtonText, R.WindowText):
        pal.setColor(G.Disabled, role, disabled)

    return pal

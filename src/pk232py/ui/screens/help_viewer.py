"""
help_viewer.py — Help system for PK232PY.

Provides:
    HelpViewer   — QDialog that renders Markdown help files
    show_help()  — convenience function to open help for a topic

Architecture:
    Help files are Markdown (.md) files in the help/ directory
    relative to the package root. Each topic has its own file.

    HelpViewer renders Markdown to HTML using Python's built-in
    markdown module (or a simple fallback renderer if not available).

    Tooltips for individual buttons are registered centrally via
    the TooltipManager in tooltip_manager.py — this keeps tooltip
    text out of the UI code and allows future localisation.

Usage:
    # Open help for a specific topic:
    from .help_viewer import show_help
    show_help("baudot", parent=self)

    # From MacroEditDialog Help button:
    show_help("baudot", anchor="macros", parent=self)

Available topics (help/*.md files):
    "baudot"    → help_baudot.md   (Baudot RTTY operation)
    "shortcuts" → help_baudot.md#keyboard-shortcuts (anchor)
    "macros"    → help_baudot.md#macros
"""

from __future__ import annotations

import os
import re
import logging

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextBrowser, QLabel, QComboBox,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QFont, QDesktopServices, QPalette

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Help file registry
# ---------------------------------------------------------------------------

# Maps topic name → (filename, optional anchor)
HELP_TOPICS: dict[str, tuple[str, str]] = {
    # top-level
    "index":     ("help_index.md",  ""),
    # modes
    "amtor":     ("help_amtor.md",  ""),
    "baudot":    ("help_baudot.md", ""),
    "ascii":     ("help_ascii.md",  ""),
    "morse":     ("help_morse.md",  ""),
    "pactor":    ("help_pactor.md", ""),
    "packet":    ("help_packet.md", ""),
    "vhf":       ("help_packet.md", ""),   # VHF Packet → same file as HF Packet
    "navtex":    ("help_navtex.md", ""),
    "fax":       ("help_fax.md",    ""),
    "signal":    ("help_signal.md", ""),
    # common topics (anchors inside help_baudot.md)
    "shortcuts": ("help_baudot.md", "keyboard-shortcuts"),
    "macros":    ("help_baudot.md", "macros"),
    "controls":  ("help_controls.md", ""),
    "rbaud":     ("help_baudot.md", "rbaud--transmission-speed"),
}

# Location of help files — anchored on this module's own __file__.
#
# This resolves correctly in BOTH a normal interpreter AND a Nuitka --onefile
# build:
#   * Normal interpreter: this module is src/pk232py/ui/screens/help_viewer.py,
#     so ../../help → src/pk232py/help.
#   * Nuitka --onefile: at startup Nuitka unpacks the payload to a TEMP dir and
#     sets __file__ to <temp>/pk232py/ui/screens/help_viewer.(py|pyc). The help
#     files, bundled via --include-data-dir=src/pk232py/help=pk232py/help, land
#     at <temp>/pk232py/help — the SAME ../../help relative to this module.
#
# Do NOT use __compiled__.containing_dir for bundled data: it points at the EXE
# directory (dist/), NOT the temp extraction dir where the data actually lives.
_HELP_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "help")
)

# In a compiled build, log the resolved help dir once so a future path problem
# is diagnosable from a --log-level DEBUG run on real hardware.
try:
    __compiled__          # noqa: F821  (Nuitka built-in, present only when compiled)
    logger.debug("onefile _HELP_DIR: %s (exists: %s)",
                 _HELP_DIR, os.path.isdir(_HELP_DIR))
except NameError:
    pass


def _find_help_file(filename: str) -> str | None:
    """Return absolute path to help file, or None if not found."""
    path = os.path.normpath(os.path.join(_HELP_DIR, filename))
    return path if os.path.isfile(path) else None


# ---------------------------------------------------------------------------
# Markdown → HTML converter
# ---------------------------------------------------------------------------

def _palette_colors() -> dict[str, str]:
    """Derive the help-page CSS colours from the current QApplication palette.

    Read at render time, so the help page matches whatever theme is active
    (dark, mono/light, retro, or the native Air palette). Reopening the viewer
    after a theme switch picks up the new colours automatically.
    """
    pal = QApplication.instance().palette()
    R = QPalette.ColorRole
    base = pal.color(R.Base)
    text = pal.color(R.Text)
    accent = pal.color(R.Link)
    alt = pal.color(R.AlternateBase)

    def blend(a: QColor, b: QColor, t: float) -> QColor:
        return QColor(round(a.red() * (1 - t) + b.red() * t),
                      round(a.green() * (1 - t) + b.green() * t),
                      round(a.blue() * (1 - t) + b.blue() * t))

    return {
        "bg":     base.name(),
        "fg":     text.name(),
        "head":   accent.name(),
        "alt":    alt.name(),
        "border": blend(text, base, 0.65).name(),   # subtle line colour
        "muted":  blend(text, base, 0.35).name(),    # blockquote / dim text
    }


def _md_to_html(md_text: str, colors: dict[str, str] | None = None) -> str:
    """Convert Markdown to HTML, styled from the active palette.

    Tries the 'markdown' package first (pip install markdown).
    Falls back to a simple built-in converter if not available.
    """
    try:
        import markdown as _md
        html = _md.markdown(
            md_text,
            extensions=["tables", "fenced_code", "toc"],
        )
    except ImportError:
        html = _simple_md_to_html(md_text)

    c = colors or _palette_colors()

    # Wrap in a palette-driven HTML document (no hardcoded dark colours).
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    background-color: {c['bg']};
    color: {c['fg']};
    margin: 16px;
    line-height: 1.5;
  }}
  h1 {{ color: {c['head']}; font-size: 18px; border-bottom: 1px solid {c['border']}; padding-bottom: 4px; }}
  h2 {{ color: {c['head']}; font-size: 15px; margin-top: 20px; border-bottom: 1px solid {c['border']}; padding-bottom: 2px; }}
  h3 {{ color: {c['head']}; font-size: 13px; margin-top: 14px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  th {{ background-color: {c['alt']}; color: {c['head']}; padding: 4px 8px;
        border: 1px solid {c['border']}; text-align: left; }}
  td {{ padding: 4px 8px; border: 1px solid {c['border']}; }}
  tr:nth-child(even) {{ background-color: {c['alt']}; }}
  code {{ background-color: {c['alt']}; color: {c['fg']};
          padding: 1px 4px; border-radius: 3px;
          font-family: 'Courier New', monospace; font-size: 12px; }}
  pre  {{ background-color: {c['alt']}; color: {c['fg']}; padding: 8px;
          border-radius: 4px; font-family: 'Courier New', monospace;
          font-size: 12px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  hr   {{ border: none; border-top: 1px solid {c['border']}; margin: 16px 0; }}
  a    {{ color: {c['head']}; }}
  strong {{ color: {c['fg']}; }}
  em   {{ color: {c['head']}; }}
  ul, ol {{ margin: 4px 0; padding-left: 24px; }}
  li   {{ margin: 2px 0; }}
  blockquote {{ border-left: 3px solid {c['border']}; margin: 8px 0;
                padding: 4px 12px; color: {c['muted']}; }}
</style>
</head>
<body>
{html}
</body>
</html>"""


def _simple_md_to_html(md: str) -> str:
    """Minimal Markdown → HTML converter (no external dependencies).

    Handles: headings, bold, italic, code, tables, hr, lists.
    """
    lines = md.split('\n')
    html_lines = []
    in_table = False
    in_code  = False
    in_list  = False

    def _inline(text: str) -> str:
        # code spans
        text = re.sub(r'`([^`]+)`',
                      r'<code>\1</code>', text)
        # bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # links
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                      r'<a href="\2">\1</a>', text)
        return text

    for line in lines:
        # Fenced code blocks
        if line.startswith('```'):
            if in_code:
                html_lines.append('</pre>')
                in_code = False
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<pre><code>')
                in_code = True
            continue
        if in_code:
            html_lines.append(line.replace('&', '&amp;')
                              .replace('<', '&lt;').replace('>', '&gt;'))
            continue

        # Headings
        m = re.match(r'^(#{1,3})\s+(.+)', line)
        if m:
            if in_list: html_lines.append('</ul>'); in_list = False
            level = len(m.group(1))
            html_lines.append(f'<h{level}>{_inline(m.group(2))}</h{level}>')
            continue

        # HR
        if re.match(r'^---+$', line.strip()):
            html_lines.append('<hr>')
            continue

        # Table rows
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append('<table>')
                in_table = True
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                html_lines.append('<tr>' +
                    ''.join(f'<th>{_inline(c)}</th>' for c in cells) + '</tr>')
            elif re.match(r'^[|\s\-:]+$', line):
                pass  # separator row — skip
            else:
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                html_lines.append('<tr>' +
                    ''.join(f'<td>{_inline(c)}</td>' for c in cells) + '</tr>')
            continue
        else:
            if in_table:
                html_lines.append('</table>')
                in_table = False

        # List items
        m = re.match(r'^[-*]\s+(.+)', line)
        if m:
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{_inline(m.group(1))}</li>')
            continue

        # Close list if needed
        if in_list and not line.strip():
            html_lines.append('</ul>')
            in_list = False

        # Blank line
        if not line.strip():
            html_lines.append('<p>')
            continue

        # Normal paragraph
        html_lines.append(f'<p>{_inline(line)}</p>')

    if in_list:  html_lines.append('</ul>')
    if in_table: html_lines.append('</table>')
    if in_code:  html_lines.append('</pre>')

    return '\n'.join(html_lines)


# ---------------------------------------------------------------------------
# HelpViewer dialog
# ---------------------------------------------------------------------------

class HelpViewer(QDialog):
    """Modal help viewer that renders Markdown help files as HTML.

    Features:
    - Renders help_baudot.md (and future help files)
    - Topic selector dropdown for navigation between topics
    - Back/Forward navigation
    - Internal anchor links work (e.g. #macros, #keyboard-shortcuts)
    - External links open in the system browser

    Usage:
        viewer = HelpViewer(topic="baudot", parent=self)
        viewer.exec()
    """

    def __init__(self, topic: str = "index", parent=None):
        super().__init__(parent)
        self.setWindowTitle("PK232PY Help")
        self.setMinimumSize(700, 560)
        self.resize(760, 600)
        self.setModal(True)
        self._current_topic = topic
        self._build_ui()
        self._load_topic(topic)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Top bar: topic selector + nav buttons ─────────────────────
        top = QHBoxLayout()

        lbl = QLabel("Topic:")
        lbl.setFixedWidth(45)
        top.addWidget(lbl)

        self._topic_combo = QComboBox()
        self._topic_combo.setFixedWidth(200)
        for key, (fname, anchor) in HELP_TOPICS.items():
            label = key.replace("-", " ").replace("_", " ").title()
            self._topic_combo.addItem(label, key)
        self._topic_combo.currentIndexChanged.connect(self._on_topic_changed)
        top.addWidget(self._topic_combo)
        top.addStretch()

        self._btn_close = QPushButton("Close")
        self._btn_close.setFixedWidth(80)
        self._btn_close.clicked.connect(self.accept)
        top.addWidget(self._btn_close)
        root.addLayout(top)

        # ── Browser ───────────────────────────────────────────────────
        self._browser = QTextBrowser()
        self._browser.setFont(QFont("Segoe UI", 10))
        self._browser.setOpenLinks(False)   # handle links ourselves
        self._browser.anchorClicked.connect(self._on_link_clicked)
        root.addWidget(self._browser)

        # ── Status bar ────────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setFont(QFont("Segoe UI", 8))
        self._status.setStyleSheet("color: #667788;")
        root.addWidget(self._status)

    def _load_topic(self, topic: str) -> None:
        """Load and render a help topic."""
        if topic not in HELP_TOPICS:
            self._browser.setHtml(
                f"<p>Help topic <b>{topic}</b> not found.</p>"
            )
            return

        filename, anchor = HELP_TOPICS[topic]
        path = _find_help_file(filename)

        if path is None:
            self._browser.setHtml(
                f"<p>Help file <b>{filename}</b> not found.<br>"
                f"Expected location: {os.path.normpath(_HELP_DIR)}</p>"
            )
            self._status.setText(f"File not found: {filename}")
            return

        try:
            with open(path, encoding="utf-8") as f:
                md_text = f.read()
        except OSError as e:
            self._browser.setHtml(f"<p>Error reading help file: {e}</p>")
            return

        colors = _palette_colors()
        # Match the widget background to the page so the body margin has no
        # mismatched border (palette-driven, like the rendered HTML).
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background: {colors['bg']}; color: {colors['fg']};"
            f" border: none; }}"
        )
        self._browser.setHtml(_md_to_html(md_text, colors))

        # Scroll to anchor if specified
        if anchor:
            self._browser.scrollToAnchor(anchor)

        self._status.setText(f"{filename}")
        self._current_topic = topic

        # Sync combo
        for i in range(self._topic_combo.count()):
            if self._topic_combo.itemData(i) == topic:
                self._topic_combo.blockSignals(True)
                self._topic_combo.setCurrentIndex(i)
                self._topic_combo.blockSignals(False)
                break

    def _on_topic_changed(self, index: int) -> None:
        topic = self._topic_combo.itemData(index)
        if topic:
            self._load_topic(topic)

    def _on_link_clicked(self, url: QUrl) -> None:
        """Handle link clicks — internal anchors, topic links, external URLs.

        Three kinds of link can appear in a help page:

          1. ``#macros``       — an anchor inside the *current* page. Just scroll.
          2. ``amtor``         — an internal *topic* link (e.g. ``[AMTOR](amtor)``).
                                 No URL scheme, and the target is a key in
                                 HELP_TOPICS → load that help page (switch topic).
          3. ``http://…``      — an external URL → hand to the system browser.

        Lernmodus: QTextBrowser hands us a QUrl. A relative Markdown link like
        ``[AMTOR](amtor)`` has *no* scheme (``url.scheme() == ""``) and its path
        is ``"amtor"``; an external link carries ``http``/``https``. We therefore
        branch on the scheme/anchor first and only treat schemeless links as
        topic keys — that is what makes the help pages cross-link to each other.
        """
        url_str = url.toString()
        if url_str.startswith('#'):
            # 1. Internal anchor within the current page
            self._browser.scrollToAnchor(url_str[1:])
            return
        if url_str.startswith('http'):
            # 3. External link — open in system browser
            QDesktopServices.openUrl(url)
            return
        # 2. Internal topic link (e.g. [AMTOR](amtor)) → switch help page
        key = url.path() or url_str
        if key in HELP_TOPICS:
            self._load_topic(key)
            return
        logger.debug("Unhandled link: %s", url_str)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def show_help(topic: str = "index", anchor: str = "",
              parent=None) -> None:
    """Open the help viewer for the given topic.

    Args:
        topic:  Topic key from HELP_TOPICS (e.g. "baudot", "macros")
        anchor: Optional section anchor (overrides HELP_TOPICS default)
        parent: Parent widget for the dialog
    """
    # Override anchor if specified
    if anchor and topic in HELP_TOPICS:
        filename = HELP_TOPICS[topic][0]
        # Temporarily patch the anchor — viewer reads from HELP_TOPICS
        orig = HELP_TOPICS[topic]
        HELP_TOPICS[topic] = (filename, anchor)
        viewer = HelpViewer(topic=topic, parent=parent)
        viewer.exec()
        HELP_TOPICS[topic] = orig
    else:
        viewer = HelpViewer(topic=topic, parent=parent)
        viewer.exec()
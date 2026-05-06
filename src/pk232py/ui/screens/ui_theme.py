"""
ui_theme.py — Theme system for PK232PY UI screens.

Provides two themes (dark / light) and helper functions to apply
them to QApplication and individual widgets.

Used by all opmode screens and the mockup launcher.

Usage:
    from .ui_theme import apply_app_style, style_rx_widget, style_tx_widget
    from .ui_theme import get_theme, set_theme, THEMES
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

THEMES: dict[str, dict] = {
    "dark": {
        "name":              "Dark",
        "bg_window":         "#1e2830",
        "bg_widget":         "#1e2830",
        "bg_input":          "#1a2430",
        "bg_input_tx":       "#1a2c1a",
        "bg_button":         "#445566",
        "bg_button_hover":   "#556677",
        "bg_button_pressed": "#334455",
        "bg_button_dis":     "#333333",
        "bg_spin":           "#2a3a4a",
        "bg_combo":          "#2a3a4a",
        "bg_line":           "#1e2830",
        "bg_tooltip":        "#2a3a4a",
        "fg_label":          "#d0e4f4",
        "fg_button":         "#ffffff",
        "fg_button_dis":     "#666666",
        "fg_groupbox":       "#ccddee",
        "fg_checkbox":       "#d0e4f4",
        "fg_spin":           "#ffffff",
        "fg_combo":          "#ffffff",
        "fg_line":           "#ffffff",
        "fg_tooltip":        "#d0e4f4",
        "rx_color":          "#88ccff",
        "tx_color":          "#ffee88",
        "border_input":      "#334455",
        "border_button":     "#334455",
        "border_spin":       "#445566",
        "border_tooltip":    "#556677",
    },
    "light": {
        "name":              "Light",
        "bg_window":         "#f0f0f0",
        "bg_widget":         "#f0f0f0",
        "bg_input":          "#ffffff",
        "bg_input_tx":       "#f0fff0",
        "bg_button":         "#d0d8e0",
        "bg_button_hover":   "#c0c8d8",
        "bg_button_pressed": "#a0b0c0",
        "bg_button_dis":     "#e0e0e0",
        "bg_spin":           "#ffffff",
        "bg_combo":          "#ffffff",
        "bg_line":           "#ffffff",
        "bg_tooltip":        "#ffffcc",
        "fg_label":          "#1a1a2e",
        "fg_button":         "#1a1a2e",
        "fg_button_dis":     "#909090",
        "fg_groupbox":       "#1a1a2e",
        "fg_checkbox":       "#1a1a2e",
        "fg_spin":           "#000000",
        "fg_combo":          "#000000",
        "fg_line":           "#000000",
        "fg_tooltip":        "#333333",
        "rx_color":          "#000080",
        "tx_color":          "#006600",
        "border_input":      "#a0a8b0",
        "border_button":     "#a0a8b0",
        "border_spin":       "#a0a8b0",
        "border_tooltip":    "#c8c800",
    },
}

_current_theme: str = "dark"


def get_theme() -> dict:
    """Return the currently active theme dict."""
    return THEMES[_current_theme]


def set_theme(name: str) -> None:
    """Set the active theme ('dark' or 'light')."""
    global _current_theme
    if name in THEMES:
        _current_theme = name


def apply_app_style(app, theme: str = "dark") -> None:
    """Apply the selected theme as global QApplication stylesheet.

    Call once in main() after creating QApplication:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        apply_app_style(app, "dark")

    Args:
        app:   The QApplication instance.
        theme: Theme name: "dark" (default) or "light".
    """
    set_theme(theme)
    t = get_theme()

    app.setStyleSheet(
        f"QWidget {{ background-color: {t['bg_window']}; }}"

        f"QPushButton {{"
        f"  background-color: {t['bg_button']};"
        f"  color: {t['fg_button']};"
        f"  border: 1px solid {t['border_button']};"
        f"  border-radius: 4px;"
        f"  padding: 4px 8px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {t['bg_button_hover']}; }}"
        f"QPushButton:pressed {{ background-color: {t['bg_button_pressed']}; }}"
        f"QPushButton:disabled {{"
        f"  background-color: {t['bg_button_dis']};"
        f"  color: {t['fg_button_dis']};"
        f"  border: 1px solid {t['border_button']};"
        f"}}"

        f"QLabel {{ color: {t['fg_label']}; }}"
        f"QCheckBox {{ color: {t['fg_checkbox']}; }}"
        f"QGroupBox {{ color: {t['fg_groupbox']}; }}"

        f"QSpinBox {{"
        f"  background-color: {t['bg_spin']};"
        f"  color: {t['fg_spin']};"
        f"  border: 1px solid {t['border_spin']};"
        f"  border-radius: 3px;"
        f"}}"

        f"QComboBox {{"
        f"  background-color: {t['bg_combo']};"
        f"  color: {t['fg_combo']};"
        f"  border: 1px solid {t['border_spin']};"
        f"  border-radius: 3px;"
        f"  padding: 2px;"
        f"}}"
        f"QComboBox QAbstractItemView {{"
        f"  background-color: {t['bg_combo']};"
        f"  color: {t['fg_combo']};"
        f"}}"

        f"QLineEdit {{"
        f"  background-color: {t['bg_line']};"
        f"  color: {t['fg_line']};"
        f"  border: 1px solid {t['border_input']};"
        f"  border-radius: 3px;"
        f"  padding: 2px;"
        f"}}"

        # QTextEdit gets no generic stylesheet —
        # RX and TX are styled individually via style_rx_widget / style_tx_widget
        f"QTextEdit {{"
        f"  border: 1px solid {t['border_input']};"
        f"}}"

        f"QToolTip {{"
        f"  background-color: {t['bg_tooltip']};"
        f"  color: {t['fg_tooltip']};"
        f"  border: 1px solid {t['border_tooltip']};"
        f"}}"
    )


def style_rx_widget(widget) -> None:
    """Apply RX colours to a QTextEdit (call after apply_app_style).

    Args:
        widget: A QTextEdit used as the RX display window.
    """
    t = get_theme()
    widget.setStyleSheet(
        f"QTextEdit {{"
        f"  background-color: {t['bg_input']};"
        f"  color: {t['rx_color']};"
        f"  border: 1px solid {t['border_input']};"
        f"}}"
    )


def style_tx_widget(widget) -> None:
    """Apply TX colours and block cursor to a QTextEdit.

    The block cursor (wide blinking bar) is much more visible than the
    default thin line cursor during fast TX input in amateur radio operation.

    Args:
        widget: A QTextEdit used as the TX input window.
    """
    t = get_theme()
    widget.setStyleSheet(
        f"QTextEdit {{"
        f"  background-color: {t['bg_input_tx']};"
        f"  color: {t['tx_color']};"
        f"  border: 1px solid {t['border_input']};"
        f"}}"
    )
    char_w = widget.fontMetrics().averageCharWidth()
    widget.setCursorWidth(char_w)
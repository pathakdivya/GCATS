"""Colours and the application stylesheet, kept in one place."""

BG = "#141412"
BG_RAIL = "#191917"
BG_BAR = "#1e1e1b"
BG_FIELD = "#1e1e1b"
BORDER = "#2c2c28"
FG = "#e8e6df"
FG_DIM = "#8a8880"
FG_MUTE = "#5a5a55"
ACCENT = "#e03030"
GREEN = "#22c55e"
AMBER = "#f59e0b"
RED = "#ef4444"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {FG};
    font-family: "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}
QLabel#title    {{ font-size: 17px; font-weight: 500; }}
QLabel#subtitle {{ color: {FG_DIM}; font-size: 12px; }}
QLabel#section  {{ color: {FG_MUTE}; font-size: 10px; letter-spacing: 1px; }}
QLabel#mono     {{ font-family: Consolas, monospace; font-size: 12px; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 9px;
    color: {FG};
}}
QLineEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {FG_MUTE}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {BG_BAR};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    color: {FG};
}}

QPushButton {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 16px;
    color: {FG};
}}
QPushButton:hover  {{ border-color: {FG_MUTE}; }}
QPushButton:disabled {{ color: {FG_MUTE}; border-color: #232320; }}
QPushButton#primary {{
    background: {ACCENT};
    border: none;
    color: #fff;
    font-weight: 500;
}}
QPushButton#primary:hover    {{ background: #f04040; }}
QPushButton#primary:disabled {{ background: #4a2020; color: #8a6a6a; }}

QTableWidget {{
    background: {BG_BAR};
    border: 1px solid {BORDER};
    border-radius: 5px;
    gridline-color: #232320;
}}
QHeaderView::section {{
    background: {BG_BAR};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    color: {FG_MUTE};
    font-size: 11px;
}}
QTableWidget::item {{ padding: 4px; }}

QRadioButton {{ spacing: 7px; padding: 3px 0; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


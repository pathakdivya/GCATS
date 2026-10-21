"""Base class for setup pages: title, body, footer (hint + button).

Subclasses override:
    build(layout)   add widgets to the body
    on_enter()      runs each time the page is shown; read self.cfg here
    on_leave()      runs on Continue; write into self.cfg here
"""

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from ..theme import BORDER, FG_DIM, GREEN

logger = logging.getLogger(__name__)


class Page(QWidget):
    done = Signal()          # MainWindow.next_page listens to this.

    title = ""
    subtitle = ""
    button_text = "Continue"

    def __init__(self, cfg, pad) -> None:
        super().__init__()
        self.cfg = cfg
        self.pad = pad

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(0)

        head = QLabel(self.title)
        head.setObjectName("title")
        outer.addWidget(head)

        if self.subtitle:
            sub = QLabel(self.subtitle)
            sub.setObjectName("subtitle")
            outer.addWidget(sub)
        outer.addSpacing(16)

        # Footer widgets exist before build() so build() can call set_ready().
        self.hint = QLabel("")
        self.hint.setStyleSheet(f"color: {FG_DIM}; font-size: 12px;")
        self.button = QPushButton(self.button_text)
        self.button.setObjectName("primary")
        self.button.clicked.connect(self.advance)

        body = QVBoxLayout()
        body.setSpacing(10)
        outer.addLayout(body, 1)
        self.build(body)

        outer.addSpacing(12)
        footer = QHBoxLayout()
        footer.addWidget(self.hint)
        footer.addStretch(1)
        footer.addWidget(self.button)
        outer.addLayout(footer)

    def build(self, layout: QVBoxLayout) -> None:
        raise NotImplementedError

    def on_enter(self) -> None:
        pass

    def on_leave(self) -> None:
        pass

    def advance(self) -> None:
        logger.debug("leaving page: %s", self.title)
        self.on_leave()
        self.done.emit()

    def set_ready(self, ready: bool, hint: str = "") -> None:
        """Enable/disable the footer button and show a hint next to it."""
        self.button.setEnabled(ready)
        self.hint.setText(hint)

    def rebind_button(self, text: str, slot) -> None:
        """Give the footer button a new label and action."""
        self.button.setText(text)
        try:
            self.button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.button.clicked.connect(slot)


def section(text: str) -> QLabel:
    """Small uppercase group heading."""
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl


def note(text: str = "") -> QLabel:
    """Dim, wrapping help text."""
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {FG_DIM}; font-size: 12px;")
    lbl.setWordWrap(True)
    return lbl


def slim_bar() -> QProgressBar:
    """Thin green 0..100 bar used for live readouts."""
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setTextVisible(False)
    bar.setFixedHeight(8)
    bar.setStyleSheet(
        f"QProgressBar {{ background: #232320; border: 1px solid {BORDER};"
        f"border-radius: 4px; }}"
        f"QProgressBar::chunk {{ background: {GREEN}; border-radius: 3px; }}")
    return bar

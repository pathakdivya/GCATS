"""Last setup page: live cursor on the real overlay, plus a Y-flip checkbox.

Uses overlay.draw(), the same code as the session, so it also previews
the appearance settings.
"""

import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from .. import overlay
from .base import Page, note


class OverlayPreview(QWidget):
    """Paints the real overlay with the live reading."""

    def __init__(self, cfg) -> None:
        super().__init__()
        self.cfg = cfg
        self.valence = cfg.neutral
        self.arousal = cfg.neutral
        self.setMinimumHeight(280)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0))
        overlay.draw(p, self.rect(), self.valence, self.arousal, self.cfg)
        p.end()


class VerifyPage(Page):
    title = "Check the mapping"
    subtitle = "Move the stick to all four corners and confirm the cursor follows"
    button_text = "Start experiment"

    def build(self, layout: QVBoxLayout) -> None:
        self.preview = OverlayPreview(self.cfg)
        layout.addWidget(self.preview, 1)

        self.invert = QCheckBox("Up on the stick sends the cursor down - flip it")
        self.invert.toggled.connect(self.toggle_invert)
        layout.addWidget(self.invert)

        self.readout = note()
        layout.addWidget(self.readout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.set_ready(True)

    def on_enter(self) -> None:
        self.invert.setChecked(not self.cfg.invert_y)
        self.pad.apply(self.cfg)
        self.timer.start(16)

    def on_leave(self) -> None:
        self.timer.stop()

    def toggle_invert(self, checked: bool) -> None:
        self.cfg.invert_y = not checked
        self.pad.apply(self.cfg)

    def refresh(self) -> None:
        r = self.pad.poll(time.perf_counter())
        self.preview.valence = r.valence
        self.preview.arousal = r.arousal
        self.preview.update()
        self.readout.setText(
            f"raw ({r.raw_x:+.3f}, {r.raw_y:+.3f})   "
            f"mapped ({r.mapped_x:+.3f}, {r.mapped_y:+.3f})   "
            f"valence {r.valence:.1f}   arousal {r.arousal:.1f}"
        )

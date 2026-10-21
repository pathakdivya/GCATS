"""Pick the thumbstick and confirm button; live bars show the stick moving.

Axis numbers are fixed (left 0/1, right 2/3), not auto-detected.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QProgressBar,
                               QVBoxLayout)

from ..gamepad import BTN_L, BTN_R, LEFT_STICK, RIGHT_STICK
from ..theme import FG_MUTE
from .base import Page, note, section, slim_bar


class MappingPage(Page):
    title = "Controls"
    subtitle = "Choose the thumbstick and the button that confirms a rating"

    def build(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(18)

        col_a = QVBoxLayout()
        col_a.setSpacing(4)
        col_a.addWidget(section("thumbstick"))
        self.stick = QComboBox()
        self.stick.addItems(["left thumbstick", "right thumbstick"])
        self.stick.currentIndexChanged.connect(self.apply_now)
        col_a.addWidget(self.stick)
        row.addLayout(col_a, 1)

        col_b = QVBoxLayout()
        col_b.setSpacing(4)
        col_b.addWidget(section("confirm button"))
        self.shoulder = QComboBox()
        self.shoulder.addItems(["right shoulder", "left shoulder"])
        self.shoulder.currentIndexChanged.connect(self.apply_now)
        col_b.addWidget(self.shoulder)
        row.addLayout(col_b, 1)

        layout.addLayout(row)
        layout.addSpacing(16)

        layout.addWidget(section("live readout"))
        self.bar_x = self._bar(layout, "left / right")
        self.bar_y = self._bar(layout, "down / up")

        self.button_state = note("no button pressed")
        layout.addSpacing(8)
        layout.addWidget(self.button_state)

        layout.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.set_ready(True, "move the stick to check it responds")

    def _bar(self, layout: QVBoxLayout, caption: str) -> QProgressBar:
        wrap = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color: {FG_MUTE}; font-size: 12px;")
        label.setFixedWidth(90)
        wrap.addWidget(label)

        bar = slim_bar()
        bar.setValue(50)
        wrap.addWidget(bar, 1)
        layout.addLayout(wrap)
        return bar

    def on_enter(self) -> None:
        self.apply_now()
        self.timer.start(33)

    def on_leave(self) -> None:
        self.timer.stop()
        self.apply_now()

    def apply_now(self) -> None:
        """Push the current choices onto the pad so the readout reflects them."""
        ax = LEFT_STICK if self.stick.currentIndex() == 0 else RIGHT_STICK
        self.cfg.axis_x, self.cfg.axis_y = ax
        if self.shoulder.currentIndex() == 0:
            self.cfg.btn_confirm, self.cfg.btn_lock = BTN_R, BTN_L
        else:
            self.cfg.btn_confirm, self.cfg.btn_lock = BTN_L, BTN_R
        self.pad.apply(self.cfg)

    def refresh(self) -> None:
        r = self.pad.poll()
        # Bars are 0..100; use mapped (-1..1) so any rating scale displays correctly.
        self.bar_x.setValue(int((r.mapped_x + 1.0) * 50))
        self.bar_y.setValue(int((r.mapped_y + 1.0) * 50))

        held = self.pad.pressed_buttons()
        if not held:
            self.button_state.setText("no button pressed")
        else:
            names = []
            for b in held:
                if b == self.cfg.btn_confirm:
                    names.append(f"button {b} (confirm)")
                elif b == self.cfg.btn_lock:
                    names.append(f"button {b} (other shoulder)")
                else:
                    names.append(f"button {b}")
            self.button_state.setText("pressed: " + ", ".join(names))


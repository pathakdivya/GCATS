"""Measure the untouched stick for SAMPLE_SECONDS.

centre    = mean position; subtracted from every reading (cfg.centre_x/y)
dead_zone = largest distance from the centre x MARGIN, within FLOOR..CEILING
A spread above MAX_SPREAD means the stick was touched; nothing is applied.
"""

import logging
import math
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout

from ..theme import FG_DIM
from .base import Page, slim_bar

logger = logging.getLogger(__name__)

SAMPLE_SECONDS = 3.0
MARGIN = 1.25
FLOOR, CEILING = 0.02, 0.08
MAX_SPREAD = 0.15


class DeadZonePage(Page):
    title = "Dead-zone"
    subtitle = "Let go of the stick while we measure how much it drifts"

    def build(self, layout: QVBoxLayout) -> None:
        self.status = QLabel("Take your hands off the controller, then press Measure.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addSpacing(14)

        self.progress = slim_bar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.result = QLabel("")
        self.result.setObjectName("mono")
        self.result.setStyleSheet(f"color: {FG_DIM};")
        layout.addSpacing(12)
        layout.addWidget(self.result)
        layout.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sample)
        self.points = []
        self.t0 = 0.0

    def on_enter(self) -> None:
        self.pad.apply(self.cfg)
        self.set_ready(True)
        self.rebind_button("Measure", self.start)

    def start(self) -> None:
        self.points = []
        self.t0 = time.perf_counter()
        self.status.setText("Measuring… do not touch the stick.")
        self.result.setText("")
        self.button.setEnabled(False)
        self.timer.start(16)

    def sample(self) -> None:
        axes = self.pad.raw_axes()
        if len(axes) > max(self.cfg.axis_x, self.cfg.axis_y):
            self.points.append((axes[self.cfg.axis_x], axes[self.cfg.axis_y]))

        done = (time.perf_counter() - self.t0) / SAMPLE_SECONDS
        self.progress.setValue(int(min(1.0, done) * 100))
        if done < 1.0:
            return

        self.timer.stop()
        self.button.setEnabled(True)
        if not self.points:
            self.status.setText("No gamepad data. Check the connection and measure again.")
            return

        n = len(self.points)
        cx = sum(x for x, _ in self.points) / n
        cy = sum(y for _, y in self.points) / n
        spread = max(math.hypot(x - cx, y - cy) for x, y in self.points)
        logger.info("dead-zone: centre=(%.4f, %.4f) spread=%.4f samples=%d",
                    cx, cy, spread, n)

        if spread > MAX_SPREAD:
            self.status.setText("The stick moved during the measurement. "
                                "Let go of it and press Measure again.")
            self.result.setText(f"spread        {spread:.4f}   (limit {MAX_SPREAD})")
            return

        dz = min(CEILING, max(FLOOR, spread * MARGIN))
        self.cfg.centre_x, self.cfg.centre_y, self.cfg.dead_zone = cx, cy, dz
        self.pad.apply(self.cfg)

        self.status.setText("Done. You can re-measure if the stick was touched.")
        self.result.setText(
            f"centre        x {cx:+.4f}   y {cy:+.4f}\n"
            f"spread        {spread:.4f}\n"
            f"dead-zone     {dz:.4f}   ({dz * 100:.1f}% of stick travel)"
        )
        self.rebind_button("Continue", self.advance)

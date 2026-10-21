"""Protocol: what sits between stimuli, and how ratings are collected."""

from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDoubleSpinBox,
                               QHBoxLayout, QLabel, QRadioButton, QVBoxLayout)

from ..config import (GAP_BLANK, GAP_FIXATION, RATE_BOTH, RATE_CONTINUOUS,
                      RATE_SUMMARY, SUMMARY_AFTER, SUMMARY_BEFORE)
from ..theme import FG_DIM
from .base import Page, section

MODES = [
    ("Continuous only", RATE_CONTINUOUS,
     "Trace valence and arousal throughout the stimulus."),
    ("Summary only", RATE_SUMMARY,
     "One deliberate rating; no tracing during the stimulus."),
    ("Continuous and summary", RATE_BOTH,
     "Trace during the stimulus, plus one deliberate rating."),
]


class ProtocolPage(Page):
    title = "Protocol"
    subtitle = "Inter-stimulus interval and rating mode"

    def build(self, layout: QVBoxLayout) -> None:
        layout.addWidget(section("between stimuli"))
        gap = QHBoxLayout()
        gap.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(4)
        self.gap_kind = QComboBox()
        self.gap_kind.addItems(["fixation cross", "blank screen"])
        left.addWidget(self.gap_kind)
        gap.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(4)
        self.gap_dur = QDoubleSpinBox()
        self.gap_dur.setRange(0.0, 30.0)
        self.gap_dur.setSingleStep(0.5)
        self.gap_dur.setValue(1.5)
        self.gap_dur.setSuffix("  s")
        right.addWidget(self.gap_dur)
        gap.addLayout(right, 1)
        layout.addLayout(gap)

        layout.addSpacing(14)
        layout.addWidget(section("rating mode"))
        self.modes = QButtonGroup(self)
        for i, (label, value, blurb) in enumerate(MODES):
            radio = QRadioButton(label)
            radio.setProperty("mode", value)
            self.modes.addButton(radio, i)
            layout.addWidget(radio)

            note = QLabel("    " + blurb)
            note.setStyleSheet(f"color: {FG_DIM}; font-size: 12px;")
            layout.addWidget(note)
            if value == RATE_BOTH:
                radio.setChecked(True)
        self.modes.buttonToggled.connect(self.sync_summary_row)

        layout.addSpacing(10)
        self.summary_label = section("summary rating timing")
        layout.addWidget(self.summary_label)
        self.summary_when = QComboBox()
        self.summary_when.addItems(["after the stimulus", "before the stimulus"])
        layout.addWidget(self.summary_when)

        layout.addStretch(1)
        self.set_ready(True)

    def on_enter(self) -> None:
        self.gap_kind.setCurrentIndex(0 if self.cfg.gap_kind == GAP_FIXATION else 1)
        self.gap_dur.setValue(self.cfg.gap_duration)
        for btn in self.modes.buttons():
            if btn.property("mode") == self.cfg.rating_mode:
                btn.setChecked(True)
        self.summary_when.setCurrentIndex(
            0 if self.cfg.summary_when == SUMMARY_AFTER else 1)
        self.sync_summary_row()

    def current_mode(self) -> str:
        btn = self.modes.checkedButton()
        return btn.property("mode") if btn else RATE_BOTH

    def sync_summary_row(self) -> None:
        """The timing choice only makes sense when a summary is collected."""
        show = self.current_mode() in (RATE_SUMMARY, RATE_BOTH)
        self.summary_label.setVisible(show)
        self.summary_when.setVisible(show)

    def on_leave(self) -> None:
        self.cfg.gap_kind = (GAP_FIXATION
                             if self.gap_kind.currentIndex() == 0 else GAP_BLANK)
        self.cfg.gap_duration = self.gap_dur.value()
        self.cfg.rating_mode = self.current_mode()
        self.cfg.summary_when = (SUMMARY_AFTER
                                 if self.summary_when.currentIndex() == 0
                                 else SUMMARY_BEFORE)


"""Configuration page: sampling, scale, mapping, appearance, labels, presets."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QScrollArea, QSlider, QVBoxLayout,
                               QSpinBox, QWidget)

from ..config import (MAP_CIRCLE_TO_SQUARE, MAP_DIRECT, REFRESH,
                      SAMPLING_CHOICES, SCALE_PRESETS)
from .base import Page, note

logger = logging.getLogger(__name__)

CUSTOM = "Custom"


class SettingsPage(Page):
    title = "Experiment configuration"
    subtitle = "Sampling, scale, joystick mapping and interface appearance"

    def build(self, layout: QVBoxLayout) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(0, 0, 12, 0)
        body.setSpacing(12)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        body.addWidget(self._acquisition_box())
        body.addWidget(self._scale_box())
        body.addWidget(self._appearance_box())
        body.addWidget(self._labels_box())
        body.addStretch(1)

        layout.addWidget(self._preset_bar())
        self.set_ready(True)

    def _acquisition_box(self) -> QGroupBox:
        box = QGroupBox("Acquisition")
        form = QFormLayout(box)

        self.sampling = QComboBox()
        for hz in SAMPLING_CHOICES:
            self.sampling.addItem(f"{hz} Hz", hz)
        self.sampling.addItem("Monitor refresh rate", REFRESH)
        form.addRow("Output sampling frequency", self.sampling)

        self.rate_note = note()
        form.addRow("", self.rate_note)
        self.sampling.currentIndexChanged.connect(self._update_rate_note)

        self.mapping = QComboBox()
        self.mapping.addItem("Circle-to-square (recommended)",
                             MAP_CIRCLE_TO_SQUARE)
        self.mapping.addItem("Direct / raw", MAP_DIRECT)
        form.addRow("Joystick mapping", self.mapping)

        form.addRow("", note(
            "A thumbstick's travel is circular; the response space is square. "
            "Circle-to-square lets the cursor reach the corners. Raw values "
            "are saved either way."))
        return box

    def _scale_box(self) -> QGroupBox:
        box = QGroupBox("Rating scale")
        form = QFormLayout(box)

        self.scale = QComboBox()
        for name in SCALE_PRESETS:
            self.scale.addItem(name)
        self.scale.addItem(CUSTOM)
        self.scale.currentIndexChanged.connect(self._sync_scale)
        form.addRow("Range", self.scale)

        row = QHBoxLayout()
        self.axis_min = QDoubleSpinBox()
        self.axis_max = QDoubleSpinBox()
        for spin in (self.axis_min, self.axis_max):
            spin.setRange(-1e6, 1e6)
            spin.setDecimals(2)
            spin.valueChanged.connect(self._validate_scale)
        row.addWidget(QLabel("min"))
        row.addWidget(self.axis_min, 1)
        row.addWidget(QLabel("max"))
        row.addWidget(self.axis_max, 1)
        holder = QWidget()
        holder.setLayout(row)
        form.addRow("Custom values", holder)

        form.addRow("", note(
            "Raw and mapped controller values are always stored alongside "
            "the scaled ones, so you can change the scale later."))
        return box

    def _appearance_box(self) -> QGroupBox:
        box = QGroupBox("Interface")
        form = QFormLayout(box)

        self.cursor_opacity, cursor_row = self._slider(75)
        form.addRow("Cursor opacity", cursor_row)

        self.cursor_size = QSpinBox()
        self.cursor_size.setRange(2, 40)
        self.cursor_size.setValue(9)
        self.cursor_size.setSuffix(" px radius")
        form.addRow("Cursor size", self.cursor_size)

        self.show_axes = QCheckBox("Show central reference axes")
        form.addRow("", self.show_axes)
        self.axes_opacity, self.axes_row = self._slider(22)
        form.addRow("Central axis opacity", self.axes_row)

        self.show_guides = QCheckBox("Show cursor guide lines")
        form.addRow("", self.show_guides)
        self.guide_opacity, self.guide_row = self._slider(16)
        form.addRow("Guide line opacity", self.guide_row)

        self.show_axes.toggled.connect(self.axes_row.setEnabled)
        self.show_guides.toggled.connect(self.guide_row.setEnabled)
        return box

    def _labels_box(self) -> QGroupBox:
        box = QGroupBox("Endpoint labels")
        form = QFormLayout(box)
        self.lab_lv = QLineEdit()
        self.lab_hv = QLineEdit()
        self.lab_la = QLineEdit()
        self.lab_ha = QLineEdit()
        self.summary_question = QLineEdit()
        form.addRow("- x-axis", self.lab_lv)
        form.addRow("+ x-axis", self.lab_hv)
        form.addRow("- y-axis", self.lab_la)
        form.addRow("+ y-axis", self.lab_ha)
        form.addRow("Summary question", self.summary_question)

        form.addRow("", note(
            "Leave axis labels blank to hide them. If the summary "
            "question is blank, the default wording is used: after-stimulus "
            "summary: \"How did this make you feel?\"; before-stimulus "
            "summary: \"How do you feel right now?\""))
        return box

    def _preset_bar(self) -> QWidget:
        bar = QHBoxLayout()
        bar.setSpacing(8)
        for text, slot in (
            ("Load preset", self.load_preset),
            ("Save preset", self.save_preset),
            ("Set as default", self.set_default),
            ("Reset to defaults", self.reset_defaults),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
        bar.addStretch(1)
        holder = QWidget()
        holder.setLayout(bar)
        return holder

    def _slider(self, default: int):
        """0..100 slider with a % readout. Returns (slider, row widget)."""
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(default)
        readout = QLabel(f"{default}%")
        readout.setFixedWidth(42)
        slider.valueChanged.connect(lambda v: readout.setText(f"{v}%"))

        row = QHBoxLayout()
        row.addWidget(slider, 1)
        row.addWidget(readout)
        holder = QWidget()
        holder.setLayout(row)
        return slider, holder

    def _update_rate_note(self) -> None:
        value = self.sampling.currentData()
        if value == REFRESH:
            hz = self.cfg.monitor_refresh
            self.rate_note.setText(
                f"Detected monitor refresh: {hz:.1f} Hz. The gamepad is polled "
                f"as fast as possible and the raw stream is saved "
                f"separately.")
        else:
            self.rate_note.setText(
                "The gamepad is polled as fast as possible and the raw stream is saved "
                "separately. The scaled values are saved at the selected frequency.")

    def _sync_scale(self) -> None:
        name = self.scale.currentText()
        custom = name == CUSTOM
        self.axis_min.setEnabled(custom)
        self.axis_max.setEnabled(custom)
        if not custom:
            lo, hi = SCALE_PRESETS[name]
            self.axis_min.blockSignals(True)
            self.axis_max.blockSignals(True)
            self.axis_min.setValue(lo)
            self.axis_max.setValue(hi)
            self.axis_min.blockSignals(False)
            self.axis_max.blockSignals(False)
        self._validate_scale()

    def _validate_scale(self) -> None:
        if self.axis_max.value() <= self.axis_min.value():
            self.set_ready(False, "scale maximum must exceed the minimum")
        else:
            self.set_ready(True)

    def on_enter(self) -> None:
        self._update_rate_note()
        self.to_widgets()

    def to_widgets(self) -> None:
        cfg = self.cfg

        idx = self.sampling.findData(cfg.sampling_hz)
        self.sampling.setCurrentIndex(idx if idx >= 0 else 1)

        idx = self.mapping.findData(cfg.joystick_mapping)
        self.mapping.setCurrentIndex(max(0, idx))

        match = next((n for n, (lo, hi) in SCALE_PRESETS.items()
                      if lo == cfg.axis_min and hi == cfg.axis_max), CUSTOM)
        self.scale.setCurrentText(match)
        self.axis_min.setValue(cfg.axis_min)
        self.axis_max.setValue(cfg.axis_max)
        self._sync_scale()

        self.cursor_opacity.setValue(int(cfg.cursor_opacity * 100))
        self.cursor_size.setValue(round(cfg.cursor_size))
        self.show_axes.setChecked(cfg.show_central_axes)
        self.axes_opacity.setValue(int(cfg.central_axes_opacity * 100))
        self.show_guides.setChecked(cfg.show_cursor_guides)
        self.guide_opacity.setValue(int(cfg.cursor_guide_opacity * 100))
        self.axes_row.setEnabled(cfg.show_central_axes)
        self.guide_row.setEnabled(cfg.show_cursor_guides)

        self.lab_lv.setText(cfg.low_valence_label)
        self.lab_hv.setText(cfg.high_valence_label)
        self.lab_la.setText(cfg.low_arousal_label)
        self.lab_ha.setText(cfg.high_arousal_label)
        self.summary_question.setText(cfg.summary_question)

    def from_widgets(self) -> None:
        cfg = self.cfg
        cfg.sampling_hz = self.sampling.currentData()
        cfg.joystick_mapping = self.mapping.currentData()
        cfg.axis_min = self.axis_min.value()
        cfg.axis_max = self.axis_max.value()

        cfg.cursor_opacity = self.cursor_opacity.value() / 100.0
        cfg.cursor_size = float(self.cursor_size.value())
        cfg.show_central_axes = self.show_axes.isChecked()
        cfg.central_axes_opacity = self.axes_opacity.value() / 100.0
        cfg.show_cursor_guides = self.show_guides.isChecked()
        cfg.cursor_guide_opacity = self.guide_opacity.value() / 100.0

        cfg.low_valence_label = self.lab_lv.text().strip()
        cfg.high_valence_label = self.lab_hv.text().strip()
        cfg.low_arousal_label = self.lab_la.text().strip()
        cfg.high_arousal_label = self.lab_ha.text().strip()
        cfg.summary_question = self.summary_question.text().strip()

    def on_leave(self) -> None:
        self.from_widgets()
        self.pad.apply(self.cfg)
        try:
            self.cfg.save_as_default()
        except Exception:
            logger.exception("could not save default preset")

    def save_preset(self) -> None:
        self.from_widgets()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save preset", "gcats_preset.json", "JSON (*.json)")
        if not path:
            return
        try:
            self.cfg.save_preset(Path(path))
            self.hint.setText(f"saved {Path(path).name}")
        except Exception as exc:
            logger.exception("could not save preset %s", path)
            QMessageBox.warning(self, "Could not save preset", str(exc))

    def load_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load preset", "", "JSON (*.json)")
        if not path:
            return
        try:
            unknown = self.cfg.load_preset(Path(path))
        except Exception as exc:
            logger.exception("could not load preset %s", path)
            QMessageBox.warning(self, "Could not load preset", str(exc))
            return
        self.to_widgets()
        msg = f"loaded {Path(path).name}"
        if unknown:
            msg += f" ({len(unknown)} unrecognised key(s) ignored)"
        self.hint.setText(msg)

    def set_default(self) -> None:
        self.from_widgets()
        try:
            self.cfg.save_as_default()
            self.hint.setText("saved as the default preset")
        except Exception as exc:
            QMessageBox.warning(self, "Could not set default", str(exc))

    def reset_defaults(self) -> None:
        self.cfg.reset_defaults()
        self.to_widgets()
        self.hint.setText("reset to built-in defaults")

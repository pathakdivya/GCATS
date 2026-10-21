"""Participant details."""

from PySide6.QtWidgets import (QComboBox, QFormLayout, QLineEdit, QSpinBox,
                               QVBoxLayout)

from .base import Page


class ParticipantPage(Page):
    title = "Participant"
    subtitle = "Identifiers written into every row of the data file"

    def build(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        form.setSpacing(10)

        self.pid = QLineEdit()
        self.pid.setPlaceholderText("P001")
        self.pid.textChanged.connect(self.validate)
        form.addRow("Participant ID", self.pid)

        self.session = QSpinBox()
        self.session.setRange(1, 99)
        form.addRow("Session", self.session)

        self.age = QLineEdit()
        self.age.setPlaceholderText("optional")
        form.addRow("Age", self.age)

        self.gender = QComboBox()
        self.gender.addItems(["prefer not to say", "female", "male",
                              "non-binary", "other"])
        form.addRow("Gender", self.gender)

        layout.addLayout(form)
        layout.addStretch(1)

    def on_enter(self) -> None:
        self.validate()

    def validate(self) -> None:
        ok = bool(self.pid.text().strip())
        self.set_ready(ok, "" if ok else "a participant ID is required")

    def on_leave(self) -> None:
        self.cfg.participant_id = self.pid.text().strip()
        self.cfg.session = self.session.value()
        self.cfg.age = self.age.text().strip()
        self.cfg.gender = self.gender.currentText()


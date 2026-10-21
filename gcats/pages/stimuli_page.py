"""Stimulus selection: one file or a folder, with a preview table."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox,
                               QFileDialog, QHBoxLayout, QHeaderView,
                               QLineEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from .. import stimuli as scan_mod
from ..config import (ASPECT_ORIGINAL, ASPECT_RATIOS, ORDER_RANDOM,
                      ORDER_SEQUENTIAL)
from .base import Page, section

KIND_COLOUR = {"image": "#85b7eb", "video": "#97c459", "audio": "#efa927"}


class StimuliPage(Page):
    title = "Stimuli"
    subtitle = "Pick one file or a folder; images, video and audio can be mixed"

    def build(self, layout: QVBoxLayout) -> None:
        self.found = []

        picker = QHBoxLayout()
        self.path_field = QLineEdit()
        self.path_field.setReadOnly(True)
        self.path_field.setPlaceholderText("no stimuli selected")
        picker.addWidget(self.path_field, 1)

        file_btn = QPushButton("Choose file")
        file_btn.clicked.connect(self.pick_file)
        picker.addWidget(file_btn)

        folder_btn = QPushButton("Choose folder")
        folder_btn.clicked.connect(self.pick_folder)
        picker.addWidget(folder_btn)
        layout.addLayout(picker)

        layout.addSpacing(6)
        layout.addWidget(section("detected"))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["file", "type", "length"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setMinimumHeight(150)
        layout.addWidget(self.table, 1)

        opts = QHBoxLayout()
        opts.setSpacing(18)

        col_a = QVBoxLayout()
        col_a.setSpacing(4)
        col_a.addWidget(section("presentation order"))
        self.order = QComboBox()
        self.order.addItems(["random", "sequential"])
        col_a.addWidget(self.order)
        opts.addLayout(col_a, 1)

        col_b = QVBoxLayout()
        col_b.setSpacing(4)
        col_b.addWidget(section("image duration (s)"))
        self.img_dur = QDoubleSpinBox()
        self.img_dur.setRange(0.5, 120.0)
        self.img_dur.setSingleStep(0.5)
        self.img_dur.setValue(5.0)
        self.img_dur.valueChanged.connect(self.refresh_table)
        col_b.addWidget(self.img_dur)
        opts.addLayout(col_b, 1)

        col_c = QVBoxLayout()
        col_c.setSpacing(4)
        col_c.addWidget(section("media aspect ratio"))
        self.aspect = QComboBox()
        self.aspect.addItem(ASPECT_ORIGINAL)
        self.aspect.addItems(ASPECT_RATIOS.keys())
        col_c.addWidget(self.aspect)
        opts.addLayout(col_c, 1)

        col_d = QVBoxLayout()
        col_d.setSpacing(4)
        col_d.addWidget(section("inner margin (%)"))
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0.0, 30.0)
        self.margin.setSingleStep(1.0)
        self.margin.setSuffix("%")
        self.margin.setValue(10.0)
        col_d.addWidget(self.margin)
        opts.addLayout(col_d, 1)

        layout.addLayout(opts)

    def on_enter(self) -> None:
        self.order.setCurrentText(self.cfg.order)
        self.img_dur.setValue(self.cfg.image_duration)
        self.aspect.setCurrentText(self.cfg.media_aspect)
        self.margin.setValue(self.cfg.media_margin_percent)
        self.validate()

    def pick_file(self) -> None:
        exts = " ".join("*" + e for e in sorted(scan_mod.ALL_EXT))
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a stimulus file", "", f"Media ({exts})")
        if path:
            self.load(Path(path))

    def pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a stimulus folder")
        if path:
            self.load(Path(path))

    def load(self, target: Path) -> None:
        self.path_field.setText(str(target))
        self.found = scan_mod.scan(target, self.img_dur.value())
        self.refresh_table()
        self.validate()

    def refresh_table(self) -> None:
        for s in self.found:
            if s.kind == "image":
                s.duration = self.img_dur.value()

        self.table.setRowCount(len(self.found))
        for row, s in enumerate(self.found):
            name = QTableWidgetItem(s.path.name)
            self.table.setItem(row, 0, name)

            kind = QTableWidgetItem(s.kind)
            kind.setForeground(QColor(KIND_COLOUR[s.kind]))
            kind.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, kind)

            if s.kind == "image":
                length = f"{s.duration:.1f} s"
            else:
                secs = scan_mod.probe_duration(s.path)
                length = f"{secs:.1f} s" if secs else "—"
            item = QTableWidgetItem(length)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item)

        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 90)

    def validate(self) -> None:
        n = len(self.found)
        if n == 0:
            self.set_ready(False, "choose a file or folder")
            return
        kinds = {s.kind for s in self.found}
        self.set_ready(True, f"{n} stimul{'us' if n == 1 else 'i'} — "
                             f"{', '.join(sorted(kinds))}")

    def on_leave(self) -> None:
        self.cfg.stimuli = self.found
        self.cfg.image_duration = self.img_dur.value()
        self.cfg.media_aspect = self.aspect.currentText()
        self.cfg.media_margin_percent = self.margin.value()
        self.cfg.order = (ORDER_RANDOM if self.order.currentText() == "random"
                          else ORDER_SEQUENTIAL)


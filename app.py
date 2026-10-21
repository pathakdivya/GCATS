"""Application shell: title bar, stage rail (left), page stack (right).

When the last setup page finishes, the fullscreen SessionWindow opens.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget)

from . import __version__
from . import stimuli as stim_mod
from .config import APP_DIR, Config
from .gamepad import Gamepad
from .pages import SEQUENCE, StimuliPage
from .runner import SessionWindow
from .theme import (AMBER, BG, BG_RAIL, BORDER, FG, FG_DIM, FG_MUTE, GREEN,
                    STYLESHEET)

logger = logging.getLogger(__name__)

LOG_FILE = APP_DIR / "gcats.log"
RAIL_W = 176
BAR_H = 38

WAIT, ACTIVE, DONE = "wait", "active", "done"
DOT = {WAIT: "#383834", ACTIVE: AMBER, DONE: GREEN}
TXT = {WAIT: FG_MUTE, ACTIVE: AMBER, DONE: GREEN}


def _logo_path() -> Path:
    return Path(__file__).resolve().parent.parent / "gcats-logo.svg"


def _logo_pixmap(size: int, tint: str | None = None) -> QPixmap:
    """Render the bundled SVG logo into a pixmap for QLabel."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    renderer = QSvgRenderer(str(_logo_path()))
    if not renderer.isValid():
        logger.warning("could not load logo: %s", _logo_path())
        return pixmap
    painter = QPainter(pixmap)
    renderer.render(painter)
    if tint:
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(tint))
    painter.end()
    return pixmap


class StageRow(QWidget):
    """One rail entry. Emits clicked(index) to jump to that page."""

    clicked = Signal(int)

    def __init__(self, label: str, index: int) -> None:
        super().__init__()
        self.state = WAIT
        self.index = index
        self.setFixedHeight(26)
        self.setCursor(Qt.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(9)

        self.dot = QLabel("●")
        self.dot.setFixedWidth(10)
        row.addWidget(self.dot)

        self.text = QLabel(label)
        row.addWidget(self.text, 1)
        self.set_state(WAIT)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)

    def set_state(self, state: str) -> None:
        self.state = state
        self.dot.setStyleSheet(f"color: {DOT[state]}; font-size: 11px;")
        weight = "500" if state == ACTIVE else "400"
        self.text.setStyleSheet(
            f"color: {TXT[state]}; font-size: 12px; font-weight: {weight};")


class TitleBar(QWidget):
    """Custom bar: brand mark, name, minimise, close. Draggable."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__()
        self.win = window
        self._drag: QPoint | None = None
        self.setFixedHeight(BAR_H)
        self.setStyleSheet("background: transparent; border: none;")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 6, 0)
        row.setSpacing(9)

        mark = QLabel()
        mark.setPixmap(_logo_pixmap(22, AMBER))
        mark.setFixedSize(22, 22)
        mark.setStyleSheet("background: transparent;")
        row.addWidget(mark)

        name = QLabel("G-CATS")
        name.setStyleSheet(f"color: {FG_DIM}; font-size: 13px; font-weight: 500;")
        row.addWidget(name)

        sub = QLabel("Gamepad-based Continuous Affect Tracing System")
        sub.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
        row.addWidget(sub)
        row.addStretch(1)

        row.addWidget(self._chip("_", self.win.showMinimized))
        row.addWidget(self._chip("x", self.win.close))

    @staticmethod
    def _chip(glyph: str, slot) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setFixedSize(30, BAR_H)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ color: {FG_DIM}; font-size: 13px; border: none;"
            f" background: transparent; padding: 0; }}"
            f"QPushButton:hover {{ color: {FG}; }}")
        btn.clicked.connect(slot)
        return btn

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag = event.globalPosition().toPoint() - self.win.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self.win.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event) -> None:
        self._drag = None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = Config()
        self.cfg.load_default()
        self.pad = Gamepad()
        self.session: SessionWindow | None = None

        self.setWindowTitle("G-CATS")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.resize(880, 600)
        self.setStyleSheet(STYLESHEET)

        root = QWidget()
        self.setCentralWidget(root)
        column = QVBoxLayout(root)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(TitleBar(self))

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        column.addLayout(body, 1)

        body.addWidget(self._build_rail())
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        self._detect_refresh()
        self._build_pages()
        self.goto(0)

    def _detect_refresh(self) -> None:
        """Store the display refresh rate in cfg.monitor_refresh."""
        try:
            screen = self.screen() or QApplication.primaryScreen()
            rate = float(screen.refreshRate())
            if rate > 0:
                self.cfg.monitor_refresh = rate
                logger.info("monitor refresh rate: %.1f Hz", rate)
        except Exception:
            logger.exception("could not read refresh rate")

    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setFixedWidth(RAIL_W)
        rail.setStyleSheet(
            f"background: {BG_RAIL}; border-right: 1px solid {BORDER};")

        col = QVBoxLayout(rail)
        col.setContentsMargins(0, 16, 0, 12)
        col.setSpacing(2)

        self.rows: list[StageRow] = []
        last_group = None
        for _, group, label in SEQUENCE:
            if group != last_group:
                header = QLabel(group.upper())
                header.setStyleSheet(
                    f"color: {FG_MUTE}; font-size: 9px; letter-spacing: 1px;"
                    f"padding: 10px 16px 4px;")
                col.addWidget(header)
                last_group = group
            row = StageRow(label, len(self.rows))
            row.clicked.connect(self.goto)
            self.rows.append(row)
            col.addWidget(row)

        col.addStretch(1)
        version = QLabel(f"v{__version__}   IIT Kanpur")
        version.setStyleSheet("color: #3a3a36; font-size: 10px; padding-left: 16px;")
        col.addWidget(version)
        return rail

    def _build_pages(self) -> None:
        self.pages = []
        for page_cls, _, _ in SEQUENCE:
            page = page_cls(self.cfg, self.pad)
            page.done.connect(self.next_page)
            self.pages.append(page)
            self.stack.addWidget(page)

    def goto(self, index: int) -> None:
        logger.info("page -> %s", SEQUENCE[index][2])
        self.index = index
        for i, row in enumerate(self.rows):
            row.set_state(DONE if i < index else ACTIVE if i == index else WAIT)
        self.stack.setCurrentIndex(index)
        self.pages[index].on_enter()

    def next_page(self) -> None:
        if self.index + 1 < len(self.pages):
            self.goto(self.index + 1)
        else:
            self.rows[-1].set_state(DONE)
            self.start_session()

    def start_session(self) -> None:
        self._detect_refresh()
        self.pad.apply(self.cfg)
        order = stim_mod.ordered(self.cfg.stimuli, self.cfg.order)
        logger.info("starting session: participant=%s session=%s stimuli=%d",
                    self.cfg.participant_id, self.cfg.session, len(order))

        self.session = SessionWindow(self.cfg, self.pad, order)
        self.session.finished.connect(self.session_over)
        self.hide()
        self.session.showFullScreen()

    def session_over(self) -> None:
        self.session = None
        self.show()
        self._show_data_saved()

    def _show_data_saved(self) -> None:
        """Mark all stages done and offer a restart or quit."""
        for row in self.rows:
            row.set_state(DONE)
        self.rows[-1].text.setText("Data saved ✓")

        panel = QWidget()
        col = QVBoxLayout(panel)
        col.setAlignment(Qt.AlignCenter)
        col.setSpacing(20)

        msg = QLabel("Session complete.\n\nData has been saved to the output folder.")
        msg.setStyleSheet(f"color: {GREEN}; font-size: 15px; font-weight: 500;")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        col.addWidget(msg)

        restart = QPushButton("Select new stimuli and run again")
        restart.setObjectName("primary")
        restart.setFixedWidth(280)
        restart.clicked.connect(self._restart)
        col.addWidget(restart, 0, Qt.AlignCenter)

        quit_btn = QPushButton("Quit")
        quit_btn.setFixedWidth(280)
        quit_btn.clicked.connect(self.close)
        col.addWidget(quit_btn, 0, Qt.AlignCenter)

        self.stack.addWidget(panel)
        self._saved_panel = panel
        self.stack.setCurrentWidget(panel)

    def _restart(self) -> None:
        """Jump to the stimuli page so another file can be loaded."""
        if hasattr(self, "_saved_panel"):
            self.stack.removeWidget(self._saved_panel)
            self._saved_panel.deleteLater()
            del self._saved_panel
        _, _, label = SEQUENCE[-1]
        self.rows[-1].text.setText(label)
        stimuli_index = next(i for i, (cls, _, _) in enumerate(SEQUENCE)
                             if cls is StimuliPage)
        self.goto(stimuli_index)

    def closeEvent(self, event) -> None:
        self.pad.close()
        super().closeEvent(event)


class SplashScreen(QWidget):
    """Short branded startup screen shown while the application initializes."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(520, 390)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(f"background: {BG}; border: none;")

        col = QVBoxLayout(self)
        col.setContentsMargins(30, 28, 30, 24)
        col.setSpacing(12)
        col.setAlignment(Qt.AlignCenter)

        logo = QLabel()
        logo.setPixmap(_logo_pixmap(150))
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background: transparent;")
        col.addWidget(logo)

        title = QLabel("GCATS")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color: {AMBER}; font-size: 24px; font-weight: 600;")
        col.addWidget(title)

        subtitle = QLabel(
            "Gamepad-based Continuous Affect Tracing System")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {FG_MUTE}; font-size: 12px;")
        col.addWidget(subtitle)

        loading = QLabel("Loading...")
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet(
            f"color: {FG_DIM}; font-size: 11px; font-style: italic;")
        col.addWidget(loading)

        screen = QApplication.primaryScreen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())


def _setup_logging() -> None:
    """Log to the console and ~/.gcats/gcats.log. Set GCATS_DEBUG=1 for detail."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    except OSError as exc:
        print(f"could not open log file {LOG_FILE}: {exc}", file=sys.stderr)

    level = logging.DEBUG if os.environ.get("GCATS_DEBUG") else logging.INFO
    logging.basicConfig(
        level=level, handlers=handlers,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    def log_uncaught(exc_type, exc, tb) -> None:
        logger.critical("uncaught error", exc_info=(exc_type, exc, tb))

    sys.excepthook = log_uncaught


def run() -> int:
    _setup_logging()
    logger.info("G-CATS %s starting", __version__)
    app = QApplication([])
    app.setApplicationName("G-CATS")
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    window = None

    def open_main_window() -> None:
        nonlocal window
        window = MainWindow()
        window.show()
        splash.close()
        splash.deleteLater()

    QTimer.singleShot(1400, open_main_window)
    return app.exec()

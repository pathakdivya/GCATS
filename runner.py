"""Fullscreen session window. One state step per timer tick:

    GAP -> [SUMMARY] -> STIMULUS -> [SUMMARY] -> GAP -> ... -> DONE

Every tick polls the gamepad and writes the reading to the raw file.
The continuous file gets the latest reading each time the chosen output
interval passes. Escape stops the session and still saves.
"""

import logging
import time
from typing import List, Optional

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QMessageBox, QWidget

from . import overlay
from .config import Config, GAP_FIXATION, SUMMARY_BEFORE, Stimulus
from .logger import SessionLogger, PHASE_SUMMARY, PHASE_TRACE
from .media import AudioUnavailable, fit_rect, make_player

logger = logging.getLogger(__name__)

GAP = "gap"
SUMMARY = "summary"
STIMULUS = "stimulus"
DONE = "done"

TICK_MS = 4

BG = QColor(0, 0, 0)
TEXT = QColor(235, 233, 226)
DIM = QColor(140, 138, 132)


class SessionWindow(QWidget):
    """Runs the trial sequence fullscreen. Emits finished() at the end."""

    finished = Signal()

    def __init__(self, cfg: Config, pad, stimuli: List[Stimulus]) -> None:
        super().__init__()
        self.cfg = cfg
        self.pad = pad
        self.stimuli = stimuli
        self.log = SessionLogger(cfg)

        self.setWindowTitle("G-CATS")
        self.setStyleSheet("background: black;")
        self.setCursor(Qt.BlankCursor)

        self.trial = 0
        self.state = GAP
        self.player = None
        self.frame_image: Optional[QImage] = None
        self.summary_done = False
        self._summary_rect = None
        self._stopped = False
        self._closed = False

        self.t_state = time.perf_counter()
        self.t_trial = time.perf_counter()
        self.reading = pad.poll(time.perf_counter())
        self._confirm_was_down = True      # Ignore a button held before the trial.

        self.out_interval = 1.0 / max(1.0, cfg.output_hz)
        self._next_sample = 0.0

        logger.info("session window: %d stimuli, output %.1f Hz, files %s",
                    len(stimuli), cfg.output_hz, self.log.raw_path.parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)

    def enter(self, state: str) -> None:
        logger.debug("trial %d: %s -> %s", self.trial + 1, self.state, state)
        self.state = state
        self.t_state = time.perf_counter()
        self._confirm_was_down = self.reading.confirm

    @property
    def stim(self) -> Optional[Stimulus]:
        if self.trial < len(self.stimuli):
            return self.stimuli[self.trial]
        return None

    def elapsed(self) -> float:
        return time.perf_counter() - self.t_state

    def confirm_edge(self) -> bool:
        """True on the frame the confirm button goes down."""
        down = self.reading.confirm
        edge = down and not self._confirm_was_down
        self._confirm_was_down = down
        return edge

    def tick(self) -> None:
        now = time.perf_counter()
        self.reading = self.pad.poll(now)

        if self.state == GAP:
            self.step_gap()
        elif self.state == SUMMARY:
            self.step_summary()
        elif self.state == STIMULUS:
            self.step_stimulus(now)

        self.update()

    def step_gap(self) -> None:
        if self.elapsed() < self.cfg.gap_duration:
            return
        if self.stim is None:
            self.end_session()
            return
        self.t_trial = time.perf_counter()
        self.summary_done = False
        logger.info("trial %d/%d: %s (%s)", self.trial + 1, len(self.stimuli),
                    self.stim.id, self.stim.kind)
        if self.cfg.summarises and self.cfg.summary_when == SUMMARY_BEFORE:
            self.enter(SUMMARY)
        else:
            self.begin_stimulus()

    def begin_stimulus(self) -> None:
        try:
            self.player = make_player(self.stim, self.cfg.image_duration,
                                      self.cfg.media_aspect,
                                      self.cfg.media_margin_percent)
        except (AudioUnavailable, RuntimeError) as exc:
            self.fail(str(exc))
            return
        self.frame_image = None
        self.player.start()
        self._next_sample = time.perf_counter()
        self.enter(STIMULUS)

    def step_stimulus(self, now: float) -> None:
        # Decode here, not in paintEvent, so playback speed does not depend on repaints.
        self.frame_image = self.player.frame()

        if self.cfg.traces:
            stim_t = now - self.t_trial
            self.log.log_raw(self.trial + 1, self.stim, PHASE_TRACE,
                             stim_t, self.reading)

            if now >= self._next_sample:
                self.log.log_continuous(self.trial + 1, self.stim,
                                        PHASE_TRACE, stim_t, self.reading)
                self._next_sample += self.out_interval
                if self._next_sample < now:
                    self._next_sample = now + self.out_interval

        if self.player.finished():
            self._summary_rect = self.media_rect()
            self.player.stop()
            self.player = None
            if self.cfg.summarises and not self.summary_done:
                self.enter(SUMMARY)
            else:
                self.finish_trial()

    def step_summary(self) -> None:
        if not self.confirm_edge():
            return
        stim_t = time.perf_counter() - self.t_trial
        self.log.log_raw(self.trial + 1, self.stim, PHASE_SUMMARY,
                         stim_t, self.reading)
        self.log.log_continuous(self.trial + 1, self.stim, PHASE_SUMMARY,
                                stim_t, self.reading)
        logger.info("trial %d summary: valence=%.2f arousal=%.2f",
                    self.trial + 1, self.reading.valence, self.reading.arousal)
        self.summary_done = True

        if self.cfg.summary_when == SUMMARY_BEFORE and self.player is None:
            self.begin_stimulus()
        else:
            self.finish_trial()

    def finish_trial(self) -> None:
        self.log.flush()
        self.trial += 1
        self.enter(GAP)

    def end_session(self) -> None:
        self._stop_and_save("all trials complete")
        self.state = DONE
        self.update()
        QTimer.singleShot(1500, self.close)

    def fail(self, message: str) -> None:
        """Stop on an unrecoverable stimulus error and tell the experimenter."""
        logger.error("playback failed: %s", message)
        self._stop_and_save("playback failed")
        QMessageBox.critical(None, "G-CATS - playback failed", message)
        self.close()

    def _stop_and_save(self, reason: str) -> None:
        """Stop timer and playback, write all data. Runs once per session."""
        if self._stopped:
            return
        self._stopped = True
        self.timer.stop()
        if self.player:
            self.player.stop()
            self.player = None
        self.log.close()
        logger.info("session stopped: %s (after %d trial(s))", reason, self.trial)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._stop_and_save("Escape pressed")
            self.close()

    def closeEvent(self, event) -> None:
        self._stop_and_save("window closed")
        super().closeEvent(event)
        if not self._closed:
            self._closed = True
            self.finished.emit()

    def media_rect(self):
        """Where the stimulus is drawn; the overlay is centred on this."""
        if self.state == SUMMARY and self._summary_rect is not None:
            return self._summary_rect
        if (self.stim and self.stim.kind == "audio" and
                self.state != SUMMARY):
            # Audio: grid in the upper area, time bar below it.
            top = int(self.height() * 0.04)
            height = int(self.height() * 0.62)
            return QRect(0, top, self.width(), height)
        if self.player is not None:
            return self.player.media_rect(self.width(), self.height())
        return fit_rect(0, 0, self.width(), self.height(),
                        self.cfg.media_aspect, self.cfg.media_margin_percent)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), BG)

        if self.state == GAP:
            if self.cfg.gap_kind == GAP_FIXATION:
                self.centre_text(p, "+", 46, TEXT)
        elif self.state == STIMULUS:
            self.paint_stimulus(p)
        elif self.state == SUMMARY:
            self.paint_summary(p)
        elif self.state == DONE:
            self.centre_text(p, "Thank you.\n\nYour responses have been saved.",
                             16, TEXT)
        p.end()

    def paint_stimulus(self, p: QPainter) -> None:
        box = self.media_rect()
        img = self.frame_image
        if img is not None and not img.isNull():
            # Fill the box without stretching; crop the overflow.
            scaled = img.scaled(box.size(), Qt.KeepAspectRatioByExpanding,
                                Qt.SmoothTransformation)
            source = QRect((scaled.width() - box.width()) // 2,
                           (scaled.height() - box.height()) // 2,
                           box.width(), box.height())
            p.drawImage(box, scaled, source)
        elif self.stim and self.stim.kind == "audio":
            self.draw_time_bar(p, box,
                               self.player.progress() if self.player else 0.0)

        if self.cfg.traces:
            overlay.draw(p, box, self.reading.valence, self.reading.arousal,
                         self.cfg,
                         side_valence=bool(self.stim and
                                           self.stim.kind == "audio"))

    def paint_summary(self, p: QPainter) -> None:
        overlay.draw(p, self.media_rect(),
                     self.reading.valence, self.reading.arousal, self.cfg,
                     side_valence=bool(self.stim and
                                       self.stim.kind == "audio"),
                     summary_bars=True)
        prompt = self.cfg.summary_question or (
            "How did this make you feel?"
            if self.cfg.summary_when != SUMMARY_BEFORE
            else "How do you feel right now?")
        self.top_text(p, prompt, 17, TEXT)
        self.bottom_text(p, "press the confirm shoulder button to continue",
                         12, DIM)

    def draw_time_bar(self, p: QPainter, box, progress: float) -> None:
        """Elapsed-time bar for audio-only stimuli."""
        w = int(self.width() * 0.4)
        x = (self.width() - w) // 2
        y = int(self.height() * 0.84)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawRoundedRect(x, y, w, 6, 3, 3)
        p.setBrush(QColor(235, 233, 226, 200))
        p.drawRoundedRect(x, y, max(2, int(w * progress)), 6, 3, 3)

        f = QFont()
        f.setPointSize(11)
        p.setFont(f)
        p.setPen(DIM)
        p.drawText(x, y - 22, w, 20, Qt.AlignCenter, "audio playing")

    def centre_text(self, p, text, size, col) -> None:
        self._text(p, text, size, col, self.rect(), Qt.AlignCenter)

    def top_text(self, p, text, size, col) -> None:
        self._text(p, text, size, col, QRect(0, 36, self.width(), 40),
                   Qt.AlignCenter)

    def bottom_text(self, p, text, size, col) -> None:
        self._text(p, text, size, col,
                   QRect(0, self.height() - 56, self.width(), 30), Qt.AlignCenter)

    @staticmethod
    def _text(p, text, size, col, rect, align) -> None:
        f = QFont()
        f.setPointSize(size)
        p.setFont(f)
        p.setPen(col)
        p.drawText(rect, align, text)

"""First page: check required packages, then wait for a gamepad."""

import logging
import subprocess
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTextEdit, QVBoxLayout

from ..theme import AMBER, BORDER, BG_BAR, FG, FG_DIM, GREEN, RED
from .base import Page

logger = logging.getLogger(__name__)

# (import name, pip name)
PACKAGES = [
    ("PySide6", "PySide6"),
    ("pygame", "pygame"),
    ("ffpyplayer", "ffpyplayer"),
]


class StartupPage(Page):
    title = "Startup checks"
    subtitle = "Verifying packages and waiting for a gamepad"
    button_text = "Continue"

    def build(self, layout: QVBoxLayout) -> None:
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            f"background: {BG_BAR}; border: 1px solid {BORDER};"
            f"border-radius: 5px; font-family: Consolas, monospace;"
            f"font-size: 12px; padding: 8px;"
        )
        layout.addWidget(self.log, 1)

        self.missing = []
        self.checked = False
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.look_for_pad)

    def on_enter(self) -> None:
        if self.checked:
            return
        self.checked = True
        self.set_ready(False, "checking…")
        QTimer.singleShot(120, self.check_packages)

    def check_packages(self) -> None:
        self.write("Checking packages", "dim")
        self.missing = []
        for mod, pip_name in PACKAGES:
            try:
                __import__(mod)
                self.write(f"  ok    {pip_name}", "ok")
            except ImportError:
                self.write(f"  MISSING  {pip_name}", "bad")
                self.missing.append(pip_name)
            except Exception as exc:
                # Installed but broken (e.g. missing system library): warn, keep going.
                logger.warning("package %s failed to import: %s", pip_name, exc)
                self.write(f"  warn  {pip_name}: {exc}", "warn")

        if self.missing:
            logger.warning("missing packages: %s", self.missing)
            cmd = f"{sys.executable} -m pip install " + " ".join(self.missing)
            self.write("\nInstall the missing packages, then restart:", "warn")
            self.write(f"  {cmd}", "warn")
            self.set_ready(False, f"{len(self.missing)} package(s) missing")
            self.rebind_button("Install now", self.install)
            self.button.setEnabled(True)
            return

        self.write("\nAll packages present.", "ok")
        self.start_pad_wait()

    def install(self) -> None:
        self.button.setEnabled(False)
        self.write("\nInstalling…", "dim")
        for pkg in list(self.missing):
            r = subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                               capture_output=True, text=True)
            if r.returncode == 0:
                self.write(f"  installed  {pkg}", "ok")
            else:
                logger.error("pip install %s failed:\n%s", pkg, r.stderr)
                self.write(f"  failed     {pkg}", "bad")
                self.write(r.stderr.strip()[:300], "dim")

        self.write("\nRestart G-CATS to pick up the new packages.", "warn")
        self.set_ready(False, "restart required")

    def start_pad_wait(self) -> None:
        self.write("\nLooking for a gamepad…", "dim")
        self.set_ready(False, "connect a USB gamepad")
        self.look_for_pad()
        if not self.pad.js:
            self.poll.start(1000)

    def look_for_pad(self) -> None:
        found = self.pad.open() if self.pad.js is None else True
        if not found:
            found = self.pad.rescan()
        if not found:
            return

        self.poll.stop()
        js = self.pad.js
        self.write(f"  ok    {js.get_name()}", "ok")
        self.write(f"        {js.get_numaxes()} axes, "
                   f"{js.get_numbuttons()} buttons", "dim")
        self.set_ready(True)

    def write(self, text: str, kind: str = "dim") -> None:
        """Append a coloured line to the on-screen log. kind: ok | bad | warn | dim."""
        colour = {"ok": GREEN, "bad": RED, "warn": AMBER, "dim": FG_DIM}.get(kind, FG)
        self.log.append(f'<span style="color:{colour}">{text}</span>')

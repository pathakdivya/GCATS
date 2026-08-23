"""
core/joystick.py
================
Pygame-based joystick handler for the affective rating experiment.

KEY INTEGRATION CONSTRAINT
──────────────────────────
PsychoPy and Pygame cannot share a window natively. However, Pygame can be
used **solely for its joystick subsystem** without ever opening a display:

    1.  Call os.environ["SDL_VIDEODRIVER"] = "dummy" BEFORE importing pygame.
        This tells SDL not to touch a display backend at all.
    2.  pygame.init() will then only initialise non-display subsystems.
    3.  pygame.joystick.init() and pygame.event.pump() will work normally.
    4.  The PsychoPy window remains the sole graphical surface.

Gamepad layout assumed (XInput / generic USB):
    Axis 0  – Left stick X   (–1 = left,   +1 = right)
    Axis 1  – Left stick Y   (–1 = up,     +1 = down)   ← note: inverted!
    Axis 2  – Right stick X
    Axis 3  – Right stick Y
    Button 4 – Left shoulder  (L1)
    Button 5 – Right shoulder (R1)
"""

import os
import math
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple


# Set dummy video driver BEFORE pygame is imported anywhere.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  (must come after env-vars)


# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class JoystickSample:
    """A single polled sample from the gamepad."""
    timestamp:        float
    raw_x:            float      # –1.0 … +1.0
    raw_y:            float      # –1.0 … +1.0 (hardware, Y-up = negative)
    valence:          float      # 0 … 100
    arousal:          float      # 0 … 100
    confirm_pressed:  bool = False   # active shoulder  → advance / end trial
    lock_pressed:     bool = False   # opposite shoulder → lock current rating

    # Calibration-corrected values (populated only when calibration has run)
    cal_valence:   Optional[float] = None
    cal_arousal:   Optional[float] = None


@dataclass
class CalibrationData:
    """Stores min/max observed values per axis for linear rescaling."""
    x_min: float = -1.0
    x_max: float =  1.0
    y_min: float = -1.0
    y_max: float =  1.0

    def update(self, x: float, y: float) -> None:
        self.x_min = min(self.x_min, x)
        self.x_max = max(self.x_max, x)
        self.y_min = min(self.y_min, y)
        self.y_max = max(self.y_max, y)


class JoystickController:
    """
    Wraps a single Pygame joystick for continuous XY sampling.

    Parameters
    ----------
    handedness : str
        "right" → left thumbstick + R2 trigger
        "left"  → right thumbstick + L2 trigger
    dead_zone  : float
        Radius (0–1) around stick centre treated as zero input.
    axis_x, axis_y : int or None
        Override axis indices (from diagnose_gamepad.py). None = handedness default.
    btn_confirm : int or None
        Override confirm button index. Only used when trigger_is_axis=False.
    invert_y : bool
        True (default) = push up gives negative raw value (most controllers).
    trigger_is_axis : bool
        True (default) = triggers are reported as axes (XInput RT/LT = axes 5/4).
        False = triggers are digital buttons; btn_confirm is used instead.
    trigger_axis : int or None
        Axis index for the confirm trigger. None = handedness default (right=5, left=4).
    trigger_threshold : float
        Axis value above which the trigger counts as pressed (default 0.3).
    """

    def __init__(
        self,
        handedness:  str   = "right",
        dead_zone:   float = 0.06,
        axis_x:      int   = None,
        axis_y:      int   = None,
        btn_confirm: int   = None,
        btn_lock:    int   = None,
        invert_y:    bool  = True,
    ):
        self.handedness   = handedness
        self.dead_zone    = dead_zone
        self._invert_y    = invert_y
        self._joystick:   Optional[pygame.joystick.Joystick] = None
        self._calibration = CalibrationData()

        # Stick axis assignments
        # "custom" handedness means caller supplies all indices explicitly
        self._axis_x = axis_x if axis_x is not None else (0 if handedness == "right" else 2)
        self._axis_y = axis_y if axis_y is not None else (1 if handedness == "right" else 3)

        # Right-handed: active = R1 (btn 5), lock = L1 (btn 4)
        # Left-handed:  active = L1 (btn 4), lock = R1 (btn 5)
        # "custom": caller must supply btn_confirm and btn_lock explicitly
        if handedness == "custom":
            self._btn_confirm = btn_confirm if btn_confirm is not None else 5
            self._btn_lock    = btn_lock    if btn_lock    is not None else 4
        else:
            default_confirm = 5 if handedness == "right" else 4
            default_lock    = 4 if handedness == "right" else 5
            self._btn_confirm = btn_confirm if btn_confirm is not None else default_confirm
            self._btn_lock    = btn_lock    if btn_lock    is not None else default_lock

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def initialise(self) -> bool:
        """
        Start Pygame's joystick subsystem and latch onto the first gamepad.
        Returns True on success, False if no device is found.
        """
        pygame.init()
        pygame.joystick.init()

        count = pygame.joystick.get_count()
        if count == 0:
            return False

        self._joystick = pygame.joystick.Joystick(0)
        self._joystick.init()
        print(f"[Joystick] Detected: '{self._joystick.get_name()}' "
              f"({self._joystick.get_numaxes()} axes, "
              f"{self._joystick.get_numbuttons()} buttons)")
        return True

    def shutdown(self) -> None:
        """Cleanly quit Pygame subsystems."""
        if self._joystick:
            self._joystick.quit()
        pygame.quit()

    # ── Raw polling ───────────────────────────────────────────────────────────
    def poll(self) -> JoystickSample:
        """
        Pump the Pygame event queue and return one JoystickSample.

        IMPORTANT: pygame.event.pump() must be called on every frame instead
        of pygame.event.get() because we do NOT want to consume events from
        a Pygame window (there is none). pump() refreshes the internal state
        so that get_axis() / get_button() return current values.
        """
        pygame.event.pump()

        raw_x = self._joystick.get_axis(self._axis_x)
        raw_y = self._joystick.get_axis(self._axis_y)

        # Apply dead-zone (circular)
        magnitude = math.sqrt(raw_x ** 2 + raw_y ** 2)
        if magnitude < self.dead_zone:
            raw_x, raw_y = 0.0, 0.0
        else:
            # Rescale so the dead-zone edge maps to 0 and 1.0 to 1.0
            scale = (magnitude - self.dead_zone) / (1.0 - self.dead_zone)
            raw_x = (raw_x / magnitude) * scale
            raw_y = (raw_y / magnitude) * scale

        # Y axis is hardware-inverted on most controllers (push up → negative).
        # invert_y=True (default) flips the sign; set False if your device is
        # already positive-up (diagnose_gamepad.py will tell you).
        raw_y_up = -raw_y if self._invert_y else raw_y

        # Active shoulder   → advance / end trial
        # Opposite shoulder → lock current rating for feedback
        confirm = bool(self._joystick.get_button(self._btn_confirm))
        lock    = bool(self._joystick.get_button(self._btn_lock))

        valence = raw_to_100(raw_x)
        arousal = raw_to_100(raw_y_up)

        sample = JoystickSample(
            timestamp=time.perf_counter(),
            raw_x=raw_x,
            raw_y=raw_y_up,
            valence=valence,
            arousal=arousal,
            confirm_pressed=confirm,
            lock_pressed=lock,
        )

        # Calibration-corrected values (if calibration has been run)
        sample.cal_valence = self._calibrated(raw_x, "x")
        sample.cal_arousal = self._calibrated(raw_y_up, "y")

        return sample

    # ── Calibration ───────────────────────────────────────────────────────────
    def run_calibration(self, win, duration_s: float = 5.0) -> None:
        """
        Ask the participant to sweep the stick to all extremes for `duration_s`
        seconds. Collects min/max per axis.

        Parameters
        ----------
        win        : psychopy.visual.Window
            Active PsychoPy window for on-screen feedback.
        duration_s : float
            How long to sample before locking in the calibration.
        """
        from ui.calibration import show_calibration_screen
        deadline = time.perf_counter() + duration_s
        while time.perf_counter() < deadline:
            pygame.event.pump()
            x = self._joystick.get_axis(self._axis_x)
            y = -self._joystick.get_axis(self._axis_y)   # invert Y
            self._calibration.update(x, y)
            show_calibration_screen(win, deadline - time.perf_counter(), duration_s)

        # Safety clamp: ensure min/max span is at least 0.5 (avoid div-by-zero)
        if self._calibration.x_max - self._calibration.x_min < 0.5:
            self._calibration.x_min, self._calibration.x_max = -1.0, 1.0
        if self._calibration.y_max - self._calibration.y_min < 0.5:
            self._calibration.y_min, self._calibration.y_max = -1.0, 1.0

    def _calibrated(self, raw: float, axis: str) -> float:
        """Map a dead-zone-corrected raw value through calibration to 0–100."""
        if axis == "x":
            lo, hi = self._calibration.x_min, self._calibration.x_max
        else:
            lo, hi = self._calibration.y_min, self._calibration.y_max
        span = hi - lo if (hi - lo) != 0 else 1.0
        return clamp_100((raw - lo) / span * 100.0)

    @property
    def calibration(self) -> CalibrationData:
        return self._calibration


# ─────────────────────────────────────────────────────────────────────────────
# Standalone helper functions
# ─────────────────────────────────────────────────────────────────────────────
def raw_to_100(raw: float) -> float:
    """
    Convert a dead-zone-corrected joystick axis value (–1.0 … +1.0)
    linearly to the 0–100 rating scale.

    Centre (0.0) → 50.0
    Full positive (+1.0) → 100.0
    Full negative (–1.0) → 0.0
    """
    return clamp_100((raw + 1.0) * 50.0)


def clamp_100(value: float) -> float:
    """Clamp a value to [0, 100]."""
    return max(0.0, min(100.0, value))

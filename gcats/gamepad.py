"""Gamepad input through pygame's joystick module.

Axes: 0/1 left stick X/Y, 2/3 right stick X/Y (pygame reports up as negative).
Buttons: 4 left shoulder, 5 right shoulder.
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

# Stop pygame from opening its own window; Qt draws everything.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from .config import MAP_CIRCLE_TO_SQUARE
from .mapping import apply_dead_zone, map_coords, to_scale

logger = logging.getLogger(__name__)

LEFT_STICK = (0, 1)
RIGHT_STICK = (2, 3)
BTN_L = 4
BTN_R = 5


@dataclass
class Reading:
    """One poll of the pad.

    raw_*              what pygame reported
    mapped_*           after dead-zone, Y flip and mapping, -1..1
    valence, arousal   mapped values on the rating scale
    """
    raw_x: float
    raw_y: float
    mapped_x: float
    mapped_y: float
    valence: float
    arousal: float
    confirm: bool
    lock: bool
    t_monotonic: float = 0.0


class Gamepad:
    """Wraps one joystick. Call open() once, then poll() every frame."""

    def __init__(self) -> None:
        self.js: Optional[pygame.joystick.Joystick] = None
        self.axis_x = 0
        self.axis_y = 1
        self.invert_y = True
        self.btn_confirm = BTN_R
        self.btn_lock = BTN_L
        self.dead_zone = 0.06
        self.centre_x = 0.0
        self.centre_y = 0.0
        self.mapping = MAP_CIRCLE_TO_SQUARE
        self.scale_lo = 0.0
        self.scale_hi = 100.0

    def open(self) -> bool:
        """Grab joystick 0. Returns False if nothing is plugged in."""
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        pygame.event.pump()
        if pygame.joystick.get_count() == 0:
            return False
        self.js = pygame.joystick.Joystick(0)
        self.js.init()
        logger.info("gamepad opened: %s (%d axes, %d buttons)", self.js.get_name(),
                    self.js.get_numaxes(), self.js.get_numbuttons())
        return True

    def rescan(self) -> bool:
        """Re-enumerate devices. Used by the waiting screen."""
        pygame.joystick.quit()
        pygame.joystick.init()
        return self.open()

    def close(self) -> None:
        if self.js is not None:
            self.js.quit()
            self.js = None

    @property
    def name(self) -> str:
        return self.js.get_name() if self.js else "no device"

    def poll(self, t: float = 0.0) -> Reading:
        """Read the pad once, running the full transformation pipeline."""
        if self.js is None:
            mid = (self.scale_lo + self.scale_hi) / 2.0
            return Reading(0.0, 0.0, 0.0, 0.0, mid, mid, False, False, t)

        pygame.event.pump()
        raw_x = self.js.get_axis(self.axis_x)
        raw_y = self.js.get_axis(self.axis_y)

        cx = max(-1.0, min(1.0, raw_x - self.centre_x))
        cy = max(-1.0, min(1.0, raw_y - self.centre_y))
        dx, dy = apply_dead_zone(cx, cy, self.dead_zone)
        up = -dy if self.invert_y else dy
        mapped_x, mapped_y = map_coords(dx, up, self.mapping)

        return Reading(
            raw_x=raw_x,
            raw_y=raw_y,
            mapped_x=mapped_x,
            mapped_y=mapped_y,
            valence=to_scale(mapped_x, self.scale_lo, self.scale_hi),
            arousal=to_scale(mapped_y, self.scale_lo, self.scale_hi),
            confirm=self._button(self.btn_confirm),
            lock=self._button(self.btn_lock),
            t_monotonic=t,
        )

    def raw_axes(self) -> List[float]:
        """All axis values, for the mapping and dead-zone screens."""
        if self.js is None:
            return []
        pygame.event.pump()
        return [self.js.get_axis(i) for i in range(self.js.get_numaxes())]

    def pressed_buttons(self) -> List[int]:
        """Indices of buttons currently held, for the mapping screen."""
        if self.js is None:
            return []
        pygame.event.pump()
        return [i for i in range(self.js.get_numbuttons()) if self.js.get_button(i)]

    def _button(self, idx: int) -> bool:
        if self.js is None or idx >= self.js.get_numbuttons():
            return False
        return bool(self.js.get_button(idx))

    def apply(self, cfg) -> None:
        """Copy calibration, mapping and scale out of a Config."""
        self.axis_x = cfg.axis_x
        self.axis_y = cfg.axis_y
        self.invert_y = cfg.invert_y
        self.btn_confirm = cfg.btn_confirm
        self.btn_lock = cfg.btn_lock
        self.dead_zone = cfg.dead_zone
        self.centre_x = cfg.centre_x
        self.centre_y = cfg.centre_y
        self.mapping = cfg.joystick_mapping
        self.scale_lo = cfg.axis_min
        self.scale_hi = cfg.axis_max
        logger.debug("pad settings: axes=(%d,%d) invert_y=%s confirm=%d "
                     "dead_zone=%.3f centre=(%.3f,%.3f) mapping=%s scale=%s..%s",
                     self.axis_x, self.axis_y, self.invert_y, self.btn_confirm,
                     self.dead_zone, self.centre_x, self.centre_y, self.mapping, self.scale_lo, self.scale_hi)

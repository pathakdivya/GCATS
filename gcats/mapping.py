"""Stick position -> rating, in three steps. All three value pairs are saved.

    raw_x, raw_y          as pygame reports it
      -> apply_dead_zone  ignore small resting drift
      -> map_coords       optional circle-to-square
    mapped_x, mapped_y    -1..1
      -> to_scale         stretch to the chosen rating range
    valence, arousal
"""

import math
from typing import Tuple

from .config import MAP_CIRCLE_TO_SQUARE


def apply_dead_zone(x: float, y: float, dead_zone: float) -> Tuple[float, float]:
    """Zero inside the dead-zone circle; outside it, rescale so full tilt is still 1.0."""
    mag = math.hypot(x, y)
    if mag == 0.0 or mag < dead_zone:
        return 0.0, 0.0
    k = ((mag - dead_zone) / (1.0 - dead_zone)) / mag
    return x * k, y * k


def circle_to_square(u: float, v: float) -> Tuple[float, float]:
    """Stretch the stick's circle onto the square so corners are reachable.

    Uses the elliptical grid mapping. Input past the circle edge is pulled
    back onto it first.
    """
    mag = math.hypot(u, v)
    if mag > 1.0:
        u, v = u / mag, v / mag

    u2, v2 = u * u, v * v
    r2 = 2.0 * math.sqrt(2.0)

    # Floating-point rounding can make a square-root term slightly negative.
    x = (0.5 * math.sqrt(max(0.0, 2.0 + u2 - v2 + r2 * u))
         - 0.5 * math.sqrt(max(0.0, 2.0 + u2 - v2 - r2 * u)))
    y = (0.5 * math.sqrt(max(0.0, 2.0 - u2 + v2 + r2 * v))
         - 0.5 * math.sqrt(max(0.0, 2.0 - u2 + v2 - r2 * v)))

    return _clip(x), _clip(y)


def map_coords(x: float, y: float, method: str) -> Tuple[float, float]:
    """Apply the selected joystick mapping. Returns values in -1..1."""
    if method == MAP_CIRCLE_TO_SQUARE:
        return circle_to_square(x, y)
    return _clip(x), _clip(y)


def to_scale(value: float, lo: float, hi: float) -> float:
    """Map a mapped coordinate (-1..1) onto the experimenter's rating range."""
    return lo + (value + 1.0) * 0.5 * (hi - lo)


def from_scale(value: float, lo: float, hi: float) -> float:
    """Inverse of to_scale, used to place the cursor from a stored rating."""
    if hi == lo:
        return 0.0
    return (value - lo) / (hi - lo) * 2.0 - 1.0


def _clip(v: float) -> float:
    return max(-1.0, min(1.0, v))

"""All session settings (Config) and preset save/load.

Presets: ~/.gcats/default_preset.json is loaded at launch; other .json
presets can be saved and loaded from the Configuration page.
"""

import json
import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

ORDER_SEQUENTIAL = "sequential"
ORDER_RANDOM = "random"

ASPECT_ORIGINAL = "original"
ASPECT_RATIOS = {
    "1:1": 1.0,
    "3:2": 3.0 / 2.0,
    "4:3": 4.0 / 3.0,
    "16:9": 16.0 / 9.0,
}

GAP_FIXATION = "fixation"
GAP_BLANK = "blank"

RATE_CONTINUOUS = "continuous"
RATE_SUMMARY = "summary"
RATE_BOTH = "both"

SUMMARY_BEFORE = "before"
SUMMARY_AFTER = "after"

SAMPLING_CHOICES = [5, 10, 15, 20, 25, 30, 40]
REFRESH = "refresh"              # Use the monitor refresh rate.

MAP_DIRECT = "direct"
MAP_CIRCLE_TO_SQUARE = "circle_to_square"

SCALE_PRESETS = {
    "0 to 10": (0.0, 10.0),
    "0 to 50": (0.0, 50.0),
    "0 to 100": (0.0, 100.0),
    "-100 to +100": (-100.0, 100.0),
    "-1000 to +1000": (-1000.0, 1000.0),
}

APP_DIR = Path.home() / ".gcats"
DEFAULT_PRESET = APP_DIR / "default_preset.json"


@dataclass
class Stimulus:
    path: Path
    kind: str            # "image", "video" or "audio"
    duration: float      # Seconds; 0.0 means "use the file's own length".

    @property
    def id(self) -> str:
        return self.path.stem


@dataclass
class Config:
    participant_id: str = ""
    session: int = 1
    age: str = ""
    gender: str = ""
    stimuli: List[Stimulus] = field(default_factory=list)
    order: str = ORDER_RANDOM
    image_duration: float = 5.0
    media_aspect: str = ASPECT_ORIGINAL
    media_margin_percent: float = 10.0
    gap_kind: str = GAP_FIXATION
    gap_duration: float = 1.5
    rating_mode: str = RATE_BOTH
    summary_when: str = SUMMARY_AFTER
    sampling_hz: object = 10            # A numeric rate or the REFRESH option.
    joystick_mapping: str = MAP_CIRCLE_TO_SQUARE
    axis_min: float = 0.0
    axis_max: float = 100.0
    cursor_opacity: float = 0.75        # Opacity from 0.0 to 1.0.
    cursor_size: float = 9.0            # Cursor radius in screen pixels.
    show_central_axes: bool = True
    central_axes_opacity: float = 0.22
    show_cursor_guides: bool = True
    cursor_guide_opacity: float = 0.16
    low_valence_label: str = "Unpleasant"
    high_valence_label: str = "Pleasant"
    low_arousal_label: str = "Calm"
    high_arousal_label: str = "Activated"
    summary_question: str = ""
    axis_x: int = 0
    axis_y: int = 1
    invert_y: bool = True
    btn_confirm: int = 5
    btn_lock: int = 4
    dead_zone: float = 0.06
    centre_x: float = 0.0        # Resting stick position, subtracted from raw x.
    centre_y: float = 0.0
    monitor_refresh: float = 60.0

    out_dir: Path = Path("data")

    @property
    def traces(self) -> bool:
        return self.rating_mode in (RATE_CONTINUOUS, RATE_BOTH)

    @property
    def summarises(self) -> bool:
        return self.rating_mode in (RATE_SUMMARY, RATE_BOTH)

    @property
    def output_hz(self) -> float:
        """The requested output rate as a number."""
        if self.sampling_hz == REFRESH:
            return float(self.monitor_refresh)
        return float(self.sampling_hz)

    @property
    def neutral(self) -> float:
        """Midpoint of the chosen rating scale."""
        return (self.axis_min + self.axis_max) / 2.0

    # Saved in presets. Participant details and stimuli are per-session, so not here.
    PRESET_KEYS = (
        "sampling_hz", "joystick_mapping", "axis_min", "axis_max",
        "cursor_opacity", "cursor_size", "show_central_axes",
        "central_axes_opacity",
        "show_cursor_guides", "cursor_guide_opacity",
        "low_valence_label", "high_valence_label",
        "low_arousal_label", "high_arousal_label", "summary_question",
        "gap_kind", "gap_duration", "rating_mode", "summary_when",
        "order", "image_duration", "media_aspect", "media_margin_percent",
    )

    def preset_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.PRESET_KEYS}

    def apply_preset(self, data: dict) -> List[str]:
        """Load known keys from a preset dict. Returns keys that were ignored."""
        known = set(self.PRESET_KEYS)
        unknown = []
        for key, value in data.items():
            if key in known:
                setattr(self, key, value)
            else:
                unknown.append(key)
        return unknown

    def save_preset(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.preset_dict(), indent=2), encoding="utf-8")

    def load_preset(self, path) -> List[str]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        unknown = self.apply_preset(data)
        logger.info("loaded preset %s (ignored keys: %s)", path, unknown or "none")
        return unknown

    def save_as_default(self) -> None:
        self.save_preset(DEFAULT_PRESET)

    def load_default(self) -> bool:
        """Restore the last-used preset if one exists. Never raises."""
        if not DEFAULT_PRESET.exists():
            return False
        try:
            self.load_preset(DEFAULT_PRESET)
            return True
        except Exception:
            logger.exception("ignoring unreadable default preset %s", DEFAULT_PRESET)
            return False

    def reset_defaults(self) -> None:
        blank = Config()
        for key in self.PRESET_KEYS:
            setattr(self, key, getattr(blank, key))

    def to_json(self, path) -> None:
        """Full session record written alongside the data files."""
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["out_dir"] = str(self.out_dir)
        d["output_hz"] = self.output_hz
        d["stimuli"] = [
            {"id": s.id, "path": str(s.path), "kind": s.kind,
             "duration": s.duration}
            for s in self.stimuli
        ]
        Path(path).write_text(json.dumps(d, indent=2), encoding="utf-8")

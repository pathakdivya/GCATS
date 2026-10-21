"""Writes the three data files of a session:

    <base>_raw.csv          every gamepad poll
    <base>_continuous.csv   one row per output interval
    <base>_config.json      the settings used

Each row holds the raw, mapped and scaled values side by side.
Rows are kept in memory and appended to disk at the end of every trial.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

PHASE_TRACE = "trace"
PHASE_SUMMARY = "summary"

# Both CSV files use the same columns.
SAMPLE_COLUMNS = [
    "participant_id", "session", "trial", "stimulus_id", "stimulus_kind",
    "phase", "sample_number",
    "t_monotonic", "stimulus_time",
    "raw_x", "raw_y",
    "mapped_x", "mapped_y",
    "valence", "arousal",
    "confirm", "lock",
]

# Repeat acquisition settings so each CSV remains understandable on its own.
META_COLUMNS = [
    "requested_hz", "achieved_hz", "sample_interval_s",
    "centre_x", "centre_y", "dead_zone",
    "axis_min", "axis_max", "joystick_mapping",
    "cursor_opacity", "monitor_refresh",
    "low_valence_label", "high_valence_label",
    "low_arousal_label", "high_arousal_label",
]

COLUMNS = SAMPLE_COLUMNS + META_COLUMNS


class SessionLogger:
    """Writes the raw stream and the resampled trajectory."""

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        out = Path(cfg.out_dir)
        out.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{cfg.participant_id or 'anon'}_S{cfg.session}_{stamp}"
        self.raw_path = out / f"{base}_raw.csv"
        self.cont_path = out / f"{base}_continuous.csv"
        self.config_path = out / f"{base}_config.json"

        self._raw: List[dict] = []
        self._cont: List[dict] = []
        self._raw_n = 0
        self._cont_n = 0

        self._raw_first: Optional[float] = None
        self._raw_last: Optional[float] = None
        self._cont_first: Optional[float] = None
        self._cont_last: Optional[float] = None

        for path in (self.raw_path, self.cont_path):
            with open(path, "w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=COLUMNS).writeheader()

        self._meta = self._meta_row()

    def _meta_row(self) -> dict:
        cfg = self.cfg
        return {
            "requested_hz": cfg.output_hz,
            "achieved_hz": "",              # Filled in by _write().
            "sample_interval_s": "",
            "centre_x": cfg.centre_x,
            "centre_y": cfg.centre_y,
            "dead_zone": cfg.dead_zone,
            "axis_min": cfg.axis_min,
            "axis_max": cfg.axis_max,
            "joystick_mapping": cfg.joystick_mapping,
            "cursor_opacity": cfg.cursor_opacity,
            "monitor_refresh": cfg.monitor_refresh,
            "low_valence_label": cfg.low_valence_label,
            "high_valence_label": cfg.high_valence_label,
            "low_arousal_label": cfg.low_arousal_label,
            "high_arousal_label": cfg.high_arousal_label,
        }

    def _row(self, trial, stim, phase, n, stim_time, r) -> dict:
        row = {
            "participant_id": self.cfg.participant_id,
            "session": self.cfg.session,
            "trial": trial,
            "stimulus_id": stim.id,
            "stimulus_kind": stim.kind,
            "phase": phase,
            "sample_number": n,
            "t_monotonic": round(r.t_monotonic, 9),
            "stimulus_time": round(stim_time, 6),
            "raw_x": r.raw_x,          # Not rounded.
            "raw_y": r.raw_y,
            "mapped_x": round(r.mapped_x, 9),
            "mapped_y": round(r.mapped_y, 9),
            "valence": round(r.valence, 6),
            "arousal": round(r.arousal, 6),
            "confirm": int(r.confirm),
            "lock": int(r.lock),
        }
        row.update(self._meta)
        return row

    def log_raw(self, trial, stim, phase, stim_time, reading) -> None:
        """Every poll of the gamepad."""
        self._raw_n += 1
        if self._raw_first is None:
            self._raw_first = reading.t_monotonic
        self._raw_last = reading.t_monotonic
        self._raw.append(
            self._row(trial, stim, phase, self._raw_n, stim_time, reading))

    def log_continuous(self, trial, stim, phase, stim_time, reading) -> None:
        """A sample retained at the experimenter's output frequency."""
        self._cont_n += 1
        if self._cont_first is None:
            self._cont_first = reading.t_monotonic
        self._cont_last = reading.t_monotonic
        self._cont.append(
            self._row(trial, stim, phase, self._cont_n, stim_time, reading))

    def flush(self) -> None:
        """Write both buffers. Called at the end of every trial."""
        logger.debug("flush: %d raw, %d continuous rows",
                     len(self._raw), len(self._cont))
        self._write(self.raw_path, self._raw,
                    self._achieved(self._raw_first, self._raw_last, self._raw_n))
        self._write(self.cont_path, self._cont,
                    self._achieved(self._cont_first, self._cont_last, self._cont_n))

    def _write(self, path: Path, rows: List[dict], achieved) -> None:
        if not rows:
            return
        hz, interval = achieved
        for row in rows:
            row["achieved_hz"] = hz
            row["sample_interval_s"] = interval
        with open(path, "a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=COLUMNS).writerows(rows)
        rows.clear()

    @staticmethod
    def _achieved(first, last, n):
        """Actual rate achieved so far, for verification against the request."""
        if first is None or last is None or n < 2 or last <= first:
            return "", ""
        span = last - first
        return round((n - 1) / span, 4), round(span / (n - 1), 9)

    def close(self) -> None:
        self.flush()
        self.cfg.to_json(self.config_path)
        logger.info("saved %s (%d rows)", self.raw_path, self._raw_n)
        logger.info("saved %s (%d rows)", self.cont_path, self._cont_n)
        logger.info("saved %s", self.config_path)

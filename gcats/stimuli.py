"""Find stimulus files and tag each one as image, video or audio."""

import logging
import random
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import List

from .config import Stimulus, ORDER_RANDOM

logger = logging.getLogger(__name__)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv"}
AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
ALL_EXT = IMAGE_EXT | VIDEO_EXT | AUDIO_EXT


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    return "audio"


def scan(target: Path, image_duration: float = 5.0) -> List[Stimulus]:
    """Stimuli from one file or a folder (not sub-folders), sorted by name.

    Images get image_duration; video/audio get 0.0 and use their own length.
    """
    target = Path(target)
    if target.is_file():
        files = [target] if target.suffix.lower() in ALL_EXT else []
    else:
        files = sorted(p for p in target.glob("*")
                       if p.is_file() and p.suffix.lower() in ALL_EXT)

    out = []
    for p in files:
        k = kind_of(p)
        out.append(Stimulus(
            path=p,
            kind=k,
            duration=image_duration if k == "image" else 0.0,
        ))
    logger.info("scanned %s: %d stimuli", target, len(out))
    return out


def ordered(stimuli: List[Stimulus], order: str) -> List[Stimulus]:
    """Return a presentation-ordered copy."""
    items = list(stimuli)
    if order == ORDER_RANDOM:
        random.shuffle(items)
    return items


@lru_cache(maxsize=512)
def probe_duration(path: Path) -> float:
    """Length in seconds via ffprobe, or 0.0. Display only; playback does not use it."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(r.stdout.strip())
    except Exception as exc:
        logger.debug("ffprobe failed for %s: %s", path, exc)
        return 0.0


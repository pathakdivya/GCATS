"""Stimulus players.

Three classes with the same interface so the runner can treat them alike:

    start()                  begin playback
    frame() -> QImage|None   current visual, None for audio-only
    finished() -> bool       has the stimulus ended
    progress() -> float      0..1, drives the audio time bar
    media_rect(w, h)         where the stimulus is drawn, for overlay centring
    stop()                   release resources

Video and audio use ffpyplayer's MediaPlayer. Video files use their embedded
audio track, while audio-only files are opened without a video stream.
"""

import time
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage

from .config import ASPECT_ORIGINAL, ASPECT_RATIOS


class AudioUnavailable(RuntimeError):
    """Raised when a stimulus with audio cannot initialise its audio output."""


def _open_player(path: Path, want_video: bool):
    """Create an ffpyplayer MediaPlayer, or raise something informative."""
    try:
        from ffpyplayer.player import MediaPlayer
    except ImportError as exc:
        raise AudioUnavailable(
            f"ffpyplayer is not installed, so '{path.name}' cannot be played "
            f"with sound. Install it with: pip install ffpyplayer"
        ) from exc

    opts = {"out_fmt": "rgb24"} if want_video else {"vn": True}
    try:
        return MediaPlayer(str(path), ff_opts=opts)
    except Exception as exc:
        raise AudioUnavailable(
            f"Could not open '{path.name}' for playback: {exc}"
        ) from exc


def fit_rect(media_w: int, media_h: int, box_w: int, box_h: int,
             aspect: str = ASPECT_ORIGINAL,
             margin_percent: float = 0.0) -> QRect:
    """Centred rectangle the stimulus is drawn into.

    The margin is removed from every side first. A fixed aspect ("16:9" etc.)
    gives the largest rectangle of that shape. "original" keeps the media's
    own size and only shrinks it if it does not fit. Unknown media size
    (0, 0) fills the space inside the margin.
    """
    margin = max(0.0, min(49.0, float(margin_percent))) / 100.0
    inner_w = max(1, int(box_w * (1.0 - 2.0 * margin)))
    inner_h = max(1, int(box_h * (1.0 - 2.0 * margin)))

    if aspect in ASPECT_RATIOS:
        ratio = ASPECT_RATIOS[aspect]
        if inner_w / inner_h > ratio:
            w, h = int(inner_h * ratio), inner_h
        else:
            w, h = inner_w, int(inner_w / ratio)
        return QRect((box_w - w) // 2, (box_h - h) // 2, w, h)

    if media_w <= 0 or media_h <= 0:
        return QRect((box_w - inner_w) // 2, (box_h - inner_h) // 2,
                     inner_w, inner_h)
    scale = min(1.0, inner_w / media_w, inner_h / media_h)
    w = max(1, int(media_w * scale))
    h = max(1, int(media_h * scale))
    return QRect((box_w - w) // 2, (box_h - h) // 2, w, h)


class ImagePlayer:
    """One still image for a fixed duration."""

    kind = "image"

    def __init__(self, path: Path, duration: float,
                 aspect: str = ASPECT_ORIGINAL,
                 margin_percent: float = 0.0) -> None:
        self.image = QImage(str(path))
        if self.image.isNull():
            raise RuntimeError(f"could not load image: {path}")
        self.duration = duration
        self.aspect = aspect
        self.margin_percent = margin_percent
        self._t0 = 0.0

    def start(self) -> None:
        self._t0 = time.perf_counter()

    def frame(self) -> Optional[QImage]:
        return self.image

    def finished(self) -> bool:
        return (time.perf_counter() - self._t0) >= self.duration

    def progress(self) -> float:
        if self.duration <= 0:
            return 1.0
        return min(1.0, (time.perf_counter() - self._t0) / self.duration)

    def media_rect(self, w: int, h: int) -> QRect:
        return fit_rect(self.image.width(), self.image.height(), w, h,
                    self.aspect, self.margin_percent)

    def stop(self) -> None:
        pass


class VideoPlayer:
    """Video with its embedded audio, decoded and synchronised by ffpyplayer."""

    kind = "video"

    def __init__(self, path: Path,
                 aspect: str = ASPECT_ORIGINAL,
                 margin_percent: float = 0.0) -> None:
        self.path = path
        self.aspect = aspect
        self.margin_percent = margin_percent
        self.player = _open_player(path, want_video=True)
        self._image: Optional[QImage] = None
        self._size: Tuple[int, int] = (0, 0)
        self._pending = None          # Frame decoded but not yet displayed.
        self._done = False
        self._duration = 0.0
        self._t0 = 0.0

    def start(self) -> None:
        self._t0 = time.perf_counter()
        # Wait briefly for the decoder to provide duration and dimensions.
        deadline = self._t0 + 2.0
        while time.perf_counter() < deadline:
            meta = self.player.get_metadata()
            if meta.get("duration"):
                self._duration = float(meta["duration"])
                size = meta.get("src_vid_size")
                if size:
                    self._size = tuple(size)
                break
            time.sleep(0.01)

    def frame(self) -> Optional[QImage]:
        """Show the frame due at the current wall-clock time.

        Frames carry a presentation timestamp, and we only swap the displayed
        image once that timestamp is due. ffpyplayer normally paces itself
        against the audio clock, but on a machine with no working audio device
        it free-runs and the video plays many times too fast -- pacing here
        keeps the stimulus duration correct either way.
        """
        if self._done:
            return self._image

        elapsed = time.perf_counter() - self._t0

        # Decode ahead until the next frame is scheduled for the future.
        # Limit catch-up work so one slow tick cannot block the interface.
        for _ in range(8):
            if self._pending is None:
                frame, val = self.player.get_frame()
                if val == "eof":
                    self._done = True
                    break
                if frame is None:
                    break            # The decoder is not ready; keep the last frame.
                self._pending = frame

            img, pts = self._pending
            if pts > elapsed:
                break                # Wait until the frame's presentation time.
            self._image = self._to_qimage(img)
            self._pending = None

        return self._image

    def _to_qimage(self, img) -> QImage:
        w, h = img.get_size()
        self._size = (w, h)
        data = img.to_bytearray()[0]
        # Copy the data so the QImage owns its buffer.
        return QImage(bytes(data), w, h, w * 3, QImage.Format_RGB888).copy()

    def finished(self) -> bool:
        # End a stalled trial even if the decoder never reports end-of-file.
        if self._done:
            return True
        if self._duration > 0:
            return (time.perf_counter() - self._t0) > self._duration + 0.5
        return False

    def progress(self) -> float:
        if self._duration <= 0:
            return 0.0
        return min(1.0, (time.perf_counter() - self._t0) / self._duration)

    def media_rect(self, w: int, h: int) -> QRect:
        src_w, src_h = self._size if self._size[0] else (640, 480)
        return fit_rect(src_w, src_h, w, h, self.aspect,
                    self.margin_percent)

    def stop(self) -> None:
        self._done = True
        try:
            self.player.close_player()
        except Exception:
            pass


class AudioPlayer:
    """Audio-only stimulus. The runner draws a time bar; there is no image."""

    kind = "audio"

    def __init__(self, path: Path, duration: float) -> None:
        self.path = path
        self.player = _open_player(path, want_video=False)
        self._duration = duration if duration > 0 else 0.0
        self._t0 = 0.0
        self._done = False

    def start(self) -> None:
        self._t0 = time.perf_counter()
        deadline = self._t0 + 2.0
        while self._duration <= 0 and time.perf_counter() < deadline:
            meta = self.player.get_metadata()
            if meta.get("duration"):
                self._duration = float(meta["duration"])
                break
            time.sleep(0.01)
        if self._duration <= 0:
            self._duration = 30.0     # Prevent an unknown duration from hanging.

    def frame(self) -> Optional[QImage]:
        # Advance decoding so the audio stream continues to play.
        _, val = self.player.get_frame()
        if val == "eof":
            self._done = True
        return None

    def finished(self) -> bool:
        return self._done or (time.perf_counter() - self._t0) >= self._duration

    def progress(self) -> float:
        if self._duration <= 0:
            return 0.0
        return min(1.0, (time.perf_counter() - self._t0) / self._duration)

    def media_rect(self, w: int, h: int) -> QRect:
        # Audio-only stimuli have no image rectangle.
        return QRect(0, 0, w, h)

    def stop(self) -> None:
        self._done = True
        try:
            self.player.close_player()
        except Exception:
            pass


def make_player(stim, image_duration: float,
                aspect: str = ASPECT_ORIGINAL,
                margin_percent: float = 0.0):
    """Pick the right player for a Stimulus."""
    if stim.kind == "image":
        return ImagePlayer(stim.path, stim.duration or image_duration, aspect,
                           margin_percent)
    if stim.kind == "video":
        return VideoPlayer(stim.path, aspect, margin_percent)
    return AudioPlayer(stim.path, stim.duration)

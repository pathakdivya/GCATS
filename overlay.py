"""Draws the valence-arousal grid, cursor and labels over the stimulus.

All positions come from the rectangle the stimulus is drawn into, not the
screen, so the grid stays centred on the media.
"""

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

CURSOR_RGB = (239, 64, 64)
LABEL_COLOUR = QColor(235, 233, 226, 170)
LABEL_PAD = 10          # Space between the response square and labels.
LABEL_BAND = 22         # Height reserved for label text.


def response_rect(media: QRect) -> QRect:
    """Largest square centred in the media rectangle (same stick travel per unit on both axes)."""
    side = max(40, min(media.width(), media.height()))
    return QRect(
        media.center().x() - side // 2,
        media.center().y() - side // 2,
        side, side,
    )


def draw(painter: QPainter, media: QRect, valence: float, arousal: float,
         cfg, side_valence: bool = False,
         summary_bars: bool = False) -> None:
    """Paint the overlay.

    media         rectangle the stimulus occupies
    valence/arousal  values on the rating scale (cfg.axis_min..axis_max)
    side_valence  put valence labels left/right (audio layout)
    summary_bars  draw the summary-rating bars instead of plain labels
    """
    box = response_rect(media)

    span = (cfg.axis_max - cfg.axis_min) or 1.0
    fx = (valence - cfg.axis_min) / span          # 0..1
    fy = (arousal - cfg.axis_min) / span          # 0..1
    fx = min(1.0, max(0.0, fx))
    fy = min(1.0, max(0.0, fy))

    cx = box.left() + box.width() * fx
    cy = box.bottom() - box.height() * fy

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(box)
    if cfg.show_central_axes:
        alpha = int(255 * _clamp01(cfg.central_axes_opacity))
        painter.setPen(QPen(QColor(255, 255, 255, alpha), 1))
        mid_y = box.center().y()
        mid_x = box.center().x()
        painter.drawLine(box.left(), mid_y, box.right(), mid_y)
        painter.drawLine(mid_x, box.top(), mid_x, box.bottom())
    if cfg.show_cursor_guides:
        alpha = int(255 * _clamp01(cfg.cursor_guide_opacity))
        painter.setPen(QPen(QColor(255, 255, 255, alpha), 1))
        painter.drawLine(box.left(), int(cy), box.right(), int(cy))
        painter.drawLine(int(cx), box.top(), int(cx), box.bottom())

    if summary_bars:
        _summary_bars(painter, box, fx, fy, cfg)
    else:
        _labels(painter, box, cfg, side_valence)

    opacity = _clamp01(cfg.cursor_opacity)
    r = max(1.0, float(cfg.cursor_size))
    fill = QColor(*CURSOR_RGB, int(255 * opacity))
    edge = QColor(255, 255, 255, int(210 * opacity))

    painter.setBrush(fill)
    painter.setPen(QPen(edge, 1.5))
    painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
    painter.restore()


def _summary_bars(painter: QPainter, box: QRect, fx: float, fy: float,
                  cfg) -> None:
    """Draw the summary controls: grid plus movable valence/arousal bars."""
    gap = LABEL_PAD + LABEL_BAND
    bar_size = 14
    bar_y = box.bottom() + gap
    bar_x = box.right() + gap
    bar_w = box.width()
    bar_h = box.height()

    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
    painter.setBrush(QColor(255, 255, 255, 24))
    painter.drawRect(box.left(), bar_y, bar_w, bar_size)
    painter.drawRect(bar_x, box.top(), bar_size, bar_h)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(235, 233, 226, 190))
    indicator_w = 5
    painter.drawRect(box.left() + int((bar_w - indicator_w) * fx),
                     bar_y, indicator_w, bar_size)
    indicator_h = 5
    painter.drawRect(bar_x, box.bottom() - int((bar_h - indicator_h) * fy),
                     bar_size, indicator_h)

    font = QFont()
    font.setPointSize(10)
    painter.setFont(font)
    painter.setPen(LABEL_COLOUR)
    if cfg.low_valence_label:
        painter.drawText(QRect(box.left(), bar_y + bar_size + LABEL_PAD,
                               bar_w // 2, LABEL_BAND),
                         Qt.AlignLeft | Qt.AlignVCenter,
                         cfg.low_valence_label)
    if cfg.high_valence_label:
        painter.drawText(QRect(box.left() + bar_w // 2,
                               bar_y + bar_size + LABEL_PAD,
                               bar_w - bar_w // 2, LABEL_BAND),
                         Qt.AlignRight | Qt.AlignVCenter,
                         cfg.high_valence_label)
    if cfg.high_arousal_label:
        painter.drawText(QRect(bar_x + bar_size + LABEL_PAD, box.top(),
                               max(1, painter.device().width() - bar_x -
                                   bar_size - LABEL_PAD),
                               LABEL_BAND),
                         Qt.AlignLeft | Qt.AlignTop, cfg.high_arousal_label)
    if cfg.low_arousal_label:
        painter.drawText(QRect(bar_x + bar_size + LABEL_PAD,
                               box.bottom() - LABEL_BAND,
                               max(1, painter.device().width() - bar_x -
                                   bar_size - LABEL_PAD),
                               LABEL_BAND),
                         Qt.AlignLeft | Qt.AlignBottom, cfg.low_arousal_label)


def _labels(painter: QPainter, box: QRect, cfg, side_valence: bool) -> None:
    """Endpoint labels. Any blank label is simply skipped."""
    font = QFont()
    font.setPointSize(10)
    painter.setFont(font)
    painter.setPen(LABEL_COLOUR)

    if side_valence:
        if cfg.low_valence_label:
            painter.drawText(
                QRect(0, box.top(), max(1, box.left() - LABEL_PAD),
                      box.height()),
                Qt.AlignRight | Qt.AlignVCenter, cfg.low_valence_label)
        if cfg.high_valence_label:
            painter.drawText(
                QRect(box.right() + LABEL_PAD, box.top(),
                      max(1, painter.device().width() - box.right() -
                          LABEL_PAD), box.height()),
                Qt.AlignLeft | Qt.AlignVCenter, cfg.high_valence_label)
    else:
        below = QRect(box.left(), box.bottom() + LABEL_PAD,
                      box.width(), LABEL_BAND)
        if cfg.low_valence_label:
            painter.drawText(below, Qt.AlignLeft | Qt.AlignVCenter,
                             cfg.low_valence_label)
        if cfg.high_valence_label:
            painter.drawText(below, Qt.AlignRight | Qt.AlignVCenter,
                             cfg.high_valence_label)

    if cfg.high_arousal_label:
        painter.drawText(
            QRect(box.left(), box.top() - LABEL_PAD - LABEL_BAND,
                  box.width(), LABEL_BAND),
            Qt.AlignHCenter | Qt.AlignVCenter, cfg.high_arousal_label)
    if cfg.low_arousal_label:
        painter.drawText(
            QRect(box.left(), box.bottom() + LABEL_PAD + LABEL_BAND,
                  box.width(), LABEL_BAND),
            Qt.AlignHCenter | Qt.AlignVCenter, cfg.low_arousal_label)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))

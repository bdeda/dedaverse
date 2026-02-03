# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################
"""Slate overlay functionality for the USD viewer."""

from __future__ import annotations

__all__ = ["SlateTextGlOverlay"]

import logging
from collections.abc import Iterable
from typing import List, Optional, Sequence, Tuple

try:
    from PySide6 import QtCore, QtGui
    PYSIDE6_AVAILABLE = True
except ImportError:
    QtCore = None
    QtGui = None
    PYSIDE6_AVAILABLE = False


log = logging.getLogger(__name__)

_Color = Tuple[float, float, float, float]


class SlateTextGlOverlay:
    """Text overlay rendered in screen space above the viewport."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        frame_placement: str = "top_left",
        padding_px: float = 12.0,
        line_spacing_px: float = 4.0,
        font_family: Optional[str] = None,
        font_size: float = 12.0,
        color: Sequence[float] = (1.0, 1.0, 1.0, 0.9),
        shadow_color: Sequence[float] = (0.0, 0.0, 0.0, 0.55),
        shadow_offset_px: Tuple[float, float] = (1.0, 1.0),
        lines: Optional[Sequence[str]] = None,
    ) -> None:
        self._enabled = bool(enabled)
        self._frame_placement = "top_left"
        self._padding_px = 12.0
        self._line_spacing_px = 4.0
        self._font_family = font_family
        self._font_size = 12.0
        self._color: _Color = (1.0, 1.0, 1.0, 0.9)
        self._shadow_color: Optional[_Color] = None
        self._shadow_offset = (1.0, 1.0)
        self._lines: List[str] = []
        self.frame_placement = frame_placement
        self.padding_px = padding_px
        self.line_spacing_px = line_spacing_px
        self.font_size = font_size
        self.color = color
        self.shadow_color = shadow_color
        self.shadow_offset_px = shadow_offset_px
        if lines:
            self.lines = lines

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def frame_placement(self) -> str:
        return self._frame_placement

    @frame_placement.setter
    def frame_placement(self, value: str) -> None:
        if value not in (
            "top_left",
            "top_center",
            "top_right",
            "bottom_left",
            "bottom_center",
            "bottom_right",
            "center",
        ):
            log.warning("Unsupported slate placement: %s", value)
            return
        self._frame_placement = value

    @property
    def padding_px(self) -> float:
        return self._padding_px

    @padding_px.setter
    def padding_px(self, value: float) -> None:
        self._padding_px = max(0.0, float(value))

    @property
    def line_spacing_px(self) -> float:
        return self._line_spacing_px

    @line_spacing_px.setter
    def line_spacing_px(self, value: float) -> None:
        self._line_spacing_px = max(0.0, float(value))

    @property
    def font_family(self) -> Optional[str]:
        return self._font_family

    @font_family.setter
    def font_family(self, value: Optional[str]) -> None:
        self._font_family = value

    @property
    def font_size(self) -> float:
        return self._font_size

    @font_size.setter
    def font_size(self, value: float) -> None:
        self._font_size = max(1.0, float(value))

    @property
    def color(self) -> _Color:
        return self._color

    @color.setter
    def color(self, value: Sequence[float]) -> None:
        normalized = self._normalize_color(value)
        if normalized is None:
            log.warning("Invalid slate color: %r", value)
            return
        self._color = normalized

    @property
    def shadow_color(self) -> Optional[_Color]:
        return self._shadow_color

    @shadow_color.setter
    def shadow_color(self, value: Sequence[float]) -> None:
        normalized = self._normalize_color(value)
        self._shadow_color = normalized

    @property
    def shadow_offset_px(self) -> Tuple[float, float]:
        return self._shadow_offset

    @shadow_offset_px.setter
    def shadow_offset_px(self, value: Sequence[float]) -> None:
        try:
            self._shadow_offset = (float(value[0]), float(value[1]))
        except Exception:
            log.warning("Invalid shadow offset: %r", value)

    @property
    def lines(self) -> List[str]:
        return list(self._lines)

    @lines.setter
    def lines(self, value: Sequence[str]) -> None:
        self._lines = [str(line) for line in value]

    def set_text(self, text: str) -> None:
        self._lines = text.splitlines() if text else []

    def clear(self) -> None:
        self._lines.clear()

    def draw(self, painter: "QtGui.QPainter", rect: "QtCore.QRect") -> bool:
        if not self._enabled or not self._lines or not PYSIDE6_AVAILABLE:
            return False
        if rect.width() <= 0 or rect.height() <= 0:
            return False
        painter.save()
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
            font = QtGui.QFont(painter.font())
            if self._font_family:
                font.setFamily(self._font_family)
            font.setPointSizeF(self._font_size)
            painter.setFont(font)
            metrics = QtGui.QFontMetricsF(font)
            line_height = metrics.height()
            spacing = self._line_spacing_px
            total_height = (line_height * len(self._lines)) + (spacing * (len(self._lines) - 1))
            max_width = 0.0
            for line in self._lines:
                max_width = max(max_width, metrics.horizontalAdvance(line))
            x, y = self._resolve_anchor(rect, max_width, total_height)
            text_color = self._to_qcolor(self._color)
            shadow_color = self._to_qcolor(self._shadow_color) if self._shadow_color else None
            for line in self._lines:
                baseline = y + metrics.ascent()
                if shadow_color is not None:
                    painter.setPen(shadow_color)
                    painter.drawText(
                        QtCore.QPointF(x + self._shadow_offset[0], baseline + self._shadow_offset[1]),
                        line,
                    )
                painter.setPen(text_color)
                painter.drawText(QtCore.QPointF(x, baseline), line)
                y += line_height + spacing
            return True
        finally:
            painter.restore()

    def draw_from_stage_view(self, stage_view: object) -> bool:
        if not PYSIDE6_AVAILABLE or QtGui is None:
            return False
        painter = QtGui.QPainter(stage_view)
        try:
            rect = stage_view.rect()
            return self.draw(painter, rect)
        finally:
            painter.end()

    def _resolve_anchor(self, rect: "QtCore.QRect", width: float, height: float) -> Tuple[float, float]:
        pad = self._padding_px
        if self._frame_placement in ("top_left",):
            return pad, pad
        if self._frame_placement in ("top_center",):
            return (rect.width() - width) * 0.5, pad
        if self._frame_placement in ("top_right",):
            return rect.width() - width - pad, pad
        if self._frame_placement in ("bottom_left",):
            return pad, rect.height() - height - pad
        if self._frame_placement in ("bottom_center",):
            return (rect.width() - width) * 0.5, rect.height() - height - pad
        if self._frame_placement in ("bottom_right",):
            return rect.width() - width - pad, rect.height() - height - pad
        if self._frame_placement in ("center",):
            return (rect.width() - width) * 0.5, (rect.height() - height) * 0.5
        return pad, pad

    @staticmethod
    def _normalize_color(value: Sequence[float]) -> Optional[_Color]:
        if not isinstance(value, Iterable):
            return None
        parts = list(value)
        if len(parts) < 3:
            return None
        if len(parts) == 3:
            parts.append(1.0)
        if len(parts) > 4:
            parts = parts[:4]
        normalized = []
        for part in parts:
            try:
                channel = float(part)
            except (TypeError, ValueError):
                return None
            if channel > 1.0:
                channel = channel / 255.0
            channel = max(0.0, min(1.0, channel))
            normalized.append(channel)
        return tuple(normalized)  # type: ignore[return-value]

    @staticmethod
    def _to_qcolor(color: Optional[_Color]) -> "QtGui.QColor":
        if not PYSIDE6_AVAILABLE or QtGui is None:
            raise RuntimeError("QtGui is not available.")
        if color is None:
            return QtGui.QColor(0, 0, 0, 0)
        r, g, b, a = color
        return QtGui.QColor.fromRgbF(r, g, b, a)

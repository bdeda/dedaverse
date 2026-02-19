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
"""Annotation overlay functionality for the USD viewer."""

from __future__ import annotations

__all__ = ["AnnotationGlOverlay", "AnnotationStroke", "AnnotationText"]

import logging
from dataclasses import dataclass, field
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
_Point = Tuple[float, float]


@dataclass
class AnnotationStroke:
    """Container for a single annotation stroke."""

    points: List[_Point] = field(default_factory=list)
    color: _Color = (1.0, 0.9, 0.2, 0.9)
    line_width: float = 2.0

    def to_dict(self) -> dict:
        return {
            "points": [list(point) for point in self.points],
            "color": list(self.color),
            "line_width": self.line_width,
        }

    @staticmethod
    def from_dict(payload: dict) -> "AnnotationStroke":
        points = payload.get("points", [])
        color = payload.get("color", (1.0, 0.9, 0.2, 0.9))
        line_width = payload.get("line_width", 2.0)
        return AnnotationStroke(
            points=[(float(x), float(y)) for x, y in points],
            color=_normalize_color(color) or (1.0, 0.9, 0.2, 0.9),
            line_width=float(line_width),
        )


@dataclass
class AnnotationText:
    """Container for a single text annotation."""

    x: float = 0.0
    y: float = 0.0
    text: str = ""
    color: _Color = (1.0, 1.0, 1.0, 0.9)
    font_size: float = 14.0
    font_family: Optional[str] = None
    shadow_color: Optional[_Color] = (0.0, 0.0, 0.0, 0.7)
    shadow_offset_px: Tuple[float, float] = (2.0, 2.0)

    def to_dict(self) -> dict:
        result = {
            "x": self.x,
            "y": self.y,
            "text": self.text,
            "color": list(self.color),
            "font_size": self.font_size,
            "font_family": self.font_family,
        }
        if self.shadow_color is not None:
            result["shadow_color"] = list(self.shadow_color)
            result["shadow_offset_px"] = list(self.shadow_offset_px)
        return result

    @staticmethod
    def from_dict(payload: dict) -> "AnnotationText":
        x = payload.get("x", 0.0)
        y = payload.get("y", 0.0)
        text = payload.get("text", "")
        color = payload.get("color", (1.0, 1.0, 1.0, 0.9))
        font_size = payload.get("font_size", 14.0)
        font_family = payload.get("font_family", None)
        shadow_color = payload.get("shadow_color", (0.0, 0.0, 0.0, 0.7))
        shadow_offset_px = payload.get("shadow_offset_px", (2.0, 2.0))
        return AnnotationText(
            x=float(x),
            y=float(y),
            text=str(text),
            color=_normalize_color(color) or (1.0, 1.0, 1.0, 0.9),
            font_size=float(font_size),
            font_family=str(font_family) if font_family else None,
            shadow_color=_normalize_color(shadow_color) if shadow_color else None,
            shadow_offset_px=(float(shadow_offset_px[0]), float(shadow_offset_px[1])) if isinstance(shadow_offset_px, (list, tuple)) and len(shadow_offset_px) >= 2 else (2.0, 2.0),
        )


class AnnotationGlOverlay:
    """OpenGL annotation layer rendered above the 3D viewport."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        color: Sequence[float] = (1.0, 0.9, 0.2, 0.9),
        line_width: float = 2.0,
        text_color: Sequence[float] = (1.0, 1.0, 1.0, 0.9),
        text_font_size: float = 14.0,
        text_shadow_color: Optional[Sequence[float]] = None,
        text_shadow_offset_px: Tuple[float, float] = (2.0, 2.0),
    ) -> None:
        self._enabled = bool(enabled)
        self._default_color = _normalize_color(color) or (1.0, 0.9, 0.2, 0.9)
        self._default_line_width = max(0.5, float(line_width))
        self._default_text_color = _normalize_color(text_color) or (1.0, 1.0, 1.0, 0.9)
        self._default_text_font_size = max(8.0, float(text_font_size))
        self._default_text_shadow_color = _normalize_color(text_shadow_color) if text_shadow_color else None
        self._default_text_shadow_offset_px = (float(text_shadow_offset_px[0]), float(text_shadow_offset_px[1]))
        self._strokes: List[AnnotationStroke] = []
        self._texts: List[AnnotationText] = []
        self._active_stroke: Optional[AnnotationStroke] = None
        self._selected_text_indices: List[int] = []  # For cut/paste operations
        self._dirty = False

    @property
    def dirty(self) -> bool:
        """True if the user has modified annotations (e.g. drawn strokes) since last load/save."""
        return self._dirty

    def clear_dirty(self) -> None:
        """Mark annotations as clean (e.g. after load or save)."""
        self._dirty = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def default_color(self) -> _Color:
        """Current default color for new strokes (RGBA 0–1)."""
        return self._default_color

    @default_color.setter
    def default_color(self, value: Sequence[float]) -> None:
        normalized = _normalize_color(value)
        if normalized is not None:
            self._default_color = normalized

    @property
    def default_text_color(self) -> _Color:
        """Current default color for new text annotations (RGBA 0–1)."""
        return self._default_text_color

    @default_text_color.setter
    def default_text_color(self, value: Sequence[float]) -> None:
        normalized = _normalize_color(value)
        if normalized is not None:
            self._default_text_color = normalized

    @property
    def default_text_font_size(self) -> float:
        """Current default font size for new text annotations."""
        return self._default_text_font_size

    @default_text_font_size.setter
    def default_text_font_size(self, value: float) -> None:
        self._default_text_font_size = max(8.0, float(value))

    @property
    def strokes(self) -> List[AnnotationStroke]:
        return list(self._strokes)

    def set_strokes(self, strokes: Sequence[AnnotationStroke]) -> None:
        self._strokes = list(strokes)

    @property
    def texts(self) -> List[AnnotationText]:
        return list(self._texts)

    def set_texts(self, texts: Sequence[AnnotationText]) -> None:
        self._texts = list(texts)

    def clear(self) -> None:
        self._strokes.clear()
        self._texts.clear()
        self._active_stroke = None
        self._selected_text_indices.clear()

    def _mark_dirty(self) -> None:
        """Mark overlay as modified by the user."""
        self._dirty = True

    def begin_stroke(
        self,
        *,
        color: Optional[Sequence[float]] = None,
        line_width: Optional[float] = None,
    ) -> None:
        stroke_color = _normalize_color(color) if color is not None else None
        stroke = AnnotationStroke(
            points=[],
            color=stroke_color or self._default_color,
            line_width=(
                max(0.5, float(line_width))
                if line_width is not None
                else self._default_line_width
            ),
        )
        self._active_stroke = stroke
        self._strokes.append(stroke)  # Add to list so it is drawn in the viewport
        self._mark_dirty()

    def add_point(self, x: float, y: float) -> None:
        if self._active_stroke is None:
            self.begin_stroke()
        if self._active_stroke is None:
            return
        self._active_stroke.points.append((float(x), float(y)))
        self._mark_dirty()

    def end_stroke(self) -> None:
        if self._active_stroke is None:
            return
        # Remove from _strokes if stroke has fewer than 2 points (click with no drag)
        if len(self._active_stroke.points) < 2 and self._active_stroke in self._strokes:
            self._strokes.remove(self._active_stroke)
        self._active_stroke = None

    def add_stroke(
        self,
        points: Sequence[Sequence[float]],
        *,
        color: Optional[Sequence[float]] = None,
        line_width: Optional[float] = None,
    ) -> None:
        if not points:
            return
        normalized = _normalize_color(color) if color is not None else None
        stroke = AnnotationStroke(
            points=[(float(x), float(y)) for x, y in points],
            color=normalized or self._default_color,
            line_width=(
                max(0.5, float(line_width))
                if line_width is not None
                else self._default_line_width
            ),
        )
        if len(stroke.points) > 1:
            self._strokes.append(stroke)

    def add_text(
        self,
        x: float,
        y: float,
        text: str,
        *,
        color: Optional[Sequence[float]] = None,
        font_size: Optional[float] = None,
        font_family: Optional[str] = None,
        shadow_color: Optional[Sequence[float]] = None,
        shadow_offset_px: Optional[Tuple[float, float]] = None,
    ) -> AnnotationText:
        """Add a text annotation at the specified position."""
        normalized_color = _normalize_color(color) if color is not None else None
        normalized_shadow_color = _normalize_color(shadow_color) if shadow_color is not None else self._default_text_shadow_color
        text_obj = AnnotationText(
            x=float(x),
            y=float(y),
            text=str(text),
            color=normalized_color or self._default_text_color,
            font_size=float(font_size) if font_size is not None else self._default_text_font_size,
            font_family=str(font_family) if font_family else None,
            shadow_color=normalized_shadow_color,
            shadow_offset_px=shadow_offset_px if shadow_offset_px is not None else self._default_text_shadow_offset_px,
        )
        self._texts.append(text_obj)
        self._mark_dirty()
        return text_obj

    def remove_text(self, index: int) -> bool:
        """Remove a text annotation by index. Returns True if removed."""
        if 0 <= index < len(self._texts):
            self._texts.pop(index)
            self._mark_dirty()
            return True
        return False

    def remove_texts(self, indices: Sequence[int]) -> int:
        """Remove multiple text annotations by indices. Returns count removed."""
        # Sort in reverse order to avoid index shifting issues
        sorted_indices = sorted(set(indices), reverse=True)
        removed = 0
        for idx in sorted_indices:
            if 0 <= idx < len(self._texts):
                self._texts.pop(idx)
                removed += 1
        if removed > 0:
            self._mark_dirty()
        return removed

    def get_text_at_position(self, x: float, y: float, tolerance: float = 5.0) -> Optional[int]:
        """Find text annotation at or near the given position. Returns index or None.
        
        Args:
            x: X coordinate in overlay coordinates (left origin)
            y: Y coordinate in overlay coordinates (bottom origin)
            tolerance: Pixel tolerance for hit detection
        """
        if not PYSIDE6_AVAILABLE or QtGui is None:
            return None
        
        # Check texts in reverse order (most recently added first, so they're on top)
        for i in range(len(self._texts) - 1, -1, -1):
            text_obj = self._texts[i]
            
            # Create a temporary font to measure text
            font = QtGui.QFont()
            if text_obj.font_family:
                font.setFamily(text_obj.font_family)
            font.setPointSizeF(text_obj.font_size)
            metrics = QtGui.QFontMetricsF(font)
            
            # Get text bounding box
            lines = text_obj.text.splitlines() if text_obj.text else [""]
            line_height = metrics.height()
            max_width = max(metrics.horizontalAdvance(line) for line in lines) if lines else 0
            total_height = line_height * len(lines)
            
            # Check if point is within text bounding box (with tolerance)
            # x is already in overlay coordinates (left origin)
            # y is in overlay coordinates (bottom origin), text_obj.y is baseline
            # We need to check if the click is within the text bounds
            text_left = text_obj.x - tolerance
            text_right = text_obj.x + max_width + tolerance
            # Baseline is at text_obj.y, text extends from (baseline - ascent) to (baseline + descent)
            # For simplicity, check if y is within baseline ± (total_height/2 + tolerance)
            text_bottom = text_obj.y - (total_height / 2) - tolerance
            text_top = text_obj.y + (total_height / 2) + tolerance
            
            if text_left <= x <= text_right and text_bottom <= y <= text_top:
                return i
        
        return None

    def copy_selected_texts(self) -> List[AnnotationText]:
        """Copy selected text annotations. Returns list of copied texts."""
        return [self._texts[i] for i in self._selected_text_indices if 0 <= i < len(self._texts)]

    def cut_selected_texts(self) -> List[AnnotationText]:
        """Cut selected text annotations (remove and return them)."""
        copied = self.copy_selected_texts()
        if copied:
            self.remove_texts(self._selected_text_indices)
            self._selected_text_indices.clear()
        return copied

    def paste_texts(self, texts: Sequence[AnnotationText], offset_x: float = 10.0, offset_y: float = 10.0) -> None:
        """Paste text annotations with an offset."""
        for text in texts:
            new_text = AnnotationText(
                x=text.x + offset_x,
                y=text.y + offset_y,
                text=text.text,
                color=text.color,
                font_size=text.font_size,
                font_family=text.font_family,
            )
            self._texts.append(new_text)
        if texts:
            self._mark_dirty()

    def select_text(self, index: int) -> None:
        """Select a text annotation by index."""
        if 0 <= index < len(self._texts) and index not in self._selected_text_indices:
            self._selected_text_indices.append(index)

    def deselect_text(self, index: int) -> None:
        """Deselect a text annotation by index."""
        if index in self._selected_text_indices:
            self._selected_text_indices.remove(index)

    def clear_selection(self) -> None:
        """Clear all text selections."""
        self._selected_text_indices.clear()

    @property
    def selected_text_indices(self) -> List[int]:
        """Get list of selected text indices."""
        return list(self._selected_text_indices)

    def to_payload(self) -> dict:
        return {
            "strokes": [stroke.to_dict() for stroke in self._strokes],
            "texts": [text.to_dict() for text in self._texts],
        }

    def load_payload(self, payload: dict) -> None:
        strokes_data = payload.get("strokes", [])
        texts_data = payload.get("texts", [])
        self._strokes = [AnnotationStroke.from_dict(item) for item in strokes_data]
        self._texts = [AnnotationText.from_dict(item) for item in texts_data]
        self._active_stroke = None
        self._selected_text_indices.clear()
        self._dirty = False

    def draw(
        self,
        viewport_width: float,
        viewport_height: float,
        *,
        gl: Optional[object] = None,
    ) -> bool:
        if not self._enabled:
            return False
        if viewport_width <= 0 or viewport_height <= 0:
            return False
        gl = gl or _resolve_gl()
        if not gl:
            log.debug("OpenGL functions not available for annotation overlay.")
            return False
        if not self._strokes:
            return False
        pushed = False
        try:
            _apply_gl_state(gl)
            pushed = _push_ortho(gl, viewport_width, viewport_height)
            if not (hasattr(gl, "glBegin") and hasattr(gl, "glEnd")):
                log.debug("OpenGL immediate mode not available for annotations.")
                return False
            for stroke in self._strokes:
                if len(stroke.points) < 2:
                    continue
                _apply_stroke_state(gl, stroke)
                gl.glBegin(gl.GL_LINE_STRIP)
                for x, y in stroke.points:
                    gl.glVertex2f(x, y)
                gl.glEnd()
        except Exception as exc:
            log.debug("Annotation OpenGL draw failed: %s", exc)
            return False
        finally:
            _pop_ortho(gl, pushed)
        return True

    def draw_texts(
        self,
        painter: "QtGui.QPainter",
        rect: "QtCore.QRect",
    ) -> bool:
        """Draw text annotations using QPainter."""
        if not self._enabled or not self._texts or not PYSIDE6_AVAILABLE:
            return False
        if rect.width() <= 0 or rect.height() <= 0:
            return False
        painter.save()
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
            viewport_height = rect.height()
            for i, text_obj in enumerate(self._texts):
                font = QtGui.QFont(painter.font())
                if text_obj.font_family:
                    font.setFamily(text_obj.font_family)
                font.setPointSizeF(text_obj.font_size)
                painter.setFont(font)
                metrics = QtGui.QFontMetricsF(font)
                # Handle multi-line text
                lines = text_obj.text.splitlines() if text_obj.text else [""]
                line_height = metrics.height()
                # Convert y coordinate from bottom-origin (OpenGL) to top-origin (Qt)
                # text_obj.y is stored in overlay coordinates (bottom origin, y=0 at bottom)
                # We need to convert to Qt coordinates (top origin, y=0 at top) for rendering
                # The stored y represents the baseline position in overlay coords
                overlay_baseline_y = text_obj.y  # Baseline y in overlay coords (bottom origin)
                qt_baseline_y = viewport_height - overlay_baseline_y  # Baseline y in Qt coords (top origin)
                # Draw text without shadow
                text_color = self._to_qcolor(text_obj.color)
                
                # Draw each line
                # Start from the baseline of the first line
                current_baseline = qt_baseline_y
                for line in lines:
                    baseline = current_baseline
                    # Draw text
                    painter.setPen(text_color)
                    painter.drawText(QtCore.QPointF(text_obj.x, baseline), line)
                    # Move to next line (baseline moves down by line_height)
                    current_baseline += line_height
                # Draw selection indicator if selected
                if i in self._selected_text_indices:
                    # Calculate bounding box for all lines
                    total_height = line_height * len(lines)
                    max_width = max(metrics.horizontalAdvance(line) for line in lines) if lines else 0
                    # Top of text box is baseline - ascent
                    text_top = qt_baseline_y - metrics.ascent()
                    selection_rect = QtCore.QRectF(
                        text_obj.x - 2,
                        text_top - 2,
                        max_width + 4,
                        total_height + 4,
                    )
                    selection_color = QtGui.QColor(255, 255, 0, 128)  # Yellow highlight
                    painter.setPen(selection_color)
                    painter.setBrush(QtGui.QBrush(selection_color))
                    painter.drawRect(selection_rect)
            return True
        except Exception as exc:
            log.debug("Annotation text draw failed: %s", exc)
            return False
        finally:
            painter.restore()

    def draw_from_stage_view(self, stage_view: object, *, gl: Optional[object] = None) -> bool:
        """Draw strokes using OpenGL. Note: Text rendering should be done in paintEvent, not here."""
        width_attr = getattr(stage_view, "width", 0)
        height_attr = getattr(stage_view, "height", 0)
        width = width_attr() if callable(width_attr) else width_attr
        height = height_attr() if callable(height_attr) else height_attr
        # Draw strokes using OpenGL
        return self.draw(float(width), float(height), gl=gl)

    @staticmethod
    def _to_qcolor(color: _Color) -> "QtGui.QColor":
        """Convert color tuple to QColor."""
        if not PYSIDE6_AVAILABLE or QtGui is None:
            raise RuntimeError("QtGui is not available.")
        r, g, b, a = color
        return QtGui.QColor.fromRgbF(r, g, b, a)


def _resolve_gl() -> Optional[object]:
    try:
        from OpenGL import GL as gl_module

        return gl_module
    except Exception:
        pass
    if not PYSIDE6_AVAILABLE or QtGui is None:
        return None
    try:
        context = QtGui.QOpenGLContext.currentContext()
        if context is None:
            return None
        funcs = context.functions()
        if hasattr(funcs, "initializeOpenGLFunctions"):
            funcs.initializeOpenGLFunctions()
        return funcs
    except Exception:
        return None


def _apply_gl_state(gl: object) -> None:
    if hasattr(gl, "glDisable"):
        try:
            gl.glDisable(gl.GL_DEPTH_TEST)
        except Exception:
            pass
    if hasattr(gl, "glEnable"):
        try:
            gl.glEnable(gl.GL_BLEND)
        except Exception:
            pass
    if hasattr(gl, "glBlendFunc"):
        try:
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        except Exception:
            pass


def _apply_stroke_state(gl: object, stroke: AnnotationStroke) -> None:
    if hasattr(gl, "glLineWidth"):
        try:
            gl.glLineWidth(stroke.line_width)
        except Exception:
            pass
    if hasattr(gl, "glColor4f"):
        try:
            r, g, b, a = stroke.color
            gl.glColor4f(r, g, b, a)
        except Exception:
            pass


def _push_ortho(gl: object, viewport_width: float, viewport_height: float) -> bool:
    if not all(hasattr(gl, name) for name in ("glMatrixMode", "glPushMatrix", "glLoadIdentity", "glOrtho")):
        return False
    try:
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glOrtho(0.0, viewport_width, 0.0, viewport_height, -1.0, 1.0)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        return True
    except Exception:
        return False


def _pop_ortho(gl: object, pushed: bool) -> None:
    if not pushed or not hasattr(gl, "glMatrixMode") or not hasattr(gl, "glPopMatrix"):
        return
    try:
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
    except Exception:
        return


def _normalize_color(value: Sequence[float]) -> Optional[_Color]:
    if value is None:
        return None
    try:
        parts = list(value)
    except TypeError:
        return None
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

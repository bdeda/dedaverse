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

__all__ = ["AnnotationGlOverlay", "AnnotationStroke"]

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

try:
    from PySide6 import QtGui
    PYSIDE6_AVAILABLE = True
except ImportError:
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


class AnnotationGlOverlay:
    """OpenGL annotation layer rendered above the 3D viewport."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        color: Sequence[float] = (1.0, 0.9, 0.2, 0.9),
        line_width: float = 2.0,
    ) -> None:
        self._enabled = bool(enabled)
        self._default_color = _normalize_color(color) or (1.0, 0.9, 0.2, 0.9)
        self._default_line_width = max(0.5, float(line_width))
        self._strokes: List[AnnotationStroke] = []
        self._active_stroke: Optional[AnnotationStroke] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def strokes(self) -> List[AnnotationStroke]:
        return list(self._strokes)

    def set_strokes(self, strokes: Sequence[AnnotationStroke]) -> None:
        self._strokes = list(strokes)

    def clear(self) -> None:
        self._strokes.clear()
        self._active_stroke = None

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

    def add_point(self, x: float, y: float) -> None:
        if self._active_stroke is None:
            self.begin_stroke()
        if self._active_stroke is None:
            return
        self._active_stroke.points.append((float(x), float(y)))

    def end_stroke(self) -> None:
        if self._active_stroke is None:
            return
        if len(self._active_stroke.points) > 1:
            self._strokes.append(self._active_stroke)
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

    def to_payload(self) -> dict:
        return {"strokes": [stroke.to_dict() for stroke in self._strokes]}

    def load_payload(self, payload: dict) -> None:
        strokes_data = payload.get("strokes", [])
        self._strokes = [AnnotationStroke.from_dict(item) for item in strokes_data]
        self._active_stroke = None

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

    def draw_from_stage_view(self, stage_view: object, *, gl: Optional[object] = None) -> bool:
        width_attr = getattr(stage_view, "width", 0)
        height_attr = getattr(stage_view, "height", 0)
        width = width_attr() if callable(width_attr) else width_attr
        height = height_attr() if callable(height_attr) else height_attr
        return self.draw(float(width), float(height), gl=gl)


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

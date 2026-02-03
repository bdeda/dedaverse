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
"""Reticle overlay functionality for the USD viewer."""

from __future__ import annotations

__all__ = ["CameraReticleGlOverlay"]

import logging
from collections.abc import Iterable as IterableABC
from typing import List, Optional, Sequence, Tuple

try:
    from PySide6 import QtGui
    PYSIDE6_AVAILABLE = True
except ImportError:
    QtGui = None
    PYSIDE6_AVAILABLE = False


log = logging.getLogger(__name__)

_Segment = Tuple[Tuple[float, float], Tuple[float, float]]


class CameraReticleGlOverlay:
    """OpenGL helper that draws a camera reticle overlay in screen space.

    This class does not own the OpenGL context. Call draw() while a valid
    OpenGL context is current (e.g. inside StageView paintGL).
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        style: str = "crosshair",
        size_px: float = 20.0,
        line_width: float = 1.0,
        color: Sequence[float] = (1.0, 1.0, 1.0, 0.7),
        grid_spacing_px: float = 20.0,
    ) -> None:
        self._enabled = bool(enabled)
        self._style = "crosshair"
        self._size_px = 20.0
        self._line_width = 1.0
        self._color = (1.0, 1.0, 1.0, 0.7)
        self._grid_spacing_px = 20.0
        self.style = style
        self.size_px = size_px
        self.line_width = line_width
        self.color = color
        self.grid_spacing_px = grid_spacing_px

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def style(self) -> str:
        return self._style

    @style.setter
    def style(self, value: str) -> None:
        if value not in ("crosshair", "frame", "grid"):
            log.warning("Unsupported reticle style: %s", value)
            return
        self._style = value

    @property
    def size_px(self) -> float:
        return self._size_px

    @size_px.setter
    def size_px(self, value: float) -> None:
        try:
            size = float(value)
        except (TypeError, ValueError):
            log.warning("Invalid reticle size: %r", value)
            return
        self._size_px = max(5.0, min(200.0, size))

    @property
    def line_width(self) -> float:
        return self._line_width

    @line_width.setter
    def line_width(self, value: float) -> None:
        try:
            width = float(value)
        except (TypeError, ValueError):
            log.warning("Invalid reticle line width: %r", value)
            return
        self._line_width = max(0.5, min(10.0, width))

    @property
    def grid_spacing_px(self) -> float:
        return self._grid_spacing_px

    @grid_spacing_px.setter
    def grid_spacing_px(self, value: float) -> None:
        try:
            spacing = float(value)
        except (TypeError, ValueError):
            log.warning("Invalid grid spacing: %r", value)
            return
        self._grid_spacing_px = max(4.0, min(200.0, spacing))

    @property
    def color(self) -> Tuple[float, float, float, float]:
        return self._color

    @color.setter
    def color(self, value: Sequence[float]) -> None:
        normalized = self._normalize_color(value)
        if normalized is None:
            log.warning("Invalid reticle color: %r", value)
            return
        self._color = normalized

    def build_segments(self, viewport_width: float, viewport_height: float) -> List[_Segment]:
        """Return reticle line segments in pixel coordinates."""
        if viewport_width <= 0 or viewport_height <= 0:
            return []
        center_x = viewport_width * 0.5
        center_y = viewport_height * 0.5
        half_size = self._size_px * 0.5
        segments: List[_Segment] = []

        if self._style == "crosshair":
            segments.extend(
                [
                    ((center_x - half_size, center_y), (center_x + half_size, center_y)),
                    ((center_x, center_y - half_size), (center_x, center_y + half_size)),
                ]
            )
            return segments

        if self._style == "frame":
            third_w = viewport_width / 3.0
            third_h = viewport_height / 3.0
            segments.extend(
                [
                    ((third_w, 0.0), (third_w, viewport_height)),
                    ((third_w * 2.0, 0.0), (third_w * 2.0, viewport_height)),
                    ((0.0, third_h), (viewport_width, third_h)),
                    ((0.0, third_h * 2.0), (viewport_width, third_h * 2.0)),
                    ((center_x - half_size, center_y), (center_x + half_size, center_y)),
                    ((center_x, center_y - half_size), (center_x, center_y + half_size)),
                ]
            )
            return segments

        if self._style == "grid":
            spacing = self._grid_spacing_px
            x = spacing
            while x < viewport_width:
                segments.append(((x, 0.0), (x, viewport_height)))
                x += spacing
            y = spacing
            while y < viewport_height:
                segments.append(((0.0, y), (viewport_width, y)))
                y += spacing
            segments.extend(
                [
                    ((center_x - half_size, center_y), (center_x + half_size, center_y)),
                    ((center_x, center_y - half_size), (center_x, center_y + half_size)),
                ]
            )
            return segments

        return segments

    def build_ndc_segments(
        self, viewport_width: float, viewport_height: float
    ) -> List[_Segment]:
        """Return reticle line segments in normalized device coordinates."""
        segments = self.build_segments(viewport_width, viewport_height)
        if not segments:
            return segments
        half_w = viewport_width * 0.5
        half_h = viewport_height * 0.5
        if half_w <= 0 or half_h <= 0:
            return []
        ndc_segments: List[_Segment] = []
        for (x1, y1), (x2, y2) in segments:
            ndc_segments.append(
                (
                    ((x1 / half_w) - 1.0, (y1 / half_h) - 1.0),
                    ((x2 / half_w) - 1.0, (y2 / half_h) - 1.0),
                )
            )
        return ndc_segments

    def draw(
        self,
        viewport_width: float,
        viewport_height: float,
        *,
        gl: Optional[object] = None,
        use_ndc: bool = False,
    ) -> bool:
        """Draw the reticle using OpenGL immediate mode, if available."""
        if not self._enabled:
            return False
        if viewport_width <= 0 or viewport_height <= 0:
            return False

        gl = gl or self._resolve_gl()
        if not gl:
            log.debug("OpenGL functions not available for reticle overlay.")
            return False

        segments = (
            self.build_ndc_segments(viewport_width, viewport_height)
            if use_ndc
            else self.build_segments(viewport_width, viewport_height)
        )
        if not segments:
            return False

        try:
            self._apply_gl_state(gl)
            pushed = False
            if not use_ndc:
                pushed = self._push_ortho(gl, viewport_width, viewport_height)
            if hasattr(gl, "glBegin") and hasattr(gl, "glEnd"):
                gl.glBegin(gl.GL_LINES)
                for (x1, y1), (x2, y2) in segments:
                    gl.glVertex2f(x1, y1)
                    gl.glVertex2f(x2, y2)
                gl.glEnd()
            else:
                log.debug(
                    "OpenGL immediate mode not available; "
                    "use build_ndc_segments() for shader rendering."
                )
                return False
        except Exception as exc:
            log.debug("Reticle OpenGL draw failed: %s", exc)
            return False
        finally:
            if not use_ndc:
                self._pop_ortho(gl, pushed)
        return True

    def draw_from_stage_view(self, stage_view: object, *, gl: Optional[object] = None) -> bool:
        """Draw the reticle using a StageView-like widget's dimensions."""
        width_attr = getattr(stage_view, "width", 0)
        height_attr = getattr(stage_view, "height", 0)
        width = width_attr() if callable(width_attr) else width_attr
        height = height_attr() if callable(height_attr) else height_attr
        return self.draw(float(width), float(height), gl=gl)

    def _resolve_gl(self) -> Optional[object]:
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

    def _apply_gl_state(self, gl: object) -> None:
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
        if hasattr(gl, "glLineWidth"):
            try:
                gl.glLineWidth(self._line_width)
            except Exception:
                pass
        if hasattr(gl, "glColor4f"):
            try:
                r, g, b, a = self._color
                gl.glColor4f(r, g, b, a)
            except Exception:
                pass

    def _push_ortho(self, gl: object, viewport_width: float, viewport_height: float) -> bool:
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

    def _pop_ortho(self, gl: object, pushed: bool) -> None:
        if not pushed or not hasattr(gl, "glMatrixMode") or not hasattr(gl, "glPopMatrix"):
            return
        try:
            gl.glMatrixMode(gl.GL_MODELVIEW)
            gl.glPopMatrix()
            gl.glMatrixMode(gl.GL_PROJECTION)
            gl.glPopMatrix()
        except Exception:
            return

    @staticmethod
    def _normalize_color(value: Sequence[float]) -> Optional[Tuple[float, float, float, float]]:
        if not isinstance(value, IterableABC):
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

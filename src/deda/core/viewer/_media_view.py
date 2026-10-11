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
"""The 2D viewport: shows one frame of an image, image sequence or video."""
import logging

from PySide6 import QtCore, QtGui, QtWidgets

from . import _media

log = logging.getLogger(__name__)

_MIN_ZOOM = 0.02
_MAX_ZOOM = 64.0


class MediaViewWidget(QtWidgets.QWidget):
    """Shows a frame with zoom, pan, channel isolation and exposure.

    Wheel zooms around the cursor, dragging pans, and :meth:`fit` / :meth:`actual_size`
    reset the view. Alpha is shown over a checkerboard.
    """

    errorOccurred = QtCore.Signal(str)
    viewChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 240)
        self._source: _media.MediaSource | None = None
        self._frame: _media.Frame | None = None
        self._frame_number = 1
        self._image: QtGui.QImage | None = None
        self._channel = 'rgba'
        self._exposure = 0.0
        self._zoom = 1.0
        self._offset = QtCore.QPointF(0.0, 0.0)  # image origin in widget pixels
        self._fit_on_resize = True
        self._drag_start: QtCore.QPoint | None = None
        self._drag_offset = QtCore.QPointF()
        self._cursor_image_pos: QtCore.QPoint | None = None
        self._show_hud = True
        self._checker = self._make_checker_brush()

    # -- state -------------------------------------------------------------------------

    @property
    def source(self) -> '_media.MediaSource | None':
        return self._source

    @property
    def frame_number(self) -> int:
        return self._frame_number

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def exposure(self) -> float:
        return self._exposure

    @property
    def show_hud(self) -> bool:
        return self._show_hud

    def set_source(self, source: '_media.MediaSource | None') -> None:
        """Show a media source (closing the previous one) from its first frame."""
        if self._source is not None and self._source is not source:
            self._source.close()
        self._source = source
        self._frame = None
        self._image = None
        self._fit_on_resize = True
        if source is not None:
            self.set_frame(source.first_frame)
        self.update()

    def set_frame(self, frame_number: int) -> bool:
        """Decode and show a frame. Returns False (and emits ``errorOccurred``) on failure."""
        if self._source is None:
            return False
        frame_number = min(max(frame_number, self._source.first_frame), self._source.last_frame)
        try:
            self._frame = self._source.read_frame(frame_number)
        except _media.MediaError as err:
            self.errorOccurred.emit(str(err))
            return False
        self._frame_number = frame_number
        self._refresh_image()
        return True

    def show_decoded(self, image: QtGui.QImage, frame_number: int) -> None:
        """Show an already decoded 8-bit RGBA image (from streaming video playback)."""
        pixels, _ = _media._qimage_to_pixels(image)
        self._frame = _media.Frame(pixels, linear=False, info={'channels': 'RGB', 'bit_depth': 8})
        self._frame_number = frame_number
        self._refresh_image()

    def set_channel(self, channel: str) -> None:
        if channel not in _media.CHANNEL_MODES:
            raise ValueError(f'channel must be one of {_media.CHANNEL_MODES}')
        self._channel = channel
        self._refresh_image()

    def set_exposure(self, stops: float) -> None:
        self._exposure = float(stops)
        self._refresh_image()

    def set_show_hud(self, show: bool) -> None:
        self._show_hud = bool(show)
        self.update()

    def _refresh_image(self) -> None:
        if self._frame is None:
            self._image = None
        else:
            self._image = _media.frame_to_qimage(self._frame, self._channel, self._exposure)
            if self._fit_on_resize:
                self.fit()
        self.update()
        self.viewChanged.emit()

    def pixel_at(self, x: int, y: int) -> tuple | None:
        """The source values at an image pixel (a tuple of 4), or None outside the image."""
        if self._frame is None or not (0 <= x < self._frame.width and 0 <= y < self._frame.height):
            return None
        return tuple(self._frame.pixels[y, x].tolist())

    # -- view --------------------------------------------------------------------------

    def fit(self) -> None:
        """Scale the image to fit the widget and centre it."""
        self._fit_on_resize = True
        if self._image is None or self.width() < 2 or self.height() < 2:
            return
        zoom = min(self.width() / self._image.width(), self.height() / self._image.height())
        self._set_zoom(min(max(zoom, _MIN_ZOOM), _MAX_ZOOM), self._viewport_centre())
        self._centre()
        self.update()

    def actual_size(self) -> None:
        """Show the image at 100%, centred."""
        self._fit_on_resize = False
        self._set_zoom(1.0, self._viewport_centre())
        self._centre()
        self.update()

    def _viewport_centre(self) -> QtCore.QPointF:
        return QtCore.QPointF(self.width() / 2.0, self.height() / 2.0)

    def _centre(self) -> None:
        if self._image is None:
            return
        self._offset = QtCore.QPointF((self.width() - self._image.width() * self._zoom) / 2.0,
                                      (self.height() - self._image.height() * self._zoom) / 2.0)

    def _set_zoom(self, zoom: float, anchor: QtCore.QPointF) -> None:
        """Change the zoom, keeping the image point under ``anchor`` fixed."""
        zoom = min(max(zoom, _MIN_ZOOM), _MAX_ZOOM)
        image_point = (anchor - self._offset) / self._zoom
        self._zoom = zoom
        self._offset = anchor - image_point * zoom

    def _widget_to_image(self, pos) -> QtCore.QPoint:
        point = (QtCore.QPointF(pos) - self._offset) / self._zoom
        return QtCore.QPoint(int(point.x() // 1), int(point.y() // 1))

    # -- painting ----------------------------------------------------------------------

    @staticmethod
    def _make_checker_brush() -> QtGui.QBrush:
        tile = QtGui.QPixmap(16, 16)
        tile.fill(QtGui.QColor(70, 70, 70))
        painter = QtGui.QPainter(tile)
        painter.fillRect(0, 0, 8, 8, QtGui.QColor(100, 100, 100))
        painter.fillRect(8, 8, 8, 8, QtGui.QColor(100, 100, 100))
        painter.end()
        return QtGui.QBrush(tile)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(38, 38, 38))
        if self._image is None:
            painter.setPen(QtGui.QColor(160, 160, 160))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter,
                             'Open an image, image sequence or video  (File > Open)')
            return
        target = QtCore.QRectF(self._offset.x(), self._offset.y(),
                               self._image.width() * self._zoom, self._image.height() * self._zoom)
        if self._image.hasAlphaChannel():
            painter.fillRect(target, self._checker)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, self._zoom < 1.0)
        painter.drawImage(target, self._image)
        painter.setPen(QtGui.QColor(90, 90, 90))
        painter.drawRect(target)
        if self._show_hud:
            self._paint_hud(painter)

    def hud_lines(self) -> list[str]:
        """The text shown in the corner: what is on screen and the value under the cursor."""
        if self._source is None or self._frame is None:
            return []
        info = self._frame.info
        lines = [self._source.name,
                 f'{self._frame.width} x {self._frame.height}   {info.get("channels", "")}   '
                 f'{info.get("bit_depth", "")}-bit   zoom {self._zoom * 100:.0f}%']
        if self._source.frame_count > 1:
            lines.append(f'frame {self._frame_number}  ({self._source.first_frame}-{self._source.last_frame})'
                         f'   {self._source.fps:g} fps')
        if self._source.kind == 'sequence':
            missing = self._source.sequence.missing
            if missing:
                lines.append(f'{len(missing)} missing frame(s), e.g. {missing[0]}')
        if self._exposure:
            lines.append(f'exposure {self._exposure:+.1f} stops')
        if self._channel != 'rgba':
            lines.append(f'channel: {self._channel}')
        if self._cursor_image_pos is not None:
            values = self.pixel_at(self._cursor_image_pos.x(), self._cursor_image_pos.y())
            if values is not None:
                shown = ' '.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in values)
                lines.append(f'({self._cursor_image_pos.x()}, {self._cursor_image_pos.y()})  {shown}')
        return lines

    def _paint_hud(self, painter: QtGui.QPainter) -> None:
        lines = self.hud_lines()
        if not lines:
            return
        metrics = painter.fontMetrics()
        width = max(metrics.horizontalAdvance(line) for line in lines) + 16
        height = metrics.height() * len(lines) + 12
        painter.fillRect(QtCore.QRect(8, 8, width, height), QtGui.QColor(0, 0, 0, 150))
        painter.setPen(QtGui.QColor(230, 230, 230))
        for index, line in enumerate(lines):
            painter.drawText(16, 8 + 6 + metrics.ascent() + index * metrics.height(), line)

    # -- interaction -------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_on_resize:
            self.fit()

    def wheelEvent(self, event):
        if self._image is None:
            return
        steps = event.angleDelta().y() / 120.0
        if not steps:
            return
        self._fit_on_resize = False
        self._set_zoom(self._zoom * (1.25 ** steps), event.position())
        self.update()
        self.viewChanged.emit()

    def mousePressEvent(self, event):
        if event.button() in (QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.MiddleButton):
            self._drag_start = event.position().toPoint()
            self._drag_offset = QtCore.QPointF(self._offset)
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            self._fit_on_resize = False
            self._offset = self._drag_offset + QtCore.QPointF(event.position().toPoint() - self._drag_start)
        self._cursor_image_pos = self._widget_to_image(event.position())
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.unsetCursor()

    def mouseDoubleClickEvent(self, event):
        self.fit()

    def leaveEvent(self, event):
        self._cursor_image_pos = None
        self.update()

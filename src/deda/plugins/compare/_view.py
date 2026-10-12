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
"""A|B image comparison view: a sliding vertical divider over pan/zoomable overlaid images."""
__all__ = ['CompareView']

from PySide6 import QtCore, QtGui, QtWidgets


class _ClippedPixmapItem(QtWidgets.QGraphicsPixmapItem):
    """A QGraphicsPixmapItem that can be clipped to a rectangle in its own local coordinates."""

    def __init__(self, pixmap: QtGui.QPixmap):
        super().__init__(pixmap)
        self._clip_rect: QtCore.QRectF | None = None

    def set_clip_rect(self, rect: QtCore.QRectF | None) -> None:
        self._clip_rect = rect
        self.update()

    def paint(self, painter, option, widget=None):
        if self._clip_rect is None:
            super().paint(painter, option, widget)
            return
        painter.save()
        painter.setClipRect(self._clip_rect)
        super().paint(painter, option, widget)
        painter.restore()


class CompareView(QtWidgets.QGraphicsView):
    """Overlay of two images (A on the left of the divider, B on the right) with pan and zoom.

    A and B are mapped onto the same scene rectangle, sized to the *larger* of the two
    images' pixel dimensions, so a lower-resolution image (e.g. an un-upscaled original)
    is scaled up to visually align with a higher-resolution one (e.g. its 4x-upscaled
    result) pixel-for-pixel. Zooming the view to 100% then inspects the larger image at
    native resolution while the divider reveals A or B for direct comparison.
    """

    divider_moved = QtCore.Signal(float)  # current divider position, 0..1 fraction of width
    zoom_changed = QtCore.Signal(float)  # current view scale (1.0 == 100%)

    _DIVIDER_HIT_MARGIN = 8  # viewport pixels
    _MIN_SCALE = 0.02
    _MAX_SCALE = 32.0
    _ZOOM_STEP = 1.25

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setRenderHints(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform | QtGui.QPainter.RenderHint.Antialiasing
        )
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QtGui.QColor(24, 24, 24))
        self.setMouseTracking(True)

        self._item_a: _ClippedPixmapItem | None = None
        self._item_b: _ClippedPixmapItem | None = None
        self._scene_rect = QtCore.QRectF()
        self._divider_fraction = 0.5

        self._divider_line: QtWidgets.QGraphicsLineItem | None = None

        self._dragging_divider = False
        self._panning = False
        self._pan_start = QtCore.QPointF()
        self._pan_scroll_start = (0, 0)

        self.clear()

    def clear(self) -> None:
        """Remove any loaded images and reset the view to empty."""
        self.scene().clear()  # deletes every item currently in the scene, incl. the old divider line
        self._item_a = self._item_b = None
        self._scene_rect = QtCore.QRectF()
        self.setSceneRect(self._scene_rect)

        # scene().clear() just deleted the previous divider line's C++ object, so the old
        # Python reference (if any) is now a dangling wrapper -- build a fresh one instead
        # of reusing it, or re-adding it later would touch an already-deleted item.
        self._divider_line = QtWidgets.QGraphicsLineItem()
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 220))
        pen.setWidth(0)  # cosmetic pen: always 1 device pixel, regardless of view scale
        self._divider_line.setPen(pen)
        self._divider_line.setZValue(10)

    def set_images(self, pixmap_a: QtGui.QPixmap | None, pixmap_b: QtGui.QPixmap | None) -> None:
        """Show pixmap_a and/or pixmap_b, replacing whatever was previously loaded.

        Either may be None/null. With only one given, it's shown full-frame with no divider.
        With both given, they're overlaid (B's resolution sets the scene size) with the
        draggable divider between them.
        """
        self.clear()
        self._divider_fraction = 0.5  # every fresh load starts centered, not wherever it was last dragged

        pixmap_a = pixmap_a if pixmap_a is not None and not pixmap_a.isNull() else None
        pixmap_b = pixmap_b if pixmap_b is not None and not pixmap_b.isNull() else None
        if pixmap_a is None and pixmap_b is None:
            return

        if pixmap_a is not None and pixmap_b is not None:
            width = max(pixmap_a.width(), pixmap_b.width())
            height = max(pixmap_a.height(), pixmap_b.height())
        else:
            reference = pixmap_a if pixmap_a is not None else pixmap_b
            width, height = reference.width(), reference.height()
        self._scene_rect = QtCore.QRectF(0, 0, width, height)

        if pixmap_a is not None:
            self._item_a = _ClippedPixmapItem(pixmap_a)
            self._item_a.setTransformationMode(QtCore.Qt.TransformationMode.SmoothTransformation)
            self._item_a.setScale(width / pixmap_a.width())
            self.scene().addItem(self._item_a)
        if pixmap_b is not None:
            self._item_b = _ClippedPixmapItem(pixmap_b)
            self._item_b.setTransformationMode(QtCore.Qt.TransformationMode.SmoothTransformation)
            self._item_b.setScale(width / pixmap_b.width())
            self.scene().addItem(self._item_b)

        self.setSceneRect(self._scene_rect)
        if self.has_images():
            self.scene().addItem(self._divider_line)
            self._update_clips()
        self.fit_to_view()

    def has_images(self) -> bool:
        return self._item_a is not None and self._item_b is not None

    def fit_to_view(self) -> None:
        if self._scene_rect.isEmpty():
            return
        self.fitInView(self._scene_rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        self.zoom_changed.emit(self.transform().m11())

    def zoom_to_actual_size(self) -> None:
        """Zoom so 1 pixel of the reference (larger) image equals 1 screen pixel."""
        if self._scene_rect.isEmpty():
            return
        self.resetTransform()
        self.zoom_changed.emit(1.0)

    def zoom_in(self) -> None:
        self._zoom_by(self._ZOOM_STEP)

    def zoom_out(self) -> None:
        self._zoom_by(1.0 / self._ZOOM_STEP)

    def set_divider_fraction(self, fraction: float) -> None:
        self._divider_fraction = max(0.0, min(1.0, fraction))
        self._update_clips()
        self.divider_moved.emit(self._divider_fraction)

    def _zoom_by(self, factor: float) -> None:
        if self._scene_rect.isEmpty():
            return
        current_scale = self.transform().m11()
        new_scale = current_scale * factor
        if new_scale < self._MIN_SCALE or new_scale > self._MAX_SCALE:
            return
        self.scale(factor, factor)
        self.zoom_changed.emit(self.transform().m11())

    def _update_clips(self) -> None:
        if self._scene_rect.isEmpty() or self._item_a is None or self._item_b is None:
            return
        width, height = self._scene_rect.width(), self._scene_rect.height()
        split_x = width * self._divider_fraction
        self._item_a.set_clip_rect(self._item_a.mapRectFromScene(QtCore.QRectF(0, 0, split_x, height)))
        self._item_b.set_clip_rect(self._item_b.mapRectFromScene(QtCore.QRectF(split_x, 0, width - split_x, height)))
        self._divider_line.setLine(split_x, 0, split_x, height)

    def _divider_viewport_x(self) -> float:
        split_x = self._scene_rect.width() * self._divider_fraction
        return self.mapFromScene(QtCore.QPointF(split_x, 0)).x()

    def _near_divider(self, viewport_x: float) -> bool:
        return self.has_images() and abs(viewport_x - self._divider_viewport_x()) <= self._DIVIDER_HIT_MARGIN

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            pos = event.position()
            if self._near_divider(pos.x()):
                self._dragging_divider = True
                self.setCursor(QtCore.Qt.CursorShape.SplitHCursor)
                event.accept()
                return
            if not self._scene_rect.isEmpty():
                self._panning = True
                self._pan_start = pos
                self._pan_scroll_start = (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
                self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._dragging_divider:
            scene_x = self.mapToScene(pos.toPoint()).x()
            width = self._scene_rect.width()
            self.set_divider_fraction(scene_x / width if width else 0.5)
            event.accept()
            return
        if self._panning:
            delta = pos - self._pan_start
            self.horizontalScrollBar().setValue(int(self._pan_scroll_start[0] - delta.x()))
            self.verticalScrollBar().setValue(int(self._pan_scroll_start[1] - delta.y()))
            event.accept()
            return
        self.setCursor(
            QtCore.Qt.CursorShape.SplitHCursor if self._near_divider(pos.x()) else QtCore.Qt.CursorShape.ArrowCursor
        )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and (self._dragging_divider or self._panning):
            self._dragging_divider = False
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self._scene_rect.isEmpty():
            return
        angle = event.angleDelta().y()
        if angle:
            self._zoom_by(self._ZOOM_STEP if angle > 0 else 1.0 / self._ZOOM_STEP)

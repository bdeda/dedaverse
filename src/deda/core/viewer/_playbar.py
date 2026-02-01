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
"""Playbar widget with playhead, frame ticks, and play/stop controls."""

__all__ = ['Playbar']

from PySide6 import QtWidgets, QtCore, QtGui


class _TimelineWidget(QtWidgets.QWidget):
    """Inner widget that draws tick marks and a draggable rectangle playhead."""

    frameChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setMinimumHeight(32)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed
        )
        self._frame_min = 0
        self._frame_max = 100
        self._frame = 0
        self._dragging = False
        self._playhead_width = 8
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def frameRange(self):
        """Return (min_frame, max_frame)."""
        return self._frame_min, self._frame_max

    def setFrameRange(self, frame_min, frame_max):
        """Set the frame range for the timeline."""
        self._frame_min = int(frame_min)
        self._frame_max = max(int(frame_max), self._frame_min + 1)
        self._frame = max(self._frame_min, min(self._frame, self._frame_max))
        self.update()

    def frame(self):
        """Return the current frame."""
        return self._frame

    def setFrame(self, frame):
        """Set the current frame and emit frameChanged."""
        f = max(self._frame_min, min(int(frame), self._frame_max))
        if f != self._frame:
            self._frame = f
            self.update()
            self.frameChanged.emit(self._frame)

    def _trackRect(self):
        """Return the horizontal track rect where the playhead slides."""
        margin = 4
        h = self.height()
        return QtCore.QRect(margin, margin, self.width() - 2 * margin, h - 2 * margin)

    def _frameToX(self, frame):
        """Map frame number to x position in the track."""
        r = self._trackRect()
        if self._frame_max <= self._frame_min:
            return r.left()
        t = (frame - self._frame_min) / (self._frame_max - self._frame_min)
        return r.left() + int(t * r.width())

    def _xToFrame(self, x):
        """Map x position to frame number."""
        r = self._trackRect()
        if r.width() <= 0:
            return self._frame_min
        t = (x - r.left()) / r.width()
        t = max(0.0, min(1.0, t))
        return int(self._frame_min + t * (self._frame_max - self._frame_min))

    def _playheadRect(self):
        """Return the rectangle for the playhead centered on current frame."""
        cx = self._frameToX(self._frame)
        r = self._trackRect()
        w = self._playhead_width
        return QtCore.QRect(cx - w // 2, r.top(), w, r.height())

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = self._trackRect()
        if r.width() <= 0 or r.height() <= 0:
            return

        # Draw track background
        painter.fillRect(r, self.palette().color(QtGui.QPalette.ColorRole.Window))
        painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.Mid))
        painter.drawRect(r.adjusted(0, 0, -1, -1))

        # Draw tick marks for frames
        span = self._frame_max - self._frame_min
        if span > 0:
            # Subdivide: show tick every N frames so we don't overcrowd
            ideal_ticks = max(2, min(span, r.width() // 20))
            step = max(1, span // ideal_ticks)
            painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.Mid))
            tick_h = 4
            for f in range(self._frame_min, self._frame_max + 1, step):
                x = self._frameToX(f)
                painter.drawLine(x, r.bottom(), x, r.bottom() - tick_h)

        # Draw playhead rectangle
        ph = self._playheadRect()
        painter.fillRect(ph, self.palette().color(QtGui.QPalette.ColorRole.Highlight))
        painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.HighlightedText))
        painter.drawRect(ph.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            ph = self._playheadRect()
            if ph.contains(event.pos()):
                self._dragging = True
                event.accept()
                return
            # Click on track: jump playhead to that position
            if self._trackRect().contains(event.pos()):
                self.setFrame(self._xToFrame(event.pos().x()))
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.setFrame(self._xToFrame(event.pos().x()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class Playbar(QtWidgets.QWidget):
    """A timeline playbar with playhead, frame ticks, play/stop buttons, and frame display."""

    frameChanged = QtCore.Signal(int)
    playClicked = QtCore.Signal()
    stopClicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setMinimumHeight(40)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Play and stop buttons on the left (icons only)
        style = QtWidgets.QApplication.style()
        play_icon = style.standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_MediaPlay
        )
        stop_icon = style.standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_MediaStop
        )
        self._play_btn = QtWidgets.QPushButton()
        self._play_btn.setIcon(play_icon)
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setToolTip('Play')
        self._play_btn.clicked.connect(self.playClicked.emit)
        layout.addWidget(self._play_btn)

        self._stop_btn = QtWidgets.QPushButton()
        self._stop_btn.setIcon(stop_icon)
        self._stop_btn.setFixedSize(32, 32)
        self._stop_btn.setToolTip('Stop')
        self._stop_btn.clicked.connect(self.stopClicked.emit)
        layout.addWidget(self._stop_btn)

        layout.addSpacing(8)

        # Timeline with ticks and playhead (center, expanding)
        self._timeline = _TimelineWidget(self)
        self._timeline.frameChanged.connect(self._on_frame_changed)
        layout.addWidget(self._timeline, 1)

        layout.addSpacing(8)

        # Frame number on the right
        self._frame_label = QtWidgets.QLabel('0')
        self._frame_label.setMinimumWidth(48)
        self._frame_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._frame_label)

    def _on_frame_changed(self, frame):
        self._frame_label.setText(str(frame))
        self.frameChanged.emit(frame)

    def frameRange(self):
        """Return (min_frame, max_frame)."""
        return self._timeline.frameRange()

    def setFrameRange(self, frame_min, frame_max):
        """Set the frame range for the timeline."""
        self._timeline.setFrameRange(frame_min, frame_max)
        self._on_frame_changed(self._timeline.frame())

    def frame(self):
        """Return the current frame."""
        return self._timeline.frame()

    def setFrame(self, frame):
        """Set the current frame."""
        self._timeline.setFrame(frame)
        self._on_frame_changed(self._timeline.frame())

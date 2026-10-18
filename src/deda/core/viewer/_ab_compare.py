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
"""A|B comparison of two USD stages: one view, split by a draggable vertical slider.

Two 3D viewports sit on top of each other. A fills the whole area; B is clipped to the right of the
slider, so dragging the slider reveals more of one or the other. The two cameras are kept identical,
so moving the camera in either side moves both and the differences line up exactly.
"""
from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ._usd_viewer import UsdViewWidget

_HANDLE_WIDTH = 16  # grab area of the slider, in pixels
_SYNC_INTERVAL_MS = 30


class _Divider(QtWidgets.QWidget):
    """The slider: a thin vertical line with a grip, dragged sideways."""

    moved = QtCore.Signal(int)  # x position, in the parent's coordinates

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        self.setToolTip('Drag to compare A and B')
        self._dragging = False

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        x = self.width() // 2
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 230), 2))
        painter.drawLine(x, 0, x, self.height())
        grip = QtCore.QRect(x - 9, self.height() // 2 - 16, 18, 32)
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40), 1))
        painter.setBrush(QtGui.QColor(255, 255, 255, 230))
        painter.drawRoundedRect(grip, 6, 6)
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40), 2))
        painter.drawLine(x - 3, grip.top() + 8, x - 3, grip.bottom() - 8)
        painter.drawLine(x + 3, grip.top() + 8, x + 3, grip.bottom() - 8)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            x = self.mapToParent(event.position().toPoint()).x()
            self.moved.emit(x)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False


class AbCompareWidget(QtWidgets.QWidget):
    """Two stages in one view, A on the left of the slider and B on the right."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._split = 0.5
        self._last_camera: list[float] | None = None

        self._viewer_a = UsdViewWidget(stage=None, parent=self)
        self._viewer_b = UsdViewWidget(stage=None, parent=self)
        self._label_a = self._make_label('A')
        self._label_b = self._make_label('B')
        self._divider = _Divider(parent=self)
        self._divider.moved.connect(self._on_divider_moved)

        self._sync_timer = QtCore.QTimer(self)
        self._sync_timer.setInterval(_SYNC_INTERVAL_MS)
        self._sync_timer.timeout.connect(self._sync_cameras)

    # -- public --------------------------------------------------------------------------

    @property
    def viewer_a(self) -> UsdViewWidget:
        return self._viewer_a

    @property
    def viewer_b(self) -> UsdViewWidget:
        return self._viewer_b

    @property
    def split(self) -> float:
        """The slider position, 0.0 (all B) to 1.0 (all A)."""
        return self._split

    def set_split(self, fraction: float) -> None:
        self._split = min(1.0, max(0.0, float(fraction)))
        self._layout_children()

    def set_stages(self, stage_a, stage_b, path_a, path_b) -> None:
        """Show ``stage_a`` and ``stage_b`` (opened from ``path_a`` and ``path_b``) and frame them together."""
        self._viewer_a.stage = stage_a
        self._viewer_b.stage = stage_b
        self._label_a.setText(f'A: {Path(path_a).name}')
        self._label_a.setToolTip(str(path_a))
        self._label_b.setText(f'B: {Path(path_b).name}')
        self._label_b.setToolTip(str(path_b))
        self._last_camera = None
        self._layout_children()
        self.frame_all()

    def frame_all(self) -> None:
        """Frame A, then give B the same camera."""
        self._viewer_a.update_view(resetCam=True, forceComputeBBox=True)
        self._last_camera = None
        self._sync_cameras(force_from_a=True)

    def set_current_frame(self, frame) -> None:
        self._viewer_a.set_current_frame(frame)
        self._viewer_b.set_current_frame(frame)

    def start(self) -> None:
        self._sync_timer.start()

    def stop(self) -> None:
        self._sync_timer.stop()

    def release(self) -> None:
        """Stop syncing and let go of both stages (their GL resources are closed with them)."""
        self.stop()
        self._viewer_a.stage = None
        self._viewer_b.stage = None

    # -- layout --------------------------------------------------------------------------

    def _make_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text, self)
        label.setStyleSheet(
            'background: rgba(0, 0, 0, 150); color: white; padding: 2px 8px; border-radius: 3px;')
        label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return label

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_children()

    def showEvent(self, event):
        super().showEvent(event)
        self._layout_children()

    def _split_x(self) -> int:
        return int(round(self.width() * self._split))

    def _layout_children(self) -> None:
        w, h = self.width(), self.height()
        x = self._split_x()
        self._viewer_a.setGeometry(0, 0, w, h)
        self._viewer_b.setGeometry(0, 0, w, h)
        self._viewer_b.setMask(QtGui.QRegion(x, 0, max(0, w - x), h))
        self._divider.setGeometry(x - _HANDLE_WIDTH // 2, 0, _HANDLE_WIDTH, h)
        self._label_a.adjustSize()
        self._label_b.adjustSize()
        self._label_a.move(8, 8)
        self._label_b.move(max(8, w - self._label_b.width() - 8), 8)
        # A's label is hidden when the slider has hidden it, so only the visible side is named
        self._label_a.setVisible(x > self._label_a.width() + 16)
        self._label_b.setVisible(w - x > self._label_b.width() + 16)
        for widget in (self._label_a, self._label_b, self._divider):
            widget.raise_()

    def _on_divider_moved(self, x: int) -> None:
        self.set_split(x / max(1, self.width()))

    # -- cameras -------------------------------------------------------------------------

    def _sync_cameras(self, force_from_a: bool = False) -> None:
        """Copy whichever camera moved to the other, so both always look the same way."""
        cam_a = self._viewer_a.get_camera_transform()
        cam_b = self._viewer_b.get_camera_transform()
        if cam_a is None or cam_b is None:
            return
        if force_from_a:
            source, target = cam_a, self._viewer_b
        elif self._last_camera is None:
            self._last_camera = cam_a
            source, target = cam_a, self._viewer_b
        elif cam_a != self._last_camera:
            source, target = cam_a, self._viewer_b
        elif cam_b != self._last_camera:
            source, target = cam_b, self._viewer_a
        else:
            return
        self._last_camera = source
        if source != (cam_b if target is self._viewer_b else cam_a):
            target.set_camera_transform(source)
            target.stage_view.update()
        self._viewer_a.stage_view.update()
        self._viewer_b.stage_view.update()


class AbCompareDialog(QtWidgets.QDialog):
    """Pick the two USD files to compare."""

    def __init__(self, path_a: str = '', path_b: str = '', parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle('A|B Compare')
        self.setMinimumWidth(560)
        form = QtWidgets.QFormLayout(self)
        self._edit_a = self._add_row(form, 'A', path_a)
        self._edit_b = self._add_row(form, 'B', path_b)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _add_row(self, form: QtWidgets.QFormLayout, name: str, path: str) -> QtWidgets.QLineEdit:
        edit = QtWidgets.QLineEdit(path, self)
        browse = QtWidgets.QPushButton('Browse...', self)
        browse.clicked.connect(lambda: self._browse(name, edit))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(edit, 1)
        row.addWidget(browse)
        form.addRow(name, row)
        return edit

    def _browse(self, name: str, edit: QtWidgets.QLineEdit) -> None:
        start = edit.text() or str(Path.home())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f'Select {name}', start, 'USD Files (*.usd *.usda *.usdc *.usdz);;All Files (*)')
        if path:
            edit.setText(path)

    def paths(self) -> tuple[str, str]:
        return self._edit_a.text().strip(), self._edit_b.text().strip()

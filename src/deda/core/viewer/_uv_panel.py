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
"""The UV editor panel: a floating view of a mesh's UV sets, styled to match the Dedaverse viewer.

The layout follows the Maya UV Editor: a UV canvas with display toggles along the top and the UV
sets listed beside it. It is read-only for now; the canvas and panel keep their state in plain
attributes and signals so editing tools can be added to them later.
"""

__all__ = ['UvCanvas', 'UvEditorDock', 'UvEditorPanel']

import colorsys
import logging

from pxr import Usd
from PySide6 import QtCore, QtGui, QtWidgets

from . import _uv

log = logging.getLogger(__name__)

# Above this many faces the per-shell tint is switched off; it needs one polygon per face.
_MAX_SHADED_FACES = 50_000

# Palette, taken from the Dedaverse app's panels and overlays (dark neutral greys, one cool accent).
_BACKGROUND = QtGui.QColor(20, 20, 20)
_SURFACE = QtGui.QColor(30, 30, 30)
_BORDER = QtGui.QColor(50, 50, 50)
_GRID_MINOR = QtGui.QColor(34, 34, 36)
_GRID_MAJOR = QtGui.QColor(62, 62, 68)
_CHECKER_LIGHT = QtGui.QColor(44, 44, 48)
_CHECKER_DARK = QtGui.QColor(36, 36, 40)
_EDGE = QtGui.QColor(200, 200, 210)
_BORDER_EDGE = QtGui.QColor(86, 156, 214)
_FLIPPED = QtGui.QColor(226, 82, 82, 150)
_TEXT = QtGui.QColor(180, 180, 200)
_TEXT_DIM = QtGui.QColor(110, 110, 124)

_STYLE = """
#UvEditorPanel { background-color: rgb(20, 20, 20); }
#UvEditorPanel QLabel { color: rgb(180, 180, 200); font-size: 11px; }
#UvEditorPanel QLabel#UvStats, #UvEditorPanel QLabel#UvCursor {
    font-family: Consolas, monospace; color: rgb(150, 150, 164);
}
#UvEditorPanel QComboBox, #UvEditorPanel QTreeWidget {
    background-color: rgb(30, 30, 30); border: 1px solid rgb(50, 50, 50); border-radius: 3px;
    color: rgb(220, 220, 220); font-size: 11px;
}
#UvEditorPanel QComboBox { padding: 3px 6px; }
#UvEditorPanel QComboBox QAbstractItemView { background-color: rgb(30, 30, 30); color: rgb(220, 220, 220); }
#UvEditorPanel QTreeWidget { outline: 0; }
#UvEditorPanel QTreeWidget::item { padding: 3px 2px; }
#UvEditorPanel QTreeWidget::item:selected { background-color: rgb(46, 74, 104); color: white; }
#UvEditorPanel QHeaderView::section {
    background-color: rgb(26, 26, 26); color: rgb(150, 150, 164); border: none;
    border-bottom: 1px solid rgb(50, 50, 50); padding: 3px 4px; font-size: 10px;
}
#UvEditorPanel QToolButton, #UvEditorPanel QPushButton {
    background-color: rgb(30, 30, 30); border: 1px solid rgb(50, 50, 50); border-radius: 3px;
    color: rgb(190, 190, 200); padding: 3px 9px; font-size: 11px;
}
#UvEditorPanel QToolButton:hover, #UvEditorPanel QPushButton:hover { border-color: rgb(80, 80, 80); }
#UvEditorPanel QToolButton:checked {
    background-color: rgb(46, 74, 104); border-color: rgb(86, 156, 214); color: white;
}
#UvEditorPanel QSplitter::handle { background-color: rgb(40, 40, 40); }
"""


class UvCanvas(QtWidgets.QWidget):
    """Draws one UV layout on a pannable, zoomable 2D canvas, UV (0, 0) at the bottom left.

    Pan with the middle mouse button (or Alt + left button), zoom with the wheel, ``F`` frames the
    UVs and ``Home`` frames the 0-1 tile.

    Signals:
        cursorMoved(u, v): The mouse moved over the canvas, in UV space.
        cursorLeft(): The mouse left the canvas.
    """

    cursorLeft = QtCore.Signal()
    cursorMoved = QtCore.Signal(float, float)

    _MAX_SCALE = 200_000.0
    _MIN_SCALE = 5.0

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName('UvCanvas')
        self.setMinimumSize(260, 260)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._layout: _uv.UvLayout | None = None
        self._interior_lines: list[QtCore.QLineF] = []
        self._border_lines: list[QtCore.QLineF] = []
        self._shell_paths: list[tuple[QtGui.QColor, QtGui.QPainterPath]] = []
        self._flipped_path = QtGui.QPainterPath()
        self._scale = 300.0  # pixels per UV unit
        self._origin = QtCore.QPointF(40, 0)  # screen position of UV (0, 0); y set on first show
        self._panning_from: QtCore.QPointF | None = None
        self._framed = False
        self._show = {'grid': True, 'checker': True, 'shaded': True, 'borders': True, 'flipped': True}

    def enterEvent(self, event: QtCore.QEvent) -> None:
        self.setFocus()
        super().enterEvent(event)

    def frame_bounds(self) -> None:
        """Zoom to fit every UV (and always the 0-1 tile) in the canvas."""
        u0, v0, u1, v1 = (0.0, 0.0, 1.0, 1.0)
        if self._layout is not None:
            b = self._layout.bounds()
            u0, v0, u1, v1 = min(u0, b[0]), min(v0, b[1]), max(u1, b[2]), max(v1, b[3])
        self._frame(u0, v0, u1, v1)

    def frame_tile(self) -> None:
        """Zoom to fit the 0-1 tile."""
        self._frame(0.0, 0.0, 1.0, 1.0)

    def is_shown(self, key: str) -> bool:
        """Whether the display toggle `key` (grid, checker, shaded, borders, flipped) is on."""
        return self._show[key]

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_F:
            self.frame_bounds()
        elif event.key() == QtCore.Qt.Key.Key_Home:
            self.frame_tile()
        else:
            super().keyPressEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        self.cursorLeft.emit()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._panning_from is not None:
            here = event.position()
            self._origin += here - self._panning_from
            self._panning_from = here
            self.update()
        u, v = self.screen_to_uv(event.position())
        self.cursorMoved.emit(u, v)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        alt_left = (event.button() == QtCore.Qt.MouseButton.LeftButton
                    and event.modifiers() & QtCore.Qt.KeyboardModifier.AltModifier)
        if event.button() == QtCore.Qt.MouseButton.MiddleButton or alt_left:
            self._panning_from = event.position()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._panning_from = None
        self.unsetCursor()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        if not self._framed:
            self.frame_bounds()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), _BACKGROUND)
        visible = self._visible_uv_rect()
        if self._show['checker']:
            self._paint_checker(painter)
        if self._show['grid']:
            self._paint_grid(painter, visible)
        painter.save()
        painter.setTransform(self._uv_to_screen_transform(), True)
        self._paint_layout(painter)
        painter.restore()
        self._paint_tile_labels(painter, visible)
        painter.setPen(QtGui.QPen(_BORDER, 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._framed:
            self.update()

    @property
    def scale(self) -> float:
        """Zoom, in pixels per UV unit."""
        return self._scale

    def screen_to_uv(self, point: QtCore.QPointF) -> tuple[float, float]:
        """The UV under a canvas position."""
        return ((point.x() - self._origin.x()) / self._scale,
                (self._origin.y() - point.y()) / self._scale)

    def set_layout(self, layout: '_uv.UvLayout | None') -> None:
        """Show `layout` (or nothing) and rebuild the cached geometry.

        Args:
            layout: The UV layout to draw, or None to clear the canvas.
        """
        self._layout = layout
        self._interior_lines, self._border_lines = [], []
        self._shell_paths = []
        self._flipped_path = QtGui.QPainterPath()
        if layout is not None and layout.face_count:
            self._build_lines(layout)
            if layout.face_count <= _MAX_SHADED_FACES:
                self._build_faces(layout)
        self._framed = False  # the next paint frames the new layout once the canvas has its size
        self.update()

    def set_shown(self, key: str, on: bool) -> None:
        """Turn the display toggle `key` (grid, checker, shaded, borders, flipped) on or off."""
        self._show[key] = bool(on)
        self.update()

    def shading_available(self) -> bool:
        """False when the layout is too large for per-shell tinting and flipped-face fills."""
        return self._layout is None or self._layout.face_count <= _MAX_SHADED_FACES

    @property
    def uv_layout(self) -> '_uv.UvLayout | None':
        """The layout being shown, or None."""
        return self._layout

    def uv_to_screen(self, u: float, v: float) -> QtCore.QPointF:
        """The canvas position of a UV."""
        return QtCore.QPointF(self._origin.x() + u * self._scale, self._origin.y() - v * self._scale)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        factor = 1.15 ** (event.angleDelta().y() / 120.0)
        new_scale = min(self._MAX_SCALE, max(self._MIN_SCALE, self._scale * factor))
        factor = new_scale / self._scale
        anchor = event.position()
        self._origin = anchor + (self._origin - anchor) * factor
        self._scale = new_scale
        self.update()

    def _build_faces(self, layout: '_uv.UvLayout') -> None:
        """Cache one filled path per shell, and one for every flipped face."""
        labels = layout.island_labels()
        flipped = layout.flipped_faces()
        starts = (layout.face_counts.cumsum() - layout.face_counts).tolist()
        counts = layout.face_counts.tolist()
        uvs = layout.uvs
        shell_paths = [QtGui.QPainterPath() for _ in range(int(labels.max()) + 1)]
        for face, (start, count) in enumerate(zip(starts, counts)):
            polygon = QtGui.QPolygonF([QtCore.QPointF(u, v) for u, v in uvs[start:start + count].tolist()])
            shell_paths[labels[face]].addPolygon(polygon)
            shell_paths[labels[face]].closeSubpath()
            if flipped[face]:
                self._flipped_path.addPolygon(polygon)
                self._flipped_path.closeSubpath()
        self._shell_paths = [(_shell_color(i), path) for i, path in enumerate(shell_paths)]

    def _build_lines(self, layout: '_uv.UvLayout') -> None:
        """Cache the wireframe as lines in UV space, split into shell borders and interior edges."""
        segments, is_border = layout.edge_segments()
        lines = [QtCore.QLineF(*row) for row in segments.tolist()]
        self._border_lines = [line for line, border in zip(lines, is_border.tolist()) if border]
        self._interior_lines = [line for line, border in zip(lines, is_border.tolist()) if not border]

    def _frame(self, u0: float, v0: float, u1: float, v1: float) -> None:
        """Fit the UV rectangle in the canvas with a margin."""
        self._framed = True
        margin = 28
        width = max(self.width() - 2 * margin, 40)
        height = max(self.height() - 2 * margin, 40)
        span_u, span_v = max(u1 - u0, 1e-6), max(v1 - v0, 1e-6)
        self._scale = min(self._MAX_SCALE, max(self._MIN_SCALE, min(width / span_u, height / span_v)))
        centre_u, centre_v = (u0 + u1) / 2, (v0 + v1) / 2
        self._origin = QtCore.QPointF(self.width() / 2 - centre_u * self._scale,
                                      self.height() / 2 + centre_v * self._scale)
        self.update()

    def _paint_checker(self, painter: QtGui.QPainter) -> None:
        """A 8x8 checker over the 0-1 tile, so stretching and shell scale read at a glance."""
        cell = self._scale / 8
        if cell < 3:
            return
        for row in range(8):
            for col in range(8):
                top_left = self.uv_to_screen(col / 8, (row + 1) / 8)
                painter.fillRect(QtCore.QRectF(top_left, QtCore.QSizeF(cell, cell)),
                                 _CHECKER_LIGHT if (row + col) % 2 else _CHECKER_DARK)

    def _paint_grid(self, painter: QtGui.QPainter, visible: QtCore.QRectF) -> None:
        """Tile boundaries at every whole UV, with a tenths grid once zoomed in enough."""
        if self._scale >= 240:
            painter.setPen(QtGui.QPen(_GRID_MINOR, 1))
            self._paint_grid_lines(painter, visible, 0.1)
        painter.setPen(QtGui.QPen(_GRID_MAJOR, 1))
        self._paint_grid_lines(painter, visible, 1.0)

    def _paint_grid_lines(self, painter: QtGui.QPainter, visible: QtCore.QRectF, step: float) -> None:
        """Grid lines every `step` UV units across the visible area (capped so zoomed-out is cheap)."""
        if (visible.width() / step > 400) or (visible.height() / step > 400):
            return
        u = (visible.left() // step) * step
        while u <= visible.right():
            x = self.uv_to_screen(u, 0).x()
            painter.drawLine(QtCore.QPointF(x, 0), QtCore.QPointF(x, self.height()))
            u += step
        v = (visible.top() // step) * step
        while v <= visible.bottom():
            y = self.uv_to_screen(0, v).y()
            painter.drawLine(QtCore.QPointF(0, y), QtCore.QPointF(self.width(), y))
            v += step

    def _paint_layout(self, painter: QtGui.QPainter) -> None:
        """Draw the cached UV geometry; the painter is already in UV space."""
        if self._show['shaded']:
            for colour, path in self._shell_paths:
                painter.fillPath(path, colour)
        if self._show['flipped'] and not self._flipped_path.isEmpty():
            painter.fillPath(self._flipped_path, _FLIPPED)
        pen = QtGui.QPen(_EDGE, 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLines(self._interior_lines)
        border_pen = QtGui.QPen(_BORDER_EDGE if self._show['borders'] else _EDGE, 1.6 if self._show['borders'] else 1)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.drawLines(self._border_lines)

    def _paint_tile_labels(self, painter: QtGui.QPainter, visible: QtCore.QRectF) -> None:
        """The UDIM number in the corner of each visible tile, once a tile is big enough to hold it."""
        if self._scale < 90 or visible.width() > 30 or visible.height() > 30:
            return
        painter.setPen(_TEXT_DIM)
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)
        for tile_v in range(int(visible.top() // 1), int(visible.bottom() // 1) + 1):
            for tile_u in range(int(visible.left() // 1), int(visible.right() // 1) + 1):
                if not (0 <= tile_u < 10 and tile_v >= 0):
                    continue
                corner = self.uv_to_screen(tile_u, tile_v + 1)
                painter.drawText(corner + QtCore.QPointF(6, 14), str(_uv.udim_tile(tile_u, tile_v)))

    def _uv_to_screen_transform(self) -> QtGui.QTransform:
        """The transform from UV space to canvas pixels (V up)."""
        transform = QtGui.QTransform()
        transform.translate(self._origin.x(), self._origin.y())
        transform.scale(self._scale, -self._scale)
        return transform

    def _visible_uv_rect(self) -> QtCore.QRectF:
        """The part of UV space the canvas currently shows."""
        u0, v1 = self.screen_to_uv(QtCore.QPointF(0, 0))
        u1, v0 = self.screen_to_uv(QtCore.QPointF(self.width(), self.height()))
        return QtCore.QRectF(QtCore.QPointF(u0, v0), QtCore.QPointF(u1, v1))


class UvEditorDock(QtWidgets.QDockWidget):
    """A floating dock holding a :class:`UvEditorPanel`.

    :meth:`toggleViewAction` is the checkable action the View menu uses to show and hide it.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__('UV Editor', parent)
        self.setObjectName('UvEditorDock')
        self.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        self._panel = UvEditorPanel(self)
        self.setWidget(self._panel)
        self.setFloating(True)
        self.resize(760, 540)
        self.hide()

    @property
    def panel(self) -> 'UvEditorPanel':
        """The panel inside the dock."""
        return self._panel

    def set_stage(self, stage: Usd.Stage | None) -> None:
        """Point the editor at a newly opened stage."""
        self._panel.set_stage(stage)


class UvEditorPanel(QtWidgets.QWidget):
    """The UV editor: a mesh picker, display toggles, the UV canvas, the UV set list and a status line.

    Nothing is read off the stage until the panel is visible, so keeping it closed costs nothing.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName('UvEditorPanel')
        self.setStyleSheet(_STYLE)
        self._stage: Usd.Stage | None = None
        self._layouts: list[_uv.UvLayout] = []
        self._dirty = False

        self._mesh_combo = QtWidgets.QComboBox()
        self._mesh_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._mesh_combo.setMinimumContentsLength(12)
        self._mesh_combo.currentIndexChanged.connect(self._on_mesh_changed)
        refresh_button = QtWidgets.QPushButton('Refresh')
        refresh_button.setToolTip('Re-read the meshes and UV sets from the stage')
        refresh_button.clicked.connect(self.refresh)

        self._canvas = UvCanvas()
        self._canvas.cursorMoved.connect(self._on_cursor_moved)
        self._canvas.cursorLeft.connect(lambda: self._cursor_label.setText(''))

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(4)
        self._toggles: dict[str, QtWidgets.QToolButton] = {}
        for key, text, tip in (
            ('grid', 'Grid', 'UDIM tile boundaries and a tenths grid when zoomed in'),
            ('checker', 'Checker', 'Checker pattern over the 0-1 tile'),
            ('shaded', 'Shells', 'Tint every UV shell a different colour'),
            ('borders', 'Borders', 'Highlight shell borders'),
            ('flipped', 'Flipped', 'Fill faces whose UV winding is reversed'),
        ):
            button = QtWidgets.QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setChecked(self._canvas.is_shown(key))
            button.toggled.connect(lambda on, k=key: self._canvas.set_shown(k, on))
            self._toggles[key] = button
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        for text, tip, slot in (('Frame', 'Frame all UVs (F)', self._canvas.frame_bounds),
                                ('0-1', 'Frame the 0-1 tile (Home)', self._canvas.frame_tile)):
            button = QtWidgets.QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            toolbar.addWidget(button)

        self._set_list = QtWidgets.QTreeWidget()
        self._set_list.setHeaderLabels(['UV Set', 'Interpolation', 'UVs'])
        self._set_list.setRootIsDecorated(False)
        self._set_list.setUniformRowHeights(True)
        self._set_list.header().setStretchLastSection(False)
        self._set_list.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            self._set_list.header().setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._set_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._set_list.currentItemChanged.connect(self._on_set_changed)

        side = QtWidgets.QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side_label = QtWidgets.QLabel('UV Sets')
        side.addWidget(side_label)
        side.addWidget(self._set_list, 1)
        side_widget = QtWidgets.QWidget()
        side_widget.setLayout(side)
        side_widget.setMinimumWidth(230)

        canvas_column = QtWidgets.QVBoxLayout()
        canvas_column.setContentsMargins(0, 0, 0, 0)
        canvas_column.setSpacing(6)
        canvas_column.addLayout(toolbar)
        canvas_column.addWidget(self._canvas, 1)
        canvas_widget = QtWidgets.QWidget()
        canvas_widget.setLayout(canvas_column)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(canvas_widget)
        splitter.addWidget(side_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([540, 230])
        splitter.setChildrenCollapsible(False)

        self._stats_label = QtWidgets.QLabel('No mesh')
        self._stats_label.setObjectName('UvStats')
        self._cursor_label = QtWidgets.QLabel('')
        self._cursor_label.setObjectName('UvCursor')
        self._cursor_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        status = QtWidgets.QHBoxLayout()
        status.addWidget(self._stats_label, 1)
        status.addWidget(self._cursor_label, 0)

        header = QtWidgets.QHBoxLayout()
        mesh_label = QtWidgets.QLabel('Mesh')
        header.addWidget(mesh_label)
        header.addWidget(self._mesh_combo, 1)
        header.addWidget(refresh_button)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        root.addLayout(header)
        root.addWidget(splitter, 1)
        root.addLayout(status)

    @property
    def canvas(self) -> UvCanvas:
        """The UV canvas."""
        return self._canvas

    def current_set_name(self) -> str | None:
        """The name of the UV set on the canvas, or None."""
        item = self._set_list.currentItem()
        return item.text(0) if item is not None else None

    @property
    def mesh_paths(self) -> list[str]:
        """The prim paths in the mesh picker."""
        return [self._mesh_combo.itemData(i) for i in range(self._mesh_combo.count())]

    def refresh(self) -> None:
        """Re-read the meshes on the stage, keeping the current mesh and UV set when they survive."""
        self._dirty = False
        keep_mesh = self._mesh_combo.currentData()
        keep_set = self.current_set_name()
        self._mesh_combo.blockSignals(True)
        self._mesh_combo.clear()
        for prim in _uv.list_meshes(self._stage):
            self._mesh_combo.addItem(str(prim.GetPath()), str(prim.GetPath()))
        index = self._mesh_combo.findData(keep_mesh) if keep_mesh else -1
        self._mesh_combo.setCurrentIndex(index if index >= 0 else (0 if self._mesh_combo.count() else -1))
        self._mesh_combo.blockSignals(False)
        self._load_mesh(prefer_set=keep_set)

    def set_stage(self, stage: Usd.Stage | None) -> None:
        """Use a newly opened stage; it is read when the panel is (or next becomes) visible."""
        self._stage = stage
        self._mesh_combo.blockSignals(True)
        self._mesh_combo.clear()
        self._mesh_combo.blockSignals(False)
        self._load_mesh()
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def show_prim(self, path: str) -> bool:
        """Show the mesh at `path`; returns False when it is not a mesh on the stage."""
        if self._dirty:
            self.refresh()
        index = self._mesh_combo.findData(str(path))
        if index < 0:
            return False
        self._mesh_combo.setCurrentIndex(index)
        return True

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if self._dirty:
            self.refresh()

    def _load_mesh(self, prefer_set: str | None = None) -> None:
        """Read the UV sets of the picked mesh into the set list and show the preferred (or first)."""
        self._layouts = []
        self._set_list.blockSignals(True)
        self._set_list.clear()
        path = self._mesh_combo.currentData()
        prim = self._stage.GetPrimAtPath(path) if (self._stage is not None and path) else None
        if prim is not None and prim.IsValid():
            self._layouts = _uv.read_uv_layouts(prim)
        items = {}
        for layout in self._layouts:
            item = QtWidgets.QTreeWidgetItem([layout.uv_set.name, layout.uv_set.interpolation,
                                              f'{len(layout.uv_set.values):,}'])
            item.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self._set_list.addTopLevelItem(item)
            items[layout.uv_set.name] = item
        # USD hands primvars back alphabetically, so pick by name: the one asked for, else the
        # conventional 'st', else the first.
        chosen = items.get(prefer_set) or items.get('st') or next(iter(items.values()), None)
        self._set_list.blockSignals(False)
        if chosen is not None:
            self._set_list.setCurrentItem(chosen)  # emits currentItemChanged -> _on_set_changed
        else:
            self._show_layout(None, 'No mesh' if not path else 'No UV sets on this mesh')

    def _on_cursor_moved(self, u: float, v: float) -> None:
        self._cursor_label.setText(f'U {u:8.4f}   V {v:8.4f}   {_uv.udim_tile(u, v)}')

    def _on_mesh_changed(self, _index: int) -> None:
        self._load_mesh(prefer_set=self.current_set_name())

    def _on_set_changed(self, current: QtWidgets.QTreeWidgetItem | None, _previous) -> None:
        if current is None:
            return
        index = self._set_list.indexOfTopLevelItem(current)
        if 0 <= index < len(self._layouts):
            self._show_layout(self._layouts[index])

    def _show_layout(self, layout: '_uv.UvLayout | None', message: str = '') -> None:
        """Put `layout` on the canvas and summarise it in the status line."""
        self._canvas.set_layout(layout)
        if layout is None:
            self._stats_label.setText(message)
            return
        stats = layout.stats()
        parts = [f'{stats.face_count:,} faces', f'{stats.island_count:,} shells']
        if stats.flipped_count:
            parts.append(f'{stats.flipped_count:,} flipped')
        if stats.degenerate_count:
            parts.append(f'{stats.degenerate_count:,} degenerate')
        parts.append('tiles ' + ', '.join(str(t) for t in stats.tiles[:4]) + (' ...' if len(stats.tiles) > 4 else ''))
        parts.append(f'{stats.coverage * 100:.1f}% of 0-1 used')
        if not self._canvas.shading_available():
            parts.append('shell tint off (large mesh)')
        self._stats_label.setText('  ·  '.join(parts))


def _shell_color(index: int) -> QtGui.QColor:
    """A soft, stable tint for shell `index`; golden-ratio hue steps keep neighbours distinct."""
    r, g, b = colorsys.hsv_to_rgb((index * 0.61803398875) % 1.0, 0.45, 0.85)
    return QtGui.QColor(int(r * 255), int(g * 255), int(b * 255), 55)

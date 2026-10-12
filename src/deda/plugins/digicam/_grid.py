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
"""Reusable photo thumbnail grid widgets for the digicam plugin."""
__all__ = ['PhotoGrid', 'PhotoTile']

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ._metadata import load_thumbnail


class PhotoTile(QtWidgets.QFrame):
    """A single photo thumbnail tile: image, filename, optional caption lines, optional checkbox-like selection."""

    activated = QtCore.Signal(Path)
    toggled = QtCore.Signal(Path, bool)
    context_menu_requested = QtCore.Signal(Path, QtCore.QPoint)

    _NORMAL_STYLE = 'background-color: rgb(30,30,30); border: 1px solid rgb(50,50,50); border-radius: 3px;'
    _SELECTED_STYLE = 'background-color: rgb(30,30,30); border: 2px solid rgb(80,160,220); border-radius: 3px;'

    def __init__(self, path: Path, tile_size=160, checkable=False, caption_lines=None, parent=None):
        super().__init__(parent=parent)
        self._path = path
        self._checkable = checkable
        self._checked = False
        self.setFixedWidth(tile_size)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setObjectName('PhotoTile')
        self.setStyleSheet(f'#PhotoTile{{{self._NORMAL_STYLE}}}')

        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)

        thumb_size = tile_size - 8
        thumb_label = QtWidgets.QLabel()
        thumb_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        thumb_label.setFixedSize(thumb_size, thumb_size)
        pixmap = load_thumbnail(path, max_size=thumb_size)
        if not pixmap.isNull():
            thumb_label.setPixmap(pixmap)
        else:
            thumb_label.setText('?')
        vbox.addWidget(thumb_label)

        name_label = QtWidgets.QLabel(path.name)
        name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_font = name_label.font()
        name_font.setPointSize(8)
        name_label.setFont(name_font)
        vbox.addWidget(name_label)

        for line in (caption_lines or []):
            caption_label = QtWidgets.QLabel(line)
            caption_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            caption_label.setWordWrap(True)
            caption_font = caption_label.font()
            caption_font.setPointSize(7)
            caption_label.setFont(caption_font)
            caption_label.setStyleSheet('color: rgb(160,160,160);')
            vbox.addWidget(caption_label)

        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.context_menu_requested.emit(self._path, self.mapToGlobal(pos))
        )

    @property
    def path(self) -> Path:
        return self._path

    def set_checked(self, checked: bool) -> None:
        self._checked = bool(checked)
        self.setStyleSheet(f'#PhotoTile{{{self._SELECTED_STYLE if self._checked else self._NORMAL_STYLE}}}')

    def mousePressEvent(self, event):
        if self._checkable and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.set_checked(not self._checked)
            self.toggled.emit(self._path, self._checked)
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.activated.emit(self._path)
        super().mouseDoubleClickEvent(event)


class PhotoGrid(QtWidgets.QScrollArea):
    """Scrollable, responsive grid of PhotoTile widgets that reflows on resize without reloading thumbnails."""

    tile_activated = QtCore.Signal(Path)
    tile_toggled = QtCore.Signal(Path, bool)
    tile_context_menu_requested = QtCore.Signal(Path, QtCore.QPoint)

    def __init__(self, tile_size=160, checkable=False, caption_fn=None, parent=None):
        super().__init__(parent=parent)
        self.setWidgetResizable(True)
        self._tile_size = tile_size
        self._checkable = checkable
        self._caption_fn = caption_fn
        self._paths: list[Path] = []
        self._tiles: list[PhotoTile] = []

        container = QtWidgets.QWidget()
        self._layout = QtWidgets.QGridLayout(container)
        self._layout.setSpacing(8)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.setWidget(container)
        self._container = container

    @property
    def paths(self) -> list[Path]:
        return list(self._paths)

    def set_paths(self, paths) -> None:
        """Replace the grid contents with tiles for the given list of Path objects."""
        for tile in self._tiles:
            tile.deleteLater()
        self._tiles = []
        self._paths = list(paths)
        for path in self._paths:
            caption_lines = self._caption_fn(path) if self._caption_fn else None
            tile = PhotoTile(
                path, tile_size=self._tile_size, checkable=self._checkable,
                caption_lines=caption_lines, parent=self._container,
            )
            tile.activated.connect(self.tile_activated.emit)
            tile.toggled.connect(self.tile_toggled.emit)
            tile.context_menu_requested.connect(self.tile_context_menu_requested.emit)
            self._tiles.append(tile)
        self._relayout()

    def clear_checked(self) -> None:
        """Reset the checked visual state of every tile without reloading them."""
        for tile in self._tiles:
            tile.set_checked(False)

    def _relayout(self) -> None:
        while self._layout.count():
            self._layout.takeAt(0)
        columns = max(1, self.viewport().width() // (self._tile_size + self._layout.spacing()))
        for index, tile in enumerate(self._tiles):
            row, col = divmod(index, columns)
            self._layout.addWidget(tile, row, col)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._relayout)

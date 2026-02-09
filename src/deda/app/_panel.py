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
"""
Panel-related widget classes: ItemTile, PanelHeader, and Panel.
"""

__all__ = ["ItemTile", "PanelHeader", "Panel"]

import html
import json
from pathlib import Path

from PySide6 import QtWidgets, QtCore, QtGui

from ._dialogs import AddItemDialog, ConfigureItemDialog

# MIME type for asset drag-and-drop from Assets panel to Apps/Services panels
ASSET_MIME_TYPE = "application/x-dedaverse-asset"


class ItemTile(QtWidgets.QFrame):
    """Tile widget for displaying an item with icon, name, and tooltip."""

    activated = QtCore.Signal(object)  # Emits item_data on double-click
    asset_dropped = QtCore.Signal(object, object)  # (asset_data, this_tile_item_data) when asset dropped on this tile

    def __init__(self, item_data, tile_width, parent=None, draggable=False, accept_asset_drop=False):
        super().__init__(parent=parent)
        self._item_data = item_data
        self._draggable = bool(draggable)
        self._accept_asset_drop = bool(accept_asset_drop)
        self._drag_start_pos = None
        self.setFixedSize(tile_width, tile_width)
        self.setObjectName("ItemTile")
        if accept_asset_drop:
            self.setAcceptDrops(True)
        # Set NoFrame so stylesheet border is used instead of QFrame's built-in frame
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._normal_border = "rgb(50,50,50)"
        self._hover_border = "rgb(80,80,80)"  # Lighter gray for hover
        # Use ID selector for reliable stylesheet application
        self.setStyleSheet(
            f"#ItemTile{{background-color: rgb(30,30,30); border: 1px solid {self._normal_border}; border-radius: 3px;}}"
        )
        self.setMouseTracking(True)
        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(2)

        icon_path = item_data.get('icon', None)
        if icon_path and Path(icon_path).is_file():
            pixmap = QtGui.QPixmap(icon_path)
        else:
            icon_path = Path(__file__).parent / 'icons' / 'questionmark_small.png'
            pixmap = QtGui.QPixmap(str(icon_path))
        icon_size = tile_width - 20
        pixmap = pixmap.scaled(
            icon_size, icon_size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(icon_label)

        if draggable:
            drag_size = 48
            self._drag_pixmap = pixmap.scaled(
                drag_size, drag_size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
        else:
            self._drag_pixmap = None

        name = item_data.get('name', 'Untitled')
        name_label = QtWidgets.QLabel(name)
        name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        font = name_label.font()
        font.setPointSize(max(8, tile_width // 20))
        name_label.setFont(font)
        name_label.setWordWrap(True)
        vbox.addWidget(name_label)

        description = item_data.get('description', '')
        title = item_data.get('title', '')
        item_type = item_data.get('type', '')
        tooltip = f'<b>{html.escape(name)}</b>'
        if title and title != name:
            tooltip += f'<br><i>{html.escape(title)}</i>'
        if item_type:
            tooltip += f'<br><i>Type: {html.escape(item_type)}</i>'
        if description:
            tooltip += f'<br>{html.escape(description)}'
        self.setToolTip(tooltip)

    def enterEvent(self, event):
        """Change border color to lighter gray when mouse enters the tile."""
        super().enterEvent(event)
        self.setStyleSheet(
            f"#ItemTile{{background-color: rgb(30,30,30); border: 1px solid {self._hover_border}; border-radius: 3px;}}"
        )

    def leaveEvent(self, event):
        """Restore normal border color when mouse leaves the tile."""
        super().leaveEvent(event)
        self.setStyleSheet(
            f"#ItemTile{{background-color: rgb(30,30,30); border: 1px solid {self._normal_border}; border-radius: 3px;}}"
        )

    def mousePressEvent(self, event):
        """Record start position for drag when draggable."""
        if self._draggable and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Start drag with asset data and icon pixmap when drag threshold exceeded."""
        if not self._draggable or self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if not (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        delta = event.position().toPoint() - self._drag_start_pos
        if delta.manhattanLength() < QtWidgets.QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._drag_start_pos = None
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setData(ASSET_MIME_TYPE, QtCore.QByteArray(json.dumps(self._item_data).encode('utf-8')))
        drag.setMimeData(mime)
        if self._drag_pixmap:
            drag.setPixmap(self._drag_pixmap)
            drag.setHotSpot(QtCore.QPoint(self._drag_pixmap.width() // 2, self._drag_pixmap.height() // 2))
        drag.exec(QtCore.Qt.DropAction.CopyAction)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Clear drag start position."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        """Accept drag if it carries asset data."""
        if self._accept_asset_drop and event.mimeData().hasFormat(ASSET_MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Accept drag move if it carries asset data."""
        if self._accept_asset_drop and event.mimeData().hasFormat(ASSET_MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """Emit asset_dropped with decoded asset data and this tile's item data."""
        if not self._accept_asset_drop or not event.mimeData().hasFormat(ASSET_MIME_TYPE):
            super().dropEvent(event)
            return
        try:
            raw = bytes(event.mimeData().data(ASSET_MIME_TYPE))
            asset_data = json.loads(raw.decode('utf-8'))
            event.acceptProposedAction()
            self.asset_dropped.emit(asset_data, self._item_data)
        except (json.JSONDecodeError, TypeError):
            pass
        super().dropEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Emit activated with item data on double-click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.activated.emit(self._item_data)
        super().mouseDoubleClickEvent(event)


class PanelHeader(QtWidgets.QWidget):
    
    gear_icon = None
    close_icon = None
    
    minmax_clicked = QtCore.Signal(bool)  # True when minimized, False when maximized
    navigate_up_clicked = QtCore.Signal()
    close_clicked = QtCore.Signal()
    settings_clicked = QtCore.Signal()

    def __init__(self, title,
                 icon=None,
                 show_minmax=True,
                 minimized=False,
                 show_close=True,
                 show_navigate_up=False,
                 settings_callback=None,
                 close_callback=None,
                 parent=None):
        super().__init__(parent=parent)

        self._minimized = bool(minimized)
        self._settings_callback = settings_callback
        self._close_callback = close_callback

        hbox = QtWidgets.QHBoxLayout()
        self.setLayout(hbox)
        hbox.setContentsMargins(0, 0, 0, 0)

        font = QtGui.QFont()
        font.setPointSize(10)
        metrics = QtGui.QFontMetrics(font)

        self._navigate_up_btn = QtWidgets.QPushButton('\u2191')  # Upward arrow
        self._navigate_up_btn.setToolTip('Go up')
        self._navigate_up_btn.setFlat(True)
        self._navigate_up_btn.setFixedSize(metrics.height(), metrics.height())
        self._navigate_up_btn.clicked.connect(self.navigate_up_clicked.emit)
        self._navigate_up_btn.setVisible(bool(show_navigate_up))
        hbox.addWidget(self._navigate_up_btn)

        self._title_label = QtWidgets.QLabel(title)
        self._title_label.setFont(font)

        if icon:
            icon = QtGui.QPixmap(icon).scaled(metrics.height(), metrics.height())
            img = QtWidgets.QLabel()
            img.setPixmap(icon)
            img.setFixedSize(metrics.height(), metrics.height())
            hbox.addWidget(img)

        hbox.addWidget(self._title_label)

        hbox.addStretch()
        
        if not PanelHeader.gear_icon:
            icon_path = Path(__file__).parent / 'icons' / 'gear_icon_32.png'
            PanelHeader.gear_icon = QtGui.QIcon(str(icon_path))
        gear_btn = QtWidgets.QPushButton(PanelHeader.gear_icon, '')
        gear_btn.setToolTip('Settings')
        gear_btn.setFlat(True)
        gear_btn.setFixedSize(metrics.height(), metrics.height())
        hbox.addWidget(gear_btn)
        gear_btn.clicked.connect(self._on_settings_clicked)
        
        if show_minmax:
            self._minmax_btn = QtWidgets.QPushButton('\u25a1' if self._minimized else '\u25a0')  # □ expand / ■ collapse
            self._minmax_btn.setFlat(True)
            self._minmax_btn.setFixedSize(metrics.height(), metrics.height())
            hbox.addWidget(self._minmax_btn)
            self._minmax_btn.clicked.connect(self._minmax_clicked)
            
        if show_close:
            close_btn = QtWidgets.QPushButton('X')
            close_btn.setFlat(True)
            close_btn.setFixedSize(metrics.height(), metrics.height())
            hbox.addWidget(close_btn)
            close_btn.clicked.connect(self.close_clicked.emit)

        self.setFixedHeight(metrics.height())

    @property
    def minimized(self):
        return self._minimized

    def set_show_navigate_up(self, visible: bool) -> None:
        """Show or hide the navigate-up (go up in hierarchy) button."""
        self._navigate_up_btn.setVisible(bool(visible))

    def set_title(self, title: str) -> None:
        """Update the header title text."""
        self._title_label.setText(title)

    def _minmax_clicked(self):
        self._minimized = not self._minimized
        if self._minimized:
            self._minmax_btn.setText('\u25a1')  # □
        else:
            self._minmax_btn.setText('\u25a0')  # ■
        self.minmax_clicked.emit(self._minimized) 
        
    def _on_settings_clicked(self):
        self.settings_clicked.emit()
        if self._settings_callback:
            self._settings_callback()        
        

class Panel(QtWidgets.QFrame):
    """Base class for all panel types."""

    close_clicked = QtCore.Signal()
    add_item = QtCore.Signal(str)
    item_created = QtCore.Signal(object)
    item_updated = QtCore.Signal(int, object)  # item_index, updated_item_data
    item_activated = QtCore.Signal(object)  # item_data when tile is double-clicked
    item_removed = QtCore.Signal(object)  # item_data when item is removed
    minimized_changed = QtCore.Signal(str, bool)
    navigate_up_clicked = QtCore.Signal()
    asset_dropped_on_tile = QtCore.Signal(object, object)  # (asset_data, target_tile_item_data)
    file_dropped = QtCore.Signal(object)  # list of file path strings from external drag (e.g. file manager)

    def __init__(self, type_name, name,
                 view=None,  # instance of the view to put into the panel
                 show_scroll_area=True,
                 show_navigate_up=False,
                 parent=None, **kwargs):
        super().__init__(parent=parent)

        self._visibility = True
        self.setObjectName(type_name)
        self._type_name = type_name
        if type_name.endswith('s'):
            self._type_name = type_name[:-1]

        self.setStyleSheet("Panel{background-color: rgb(20,20,20); border: 1px solid rgb(40,40,40); border-radius: 5px;}")

        self._scroll_area = None

        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        header = PanelHeader(name, parent=self, show_navigate_up=show_navigate_up, **kwargs)
        self._header = header
        vbox.addWidget(header)
        header.close_clicked.connect(self.close)
        header.navigate_up_clicked.connect(self.navigate_up_clicked.emit)
        
        if show_scroll_area:
            self._scroll_area = QtWidgets.QScrollArea()
            self._scroll_area.setWidgetResizable(True)
            self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            container = QtWidgets.QWidget()
            container_layout = QtWidgets.QGridLayout(container)
            container_layout.setSpacing(8)
            container_layout.setContentsMargins(8, 8, 8, 8)
            container_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
            self._tiles_container = container
            self._tiles_layout = container_layout
            self._tiles_count = 0
            self._tiles_per_row = 5
            container.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Minimum
            )
            self._scroll_area.setWidget(container)

            vbox.addWidget(self._scroll_area)
            # Bind to this panel only so the expand/collapse button only affects this panel
            header.minmax_clicked.connect(lambda minimized, p=self: p._on_minimized(minimized))
            self._on_minimized(header.minimized)

            # Context menu on scroll area so it is always triggered when right-clicking in panel
            self._scroll_area.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self._scroll_area.customContextMenuRequested.connect(self._show_context_menu)
            self._items = []

            if type_name == 'Assets':
                self._scroll_area.viewport().setAcceptDrops(True)
                self._scroll_area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle file drops on Assets panel scroll viewport."""
        if (
            self.objectName() == 'Assets'
            and self._scroll_area
            and obj is self._scroll_area.viewport()
        ):
            t = event.type()
            if t == QtCore.QEvent.Type.DragEnter:
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                return False
            if t == QtCore.QEvent.Type.DragMove:
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                return False
            if t == QtCore.QEvent.Type.Drop:
                if event.mimeData().hasUrls():
                    paths = []
                    for url in event.mimeData().urls():
                        if url.isLocalFile():
                            p = Path(url.toLocalFile())
                            if p.is_file():
                                paths.append(str(p.resolve()))
                    if paths:
                        self.file_dropped.emit(paths)
                    event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)

    @property
    def visibility(self):
        return self._visibility
    
    @visibility.setter
    def visibility(self, value: bool):
        self._visibility = bool(value)
        self.setVisible(self._visibility)

    def set_show_navigate_up(self, visible: bool) -> None:
        """Show or hide the navigate-up button in the header."""
        if self._header:
            self._header.set_show_navigate_up(visible)

    def set_title(self, title: str) -> None:
        """Update the panel header title."""
        if self._header:
            self._header.set_title(title)

    @property
    def minimized(self) -> bool:
        """True if the panel content is collapsed (only header visible)."""
        return self._header.minimized if self._header else False

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.objectName()}>'
        
    def close(self):        
        super().close() 
        self.close_clicked.emit()
        
    def _add_item(self):
        self.add_item.emit(self._type_name)
        dlg = AddItemDialog(self._type_name, parent=self._scroll_area)
        dlg.item_created.connect(self.item_created.emit) # propogate signal
        if self._scroll_area:
            rect = self._scroll_area.geometry()
            dlg_rect = dlg.geometry()
            pt = QtCore.QPoint((rect.width()/2) - (dlg_rect.width()/2),
                               (rect.height()/2) - (dlg_rect.height()/2))
            dlg.move(self._scroll_area.mapToGlobal(pt))
        dlg.exec()
               
    def _on_minimized(self, minimized):
        """Show or hide this panel's content only; does not affect other panels."""
        if self._scroll_area is not None:
            self._scroll_area.setVisible(not minimized)
        self.minimized_changed.emit(self.objectName(), minimized)

    def _update_tile_size(self):
        """Update tile size based on scroll area width (1/5 when vertical scrollbar present)."""
        if not self._scroll_area or not self._tiles_container:
            return
        scroll_width = self._scroll_area.viewport().width()
        if scroll_width <= 0:
            return
        # When vertical scrollbar is present, use 1/5 width for tiles
        # Account for margins (8px each side = 16px) and spacing between tiles
        available_width = scroll_width - 16
        # Use 5 tiles per row (1/5 width each) when vertical scrollbar present
        self._tiles_per_row = 5
        spacing = 8
        tile_width = max(80, (available_width - (self._tiles_per_row - 1) * spacing) // self._tiles_per_row)
        # Update existing tiles
        for i in range(self._tiles_layout.count()):
            item = self._tiles_layout.itemAt(i)
            if item and item.widget():
                item.widget().setFixedSize(tile_width, tile_width)
        # Relayout tiles
        self._relayout_tiles()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._update_tile_size)

    def _relayout_tiles(self):
        """Relayout all tiles in the grid."""
        if not self._tiles_container:
            return
        # Remove all widgets from layout
        while self._tiles_layout.count():
            item = self._tiles_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        # Re-add widgets in grid
        scroll_width = self._scroll_area.viewport().width() if self._scroll_area else 400
        available_width = scroll_width - 16
        spacing = 8
        tile_width = max(80, (available_width - (self._tiles_per_row - 1) * spacing) // self._tiles_per_row)
        is_assets = self.objectName() == 'Assets'
        is_apps_or_services = self.objectName() in ('Apps', 'Services')
        for idx, item_data in enumerate(self._items):
            row = idx // self._tiles_per_row
            col = idx % self._tiles_per_row
            tile = ItemTile(
                item_data,
                tile_width,
                parent=self._tiles_container,
                draggable=is_assets,
                accept_asset_drop=is_apps_or_services,
            )
            tile._item_index = idx  # used by context menu to find item
            tile.activated.connect(self.item_activated.emit)
            if is_apps_or_services:
                tile.asset_dropped.connect(self.asset_dropped_on_tile.emit)
            self._tiles_layout.addWidget(
                tile, row, col,
                alignment=QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft
            )

    def add_item_tile(self, item_data):
        """Add a tile widget for the given item data."""
        if not self._tiles_container:
            return
        self._items.append(item_data)
        self._update_tile_size()
        
    def _tile_at_position(self, position):
        """Return the ItemTile under the given position. Position is in scroll area viewport coordinates."""
        # customContextMenuRequested provides coordinates relative to the viewport
        # Find the widget at this position by using childAt on the viewport
        viewport = self._scroll_area.viewport()
        w = viewport.childAt(position)
        # Walk up the parent chain to find an ItemTile
        while w is not None:
            if isinstance(w, ItemTile):
                return w
            w = w.parentWidget()
        return None

    def _show_context_menu(self, position):
        """Build and show the panel context menu. Position is in scroll area viewport coordinates."""
        menu = QtWidgets.QMenu(parent=self)

        tile = self._tile_at_position(position)
        if tile is not None and hasattr(tile, '_item_index'):
            idx = tile._item_index
            if 0 <= idx < len(self._items):
                item_data = self._items[idx]
                is_writable = item_data.get('is_writable', True)  # Default True for non-app items
                is_apps_or_services = self.objectName() in ('Apps', 'Services')
                # Configure: always show for Apps/Services; otherwise only when writable
                show_configure = is_apps_or_services and is_writable
                if show_configure:
                    config_icon_path = Path(__file__).parent / 'icons' / 'gear_icon_32.png'
                    config_icon = QtGui.QIcon(str(config_icon_path)) if config_icon_path.is_file() else QtGui.QIcon()
                    menu.addAction(config_icon, 'Configure...').triggered.connect(
                        lambda checked=False, i=idx: self._open_configure_dialog(i)
                    )
                if is_writable:
                    remove_action = menu.addAction('Remove')
                    remove_action.triggered.connect(lambda checked=False, i=idx: self._remove_item_at(i))
                if show_configure or is_writable:
                    menu.addSeparator()

        icon_path = Path(__file__).parent / 'icons' / 'green_plus.png'
        plus_icon = QtGui.QIcon(str(icon_path))
        menu.addAction(plus_icon, f'Add {self._type_name}').triggered.connect(self._add_item)

        # Convert viewport coordinates to global coordinates for menu.exec()
        viewport = self._scroll_area.viewport()
        global_pos = viewport.mapToGlobal(position)
        menu.exec(global_pos)

    def _remove_item_at(self, item_index):
        """Remove the item at the given index and refresh the tile layout."""
        if 0 <= item_index < len(self._items):
            item_data = self._items.pop(item_index)
            self._relayout_tiles()
            # Emit signal so parent can remove from config if needed
            self.item_removed.emit(item_data)

    def _open_configure_dialog(self, item_index):
        """Open the configuration dialog for the item at the given index."""
        if item_index < 0 or item_index >= len(self._items):
            return
        item_data = self._items[item_index]
        dlg = ConfigureItemDialog(
            self._type_name.capitalize(),
            item_data,
            item_index,
            parent=self._scroll_area
        )
        dlg.item_updated.connect(self._on_item_configured)
        if self._scroll_area:
            rect = self._scroll_area.geometry()
            dlg_rect = dlg.geometry()
            pt = QtCore.QPoint(
                (rect.width() / 2) - (dlg_rect.width() / 2),
                (rect.height() / 2) - (dlg_rect.height() / 2)
            )
            dlg.move(self._scroll_area.mapToGlobal(pt))
        dlg.exec()

    def _on_item_configured(self, item_index, updated_data):
        """Update the item at the given index and refresh the tile layout."""
        if 0 <= item_index < len(self._items):
            self._items[item_index] = updated_data
            self._relayout_tiles()
            # Emit signal so parent can update config if needed
            self.item_updated.emit(item_index, updated_data)

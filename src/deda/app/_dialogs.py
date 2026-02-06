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
Graphics views for panels and browsers.
"""

__all__ = ["AddItemDialog", "ConfigureItemDialog"]

import os
from pathlib import Path

from PySide6 import QtWidgets, QtGui, QtCore

from ..core import _types


class ClickableLabel(QtWidgets.QLabel):
    """
    A custom QLabel that emits a 'clicked' signal when pressed.
    """
    clicked = QtCore.Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMouseTracking(True) # Optional: enable mouse tracking for hover effects

    def mousePressEvent(self, event):
        """
        Overrides the mousePressEvent to emit a custom 'clicked' signal.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event) # Call the base class method


class AddItemDialog(QtWidgets.QDialog):
    """Add an item of a certain type to the project library."""
    
    item_created = QtCore.Signal(object)
    
    def __init__(self, type_name, parent=None):
        super().__init__(parent=parent)
        
        self.setWindowTitle(f'Add {type_name}')
        icon_path = Path(__file__).parent / 'icons' / 'green_plus.png'
        plus_icon = QtGui.QIcon(str(icon_path))   
        self.setWindowIcon(plus_icon)
        
        self._type_name = type_name
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        grid = QtWidgets.QGridLayout()
        vbox.addLayout(grid)
                
        # default icon for type
        icon_path = Path(__file__).parent / 'icons' / 'questionmark_small.png'
        questionmark_icon = QtGui.QPixmap(str(icon_path))          
        # customization of icon allows drag and drop, resize and store icon on drop
        self._icon_lbl = ClickableLabel()
        self._icon_lbl.setPixmap(questionmark_icon)
        self._selected_icon_path = None
        grid.addWidget(self._icon_lbl, 0, 0, 2, 1)
        self._icon_lbl.clicked.connect(self._open_icon_browser)
                
        # editable name field, default is "untitled" 
        lbl = QtWidgets.QLabel('Name:')
        grid.addWidget(lbl, 0, 2)
        self._name_le = QtWidgets.QLineEdit()
        grid.addWidget(self._name_le, 0, 3)
        self._name_le.textEdited.connect(self._name_changed)
        
        # subtype for types
        lbl = QtWidgets.QLabel('Type:')
        grid.addWidget(lbl, 1, 2)
        self._types_cb = QtWidgets.QComboBox()
        items = []
        if type_name == 'Asset':
            items = _types.all_default_asset_types()
        elif type_name == 'App':
            items = ['Command', 'Python']
        elif type_name == 'Service':
            items = ['REST']  # Services are REST-based
        elif type_name == 'Task':
            items = ['Work', 'Review', 'Notify']        
        self._types_cb.addItems(items)

        # Restore last selected type from settings
        self._settings = QtCore.QSettings('DedaFX', 'Dedaverse')
        last_type = self._settings.value(f'AddItemDialog/{type_name}/lastType', '', type=str)
        idx = self._types_cb.findText(last_type)
        if idx >= 0:
            self._types_cb.setCurrentIndex(idx)
        self._types_cb.currentTextChanged.connect(self._on_type_changed)

        if type_name == 'App':
            grid.addWidget(self._types_cb, 1, 3)
            
            lbl = QtWidgets.QLabel('Command:')
            grid.addWidget(lbl, 2, 2)
            self._command_le = QtWidgets.QLineEdit()
            grid.addWidget(self._command_le, 2, 3, -1, 1)
            #self._command_le.textEdited.connect(self._name_changed)
        elif type_name == 'Service':
            grid.addWidget(self._types_cb, 1, 3)
            
            lbl = QtWidgets.QLabel('URL:')
            grid.addWidget(lbl, 2, 2)
            self._url_le = QtWidgets.QLineEdit()
            grid.addWidget(self._url_le, 2, 3, -1, 1)
        else:
            grid.addWidget(self._types_cb, 1, 3, -1, 1)            
        
        # buttons to create or cancel
        self._btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel,
                                          parent=self)
        vbox.addWidget(self._btns)
        self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
        
        self._btns.accepted.connect(self._create_item)
        self._btns.rejected.connect(self.close)
        
    def _on_type_changed(self, text: str) -> None:
        """Persist the selected type for this dialog category."""
        self._settings.setValue(f'AddItemDialog/{self._type_name}/lastType', text)

    def _create_item(self):
        item = {
            'name': self._name_le.text().strip(),
            'type': self._types_cb.currentText(),
            'description': '',  # Can be extended later
        }
        if self._type_name == 'App':
            item['command'] = self._command_le.text()
        elif self._type_name == 'Service':
            item['url'] = self._url_le.text().strip()
            item['params'] = []  # Parameters can be added later via configure dialog
        # Store the icon path if a custom icon was selected
        if self._selected_icon_path:
            item['icon'] = self._selected_icon_path
        self.item_created.emit(item)
        self.close()
        
    def _open_icon_browser(self):
        """Open file dialog to select an icon image."""
        start_dir = str(Path.home())
        if self._selected_icon_path:
            start_dir = str(Path(self._selected_icon_path).parent)
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Select Icon Image',
            start_dir,
            'Image Files (*.png *.jpg *.jpeg *.bmp *.ico);;All Files (*)'
        )
        if file_path and Path(file_path).is_file():
            self._selected_icon_path = file_path
            pixmap = QtGui.QPixmap(file_path)
            if not pixmap.isNull():
                self._icon_lbl.setPixmap(pixmap.scaled(
                    64, 64,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                ))
        
    def _name_changed(self, value):
        if not value.strip():
            self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
        else:
            self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(True)


class ConfigureItemDialog(QtWidgets.QDialog):
    """Edit an existing panel item: icon, name, title, description; for apps, command too."""

    item_updated = QtCore.Signal(int, object)  # item_index, updated item dict

    def __init__(self, type_name, item_data, item_index, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(f'Configure {type_name}')
        icon_path = Path(__file__).parent / 'icons' / 'gear_icon_32.png'
        if icon_path.is_file():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        self._type_name = type_name
        self._item_data = dict(item_data)
        self._item_index = item_index

        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        grid = QtWidgets.QGridLayout()
        vbox.addLayout(grid)

        # Icon (clickable to browse)
        default_icon = Path(__file__).parent / 'icons' / 'questionmark_small.png'
        self._selected_icon_path = self._item_data.get('icon') or None
        if self._selected_icon_path and not Path(self._selected_icon_path).is_file():
            self._selected_icon_path = None
        pix_path = self._selected_icon_path or str(default_icon)
        pixmap = QtGui.QPixmap(pix_path)
        if pixmap.isNull():
            pixmap = QtGui.QPixmap(str(default_icon))
        self._icon_lbl = ClickableLabel()
        self._icon_lbl.setPixmap(pixmap.scaled(
            64, 64,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        ))
        self._icon_lbl.clicked.connect(self._open_icon_browser)
        grid.addWidget(self._icon_lbl, 0, 0, 3, 1)

        # Name
        grid.addWidget(QtWidgets.QLabel('Name:'), 0, 1)
        self._name_le = QtWidgets.QLineEdit()
        self._name_le.setText(self._item_data.get('name', 'Untitled'))
        grid.addWidget(self._name_le, 0, 2)

        # Title
        grid.addWidget(QtWidgets.QLabel('Title:'), 1, 1)
        self._title_le = QtWidgets.QLineEdit()
        self._title_le.setText(self._item_data.get('title', self._item_data.get('name', '')))
        self._title_le.setPlaceholderText('Optional display title')
        grid.addWidget(self._title_le, 1, 2)

        # Description
        grid.addWidget(QtWidgets.QLabel('Description:'), 2, 1)
        self._desc_le = QtWidgets.QLineEdit()
        self._desc_le.setText(self._item_data.get('description', ''))
        self._desc_le.setPlaceholderText('Optional description')
        grid.addWidget(self._desc_le, 2, 2)

        # Command (Apps only) or URL (Services only)
        if type_name == 'App':
            grid.addWidget(QtWidgets.QLabel('Command:'), 3, 1)
            self._command_le = QtWidgets.QLineEdit()
            self._command_le.setText(self._item_data.get('command', ''))
            grid.addWidget(self._command_le, 3, 2)
            self._url_le = None
        elif type_name == 'Service':
            grid.addWidget(QtWidgets.QLabel('URL:'), 3, 1)
            self._url_le = QtWidgets.QLineEdit()
            self._url_le.setText(self._item_data.get('url', ''))
            grid.addWidget(self._url_le, 3, 2)
            self._command_le = None
        else:
            self._command_le = None
            self._url_le = None

        self._btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel,
            parent=self
        )
        vbox.addWidget(self._btns)
        self._btns.accepted.connect(self._save)
        self._btns.rejected.connect(self.close)

    def _open_icon_browser(self):
        start_dir = str(Path.home())
        if self._selected_icon_path:
            start_dir = str(Path(self._selected_icon_path).parent)
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Select Icon Image',
            start_dir,
            'Image Files (*.png *.jpg *.jpeg *.bmp *.ico);;All Files (*)'
        )
        if file_path and Path(file_path).is_file():
            self._selected_icon_path = file_path
            pixmap = QtGui.QPixmap(file_path)
            if not pixmap.isNull():
                self._icon_lbl.setPixmap(pixmap.scaled(
                    64, 64,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                ))

    def _save(self):
        name = self._name_le.text().strip() or 'Untitled'
        updated = {
            'name': name,
            'type': self._item_data.get('type', ''),
            'title': self._title_le.text().strip() or name,
            'description': self._desc_le.text().strip(),
        }
        if self._selected_icon_path:
            updated['icon'] = self._selected_icon_path
        if self._type_name == 'App' and self._command_le is not None:
            updated['command'] = self._command_le.text()
        elif self._type_name == 'Service' and self._url_le is not None:
            updated['url'] = self._url_le.text().strip()
            updated['params'] = self._item_data.get('params', [])  # Preserve existing params
        self.item_updated.emit(self._item_index, updated)
        self.close()


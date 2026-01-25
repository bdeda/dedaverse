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

__all__ = ["AddItemDialog"]

import os

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
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'green_plus.png')
        plus_icon = QtGui.QIcon(icon_path)   
        self.setWindowIcon(plus_icon)
        
        self._type_name = type_name
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        grid = QtWidgets.QGridLayout()
        vbox.addLayout(grid)
                
        # default icon for type
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'questionmark_small.png')
        questionmark_icon = QtGui.QPixmap(icon_path)          
        # customization of icon allows drag and drop, resize and store icon on drop
        self._icon_lbl = ClickableLabel()
        self._icon_lbl.setPixmap(questionmark_icon)
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
        elif type_name == 'Task':
            items = ['Work', 'Review', 'Notify']        
        self._types_cb.addItems(items)
        if type_name != 'App':
            grid.addWidget(self._types_cb, 1, 3, -1, 1)        
        else:
            grid.addWidget(self._types_cb, 1, 3)
            
            lbl = QtWidgets.QLabel('Command:')
            grid.addWidget(lbl, 2, 2)
            self._command_le = QtWidgets.QLineEdit()
            grid.addWidget(self._command_le, 2, 3, -1, 1)
            #self._command_le.textEdited.connect(self._name_changed)            
        
        # buttons to create or cancel
        self._btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel,
                                          parent=self)
        vbox.addWidget(self._btns)
        self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
        
        self._btns.accepted.connect(self._create_item)
        self._btns.rejected.connect(self.close)
        
    def _create_item(self):
        item = {
            'name': self._name_le.text().strip(),
            'type': self._types_cb.currentText(),
        }
        if self._type_name == 'App':
            item['command'] = self._command_le.text()
        self.item_created.emit(item)
        self.close()
        
    def _open_icon_browser(self):
        print('Icon clicked')
        
    def _name_changed(self, value):
        if not value.strip():
            self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
        else:
            self._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(True)
            
        
        
    
    

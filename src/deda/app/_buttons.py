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
__all__ = ['AddButton']

import os

from PySide6 import QtWidgets, QtGui, QtCore


class AddButton(QtWidgets.QPushButton):
    """Button with a green plus icon."""
    
    _ICON = None # for caching the icon for later use
    
    def __init__(self, parent=None):
        super().__init__(parent=None)
        
        if not AddButton._ICON:
            path = os.path.join(os.path.dirname(__file__), 'icons', 'green_plus.png')
            AddButton._ICON = QtGui.QIcon(path)
            
        self.setIcon(AddButton._ICON)
        size_hint = self.sizeHint()
        self.setFixedSize(size_hint.height(), size_hint.height())        
    
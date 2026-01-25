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


from PySide6 import QtWidgets


class AddItemDialog(QtWidgets.QDialog):
    """Add an item of a certain type to the project library."""
    
    def __init__(self, type_name, parent=None):
        super().__init__(parent=parent)
        
        self.setWindowTitle(f'Add {type_name}')
    
    

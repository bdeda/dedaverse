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

__all__ = ["IconGraphicsItem", "TiledGraphicsView"]


from PySide6 import QtWidgets


class IconGraphicsItem(QtWidgets.QGraphicsPixmapItem):
    """Icon graphics item to present in a tiled graphics view."""
    
    def __init__(self, pixmap, parent=None):
        # TODO: if pixmap is not square, resize to square
        super().__init__(pixmap, parent=parent)
    
    

class TiledGraphicsView(QtWidgets.QGraphicsView):
    """Tiled view of the scene."""
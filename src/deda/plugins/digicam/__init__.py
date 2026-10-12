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
"""Digicam: review a folder of camera photos, curate a printable-image library, and
open library images directly in Photoshop, Lightroom Classic, or Lightroom.
"""
import logging

import deda.app
import deda.core
from PySide6 import QtGui

__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.digicam')


class Digicam(deda.core.Tool):
    """Tool for reviewing camera photos and curating a printable-image library."""

    def initialize_window(self, parent):
        """Initialize the tool window. Called once to construct the UI when first shown."""
        from ._window import DigicamWindow
        return DigicamWindow(parent=parent)

    def load(self):
        """Load the plugin and add a menu action to launch it."""
        log.info('Digicam plugin loading...')

        menu = deda.app.get_main_menu()
        show_action = QtGui.QAction('Digicam', parent=menu)
        show_action.triggered.connect(self.launch)
        menu.addAction(show_action)

        self._loaded = True
        log.info('Digicam plugin loaded successfully.')
        return True


deda.core.PluginRegistry().register(Digicam('Digicam', __version__, __vendor__,
                                             description=Digicam.__doc__))

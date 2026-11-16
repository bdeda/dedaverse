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
"""Game asset optimizer: reduce, unwrap and bake dense (e.g. AI-generated) meshes into game-ready assets.

The pipeline runs in a background Blender; see docs/GAME_ASSET_OPTIMIZER.md for how it was chosen.
"""
import logging

from PySide6 import QtGui

import deda.app
import deda.core

from ._options import OptimizeError, OptimizeOptions, OptimizeResult
from ._runner import optimize

__all__ = ['GameAssetOptimizer', 'OptimizeError', 'OptimizeOptions', 'OptimizeResult', 'optimize']
__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.game_asset')


class GameAssetOptimizer(deda.core.Tool):
    """Tool that turns dense meshes into game-ready meshes with baked PBR textures."""

    def initialize_window(self, parent):
        """Initialize the tool window. Called once to construct the UI when first shown."""
        from ._tool_window import GameAssetWindow  # pylint: disable=import-outside-toplevel
        return GameAssetWindow(parent=parent)

    def load(self):
        """Load the plugin and add a menu action to launch it."""
        log.info('Game asset optimizer plugin loading...')
        menu = deda.app.get_main_menu()
        show_action = QtGui.QAction('Game Asset Optimizer', parent=menu)
        show_action.triggered.connect(self.launch)
        menu.addAction(show_action)
        self._loaded = True
        log.info('Game asset optimizer plugin loaded successfully.')
        return True


deda.core.PluginRegistry().register(GameAssetOptimizer('GameAssetOptimizer', __version__, __vendor__,
                                                       description=GameAssetOptimizer.__doc__))

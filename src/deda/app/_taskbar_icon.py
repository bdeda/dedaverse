# ###################################################################################
#
# Copyright 2024 Ben Deda
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
TaskbarIcon class definition, used as a main entry point to interact with the dedaverse services.
"""

__all__ = ["TaskbarIcon"]

import sys
import logging

from PySide6 import QtWidgets


log = logging.getLogger(__name__)


class TaskbarIcon(QtWidgets.QSystemTrayIcon):
    """Main system tray icon for all DedaFX apps."""

    def __init__(self, icon, *args, **kwargs):        
        super().__init__(*args, **kwargs)
        
        self.setIcon(icon)
        self._menu = self._create_menu()
        self.setContextMenu(self._menu)  
        self.setToolTip('Dedaverse is running.')
        
        log.debug("Dedaverse taskbar icon created.")
        
    
    def _create_menu(self):
        menu = QtWidgets.QMenu()
        menu.addAction('Restart', self._on_restart)
        menu.addAction('Exit', self._on_exit)
        return menu
    
    def _on_exit(self):
        self.setVisible(False)
        self.parent().close()
        QtWidgets.QApplication.instance().quit()
        
    def _on_restart(self):
        """Restart teh application"""
        import deda.app
        log.warning('Restarting dedaverse system...')
        sys.exit(deda.app.RESTART_CODE)
        
    def format_tool_tip(self, project):
        msg = f'<b>Dedaverse :: {project}</b>'
        self.setToolTip(msg)
        
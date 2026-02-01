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
TaskbarIcon class definition, used as a main entry point to interact with the dedaverse services.
"""

__all__ = ["TaskbarIcon"]

import logging
import sys

from PySide6 import QtCore, QtWidgets


log = logging.getLogger(__name__)


_KEY_VIEW_ASSETS = 'view/assets'
_KEY_VIEW_APPS = 'view/apps'
_KEY_VIEW_SERVICES = 'view/services'
_KEY_VIEW_TASKS = 'view/tasks'


class TaskbarIcon(QtWidgets.QSystemTrayIcon):
    """Main system tray icon for all DedaFX apps."""

    def __init__(self, icon, *args, **kwargs):        
        super().__init__(*args, **kwargs)
        self.setObjectName('DedaverseTaskbarIcon')
        self.setIcon(icon)
        self._settings = QtCore.QSettings('DedaFX', 'Dedaverse')
        self._menu = self._create_menu()
        self.setContextMenu(self._menu)  
        self.setToolTip('Dedaverse is running.')
        log.debug("Dedaverse taskbar icon created.")        
    
    def _create_menu(self):
        menu = QtWidgets.QMenu(parent=self.parent())
        menu.setObjectName('DedaverseTaskbarContextMenu')
        
        menu.addAction('Project', self.parent()._open_project_settings)

        # View submenu with checkable items for Assets, Apps, Services, Tasks
        view_menu = menu.addMenu('View')
        view_menu.setObjectName('ViewSubmenu')
        self._action_assets = view_menu.addAction('Assets')
        self._action_assets.setCheckable(True)
        self._action_assets.setChecked(self._settings.value(_KEY_VIEW_ASSETS, True, type=bool))
        self._action_assets.triggered.connect(lambda: self._on_view_toggled(_KEY_VIEW_ASSETS, self._action_assets))

        self._action_apps = view_menu.addAction('Apps')
        self._action_apps.setCheckable(True)
        self._action_apps.setChecked(self._settings.value(_KEY_VIEW_APPS, True, type=bool))
        self._action_apps.triggered.connect(lambda: self._on_view_toggled(_KEY_VIEW_APPS, self._action_apps))

        self._action_services = view_menu.addAction('Services')
        self._action_services.setCheckable(True)
        self._action_services.setChecked(self._settings.value(_KEY_VIEW_SERVICES, True, type=bool))
        self._action_services.triggered.connect(lambda: self._on_view_toggled(_KEY_VIEW_SERVICES, self._action_services))

        self._action_tasks = view_menu.addAction('Tasks')
        self._action_tasks.setCheckable(True)
        self._action_tasks.setChecked(self._settings.value(_KEY_VIEW_TASKS, True, type=bool))
        self._action_tasks.triggered.connect(lambda: self._on_view_toggled(_KEY_VIEW_TASKS, self._action_tasks))
        
        menu.addAction('Restart', self._on_restart)
        #menu.addAction('Exit', self._on_exit)
        return menu

    def _on_view_toggled(self, key, action):
        """Save the checked state of a View submenu item to QSettings."""
        self._settings.setValue(key, action.isChecked())
    
    def _on_exit(self):
        self.setVisible(False)
        self.parent().close()
        QtWidgets.QApplication.instance().quit()
        
    def _on_restart(self):
        """Restart the application"""
        import deda.app
        log.warning('Restarting dedaverse system...')
        sys.exit(deda.app.RESTART_CODE)
        
    def format_tool_tip(self, project):
        msg = f'<b>Dedaverse :: {project}</b>'
        self.setToolTip(msg)
        
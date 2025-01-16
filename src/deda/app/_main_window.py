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
MainWindow class definition, used for all Dedaverse tools.
"""

__all__ = ["MainWindow", "get_top_window", "get_main_menu"]

import sys
import os
import logging
import json
import getpass
import functools

from PySide6 import QtWidgets, QtCore, QtGui

from ._asset_browser import AssetBrowserWidget
from ._asset_info import AssetInfoWidget
from ._project_settings import ProjectSettingsDialog
from ._taskbar_icon import TaskbarIcon
from ._usd_viewer import UsdViewWidget


log = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    """Main Window base class for all DedaFX applications."""

    def __init__(self, app_name=None, parent=None):
        """Initialize the main window.

        Args:
            app_name: (str) Default=None, The application name, used for settings and
                window title. If None, this will be set to Dedaverse.
            parent: (QWidget) Default=None, The optional parent window of this window.

        """
        import deda  # pylint: disable=import-outside-toplevel

        if not parent:
            try:
                parent = get_top_window()
            except RuntimeError:
                parent = None
            log.debug("Setting main window's parent to {}".format(parent))
        super().__init__(parent=parent)
        if app_name is None:
            app_name = "Dedaverse"
        self._settings = QtCore.QSettings("DedaFX", app_name)
        version = deda.__version__
        self._window_title_context = f"{app_name} [deda@{version}]"
        self.setWindowTitle(self._window_title_context)
        self.setObjectName('DedaverseMainWindow')
        
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint) # QtCore.Qt.Window |
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground) #, True)
        
        icon_path = os.path.join(os.path.dirname(__file__), 'star_icon.png')
        icon = QtGui.QIcon(icon_path)
        self.setWindowIcon(icon)
        
        self._icon = TaskbarIcon(icon, parent=self)
        self._icon.setVisible(True)
        self._icon.activated.connect(self.toggle_visibility)
        
        w = QtWidgets.QWidget(parent=self)
        w.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setCentralWidget(w)
        
        #self._create_menu()
        #self._create_status()
        #self._create_main_widget()
        
        self._user_settings_path = None
        self._user_settings = {'projects': {}, 'current_project': None}
        self._project_settings = {}
        
        self._load_user_settings()
        self._load_project() 
        self.load_settings()

    @property
    def settings(self):
        """The window settings object."""
        return self._settings

    def closeEvent(self, event):
        """Overriden closeEvent to handle saving the window settings.

        Args:
            event: (QEvent) The event.

        Returns:
            None

        """
        if self._icon.isVisible():
            self.hide()
            event.ignore()
            return
        self.save_settings()
        super().closeEvent(event)

    def load_settings(self):
        """Load the window settings for this window.

        Subclasses should implement their own load_settings method and
        call super().load_settings() to load base class settings.

        Returns:
            None

        """
        if self.settings.contains("mainwindow.geometry"):
            self.restoreGeometry(self.settings.value("mainwindow.geometry"))
            
    def _load_project(self):
        """Load the current project, if there is one set in the user settings."""
        current_project = self._user_settings.get('current_project')
        if not current_project:
            # TODO: Open Project Manager, if plugin is installed
            return
        cfg = self._user_settings['projects'].get(current_project)
        if not cfg:
            log.error(f'User settings file is not set up properly! The project {current_project} is not found in the available user projects.')
            return
        if not os.path.isfile(cfg):
            log.error(f'Project settings file {cfg} does not exist!')
            return
        with open(cfg, 'r') as f:
            self._project_settings = json.load(f)
        self._icon.format_tool_tip(current_project)        
            
    def _load_user_settings(self):
        """Load the user settings from the local machine, or from the env configured user settings location."""
        user_config_dir = os.getenv('DEDA_USER_CONFIG_DIR')
        if not user_config_dir:
            user_config_dir = os.path.expanduser('~\\.dedaverse')
        else:
            user_config_dir = f'{user_config_dir}\\{getpass.getuser()}'
        # Once the user has created a project, it will be saved in the user projects dict in the form {name: config_path}.
        self._user_settings_path = f'{user_config_dir}\\user_settings.cfg'
        if os.path.isfile(self._user_settings_path):
            log.debug('Loading user settings from {}'.format(self._user_settings_path))
            with open(self._user_settings_path, 'r') as f:
                data = f.read()
                log.debug('User_settings.cfg contents:')
                log.debug(data)
                user_settings = json.loads(data)
                if isinstance(user_settings, dict):
                    self._user_settings = user_settings
                else:
                    log.error(f'Bad format of user settings cfg file! Expecting dict but got {type(user_settings)}')
        else:
            log.warning('User settings not found!')
            # TODO: show the new project dialog
            self._save_user_settings()

    def save_settings(self):
        """Save the window settings for this window.

        Subclasses should implement their own save_settings method and
        call super().save_settings() to save base class settings.
        
        Returns:
            None
            
        """
        self.settings.setValue("mainwindow.geometry", self.saveGeometry())
        self._save_user_settings()
        
    def _save_user_settings(self):
        """Save the user settings to disk."""
        settings_dir = os.path.dirname(self._user_settings_path)
        if not os.path.isdir(settings_dir):
            os.makedirs(settings_dir)
        with open(self._user_settings_path, 'w') as f:
            json.dump(self._user_settings, f, sort_keys=True, indent=4)
       
    def show_message(self, title, message, icon=QtWidgets.QSystemTrayIcon.Information, timeout=10000):
        """Show a message in the tray icon, status, and log."""
        if icon == QtWidgets.QSystemTrayIcon.NoIcon:
            log.debug(title)
            log.debug(message)
        elif icon == QtWidgets.QSystemTrayIcon.Information:
            log.info(title)
            log.info(message)
        elif icon == QtWidgets.QSystemTrayIcon.Warning:
            log.warning(title)
            log.warning(message)
        elif icon == QtWidgets.QSystemTrayIcon.Critical:
            log.critical(title)
            log.critical(message)
        self.status().showMessage(message, timeout)
        self._icon.showMessage(title, message, icon, timeout)        
        
    def toggle_visibility(self, context=None):
        """Toggle the visibility of the main window."""
        if context in (QtWidgets.QSystemTrayIcon.Context, QtWidgets.QSystemTrayIcon.DoubleClick):
            return
        if self.isVisible():
            self.hide()
        else:
            self.show()
        
    def _create_menu(self):
        """Create the main menu bar for the window."""
        menubar = self.menuBar()
        
        file_menu = QtWidgets.QMenu('Project')
        file_menu.addAction('Project Settings', self._open_project_settings)
        menubar.addMenu(file_menu)
        
        help_menu = QtWidgets.QMenu('Help')
        help_menu.addAction('About', self._open_about)
        menubar.addMenu(help_menu)
    
    def _create_status(self):
        pass
    
    def _create_main_widget(self):
        widget = self.centralWidget()
        vbox = QtWidgets.QVBoxLayout()
        widget.setLayout(vbox)
        vbox.setContentsMargins(0, 0, 0, 0)
        
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        vbox.addWidget(splitter)
        
        self._asset_browser = AssetBrowserWidget(parent=self)
        self._asset_info = AssetInfoWidget(parent=self)
        self._tabs = QtWidgets.QTabWidget(parent=self)
        splitter.addWidget(self._tabs)
        self._tabs.addTab(self._asset_browser, 'Library')
        self._tabs.addTab(self._asset_info, 'Info')
        
        self._usd_view = UsdViewWidget(parent=self)
        splitter.addWidget(self._usd_view)        
    
    def _open_project_settings(self):
        dlg = ProjectSettingsDialog(parent=self)
        dlg.exec_() # modal        
    
    def _open_about(self):
        pass


@functools.lru_cache
def get_top_window():
    """Retrun the top window of the application to use as a parent for other tool windows.
    
    Returns:
        QWidget or None
        
    Raises:
        RuntimeError when top level window is not found. This prevents the 
        function from cachine the window value.
        
    """
    try:
        import hou  # pylint: disable=import-outside-toplevel
        return hou.qt.mainWindow()
    except ImportError:
        pass    
    for top_window in QtWidgets.QApplication.instance().topLevelWidgets():
        if top_window.objectName() in ('DedaverseMainWindow', 'MayaWindow'):
            return top_window
    for window in QtWidgets.QApplication.instance().topLevelWidgets():
        if isinstance(window, QtWidgets.QMainWindow):
            return window
    raise RuntimeError('No top-level windows found!') # prevents caching
        
        
@functools.lru_cache
def get_main_menu():
    """Get the main menu for the app. When this is running as the standalone dedaverse app
    in the windows system tray, this will return the main context menu instance. In the
    DCC applications, thisi will be the main dedaverse menu.
    
    Returns:
        QMenu
    
    """
    window = get_top_window()
    for child in window.children():
        if not isinstance(child, QtWidgets.QMenu):
            continue
        if child.objectName() == 'DedaverseTaskbarContextMenu':
            return child

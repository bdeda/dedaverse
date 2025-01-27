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

import os
import logging
import json
import functools
import pkg_resources

from PySide6 import QtWidgets, QtCore, QtGui

from deda.core import LayeredConfig

#from ._asset_browser import AssetBrowserWidget
#from ._asset_info import AssetInfoWidget
from ._project_settings import ProjectSettingsDialog, StartProjectDialog
from ._taskbar_icon import TaskbarIcon
#from ._usd_viewer import UsdViewWidget


log = logging.getLogger(__name__)


class PanelHeader(QtWidgets.QWidget):
    
    gear_icon = None
    close_icon = None
    
    settings_clicked = QtCore.Signal()
    minmax_clicked = QtCore.Signal(bool) # True when minimized, False when maximized
    close_clicked = QtCore.Signal()
    
    
    def __init__(self, title, 
                 icon=None, 
                 show_minmax=True,
                 minimized=False,
                 show_close=True,
                 settings_callback=None,
                 close_callback=None, 
                 parent=None):
        super().__init__(parent=parent)
        
        self._minimized = False
        self._settings_callback = settings_callback
        self._close_callback = close_callback
        
        hbox = QtWidgets.QHBoxLayout()
        self.setLayout(hbox)
        hbox.setContentsMargins(0, 0, 0, 0)
        
        label = QtWidgets.QLabel(title)
        font = label.font()
        font.setPointSize(10)
        metrics = QtGui.QFontMetrics(font)
        label.setFont(font)         
        
        if icon:
            icon = QtGui.QPixmap(icon).scaled(metrics.height(), metrics.height())
            img = QtWidgets.QLabel()
            img.setPixmap(icon)
            img.setFixedSize(metrics.height(), metrics.height())
            hbox.addWidget(img)       
        
        hbox.addWidget(label)
        
        hbox.addStretch()
        
        if not PanelHeader.gear_icon:
            icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'gear_icon_32.png')
            PanelHeader.gear_icon = QtGui.QIcon(icon_path)
        gear_btn = QtWidgets.QPushButton(PanelHeader.gear_icon, '')
        gear_btn.setToolTip('Settings')
        gear_btn.setFlat(True)
        gear_btn.setFixedSize(metrics.height(), metrics.height())
        hbox.addWidget(gear_btn)
        gear_btn.clicked.connect(self._on_settings_clicked)
        
        if show_minmax:
            self._minmax_btn = QtWidgets.QPushButton('__')
            self._minmax_btn.setFlat(True)
            self._minmax_btn.setFixedSize(metrics.height(), metrics.height())
            hbox.addWidget(self._minmax_btn)
            self._minmax_btn.clicked.connect(self._minmax_clicked)
            
        if show_close:
            close_btn = QtWidgets.QPushButton('X')
            close_btn.setFlat(True)
            close_btn.setFixedSize(metrics.height(), metrics.height())
            hbox.addWidget(close_btn) 
            close_btn.clicked.connect(self.close_clicked.emit)
        
        self.setFixedHeight(metrics.height())        
        
    @property
    def minimized(self):
        return self._minimized
        
    def _minmax_clicked(self):
        self._minimized = not self._minimized
        if self._minimized:
            self._minmax_btn.setText('[]')
        else:
            self._minmax_btn.setText('__')
        self.minmax_clicked.emit(self._minimized) 
        
    def _on_settings_clicked(self):
        self.settings_clicked.emit()
        if self._settings_callback:
            self._settings_callback()        
        

class Panel(QtWidgets.QFrame):
    """Base class for all panel types."""
    
    close_clicked = QtCore.Signal()
    
    def __init__(self, type_name, name, show_scroll_area=True, parent=None, **kwargs):
        super().__init__(parent=parent)
        
        self.setObjectName(type_name)
        
        self.setStyleSheet("Panel{background-color: rgb(20,20,20); border: 1px solid rgb(40,40,40); border-radius: 5px;}")
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        header = PanelHeader(name, parent=self, **kwargs) 
        vbox.addWidget(header)
        header.close_clicked.connect(self.close)
        
        if show_scroll_area:
            self._scroll_area = QtWidgets.QScrollArea()
            #self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            #self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)        
            vbox.addWidget(self._scroll_area)
            header.minmax_clicked.connect(self._on_minimized)
            
    def __repr__(self):
        return f'<{self.__class__} {self.objectName()}>'
            
    def _on_minimized(self, minimized):
        self._scroll_area.setVisible(not minimized)
        
    def close(self):        
        super().close() 
        self.close_clicked.emit()
        
              

class MainWindow(QtWidgets.QMainWindow):
    """Main Window base class for all DedaFX applications."""

    def __init__(self, app_name=None, parent=None):
        """Initialize the main window.

        Args:
            app_name: (str) Default=None, The application name, used for settings and
                window title. If None, this will be set to Dedaverse.
            parent: (QWidget) Default=None, The optional parent window of this window.

        """
        if not parent:
            try:
                parent = get_top_window()
            except RuntimeError:
                parent = None
            log.debug("Setting main window's parent to {}".format(parent))
        super().__init__(parent=parent)
        
        self._config = None
        self._proj_settings_dlg = None
        
        if app_name is None:
            app_name = "Dedaverse"
        self._settings = QtCore.QSettings("DedaFX", app_name)
        version = pkg_resources.get_distribution('dedaverse').version
        self._window_title_context = f"{app_name} [deda@{version}]"
        self.setWindowTitle(self._window_title_context)
        self.setObjectName('DedaverseMainWindow')
        
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint) # QtCore.Qt.Window |
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        
        geo = QtWidgets.QApplication.primaryScreen().availableGeometry()
        size = QtWidgets.QApplication.primaryScreen().size()
        width = 450
        self.setFixedWidth(width)
        self.setFixedHeight(geo.height())
        self.setGeometry(size.width()-self.width(), 0, width, geo.height()) 
        
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'star_icon.png')
        icon = QtGui.QIcon(icon_path)
        self.setWindowIcon(icon)
        
        self._icon = TaskbarIcon(icon, parent=self)
        self._icon.setVisible(True)
        self._icon.activated.connect(self.toggle_visibility)
        self._icon.messageClicked.connect(self.message_clicked)
        
        self._load_config()
        self._create_main_widget()
        if self.current_project:
            self._icon.setToolTip(f'Dedaverse :: {self.current_project.name}')
        
    @property 
    def current_project(self):
        return self._config.current_project        
    
    @current_project.setter
    def current_project(self, project):
        """User selected a different project to be the current project."""
        if project == self.current_project:
            return
        self._config.current_project = project
        # TODO: emit signal?
        self._create_main_widget()
        self._icon.setToolTip(f'Dedaverse :: {project.name}')

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
        #self.save_settings()
        super().closeEvent(event)

    #def load_settings(self):
        #"""Load the window settings for this window.

        #Subclasses should implement their own load_settings method and
        #call super().load_settings() to load base class settings.

        #Returns:
            #None

        #"""
        ##if self.settings.contains("mainwindow.geometry"):
        ##    self.restoreGeometry(self.settings.value("mainwindow.geometry"))
        
    #def save_settings(self):
        #"""Save the window settings for this window.

        #Subclasses should implement their own save_settings method and
        #call super().save_settings() to save base class settings.
        
        #Returns:
            #None
            
        #"""
        #self.settings.setValue("mainwindow.geometry", self.saveGeometry()) 
        
    def message_clicked(self):
        if not self._config.current_project:
            self._open_project_settings()
            
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
        #self.status().showMessage(message, timeout)
        self._icon.showMessage(title, message, icon, timeout)        
        
    def toggle_visibility(self, context=None):
        """Toggle the visibility of the main window."""
        if context in (QtWidgets.QSystemTrayIcon.Context, QtWidgets.QSystemTrayIcon.DoubleClick):
            return
        if self.isVisible():            
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow() 
            
    def _create_main_widget(self):
        """Reconstruct the central widget. This will generate all of the panels for the current project
        based on the config settings.
        
        """
        widget = QtWidgets.QWidget(parent=self)
        self.setCentralWidget(widget)        
        vbox = QtWidgets.QVBoxLayout()
        widget.setLayout(vbox)
        
        current_project = self.current_project
        
        # TODO: get this list from a user/project config
        panels = {
            'Project': {'show_minmax': False, 
                        'show_close': False, 
                        'show_scroll_area': False, 
                        'icon': None,
                        'settings_callback': self._open_project_settings,
                        },
            #'Assets': {}, # additional panels shown are added based on the project, when the project is loaded.
            #'Apps': {}, 
            #'Services': {},
            #'Tasks': {}, 
        }
        
        if current_project:
            # TODO: load the plugin panel info, etc...
            pass
        
        if tuple(panels.keys()) == ('Project',):
            vbox.addStretch() # only a project with no other plugins loaded        
        
        for panel, settings in panels.items():
            title = panel
            if panel == 'Project':
                title = 'Untitled Project'
                if current_project:
                    title = current_project.name
                # TODO: Project panel also control drag positioning of main window
            panel_obj = Panel(panel, title, parent=self, **settings)
            vbox.addWidget(panel_obj)
            panel_obj.close_clicked.connect(self._on_panel_closed)
        
        #vbox.addWidget(AssetPanel(parent=self))
        #vbox.addWidget(AppPanel(parent=self))
        #vbox.addWidget(TaskPanel(parent=self))
        
        #splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        #vbox.addWidget(splitter)
        
        #self._asset_browser = AssetBrowserWidget(parent=self)
        #self._asset_info = AssetInfoWidget(parent=self)
        #self._tabs = QtWidgets.QTabWidget(parent=self)
        #splitter.addWidget(self._tabs)
        #self._tabs.addTab(self._asset_browser, 'Library')
        #self._tabs.addTab(self._asset_info, 'Info')
        
        #self._usd_view = UsdViewWidget(parent=self)
        #splitter.addWidget(self._usd_view)     
        
    def _load_config(self):
        """Load the user settings from the local machine, or from the env configured user settings location."""
        self._config = LayeredConfig()
        if not self._config.current_project:
            # TODO: open the project settings dialog so the user can choose a project name 
            # and root directory location to save files to.
            #log.warning('Choose a project to start.')        
            self.show_message('Choose a project.', 
                              'You must set up your project before starting work.', 
                              icon=QtWidgets.QSystemTrayIcon.Warning)    
            
    #def _load_project(self):
        #"""Load the current project, if there is one set in the user settings."""
        #current_project = self._user_settings.get('current_project')
        #if not current_project:
            ## TODO: Open Project Manager, if plugin is installed
            #return
        #cfg = self._user_settings['projects'].get(current_project)
        #if not cfg:
            #log.error(f'User settings file is not set up properly! The project {current_project} is not found in the available user projects.')
            #return
        #if not os.path.isfile(cfg):
            #log.error(f'Project settings file {cfg} does not exist!')
            #return
        #with open(cfg, 'r') as f:
            #self._project_settings = json.load(f)
        #self._icon.format_tool_tip(current_project)        
                   
    def _on_panel_closed(self):
        widget = self.centralWidget()
        visible_panels = [p for p in widget.children() if isinstance(p, Panel) and p.isVisible()]
        if not visible_panels:
            return        
        elif len(visible_panels) == 1:
            widget.layout().insertStretch(0)     
    
    def _open_project_settings(self):
        
        if not self.current_project:
            if self._proj_settings_dlg and not isinstance (self._proj_settings_dlg, StartProjectDialog):
                self._proj_settings_dlg.close() 
                self._proj_settings_dlg = None
            # show the dialog to create a new project
            if not self._proj_settings_dlg:
                self._proj_settings_dlg = StartProjectDialog(self._config, parent=self)
                self._proj_settings_dlg.project_changed.connect(self._create_main_widget)
            self._proj_settings_dlg.show()
            self._proj_settings_dlg.raise_()
            self._proj_settings_dlg.activateWindow()
            self._proj_settings_dlg.exec_()
        else:
            if self._proj_settings_dlg and not isinstance (self._proj_settings_dlg, ProjectSettingsDialog):
                self._proj_settings_dlg.close() 
                self._proj_settings_dlg = None
            # show the dialog to create a new project
            if not self._proj_settings_dlg:            
                self._proj_settings_dlg = ProjectSettingsDialog(self._config, parent=self)
                self._proj_settings_dlg.project_changed.connect(self._create_main_widget)
            self._proj_settings_dlg.show()
            self._proj_settings_dlg.raise_()
            self._proj_settings_dlg.activateWindow()
            self._proj_settings_dlg.exec_() 


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

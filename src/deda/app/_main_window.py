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
MainWindow class definition, used for all Dedaverse tools.
"""

__all__ = ["MainWindow", "get_top_window", "get_main_menu"]

import sys
try:    
    sys.path.insert(0, r'')
    import wingdbstub # Do not remove this, agent!
except ImportError:
    pass
finally:
    sys.path = sys.path[1:]
import os
import logging
import json
import functools
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from PySide6 import QtWidgets, QtCore, QtGui

from deda.core import LayeredConfig, Project

from ._project_settings import ProjectSettingsDialog, StartProjectDialog
from ._taskbar_icon import TaskbarIcon
from ._dialogs import AddItemDialog
#from deda.core.viewer import UsdViewWidget


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
        
        self._minimized = bool(minimized)
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
            icon_path = Path(__file__).parent / 'icons' / 'gear_icon_32.png'
            PanelHeader.gear_icon = QtGui.QIcon(str(icon_path))
        gear_btn = QtWidgets.QPushButton(PanelHeader.gear_icon, '')
        gear_btn.setToolTip('Settings')
        gear_btn.setFlat(True)
        gear_btn.setFixedSize(metrics.height(), metrics.height())
        hbox.addWidget(gear_btn)
        gear_btn.clicked.connect(self._on_settings_clicked)
        
        if show_minmax:
            self._minmax_btn = QtWidgets.QPushButton('[]' if self._minimized else '__')
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
    add_item = QtCore.Signal(str)
    item_created = QtCore.Signal(object)
    minimized_changed = QtCore.Signal(str, bool)
    
    def __init__(self, type_name, name, 
                 view=None, # instance of the view to put into the panel
                 show_scroll_area=True, 
                 parent=None, **kwargs):
        super().__init__(parent=parent)
        
        self._visibility = True
        self.setObjectName(type_name)
        self._type_name = type_name
        if type_name.endswith('s'):
            self._type_name = type_name[:-1]
        
        self.setStyleSheet("Panel{background-color: rgb(20,20,20); border: 1px solid rgb(40,40,40); border-radius: 5px;}")
        
        self._scroll_area = None
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        header = PanelHeader(name, parent=self, **kwargs) 
        vbox.addWidget(header)
        header.close_clicked.connect(self.close)
        
        if show_scroll_area:
            self._scroll_area = QtWidgets.QScrollArea()
            
            # TODO: Add tiled icons or list to scroll area
            # Need to add a graphics view with tiles of object types
            # sortable, or custom drag-drop organization of tiles, in "edit" mode
            # optional list view
            
            #self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            #self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)        
            vbox.addWidget(self._scroll_area)
            header.minmax_clicked.connect(self._on_minimized)
            self._on_minimized(header.minimized)
            
            self._scroll_area.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self._scroll_area.customContextMenuRequested.connect(self._show_context_menu)   
            
    @property
    def visibility(self):
        return self._visibility
    
    @visibility.setter
    def visibility(self, value: bool):
        self._visibility = bool(value)
        self.setVisible(self._visibility)
            
    def __repr__(self):
        return f'<{self.__class__.__name__} {self.objectName()}>'
        
    def close(self):        
        super().close() 
        self.close_clicked.emit()
        
    def _add_item(self):
        self.add_item.emit(self._type_name)
        dlg = AddItemDialog(self._type_name, parent=self._scroll_area)
        dlg.item_created.connect(self.item_created.emit) # propogate signal
        if self._scroll_area:
            rect = self._scroll_area.geometry()
            dlg_rect = dlg.geometry()
            pt = QtCore.QPoint((rect.width()/2) - (dlg_rect.width()/2),
                               (rect.height()/2) - (dlg_rect.height()/2))
            dlg.move(self._scroll_area.mapToGlobal(pt))
        dlg.exec()
               
    def _on_minimized(self, minimized):
        self._scroll_area.setVisible(not minimized)
        self.minimized_changed.emit(self.objectName(), minimized)
        
    def _show_context_menu(self, position):
        menu = QtWidgets.QMenu(parent=self)
        
        icon_path = Path(__file__).parent / 'icons' / 'green_plus.png'
        plus_icon = QtGui.QIcon(str(icon_path))        
        action = menu.addAction(plus_icon, f'Add {self._type_name}')
        action.triggered.connect(self._add_item)
        
        menu.exec(self._scroll_area.mapToGlobal(position))
        
              

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
        self._force_close = False
        self._asset_library = None
        
        if app_name is None:
            app_name = "Dedaverse"
        self._settings = QtCore.QSettings("DedaFX", app_name)
        try:
            package_version = version('dedaverse')
        except PackageNotFoundError:
            # Fallback if package is not installed (e.g., running from source)
            package_version = 'dev'
        self._window_title_context = f"{app_name} [deda@{package_version}]"
        self.setWindowTitle(self._window_title_context)
        self.setObjectName('DedaverseMainWindow')
        
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint) 
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        
        geo = QtWidgets.QApplication.primaryScreen().availableGeometry()
        size = QtWidgets.QApplication.primaryScreen().size()
        width = 450
        self.setFixedWidth(width)
        self.setFixedHeight(geo.height())
        self.setGeometry(size.width()-self.width(), 0, width, geo.height()) 
        
        icon_path = Path(__file__).parent / 'icons' / 'star_icon.png'
        icon = QtGui.QIcon(str(icon_path))
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
    def asset_library(self):
        return self._asset_library
    
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
        if not self._force_close and self._icon.isVisible():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)
        
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
            'Assets': {}, # additional panels shown are added based on the project, when the project is loaded.
            'Apps': {}, 
            'Services': {},
            'Tasks': {}, 
        }
        
        if current_project:
            # TODO: load the plugin panel info, etc...
            pass
        
        self._panel_stack_has_top_stretch = False
        if tuple(panels.keys()) == ('Project',):
            vbox.addStretch()
            self._panel_stack_has_top_stretch = True

        for panel, settings in panels.items():
            title = panel
            if panel == 'Project':
                title = 'Untitled Project'
                if current_project:
                    title = current_project.name
                # TODO: Project panel also control drag positioning of main window
            panel_settings = dict(settings)
            if panel != 'Project':
                panel_settings['minimized'] = self._settings.value(
                    f'view/{panel.lower()}_minimized', False, type=bool
                )
            panel_obj = Panel(panel, title, parent=self, **panel_settings)
            if panel == 'Assets':
                panel_obj.item_created.connect(self._on_asset_created)
            vbox.addWidget(panel_obj)
            if panel != 'Project':
                panel_obj.close_clicked.connect(
                    lambda p=panel_obj: self._on_panel_closed(p)
                )
                panel_obj.minimized_changed.connect(self._on_panel_minimized_changed)
                self._apply_view_state_to_panel(panel_obj)
                self._connect_view_action_for_panel(panel_obj)

        #if tuple(panels.keys()) != ('Project',):
        self._update_panel_stack_layout()
        
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
        # This layered config is how we store teh user projects as well as shared projects with other people.
        self._config = LayeredConfig()
        if not self._config.current_project:
            # TODO: open the project settings dialog so the user can choose a project name 
            # and root directory location to save files to.
            #log.warning('Choose a project to start.')        
            self.show_message('Choose a project.', 
                              'You must set up your project before starting work.', 
                              icon=QtWidgets.QSystemTrayIcon.Warning)   
            
    def _initialize_project(self, project):
        """Initialize the project with the new settings from the project arg."""
        self._asset_library = Project(project.name, project.rootdir)
        self._create_main_widget()
                   
    def _action_for_panel_name(self, name):
        """Return the View submenu action for the given panel name."""
        mapping = {
            'Assets': self._icon._action_assets,
            'Apps': self._icon._action_apps,
            'Services': self._icon._action_services,
            'Tasks': self._icon._action_tasks,
        }
        return mapping.get(name)

    def _apply_view_state_to_panel(self, panel_obj):
        """Set panel visibility from the View submenu checked state."""
        action = self._action_for_panel_name(panel_obj.objectName())
        if action:
            panel_obj.visibility = action.isChecked()

    def _connect_view_action_for_panel(self, panel_obj):
        """Connect the View submenu action to show/hide this panel."""
        action = self._action_for_panel_name(panel_obj.objectName())
        if action:
            action.triggered.connect(
                lambda checked, p=panel_obj: self._on_view_toggled_for_panel(checked, p)
            )

    def _all_non_project_panels_hidden(self):
        """Return True if Assets, Apps, Services, and Tasks are all hidden."""
        vbox = self.centralWidget().layout()
        for i in range(vbox.count()):
            item = vbox.itemAt(i)
            w = item.widget() if item else None
            if w and isinstance(w, Panel) and w.objectName() in ('Assets', 'Apps', 'Services', 'Tasks'):
                if w.visibility:
                    return False
        return True

    def _on_panel_closed(self, panel):
        """When a panel is closed, uncheck the corresponding View submenu item."""
        action = self._action_for_panel_name(panel.objectName())
        if action:
            action.setChecked(False)
            self._icon._settings.setValue(
                f'view/{panel.objectName().lower()}', False
            )
        #QtCore.QTimer.singleShot(0, self._update_panel_stack_layout)
        self._update_panel_stack_layout()

    def _on_panel_minimized_changed(self, panel_name, minimized):
        """Save the panel minimized state to QSettings."""
        self._settings.setValue(f'view/{panel_name.lower()}_minimized', minimized)

    def _on_view_toggled_for_panel(self, checked, panel_obj):
        """Handle View submenu toggle: show/hide panel and update layout."""
        panel_obj.visibility = checked
        self._update_panel_stack_layout()

    def _update_panel_stack_layout(self):
        """When all non-Project panels are hidden, add top stretch to pin Project at bottom."""
        vbox = self.centralWidget().layout()
        if vbox is None:
            return
        need_stretch = self._all_non_project_panels_hidden()
        if need_stretch and not self._panel_stack_has_top_stretch:
            vbox.insertStretch(0, 1)
            self._panel_stack_has_top_stretch = True
        elif not need_stretch and self._panel_stack_has_top_stretch:
            item = vbox.takeAt(0)
            if item:
                del item
            self._panel_stack_has_top_stretch = False
            
    def _on_asset_created(self, asset_info):
        """Handle the creation of the asset in the asset library."""
        if not self._asset_library:
            rootdir = None # get this from the project config
            self._asset_library = Project.create(self.current_project, rootdir)
    
    def _open_project_settings(self):
        
        if not self.current_project:
            if self._proj_settings_dlg and not isinstance (self._proj_settings_dlg, StartProjectDialog):
                self._proj_settings_dlg.close() 
                self._proj_settings_dlg = None
            # show the dialog to create a new project
            if not self._proj_settings_dlg:
                self._proj_settings_dlg = StartProjectDialog(self._config, parent=self)
                self._proj_settings_dlg.project_changed.connect(self._initialize_project)
        else:
            if self._proj_settings_dlg and not isinstance (self._proj_settings_dlg, ProjectSettingsDialog):
                self._proj_settings_dlg.close() 
                self._proj_settings_dlg = None
            # show the dialog to create a new project
            if not self._proj_settings_dlg:            
                self._proj_settings_dlg = ProjectSettingsDialog(self._config, parent=self)
                self._proj_settings_dlg.project_changed.connect(self._initialize_project) 
        self._proj_settings_dlg.adjustSize()
        screen_geo = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self._proj_settings_dlg.show()
        dlg_geo = self._proj_settings_dlg.geometry()
        x = screen_geo.width() - dlg_geo.width()
        self._proj_settings_dlg.move(x, dlg_geo.y())          
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

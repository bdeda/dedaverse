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
import subprocess
import logging
import json
import functools
import html
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from PySide6 import QtWidgets, QtCore, QtGui

from deda.core import LayeredConfig, Project
from deda.core._config import AppConfig

from ._project_settings import ProjectSettingsDialog, StartProjectDialog
from ._taskbar_icon import TaskbarIcon
from ._dialogs import AddItemDialog, ConfigureItemDialog
from ._panel import ItemTile, PanelHeader, Panel
#from deda.core.viewer import UsdViewWidget


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
            elif panel == 'Apps':
                panel_obj.item_created.connect(self._on_app_created)
                panel_obj.item_updated.connect(self._on_app_updated)
                panel_obj.item_activated.connect(self._on_app_activated)
            # Connect item_created to add tile to the panel
            panel_obj.item_created.connect(
                lambda item, p=panel_obj: p.add_item_tile(item)
            )
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

        # Re-load apps from project config (on startup or when project is switched)
        apps_panel = widget.findChild(Panel, 'Apps')
        if apps_panel:
            self._load_apps_to_panel(apps_panel)
        
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

    def _on_app_activated(self, item_data):
        """Launch the app via its command in a subprocess (double-click on Apps panel tile)."""
        command = item_data.get('command', '').strip()
        if not command:
            log.warning("App item has no command; cannot launch.")
            return
        # Run Python commands with current interpreter and env so PYTHONPATH/venv are inherited
        argv, use_env = self._parse_python_launch(command)
        if argv is not None:
            kwargs = {'env': os.environ.copy()} if use_env else {}
            try:
                subprocess.Popen(argv, **kwargs)
                log.info(f"Launched app: {command}")
            except Exception as err:
                log.error(f"Failed to launch app '{command}': {err}")
                self.show_message("Launch failed", str(err), icon=QtWidgets.QSystemTrayIcon.Critical)
            return
        # Non-Python or unparseable: run via shell
        try:
            subprocess.Popen(command, shell=True)
            log.info(f"Launched app: {command}")
        except Exception as err:
            log.error(f"Failed to launch app '{command}': {err}")
            self.show_message("Launch failed", str(err), icon=QtWidgets.QSystemTrayIcon.Critical)

    def _parse_python_launch(self, command):
        """If command is a Python invocation, return (argv_list, use_main_env); else (None, False).
        Running with sys.executable and env=os.environ.copy() ensures PYTHONPATH and venv are inherited.
        """
        parts = command.split()
        if not parts:
            return None, False
        first = parts[0].lower()
        if not (first == 'python' or first.startswith('python3') or first.startswith('python-')):
            return None, False
        if len(parts) >= 3 and parts[1] == '-m':
            # python -m module [args...]
            return [sys.executable, '-m', parts[2]] + parts[3:], True
        if len(parts) >= 2:
            # python script.py [args...]
            return [sys.executable] + parts[1:], True
        return None, False

    def _load_apps_to_panel(self, apps_panel):
        """Load apps from site (studio), user, and project config layers into the Apps panel.
        Later layers override earlier when the same app name exists.
        """
        if not apps_panel:
            return

        merged = self._config.get_merged_apps()

        # Clear existing items in the panel
        apps_panel._items.clear()
        apps_panel._relayout_tiles()

        count = 0
        for app_config in merged:
            if not app_config.enabled:
                continue
            item_data = {
                'name': app_config.name,
                'type': 'Command',
                'description': '',
                'command': app_config.command,
            }
            if app_config.icon_path:
                item_data['icon'] = app_config.icon_path
            apps_panel.add_item_tile(item_data)
            count += 1

        log.debug("Loaded %d apps from config layers (site + user + project)", count)

    def _on_app_created(self, app_info):
        """Handle the creation of an app and save it to the project config."""
        if not self.current_project:
            log.warning("Cannot save app: no current project")
            return
        
        # Convert item dict to AppConfig
        app_name = app_info.get('name', 'Untitled')
        app_type = app_info.get('type', 'Command')
        command = app_info.get('command', '')
        icon_path = app_info.get('icon', '')
        
        # Do not add if an app with the same name already exists
        existing_names = {a.name for a in self.current_project.apps}
        if app_name in existing_names:
            log.warning(f"App '{app_name}' already exists in project config; not adding duplicate.")
            return

        # Create AppConfig with required fields
        app_config = AppConfig(
            name=app_name,
            version='',  # Version not provided in AddItemDialog
            command=command,
            icon_path=icon_path if icon_path else '',
            install_url='',  # Not provided in AddItemDialog
            help_url='',  # Not provided in AddItemDialog
            enabled=True  # New apps are enabled by default
        )

        # Add to project config apps list
        self.current_project.apps.append(app_config)

        # Save the project config
        try:
            self.current_project.save()
            log.info(f"Saved app '{app_name}' to project config")
        except Exception as err:
            log.error(f"Failed to save app to project config: {err}")

    def _on_app_updated(self, item_index, updated_data):
        """Handle the update of an app and persist to the project config (by name).
        Panel order is merged (site + user + project), so we find or add by name in project.
        """
        if not self.current_project:
            log.warning("Cannot update app: no current project")
            return

        app_name = updated_data.get('name', '').strip() or 'Untitled'
        command = updated_data.get('command', '')
        icon_path = updated_data.get('icon', '')

        # Find app by name in project config (app may have come from site/user layer)
        app_config = None
        for a in self.current_project.apps:
            if a.name == app_name:
                app_config = a
                break

        if app_config is None:
            # App came from site or user; add project-level override
            app_config = AppConfig(
                name=app_name,
                version='',
                command=command,
                icon_path=icon_path if icon_path else '',
                install_url='',
                help_url='',
                enabled=True,
            )
            self.current_project.apps.append(app_config)
        else:
            app_config.command = command
            app_config.icon_path = icon_path if icon_path else ''

        try:
            self.current_project.save()
            log.info("Updated app '%s' in project config", app_name)
        except Exception as err:
            log.error("Failed to update app in project config: %s", err)
    
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

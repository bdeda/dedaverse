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
import shlex
import shutil
import subprocess
import webbrowser
import logging
import json
import functools
import html
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from PySide6 import QtWidgets, QtCore, QtGui

from deda.core import LayeredConfig, Project
from deda.core._config import AppConfig, ServiceConfig, _sanitize_prim_name
from deda.core.types import Asset, Collection

# Asset types that are created as Collection in project USD metadata
_COLLECTION_ASSET_TYPES = frozenset({'Collection', 'Sequence', 'Shot'})


def _collect_usd_dependencies(root_file_path):
    """Collect root USD file and all nested references; return list of (abs_path, relative_path).

    relative_path is from the root file's directory, for use under an asset root.
    Preserves directory structure. Returns [(abs_str, rel_str), ...].
    """
    root_path = Path(root_file_path).resolve()
    if not root_path.is_file():
        return [(str(root_path), root_path.name)]
    root_dir = root_path.parent
    result = {}  # abs_path_str -> relative_path_str

    def process(path_str):
        path = Path(path_str).resolve()
        abs_str = str(path)
        if abs_str in result:
            return
        try:
            rel = path.relative_to(root_dir)
        except ValueError:
            rel = Path('external') / path.name
        rel_str = str(rel).replace('\\', '/')
        result[abs_str] = rel_str
        if not path.is_file():
            return
        try:
            from pxr import Sdf, UsdUtils
        except ImportError:
            return
        layer = Sdf.Layer.FindOrOpen(abs_str)
        if not layer:
            return
        rp = getattr(layer, 'realPath', None)
        if not rp:
            rp = abs_str
        layer_dir = Path(rp).resolve().parent
        try:
            sublayers, refs, payloads = [], [], []
            UsdUtils.ExtractExternalReferences(rp, sublayers, refs, payloads)
            for ref in sublayers + refs + payloads:
                ref_clean = ref.strip().strip('@')
                if not ref_clean:
                    continue
                ref_path = (layer_dir / ref_clean).resolve()
                if ref_path.is_file() and str(ref_path) not in result:
                    process(str(ref_path))
        except Exception:
            pass

    process(str(root_path))
    # Root file first, then rest sorted by path (deepest last for move order)
    root_abs = str(root_path)
    root_rel = result.get(root_abs, root_path.name)
    ordered = [(root_abs, root_rel)]
    for abs_p in sorted(result.keys()):
        if abs_p != root_abs:
            ordered.append((abs_p, result[abs_p]))
    return ordered


# Extensions supported by Usd.Stage.Open and the deda viewer (order = resolution order).
USD_FILE_EXTENSIONS = ('.usda', '.usd', '.usdc', '.usdz')


def _first_usd_file_in_directory(asset_dir: Path, asset_name: str) -> Path | None:
    """Return the first USD file in asset_dir, preferring asset_name + ext, then any *.{ext}.

    Checks .usda, .usd, .usdc, .usdz in that order. Used when launching an app with an asset.
    """
    if not asset_dir.is_dir():
        return None
    for ext in USD_FILE_EXTENSIONS:
        p = asset_dir / f"{asset_name}{ext}"
        if p.is_file():
            return p
    for ext in USD_FILE_EXTENSIONS:
        matches = sorted(asset_dir.glob(f"*{ext}"))
        if matches:
            return matches[0]
    return None


from ._project_settings import ProjectSettingsDialog, StartProjectDialog
from ._taskbar_icon import TaskbarIcon
from ._dialogs import AddItemDialog, ConfigureItemDialog, CopyMoveUsdFilesDialog
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
        self._assets_view_container = None  # Project | Collection | None; current level in Assets panel
        self._pending_drop_file_path = None  # When set, after creating asset prompt to copy/move this file into it

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
        
    def _on_update_check_result(self, available: bool, latest_version: str | None) -> None:
        """Handle result of background update check: notify user and enable Update and restart if available."""
        if not available:
            return
        self._icon.set_update_available(True, latest_version)
        msg = f'A new version (v{latest_version}) is available. Use the taskbar menu: Update and restart.'
        self.show_message('Dedaverse update available', msg, icon=QtWidgets.QSystemTrayIcon.Information)

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
        # Disconnect view menu actions from previous panels so we don't hold references to
        # deleted Panel widgets (avoids "Internal C++ object already deleted" when toggling view).
        _connections = getattr(self, '_view_action_connections', None)
        if _connections:
            for conn in _connections.values():
                try:
                    QtCore.QObject.disconnect(conn)
                except (RuntimeError, TypeError):
                    pass
            self._view_action_connections.clear()
        else:
            self._view_action_connections = {}

        widget = QtWidgets.QWidget(parent=self)
        self.setCentralWidget(widget)
        vbox = QtWidgets.QVBoxLayout()
        widget.setLayout(vbox)

        current_project = self.current_project

        # Sync asset library and assets view to current project (covers app restart and project change)
        if current_project:
            self._asset_library = Project(
                current_project.name,
                current_project.rootdir,
                prim_name=getattr(current_project, 'prim_name', None),
            )
            self._assets_view_container = self._asset_library
            self._restore_assets_panel_path()
        else:
            self._asset_library = None
            self._assets_view_container = None

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
            if panel == 'Assets':
                # Top level (no container or container is Project) -> title "Project"
                title = 'Project' if (
                    self._assets_view_container is None
                    or self._assets_view_container.parent is None
                ) else self._assets_view_container.name
                panel_settings['show_navigate_up'] = False
            panel_obj = Panel(panel, title, parent=self, **panel_settings)
            if panel == 'Assets':
                panel_obj.item_created.connect(self._on_asset_created)
                panel_obj.item_activated.connect(self._on_asset_panel_item_activated)
                panel_obj.navigate_up_clicked.connect(self._on_assets_navigate_up)
                panel_obj.file_dropped.connect(self._on_assets_panel_file_dropped)
                panel_obj.item_removed.connect(self._on_asset_removed)
            elif panel == 'Apps':
                panel_obj.item_created.connect(self._on_app_created)
                panel_obj.item_updated.connect(self._on_app_updated)
                panel_obj.item_activated.connect(self._on_app_activated)
                panel_obj.item_removed.connect(self._on_app_removed)
            elif panel == 'Services':
                panel_obj.item_created.connect(self._on_service_created)
                panel_obj.item_updated.connect(self._on_service_updated)
                panel_obj.item_removed.connect(self._on_service_removed)
            if panel in ('Apps', 'Services'):
                panel_obj.asset_dropped_on_tile.connect(
                    self._on_asset_dropped_on_app if panel == 'Apps' else self._on_asset_dropped_on_service
                )
            # Connect item_created to add tile to the panel (Assets panel is populated by _load_assets_to_panel only)
            if panel != 'Assets':
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
        
        # Re-load services from project config (on startup or when project is switched)
        services_panel = widget.findChild(Panel, 'Services')
        if services_panel:
            self._load_services_to_panel(services_panel)

        # Load Assets panel from asset library (project or current collection)
        assets_panel = widget.findChild(Panel, 'Assets')
        if assets_panel:
            self._load_assets_to_panel(assets_panel)

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
        """Connect the View submenu action to show/hide this panel by name.
        Uses panel name so we never hold a reference to a deleted panel.
        """
        action = self._action_for_panel_name(panel_obj.objectName())
        if not action:
            return
        panel_name = panel_obj.objectName()
        # Disconnect previous connection for this panel if we rebuilt the main widget
        existing = self._view_action_connections.get(panel_name)
        if existing is not None:
            try:
                QtCore.QObject.disconnect(existing)
            except (RuntimeError, TypeError):
                pass
        conn = action.triggered.connect(
            lambda checked, name=panel_name: self._on_view_toggled_for_panel_by_name(checked, name)
        )
        self._view_action_connections[panel_name] = conn

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

    def _all_visible_non_project_panels_collapsed(self):
        """Return True if every visible non-Project panel is minimized (collapsed)."""
        vbox = self.centralWidget().layout()
        if vbox is None:
            return False
        for i in range(vbox.count()):
            item = vbox.itemAt(i)
            w = item.widget() if item else None
            if w and isinstance(w, Panel) and w.objectName() in ('Assets', 'Apps', 'Services', 'Tasks'):
                if w.visibility and not w.minimized:
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
        """Save the panel minimized state to QSettings and update stretch so collapsed panels stack at bottom."""
        self._settings.setValue(f'view/{panel_name.lower()}_minimized', minimized)
        self._update_panel_stack_layout()

    def _on_view_toggled_for_panel(self, checked, panel_obj):
        """Handle View submenu toggle: show/hide panel and update layout."""
        panel_obj.visibility = checked
        self._update_panel_stack_layout()

    def _on_view_toggled_for_panel_by_name(self, checked, panel_name):
        """Handle View submenu toggle by panel name; finds current panel so we never touch a deleted widget."""
        widget = self.centralWidget()
        if not widget:
            return
        panel = widget.findChild(Panel, panel_name)
        if panel is not None:
            panel.visibility = checked
            self._update_panel_stack_layout()

    def _update_panel_stack_layout(self):
        """When all non-Project panels are hidden or all visible ones are collapsed, add top stretch
        so Project and collapsed panels stack in the lower right corner.
        """
        vbox = self.centralWidget().layout()
        if vbox is None:
            return
        need_stretch = (
            self._all_non_project_panels_hidden()
            or self._all_visible_non_project_panels_collapsed()
        )
        if need_stretch and not self._panel_stack_has_top_stretch:
            vbox.insertStretch(0, 1)
            self._panel_stack_has_top_stretch = True
        elif not need_stretch and self._panel_stack_has_top_stretch:
            item = vbox.takeAt(0)
            if item:
                del item
            self._panel_stack_has_top_stretch = False
            
    def _restore_assets_panel_path(self) -> None:
        """Restore the Assets panel view to the saved path for the current project."""
        if not self.current_project or not self._assets_view_container:
            return
        path = self._config.user.assets_panel_path.get(self.current_project.name) or []
        if not path:
            return
        container = self._assets_view_container
        for name in path:
            children = {c['name']: c for c in container.get_immediate_children()}
            if name not in children or not children[name].get('is_collection'):
                break
            container = Collection(name, container)
        self._assets_view_container = container

    def _save_assets_panel_path(self) -> None:
        """Save the current Assets panel view path to user config."""
        if not self.current_project or not self._assets_view_container:
            return
        if self._assets_view_container.parent is None:
            path = []
        else:
            segments = []
            c = self._assets_view_container
            while c is not None and c.parent is not None:
                segments.append(c.name)
                c = c.parent
            path = list(reversed(segments))
        self._config.user.assets_panel_path[self.current_project.name] = path
        try:
            self._config.user.save()
        except OSError as err:
            log.warning("Could not save Assets panel path to user config: %s", err)

    def _load_assets_to_panel(self, assets_panel):
        """Populate the Assets panel from the current view container (Project or Collection)."""
        if not assets_panel:
            return
        container = self._assets_view_container
        if container is None or container.parent is None:
            assets_panel.set_title('Project')
            assets_panel.set_show_navigate_up(False)
        else:
            assets_panel.set_title(container.name)
            assets_panel.set_show_navigate_up(True)

        assets_panel._items.clear()
        assets_panel._relayout_tiles()

        if container is None:
            return

        for child in container.get_immediate_children():
            item_data = {
                'name': child['name'],
                'type': child['type'],
                'description': child.get('description', ''),
                'title': child.get('title', ''),
                'is_collection': child.get('is_collection', False),
            }
            assets_panel.add_item_tile(item_data)

    def _on_asset_panel_item_activated(self, item_data):
        """When a tile is double-clicked: if it is a collection, navigate into it."""
        if not item_data.get('is_collection'):
            return
        container = self._assets_view_container
        if container is None:
            return
        name = (item_data or {}).get('name', '').strip()
        if not name:
            return
        self._assets_view_container = Collection(name, container)
        assets_panel = self.centralWidget().findChild(Panel, 'Assets') if self.centralWidget() else None
        if assets_panel:
            self._load_assets_to_panel(assets_panel)
        self._save_assets_panel_path()

    def _on_assets_navigate_up(self):
        """Move the Assets panel view up one level in the hierarchy."""
        container = self._assets_view_container
        if container is None or container.parent is None:
            return
        self._assets_view_container = container.parent
        assets_panel = self.centralWidget().findChild(Panel, 'Assets') if self.centralWidget() else None
        if assets_panel:
            self._load_assets_to_panel(assets_panel)
        self._save_assets_panel_path()

    def _on_asset_removed(self, item_data):
        """Remove the asset/collection from the parent's USD metadata, archive its directory, and reload the panel."""
        if not item_data or not self._assets_view_container:
            return
        name = (item_data or {}).get('name', '').strip()
        if not name:
            return
        container = self._assets_view_container
        proj = container.project
        child_prim_path = f"{container.prim_path}/{name}"
        asset_dir = Path(proj.asset_directory_for_prim_path(child_prim_path)).resolve()

        # Move all contents of asset root into archive/ (warn if archive would be overwritten)
        if asset_dir.is_dir():
            to_move = [p for p in asset_dir.iterdir() if p.name != "archive"]
            if to_move:
                archive_dir = asset_dir / "archive"
                existing_in_archive = set(archive_dir.iterdir()) if archive_dir.exists() else []
                existing_names = {p.name for p in existing_in_archive}
                conflicts = [p.name for p in to_move if p.name in existing_names]
                if conflicts:
                    msg = (
                        "The following items in the archive folder would be overwritten:\n\n"
                        + "\n".join(conflicts)
                        + "\n\nContinue and overwrite?"
                    )
                    box = QtWidgets.QMessageBox(self)
                    box.setWindowTitle("Archive overwrite")
                    box.setText(msg)
                    box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
                    box.setStandardButtons(
                        QtWidgets.QMessageBox.StandardButton.Cancel | QtWidgets.QMessageBox.StandardButton.Ok
                    )
                    box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Cancel)
                    if box.exec() != QtWidgets.QMessageBox.StandardButton.Ok:
                        return
                try:
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    for p in to_move:
                        dest = asset_dir / "archive" / p.name
                        shutil.move(str(p), str(dest))
                    log.info("Archived %s items from %s into archive/", len(to_move), asset_dir)
                except OSError as err:
                    log.error("Failed to archive asset directory %s: %s", asset_dir, err)
                    self.show_message(
                        "Archive failed",
                        f"Could not move contents to archive: {err}",
                        icon=QtWidgets.QSystemTrayIcon.Critical,
                    )
                    return

        try:
            if container.remove_child(name):
                assets_panel = self.centralWidget().findChild(Panel, 'Assets') if self.centralWidget() else None
                if assets_panel:
                    self._load_assets_to_panel(assets_panel)
            else:
                log.warning("Could not remove child %r from parent USDA.", name)
        except Exception as err:
            log.error("Failed to remove asset from parent collection USDA: %s", err)
            log.exception(err)

    def _on_assets_panel_file_dropped(self, paths):
        """When files from outside the project are dropped on the Assets panel, open Create Asset dialog."""
        if not paths or not self.current_project:
            return
        project_root = Path(self.current_project.rootdir).resolve()
        for p in paths:
            path = Path(p)
            if not path.is_file():
                continue
            try:
                path_resolved = path.resolve()
                path_resolved.relative_to(project_root)
                continue
            except (OSError, ValueError):
                pass
            self._pending_drop_file_path = str(path)
            initial_name = _sanitize_prim_name(path.stem) or path.stem or 'asset'
            assets_panel = self.centralWidget().findChild(Panel, 'Assets') if self.centralWidget() else None
            parent_for_dlg = assets_panel._scroll_area if assets_panel and assets_panel._scroll_area else self
            dlg = AddItemDialog('Asset', parent=parent_for_dlg, initial_name=initial_name)
            dlg.item_created.connect(self._on_asset_created)
            if parent_for_dlg and hasattr(parent_for_dlg, 'geometry'):
                rect = parent_for_dlg.geometry()
                dlg_rect = dlg.geometry()
                pt = QtCore.QPoint(
                    (rect.width() / 2) - (dlg_rect.width() / 2),
                    (rect.height() / 2) - (dlg_rect.height() / 2)
                )
                dlg.move(parent_for_dlg.mapToGlobal(pt))
            dlg.exec()
            return

    def _on_asset_created(self, asset_info):
        """Handle the creation of the asset in the asset library and in project USD metadata."""
        if not self.current_project:
            return
        if not self._asset_library:
            self._asset_library = Project.find_or_create(
                self.current_project.name,
                self.current_project.rootdir,
                prim_name=getattr(self.current_project, 'prim_name', None),
            )
            self._assets_view_container = self._asset_library
        container = self._assets_view_container or self._asset_library
        if container is None:
            return
        name = (asset_info or {}).get('name', '').strip()
        if not name:
            return
        asset_type = (asset_info or {}).get('type', 'Asset')
        try:
            if asset_type in _COLLECTION_ASSET_TYPES:
                container.add_collection(name)
            else:
                container.add_asset(name)
        except ValueError as e:
            log.warning("Could not add asset to project metadata: %s", e)
            self.show_message(
                "Invalid asset name",
                str(e) + "\n\nUse only letters, numbers, and underscores; must not start with a number.",
                icon=QtWidgets.QSystemTrayIcon.Warning,
            )
            return
        assets_panel = self.centralWidget().findChild(Panel, 'Assets') if self.centralWidget() else None
        if assets_panel:
            self._load_assets_to_panel(assets_panel)

        pending = getattr(self, '_pending_drop_file_path', None)
        if pending and container and name:
            self._pending_drop_file_path = None
            asset_dir = container.project.asset_directory_for_prim_path(f"{container.prim_path}/{name}")
            try:
                asset_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            file_list = _collect_usd_dependencies(pending)
            if file_list:
                root_abs, _ = file_list[0]
                ext = Path(root_abs).suffix or '.usd'
                file_list[0] = (root_abs, f"{name}{ext}")
            dlg = CopyMoveUsdFilesDialog(file_list, parent=self)
            dlg.exec()
            action = dlg.result_action()
            if action == CopyMoveUsdFilesDialog.CancelAction:
                return
            try:
                if action == CopyMoveUsdFilesDialog.CopyAction:
                    for src, rel in file_list:
                        dest = asset_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)
                        log.info("Copied %s to %s", src, dest)
                else:
                    for src, rel in sorted(file_list, key=lambda x: -len(x[1].split('/'))):
                        dest = asset_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(src, dest)
                        log.info("Moved %s to %s", src, dest)
            except OSError as err:
                log.error("Failed to copy/move files: %s", err)
                self.show_message("File operation failed", str(err), icon=QtWidgets.QSystemTrayIcon.Critical)

    def _on_asset_dropped_on_app(self, asset_data, app_data):
        """Launch the app with the USD file in the asset's root directory (e.g. .../Characters/Monsters/Kitchen_set/Kitchen_set.usd)."""
        command = (app_data or {}).get('command', '').strip()
        if not command:
            log.warning("App item has no command; cannot launch with asset.")
            return
        container = self._assets_view_container
        if not container:
            log.warning("No asset view container; cannot resolve asset path.")
            return
        asset_name = (asset_data or {}).get('name', '').strip() or 'asset'
        proj = container.project
        child_prim_path = f"{container.prim_path}/{asset_name}"
        asset_dir = proj.asset_directory_for_prim_path(child_prim_path)
        usd_file = _first_usd_file_in_directory(asset_dir, asset_name)
        if usd_file is None:
            log.warning("No USD file (.usda, .usd, .usdc, .usdz) found in asset directory: %s", asset_dir)
            self.show_message("No USD file", f"No USD file found in {asset_dir}.", icon=QtWidgets.QSystemTrayIcon.Warning)
            return
        arg = str(usd_file.resolve())
        argv, use_env = self._parse_python_launch(command)
        if argv is not None:
            argv = argv + [arg]
            kwargs = {'env': os.environ.copy()} if use_env else {}
            try:
                subprocess.Popen(argv, **kwargs)
                log.info("Launched app with asset USD path %s: %s", arg, command)
            except Exception as err:
                log.error("Failed to launch app with asset: %s", err)
                self.show_message("Launch failed", str(err), icon=QtWidgets.QSystemTrayIcon.Critical)
            return
        try:
            safe_arg = shlex.quote(arg)
            subprocess.Popen(f"{command} {safe_arg}", shell=True)
            log.info("Launched app with asset USD path %s: %s", arg, command)
        except Exception as err:
            log.error("Failed to launch app with asset: %s", err)
            self.show_message("Launch failed", str(err), icon=QtWidgets.QSystemTrayIcon.Critical)

    def _on_asset_dropped_on_service(self, asset_data, service_data):
        """Open the service URL with the dropped asset as a query parameter."""
        url = (service_data or {}).get('url', '').strip()
        if not url:
            log.warning("Service item has no URL; cannot open with asset.")
            return
        asset_name = (asset_data or {}).get('name', '').strip() or 'asset'
        try:
            parsed = list(urlparse(url))
            query = parse_qs(parsed[4])
            query['asset'] = [asset_name]
            parsed[4] = urlencode(query, doseq=True)
            open_url = urlunparse(parsed)
        except Exception:
            open_url = f"{url}?asset={asset_name}" if '?' not in url else f"{url}&asset={asset_name}"
        try:
            webbrowser.open(open_url)
            log.info(f"Opened service with asset '{asset_name}': {url}")
        except Exception as err:
            log.error(f"Failed to open service with asset: {err}")
            self.show_message("Open failed", str(err), icon=QtWidgets.QSystemTrayIcon.Critical)

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
            # Get layer information for this app
            layer_name, is_writable = self._config.get_app_layer_info(app_config.name)
            item_data = {
                'name': app_config.name,
                'type': 'Command',
                'description': '',
                'command': app_config.command,
                'layer': layer_name,  # 'site', 'user', or 'project'
                'is_writable': is_writable,  # True if the layer's config file is writable
            }
            if app_config.icon_path:
                item_data['icon'] = app_config.icon_path
            apps_panel.add_item_tile(item_data)
            count += 1

        log.debug("Loaded %d apps from config layers (site + user + project)", count)

    def _load_services_to_panel(self, services_panel):
        """Load services from site (studio), user, and project config layers into the Services panel.
        Later layers override earlier when the same service name exists.
        """
        if not services_panel:
            return

        merged = self._config.get_merged_services()

        # Clear existing items in the panel
        services_panel._items.clear()
        services_panel._relayout_tiles()

        count = 0
        for service_config in merged:
            if not service_config.enabled:
                continue
            # Get layer information for this service
            layer_name, is_writable = self._config.get_service_layer_info(service_config.name)
            item_data = {
                'name': service_config.name,
                'type': 'Service',
                'description': service_config.url or '',
                'url': service_config.url,
                'params': service_config.params or [],
                'layer': layer_name,  # 'site', 'user', or 'project'
                'is_writable': is_writable,  # True if the layer's config file is writable
            }
            services_panel.add_item_tile(item_data)
            count += 1

        log.debug("Loaded %d services from config layers (site + user + project)", count)

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

    def _on_service_created(self, service_info):
        """Handle the creation of a service and save it to the project config."""
        if not self.current_project:
            log.warning("Cannot save service: no current project")
            return
        
        # Convert item dict to ServiceConfig
        service_name = service_info.get('name', 'Untitled')
        url = service_info.get('url', '')
        params = service_info.get('params', [])
        
        # Do not add if a service with the same name already exists
        existing_names = {s.name for s in self.current_project.services}
        if service_name in existing_names:
            log.warning(f"Service '{service_name}' already exists in project config; not adding duplicate.")
            return

        # Create ServiceConfig with required fields
        service_config = ServiceConfig(
            name=service_name,
            enabled=True,  # New services are enabled by default
            url=url,
            params=params if params else []
        )

        # Add to project config services list
        self.current_project.services.append(service_config)

        # Save the project config
        try:
            self.current_project.save()
            log.info(f"Saved service '{service_name}' to project config")
        except Exception as err:
            log.error(f"Failed to save service to project config: {err}")

    def _on_service_updated(self, item_index, updated_data):
        """Handle the update of a service and persist to the project config (by name).
        Panel order is merged (site + user + project), so we find or add by name in project.
        """
        if not self.current_project:
            log.warning("Cannot update service: no current project")
            return

        service_name = updated_data.get('name', '').strip() or 'Untitled'
        url = updated_data.get('url', '')
        params = updated_data.get('params', [])

        # Find service by name in project config (service may have come from site/user layer)
        service_config = None
        for s in self.current_project.services:
            if s.name == service_name:
                service_config = s
                break

        if service_config is None:
            # Service came from site or user; add project-level override
            service_config = ServiceConfig(
                name=service_name,
                enabled=True,
                url=url,
                params=params if params else []
            )
            self.current_project.services.append(service_config)
        else:
            service_config.url = url
            service_config.params = params if params else []

        try:
            self.current_project.save()
            log.info("Updated service '%s' in project config", service_name)
        except Exception as err:
            log.error("Failed to update service in project config: %s", err)

    def _on_app_removed(self, item_data):
        """Handle the removal of an app and delete it from the project config."""
        if not self.current_project:
            log.warning("Cannot remove app: no current project")
            return
        
        app_name = item_data.get('name', '').strip()
        if not app_name:
            return

        # Find and remove app by name from project config
        removed = False
        for i, app_config in enumerate(self.current_project.apps):
            if app_config.name == app_name:
                self.current_project.apps.pop(i)
                removed = True
                break

        if removed:
            try:
                self.current_project.save()
                log.info(f"Removed app '{app_name}' from project config")
                # Reload the apps panel to reflect the change
                widget = self.centralWidget()
                if widget:
                    apps_panel = widget.findChild(Panel, 'Apps')
                    if apps_panel:
                        self._load_apps_to_panel(apps_panel)
            except Exception as err:
                log.error(f"Failed to remove app from project config: {err}")
        else:
            log.warning(f"App '{app_name}' not found in project config (may be from site/user layer)")

    def _on_service_removed(self, item_data):
        """Handle the removal of a service and delete it from the project config."""
        if not self.current_project:
            log.warning("Cannot remove service: no current project")
            return
        
        service_name = item_data.get('name', '').strip()
        if not service_name:
            return

        # Find and remove service by name from project config
        removed = False
        for i, service_config in enumerate(self.current_project.services):
            if service_config.name == service_name:
                self.current_project.services.pop(i)
                removed = True
                break

        if removed:
            try:
                self.current_project.save()
                log.info(f"Removed service '{service_name}' from project config")
                # Reload the services panel to reflect the change
                widget = self.centralWidget()
                if widget:
                    services_panel = widget.findChild(Panel, 'Services')
                    if services_panel:
                        self._load_services_to_panel(services_panel)
            except Exception as err:
                log.error(f"Failed to remove service from project config: {err}")
        else:
            log.warning(f"Service '{service_name}' not found in project config (may be from site/user layer)")
    
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

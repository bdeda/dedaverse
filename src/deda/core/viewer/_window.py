
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
"""Main window and viewer widget for USD scene display."""

import sys
from pathlib import Path

sys.path.insert(0, r'C:\Program Files\Wing Pro 10')
import wingdbstub

from pxr import Usd, UsdUtils

from PySide6 import QtWidgets, QtCore, QtGui

from pxr.Usdviewq.common import CameraMaskModes

from ._usd_viewer import UsdViewWidget

from . import _annotation
from . import _playbar
from . import _reticle
from . import _slate

# Directory containing HDR/EXR environment textures for the dome light
HDR_IMAGES_DIR = Path(r'F:\hdri')

# Default FPS when stage does not explicitly set timeCodesPerSecond
_DEFAULT_FPS = 24

# QSettings keys for persisted view options
_SETTINGS_ORG = 'DedaFX'
_SETTINGS_APP = 'DedaverseViewer'
_KEY_DOME_LIGHT = 'view/domeLightEnabled'
_KEY_MASK_OPAQUE = 'view/maskOpaque'
_KEY_SHOW_HUD = 'view/showHUD'
_KEY_SHOW_BBOXES = 'view/showBBoxes'
_KEY_ASPECT_LOCKED = 'view/aspectRatioLocked'
_KEY_ASPECT_RATIO = 'view/aspectRatio'
_KEY_ENV_TEXTURE = 'view/environmentTexturePath'
_KEY_GEOMETRY = 'window/geometry'
_KEY_RECENT_FILES = 'file/recentFiles'

_MAX_RECENT_FILES = 10


class MainWindow(QtWidgets.QMainWindow):
    """This is the main window class for the dedaverse viewer.
    
    This will contain the Hydra viewport 3d view from usdviewq.
    It will add a camera reticle with view options, a slate overlay that can be toggled on or off,
    a way to playback and scrub the animation, 
    and subtools to interact with the contents of the scene.
    
    """
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self._settings = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._env_texture_path = None  # Track selected environment texture for persistence
        self._recent_files = self._load_recent_files()
        
        self.setWindowTitle('Dedaverse')
        
        w = QtWidgets.QWidget(parent=self)
        self.setCentralWidget(w)
        
        vbox = QtWidgets.QVBoxLayout()
        w.setLayout(vbox)
        
        self._viewer = UsdViewWidget(stage=None, parent=self)
        vbox.addWidget(self._viewer, 1)
        
        self._playbar = _playbar.Playbar(parent=self)
        self._playbar.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed
        )
        self._playbar.frameChanged.connect(self._on_playbar_frame_changed)
        self._playbar.playClicked.connect(self._on_play_clicked)
        self._playbar.stopClicked.connect(self._on_stop_clicked)
        vbox.addWidget(self._playbar, 0)
        
        self._play_timer = QtCore.QTimer(self)
        self._play_timer.timeout.connect(self._on_play_tick)
        
        self._build_menu_bar()
        self._restore_view_settings()
        self._restore_geometry()

    def _build_menu_bar(self):
        """Create the main menu bar and menus."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('&File')
        open_action = file_menu.addAction('&Open...')
        open_action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_file)
        self._recent_files_menu = file_menu.addMenu('Recent &Files')
        self._update_recent_files_menu()
        view_menu = menu_bar.addMenu('&View')
        frame_all_action = view_menu.addAction('Frame &All')
        frame_all_action.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F))
        frame_all_action.triggered.connect(self._on_frame_all)
        self._dome_light_action = view_menu.addAction('&Dome Light')
        self._dome_light_action.setCheckable(True)
        self._dome_light_action.setChecked(self._viewer.viewSettings.domeLightEnabled)
        self._dome_light_action.triggered.connect(self._on_dome_light_toggled)
        self._mask_opaque_action = view_menu.addAction('&Opaque Mask')
        self._mask_opaque_action.setCheckable(True)
        self._mask_opaque_action.setChecked(
            self._viewer.viewSettings.cameraMaskMode == CameraMaskModes.FULL
        )
        self._mask_opaque_action.triggered.connect(self._on_mask_opaque_toggled)
        self._show_hud_action = view_menu.addAction('Show &HUD')
        self._show_hud_action.setCheckable(True)
        self._show_hud_action.setChecked(self._viewer.viewSettings.showHUD)
        self._show_hud_action.triggered.connect(self._on_show_hud_toggled)
        self._show_bboxes_action = view_menu.addAction('Show &BBoxes')
        self._show_bboxes_action.setCheckable(True)
        self._show_bboxes_action.setChecked(self._viewer.viewSettings.showBBoxes)
        self._show_bboxes_action.triggered.connect(self._on_show_bboxes_toggled)
        view_menu.addSeparator()
        self._build_aspect_ratio_submenu(view_menu)
        self._build_environment_texture_submenu(view_menu)

    def _build_aspect_ratio_submenu(self, view_menu):
        """Add submenu to select view aspect ratio."""
        aspect_menu = view_menu.addMenu('&Aspect Ratio')
        unlock_action = aspect_menu.addAction('&Unlock (Fill Window)')
        unlock_action.triggered.connect(lambda: self._on_set_aspect_ratio(None, None))
        aspect_menu.addSeparator()
        for label, w, h in [
            ('16:9 (Widescreen)', 16, 9),
            ('21:9 (Ultrawide)', 21, 9),
            ('4:3 (Standard)', 4, 3),
            ('3:2', 3, 2),
            ('1:1 (Square)', 1, 1),
        ]:
            action = aspect_menu.addAction(label)
            action.triggered.connect(
                (lambda wr, hr: lambda: self._on_set_aspect_ratio(wr, hr))(w, h)
            )

    def _on_set_aspect_ratio(self, width_ratio, height_ratio):
        """Set the view aspect ratio."""
        self._viewer.set_fixed_aspect_ratio(width_ratio, height_ratio)
        # Sync Opaque Mask menu when aspect ratio changes (FULL when ratio set, NONE when unlocked)
        if width_ratio is not None and height_ratio is not None:
            self._mask_opaque_action.setChecked(True)

    def _save_view_settings(self):
        """Persist view options to QSettings."""
        s = self._settings
        s.setValue(_KEY_DOME_LIGHT, self._viewer.viewSettings.domeLightEnabled)
        s.setValue(
            _KEY_MASK_OPAQUE,
            self._viewer.viewSettings.cameraMaskMode == CameraMaskModes.FULL
        )
        s.setValue(_KEY_SHOW_HUD, self._viewer.viewSettings.showHUD)
        s.setValue(_KEY_SHOW_BBOXES, self._viewer.viewSettings.showBBoxes)
        vs = self._viewer.viewSettings
        s.setValue(_KEY_ASPECT_LOCKED, vs.lockFreeCameraAspect)
        s.setValue(
            _KEY_ASPECT_RATIO,
            vs.freeCameraAspect if vs.lockFreeCameraAspect else 0.0
        )
        s.setValue(_KEY_ENV_TEXTURE, self._env_texture_path or '')
        s.setValue(_KEY_GEOMETRY, self.saveGeometry())
        s.setValue(_KEY_RECENT_FILES, self._recent_files)

    def _restore_view_settings(self):
        """Restore view options from QSettings."""
        s = self._settings
        # Dome light
        if s.contains(_KEY_DOME_LIGHT):
            enabled = s.value(_KEY_DOME_LIGHT, True, type=bool)
            self._viewer.set_dome_light_enabled(enabled)
            self._dome_light_action.setChecked(enabled)
        # Mask opacity
        if s.contains(_KEY_MASK_OPAQUE):
            opaque = s.value(_KEY_MASK_OPAQUE, True, type=bool)
            self._viewer.viewSettings.cameraMaskMode = (
                CameraMaskModes.FULL if opaque else CameraMaskModes.PARTIAL
            )
            self._mask_opaque_action.setChecked(opaque)
        # Show HUD
        if s.contains(_KEY_SHOW_HUD):
            show = s.value(_KEY_SHOW_HUD, True, type=bool)
            self._viewer.viewSettings.showHUD = show
            self._show_hud_action.setChecked(show)
        # Show BBoxes
        if s.contains(_KEY_SHOW_BBOXES):
            show = s.value(_KEY_SHOW_BBOXES, True, type=bool)
            self._viewer.viewSettings.showBBoxes = show
            self._show_bboxes_action.setChecked(show)
        # Aspect ratio (restore after mask opacity so opaque preference is preserved)
        if s.contains(_KEY_ASPECT_LOCKED) and s.contains(_KEY_ASPECT_RATIO):
            locked = s.value(_KEY_ASPECT_LOCKED, False, type=bool)
            ar = s.value(_KEY_ASPECT_RATIO, 0.0, type=float)
            if locked and ar > 0:
                vs = self._viewer.viewSettings
                vs.lockFreeCameraAspect = True
                vs.freeCameraAspect = ar
                # Use saved opaque mask preference; if not yet restored, default to FULL
                opaque = (
                    s.value(_KEY_MASK_OPAQUE, True, type=bool)
                    if s.contains(_KEY_MASK_OPAQUE)
                    else True
                )
                vs.cameraMaskMode = (
                    CameraMaskModes.FULL if opaque else CameraMaskModes.PARTIAL
                )
                self._mask_opaque_action.setChecked(opaque)
                self._viewer.update_view(resetCam=False, forceComputeBBox=False)
        # Environment texture
        if s.contains(_KEY_ENV_TEXTURE):
            path = s.value(_KEY_ENV_TEXTURE, '', type=str)
            if path and Path(path).exists():
                self._env_texture_path = path
                self._viewer.set_dome_light_texture(path)

    def _restore_geometry(self):
        """Restore window geometry (position and size) from QSettings."""
        geom = self._settings.value(_KEY_GEOMETRY)
        if geom:
            self.restoreGeometry(geom)

    def _build_environment_texture_submenu(self, view_menu):
        """Add submenu to select dome light environment texture from D:\\hdr_images."""
        env_menu = view_menu.addMenu('&Environment Texture')
        clear_action = env_menu.addAction('&Clear (Default)')
        clear_action.triggered.connect(lambda: self._on_set_environment_texture(None))
        env_menu.addSeparator()
        if HDR_IMAGES_DIR.is_dir():
            textures = sorted(
                list(HDR_IMAGES_DIR.glob('*.exr')) + list(HDR_IMAGES_DIR.glob('*.hdr'))
            )
            for tex_path in textures:
                action = env_menu.addAction(tex_path.stem)
                action.triggered.connect(
                    (lambda p: lambda: self._on_set_environment_texture(p))(tex_path)
                )
        else:
            no_textures = env_menu.addAction('(No textures found)')
            no_textures.setEnabled(False)

    def _on_set_environment_texture(self, texture_path):
        """Set the dome light environment texture."""
        self._env_texture_path = str(texture_path) if texture_path else None
        self._viewer.set_dome_light_texture(self._env_texture_path)

    def _load_recent_files(self):
        """Load recent files list from QSettings."""
        paths = self._settings.value(_KEY_RECENT_FILES, [])
        if isinstance(paths, str):
            paths = [paths] if paths else []
        return paths[:] if paths else []

    def _save_recent_files(self):
        """Save recent files list to QSettings."""
        self._settings.setValue(_KEY_RECENT_FILES, self._recent_files)

    def _add_to_recent_files(self, file_path):
        """Add file to recent list (front), remove duplicates, limit to _MAX_RECENT_FILES."""
        path = str(Path(file_path).resolve())
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:_MAX_RECENT_FILES]
        self._save_recent_files()
        self._update_recent_files_menu()

    def _update_recent_files_menu(self):
        """Rebuild the Recent Files submenu from _recent_files."""
        self._recent_files_menu.clear()
        for path in self._recent_files:
            action = self._recent_files_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(
                (lambda p: lambda: self._on_open_recent_file(p))(path)
            )

    def _on_open_recent_file(self, file_path):
        """Open a USD file from the recent files list."""
        path = Path(file_path)
        if not path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                'Open Failed',
                f'File no longer exists:\n{file_path}'
            )
            self._recent_files = [p for p in self._recent_files if Path(p).exists()]
            self._save_recent_files()
            self._update_recent_files_menu()
            return
        self._open_stage_file(str(path))

    def _open_stage_file(self, file_path):
        """Load a USD stage from file_path and update the viewer. Used by Open and Recent Files."""
        try:
            stage = Usd.Stage.Open(file_path)
            if stage:
                self._play_timer.stop()
                self._viewer.stage = stage
                self.setWindowTitle(f'Asset Viewer - {Path(file_path).name}')
                start_frame = int(stage.GetStartTimeCode())
                end_frame = int(stage.GetEndTimeCode())
                if end_frame <= start_frame:
                    start_frame, end_frame = 0, max(100, start_frame + 1)
                self._playbar.setFrameRange(start_frame, end_frame)
                self._playbar.setFrame(start_frame)
                self._viewer.set_dome_light_texture(self._env_texture_path)
                self._add_to_recent_files(file_path)
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Open Failed',
                    f'Could not open USD file:\n{file_path}'
                )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Open Failed',
                f'Could not open USD file:\n{file_path}\n\n{e}'
            )

    def _on_open_file(self):
        """Open a file dialog and load the selected USD stage."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Open USD File',
            '',
            'USD Files (*.usd *.usda *.usdc *.usdz);;All Files (*)'
        )
        if file_path:
            self._open_stage_file(file_path)

    def _on_playbar_frame_changed(self, frame):
        """Sync the stage view to the playbar's current frame."""
        self._viewer.set_current_frame(frame)

    def _get_stage_fps(self):
        """Return the stage's frames per second, or _DEFAULT_FPS if not set."""
        stage = self._viewer.stage
        if not stage:
            return _DEFAULT_FPS
        fps = stage.GetTimeCodesPerSecond()
        return _DEFAULT_FPS if not fps or fps <= 0 else fps

    def _on_play_clicked(self):
        """Start playback at the stage's FPS."""
        self._play_timer.stop()
        fps = self._get_stage_fps()
        interval_ms = max(1, int(1000.0 / fps))
        self._play_timer.start(interval_ms)

    def _on_stop_clicked(self):
        """Stop playback."""
        self._play_timer.stop()

    def _on_play_tick(self):
        """Advance playbar by one frame; loop to first frame when reaching the end."""
        frame_min, frame_max = self._playbar.frameRange()
        current = self._playbar.frame()
        if current >= frame_max:
            self._playbar.setFrame(frame_min)
        else:
            self._playbar.setFrame(current + 1)

    def _on_frame_all(self):
        """Frame the view to fit all geometry."""
        self._viewer.update_view(resetCam=True, forceComputeBBox=True)

    def _on_dome_light_toggled(self):
        """Enable or disable the stage view dome light based on menu check state."""
        self._viewer.set_dome_light_enabled(self._dome_light_action.isChecked())

    def _on_mask_opaque_toggled(self):
        """Toggle camera mask opacity: checked = opaque (FULL), unchecked = semi-transparent (PARTIAL)."""
        vs = self._viewer.viewSettings
        vs.cameraMaskMode = (
            CameraMaskModes.FULL if self._mask_opaque_action.isChecked()
            else CameraMaskModes.PARTIAL
        )
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)

    def _on_show_hud_toggled(self):
        """Show or hide the HUD overlay (camera, renderer, performance info)."""
        self._viewer.viewSettings.showHUD = self._show_hud_action.isChecked()
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)

    def _on_show_bboxes_toggled(self):
        """Show or hide bounding boxes in the stage view."""
        self._viewer.viewSettings.showBBoxes = self._show_bboxes_action.isChecked()
        self._viewer.update_view(resetCam=False, forceComputeBBox=True)

    def closeEvent(self, event):
        self._save_view_settings()
        self._viewer.closeEvent(event)
        super().closeEvent(event)
        
    

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

import getpass
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from pxr import Usd, UsdUtils

from PySide6 import QtWidgets, QtCore, QtGui

from pxr.Usdviewq.common import CameraMaskModes

from deda.core.types import Element, Project

from ._usd_viewer import UsdViewWidget

from . import _annotation
from . import _playbar
from . import _reticle
from . import _slate

log = logging.getLogger(__name__)

# Fallback HDR directory when project has none set (e.g. viewer run without project)
_DEFAULT_HDR_IMAGES_DIR = Path(r'F:\hdri')


def _get_hdr_images_dir() -> Path:
    """Return the directory for HDR/environment textures (from project config or default)."""
    try:
        from deda.core import LayeredConfig
        config = LayeredConfig.instance()
        proj = config.current_project if config else None
        if proj and getattr(proj, 'hdr_images_dir', None):
            p = Path(proj.hdr_images_dir)
            if p.is_dir():
                return p
    except Exception:
        pass
    return _DEFAULT_HDR_IMAGES_DIR


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
_KEY_RETICLE_ENABLED = 'view/reticleEnabled'
_KEY_RETICLE_STYLE = 'view/reticleStyle'
_KEY_SLATE_ENABLED = 'view/slateEnabled'

_MAX_RECENT_FILES = 10


def _flatten_camera_transform(camera: list) -> list[float] | None:
    """Return a flat list of 16 floats (row-major 4x4) from notes payload camera_transform.
    Accepts either a flat list of 16 or a 4x4 nested list.
    """
    if not camera or not isinstance(camera, list):
        return None
    try:
        if len(camera) == 16 and all(isinstance(x, (int, float)) for x in camera):
            return [float(x) for x in camera]
        if len(camera) == 4 and all(isinstance(r, list) and len(r) == 4 for r in camera):
            return [float(camera[i][j]) for i in range(4) for j in range(4)]
    except (TypeError, IndexError):
        pass
    return None


class LoadingOverlay(QtWidgets.QWidget):
    """Semi-transparent overlay with a spinning indicator for loading state."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self._angle_deg = 0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self._angle_deg = 0
        self._timer.start(50)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        self._angle_deg = (self._angle_deg + 30) % 360
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        # Semi-transparent background
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 120))
        # Spinning arc at center
        side = min(self.width(), self.height()) // 4
        x = (self.width() - side) // 2
        y = (self.height() - side) // 2
        rect = QtCore.QRect(x, y, side, side)
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 220))
        pen.setWidth(max(2, side // 16))
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        start_angle = 90 - self._angle_deg
        span_angle = 270
        painter.drawArc(rect, start_angle * 16, span_angle * 16)


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
        self._opened_entity = None  # Project/Collection/Asset from Project.from_path when a file is opened
        
        self.setWindowTitle('Dedaverse')
        # Use same star icon as main Dedaverse window (deda.app._main_window)
        from deda.app import _main_window as _app_main_window
        icon_path = Path(_app_main_window.__file__).parent / 'icons' / 'star_icon.png'
        if icon_path.is_file():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        
        w = QtWidgets.QWidget(parent=self)
        self.setCentralWidget(w)
        
        vbox = QtWidgets.QVBoxLayout()
        w.setLayout(vbox)
        
        self._viewer = UsdViewWidget(stage=None, parent=self)
        vbox.addWidget(self._viewer, 1)

        self._loading_overlay = LoadingOverlay(parent=self._viewer)
        self._loading_overlay.raise_()
        self._viewer.installEventFilter(self)

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
        save_notes_action = file_menu.addAction('Save &Notes...')
        save_notes_action.triggered.connect(self._on_save_annotations_to_notes)
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
        self._build_reticle_submenu(view_menu)
        self._slate_layer_action = view_menu.addAction('Slate &Layer')
        self._slate_layer_action.setCheckable(True)
        self._slate_layer_action.setChecked(self._viewer.slate_overlay.enabled)
        self._slate_layer_action.triggered.connect(self._on_slate_layer_toggled)
        self._annotation_layer_action = view_menu.addAction('Annotation &Layer')
        self._annotation_layer_action.setCheckable(True)
        self._annotation_layer_action.setChecked(self._viewer.annotation_overlay.enabled)
        self._annotation_layer_action.triggered.connect(self._on_annotation_layer_toggled)
        annotation_color_action = view_menu.addAction('Annotation &Color...')
        annotation_color_action.triggered.connect(self._on_annotation_color)
        annotation_text_color_action = view_menu.addAction('Annotation &Text Color...')
        annotation_text_color_action.triggered.connect(self._on_annotation_text_color)
        if hasattr(self._viewer, 'annotation_overlay_enabled_changed'):
            self._viewer.annotation_overlay_enabled_changed.connect(self._on_annotation_overlay_enabled_changed)
        self._load_notes_menu = view_menu.addMenu('Load &Notes')
        self._load_notes_menu.aboutToShow.connect(self._populate_load_notes_menu)
        view_menu.addSeparator()
        self._build_aspect_ratio_submenu(view_menu)
        self._build_environment_texture_submenu(view_menu)

    def eventFilter(self, obj, event):
        """Keep loading overlay sized to the viewer when the viewer is resized."""
        if obj is self._viewer and event.type() == QtCore.QEvent.Type.Resize:
            self._loading_overlay.setGeometry(self._viewer.rect())
        return super().eventFilter(obj, event)

    def _show_loading_overlay(self):
        """Show the spinning loading overlay over the viewer."""
        self._loading_overlay.setGeometry(self._viewer.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.show()
        QtWidgets.QApplication.processEvents()

    def _hide_loading_overlay(self):
        """Hide the loading overlay."""
        self._loading_overlay.hide()

    def _build_reticle_submenu(self, view_menu):
        """Add submenu to turn camera reticle on/off and set style. Default off."""
        reticle_menu = view_menu.addMenu('Camera &Reticle')
        self._reticle_enabled_action = reticle_menu.addAction('&Show Reticle')
        self._reticle_enabled_action.setCheckable(True)
        self._reticle_enabled_action.setChecked(False)
        self._reticle_enabled_action.triggered.connect(self._on_reticle_enabled_toggled)
        reticle_menu.addSeparator()
        style_menu = reticle_menu.addMenu('&Style')
        self._reticle_style_actions = {}
        for label, style in [
            ('&Crosshair', 'crosshair'),
            ('&Frame', 'frame'),
            ('&Grid', 'grid'),
        ]:
            action = style_menu.addAction(label)
            action.setCheckable(True)
            action.setData(style)
            action.triggered.connect(
                (lambda s: lambda: self._on_reticle_style_changed(s))(style)
            )
            self._reticle_style_actions[style] = action

    def _on_reticle_enabled_toggled(self):
        """Toggle camera reticle visibility and save to settings."""
        checked = self._reticle_enabled_action.isChecked()
        self._viewer.reticle_overlay.enabled = checked
        self._settings.setValue(_KEY_RETICLE_ENABLED, checked)
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)

    def _on_slate_layer_toggled(self):
        """Toggle slate text overlay and save to settings."""
        checked = self._slate_layer_action.isChecked()
        self._viewer.slate_overlay.enabled = checked
        self._settings.setValue(_KEY_SLATE_ENABLED, checked)
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)

    def _on_annotation_layer_toggled(self):
        """Turn annotation layer on or off from the View menu."""
        checked = self._annotation_layer_action.isChecked()
        self._viewer.annotation_overlay.enabled = checked
        if not checked:
            self._viewer.annotation_mode_enabled = False
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)

    def _on_annotation_overlay_enabled_changed(self, enabled: bool):
        """Keep the Annotation Layer menu option checked when overlay is enabled (e.g. via 'a' key)."""
        self._annotation_layer_action.setChecked(bool(enabled))

    def _on_annotation_color(self):
        """Open color chooser for annotation stroke color."""
        overlay = self._viewer.annotation_overlay
        r, g, b, a = overlay.default_color
        initial = QtGui.QColor(
            int(r * 255), int(g * 255), int(b * 255), int(a * 255)
        )
        color = QtWidgets.QColorDialog.getColor(
            initial, self, "Annotation Stroke Color"
        )
        if color.isValid():
            overlay.default_color = (
                color.redF(), color.greenF(), color.blueF(), color.alphaF()
            )

    def _on_annotation_text_color(self):
        """Open color chooser for annotation text color."""
        overlay = self._viewer.annotation_overlay
        r, g, b, a = overlay.default_text_color
        initial = QtGui.QColor(
            int(r * 255), int(g * 255), int(b * 255), int(a * 255)
        )
        color = QtWidgets.QColorDialog.getColor(
            initial, self, "Annotation Text Color"
        )
        if color.isValid():
            overlay.default_text_color = (
                color.redF(), color.greenF(), color.blueF(), color.alphaF()
            )
            self._viewer.update_view(resetCam=False, forceComputeBBox=False)

    def _on_reticle_style_changed(self, style):
        """Set reticle style and save to settings. Uncheck other styles."""
        self._viewer.reticle_overlay.style = style
        self._settings.setValue(_KEY_RETICLE_STYLE, style)
        for s, action in self._reticle_style_actions.items():
            action.setChecked(s == style)
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)

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
        s.setValue(_KEY_RETICLE_ENABLED, self._viewer.reticle_overlay.enabled)
        s.setValue(_KEY_RETICLE_STYLE, self._viewer.reticle_overlay.style)
        s.setValue(_KEY_SLATE_ENABLED, self._viewer.slate_overlay.enabled)

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
        # Camera reticle (default off)
        enabled = s.value(_KEY_RETICLE_ENABLED, False, type=bool)
        self._viewer.reticle_overlay.enabled = enabled
        self._reticle_enabled_action.setChecked(enabled)
        style = s.value(_KEY_RETICLE_STYLE, 'crosshair', type=str)
        if style not in ('crosshair', 'frame', 'grid'):
            style = 'crosshair'
        self._viewer.reticle_overlay.style = style
        for st, action in self._reticle_style_actions.items():
            action.setChecked(st == style)
        # Slate layer (default off)
        slate_enabled = s.value(_KEY_SLATE_ENABLED, False, type=bool)
        self._viewer.slate_overlay.enabled = slate_enabled
        self._slate_layer_action.setChecked(slate_enabled)

    def _restore_geometry(self):
        """Restore window geometry (position and size) from QSettings."""
        geom = self._settings.value(_KEY_GEOMETRY)
        if geom:
            self.restoreGeometry(geom)

    def _build_environment_texture_submenu(self, view_menu):
        """Add submenu to select dome light environment texture from project HDR directory."""
        env_menu = view_menu.addMenu('&Environment Texture')
        clear_action = env_menu.addAction('&Clear (Default)')
        clear_action.triggered.connect(lambda: self._on_set_environment_texture(None))
        env_menu.addSeparator()
        hdr_dir = _get_hdr_images_dir()
        if hdr_dir.is_dir():
            textures = sorted(
                list(hdr_dir.glob('*.exr')) + list(hdr_dir.glob('*.hdr'))
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
        try:
            self._show_loading_overlay()
            self._viewer.set_dome_light_texture(self._env_texture_path)
        finally:
            self._hide_loading_overlay()

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
        self._show_loading_overlay()
        self._opened_entity = None
        try:
            stage = Usd.Stage.Open(file_path)
            if stage:
                self._play_timer.stop()
                self._viewer.stage = stage
                # Resolve entity for title (project name) and content rootdir
                self._opened_entity = Project.from_path(file_path)
                project_part = f'[{self._opened_entity.project.name}] ' if self._opened_entity else ''
                self.setWindowTitle(f'Dedaverse - {project_part}{Path(file_path).name}')
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
        finally:
            self._hide_loading_overlay()

    @property
    def opened_entity(self):
        """Project, Collection, or Asset for the currently opened file, or None.

        Set when a file is opened via Project.from_path(file_path). None if the
        opened path is not under a Dedaverse project or resolution failed.
        """
        return self._opened_entity

    @property
    def rootdir(self) -> Path:
        """Content root directory for the opened entity, or empty Path.

        When a Dedaverse asset/project file is opened, this is the entity's
        rootdir (content directory, not metadata). Use for resolving paths as
        we build up surrounding systems. Returns Path() when no entity is open.
        """
        if self._opened_entity is None:
            return Path()
        return Path(self._opened_entity.rootdir)

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

    def _on_save_annotations_to_notes(self):
        """Save annotation strokes and a viewport snapshot to notes/ under the asset root.

        Resolves the opened file as an Element from the stage root layer identifier;
        uses the Element's scope (parent Asset) rootdir for notes. Writes annotations
        as JSON and the current view (with annotations) as PNG for later reference
        and AI model input.
        """
        entity = self.opened_entity
        if entity is None:
            QtWidgets.QMessageBox.warning(
                self,
                'Save Notes',
                'The opened file is not under a Dedaverse project. Open a file from an asset.',
            )
            return
        if isinstance(entity, Element) and entity.scope is not None:
            root = Path(entity.scope.rootdir)
        else:
            root = Path(entity.rootdir)
        if not root or not root.is_dir():
            QtWidgets.QMessageBox.warning(
                self,
                'Save Notes',
                'Could not resolve asset content root for the opened file.',
            )
            return
        notes_dir = root / 'notes'
        try:
            notes_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Save Notes',
                f'Could not create notes directory:\n{notes_dir}\n{e}',
            )
            return
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Prompt for optional extra information to store in the notes JSON
        description, ok = QtWidgets.QInputDialog.getMultiLineText(
            self,
            'Save Notes',
            'Add information for this note (optional). You can describe the feedback, context, or reference for future use:',
            '',
        )
        info = description.strip() if (ok and description) else ''
        overlay = self._viewer.annotation_overlay
        payload = overlay.to_payload()
        if info:
            payload['description'] = info
        camera_transform = self._viewer.get_camera_transform()
        payload['camera_transform'] = camera_transform  # list of 16 floats or None
        if camera_transform is None and self._viewer.stage is not None:
            log.warning(
                'Save Notes: could not read free camera matrix; camera will not be restored when loading these notes.',
            )
        try:
            payload['user'] = getpass.getuser()
        except Exception:
            payload['user'] = ''
        annotations_path = notes_dir / f'annotations_{ts}.json'
        try:
            with open(annotations_path, 'w') as f:
                json.dump(payload, f, indent=2)
        except OSError as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Save Notes',
                f'Could not write notes file:\n{e}',
            )
            return
        snapshot_path = notes_dir / f'snapshot_{ts}.png'
        img = self._viewer.capture_viewport_image()
        if img and not img.isNull():
            try:
                if not img.save(str(snapshot_path)):
                    QtWidgets.QMessageBox.warning(
                        self,
                        'Save Notes',
                        f'Saved notes to {annotations_path} but failed to save PNG to {snapshot_path}.',
                    )
                    return
            except OSError as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Save Notes',
                    f'Saved notes to {annotations_path} but could not save PNG:\n{e}',
                )
                return
        else:
            QtWidgets.QMessageBox.warning(
                self,
                'Save Notes',
                f'Saved notes to {annotations_path} but could not capture viewport image.',
            )
            return
        QtWidgets.QMessageBox.information(
            self,
            'Save Notes',
            f'Saved to {notes_dir}\n  • {annotations_path.name}\n  • {snapshot_path.name}',
        )
        overlay.clear_dirty()

    def _get_notes_dir(self) -> Path | None:
        """Return the notes directory for the current element, or None."""
        stage = self._viewer.stage
        if not stage:
            return None
        root_layer = stage.GetRootLayer()
        if not root_layer:
            return None
        identifier = root_layer.identifier
        if not identifier:
            return None
        path_str = identifier
        if identifier.startswith('file:'):
            path_str = unquote(identifier.split('file:', 1)[1]).lstrip('/')
        path_str = str(Path(path_str).resolve())
        entity = Project.from_path(path_str)
        if entity is None:
            return None
        if isinstance(entity, Element) and entity.scope is not None:
            root = Path(entity.scope.rootdir)
        else:
            root = Path(entity.rootdir)
        if not root or not root.is_dir():
            return None
        notes_dir = root / 'notes'
        return notes_dir if notes_dir.is_dir() else None

    def _populate_load_notes_menu(self):
        """Populate the Load Notes submenu with historic notes (newest first), including user."""
        menu = self._load_notes_menu
        menu.clear()
        notes_dir = self._get_notes_dir()
        if notes_dir is None:
            action = menu.addAction('(No notes for current element)')
            action.setEnabled(False)
            return
        files = sorted(notes_dir.glob('annotations_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            action = menu.addAction('(No saved notes)')
            action.setEnabled(False)
            return
        for path in files:
            try:
                with open(path) as f:
                    data = json.load(f)
                user = data.get('user', '') or '(unknown)'
            except Exception:
                user = '(unknown)'
            try:
                mtime = path.stat().st_mtime
                dt = datetime.fromtimestamp(mtime)
                date_str = dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                date_str = path.stem.replace('annotations_', '').replace('_', ' ')
            label = f'{date_str} — {user}'
            action = menu.addAction(label)
            action.setData(str(path))
            action.triggered.connect(lambda checked=False, p=str(path): self._on_load_historic_notes(p))

    def _on_load_historic_notes(self, json_path: str):
        """Load a historic notes file: replace annotations and set camera. Warn only if current notes are dirty."""
        overlay = self._viewer.annotation_overlay
        if overlay.dirty:
            reply = QtWidgets.QMessageBox.warning(
                self,
                'Load Notes',
                'Current notes will be replaced. Save them first if you need to keep them.',
                QtWidgets.QMessageBox.StandardButton.Cancel | QtWidgets.QMessageBox.StandardButton.Ok,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Ok:
                return
        path = Path(json_path)
        if not path.is_file():
            QtWidgets.QMessageBox.warning(self, 'Load Notes', f'File not found:\n{path}')
            return
        try:
            with open(path) as f:
                payload = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Load Notes', f'Could not read notes:\n{e}')
            return
        overlay.load_payload(payload)
        overlay.enabled = True
        self._annotation_layer_action.setChecked(True)
        # Refresh view so annotations are visible, then restore free camera from saved transform
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)
        camera = payload.get('camera_transform')
        if camera is not None:
            flat = _flatten_camera_transform(camera)
            if flat is not None and len(flat) == 16:
                self._viewer.set_camera_transform(flat)
        self._viewer.update_view(resetCam=False, forceComputeBBox=False)
        QtWidgets.QApplication.processEvents()

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
        
    

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

from deda.app._usd_viewer import UsdViewWidget

from . import _annotation
from . import _reticle
from . import _slate

# Directory containing HDR/EXR environment textures for the dome light
HDR_IMAGES_DIR = Path(r'D:\hdr_images')


class MainWindow(QtWidgets.QMainWindow):
    """This is the main window class for the dedaverse viewer.
    
    This will contain the Hydra viewport 3d view from usdviewq.
    It will add a camera reticle with view options, a slate overlay that can be toggled on or off,
    a way to playback and scrub the animation, 
    and subtools to interact with the contents of the scene.
    
    """
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self.setWindowTitle('Asset Viewer')
        
        w = QtWidgets.QWidget(parent=self)
        self.setCentralWidget(w)
        
        vbox = QtWidgets.QVBoxLayout()
        w.setLayout(vbox)
        
        self._viewer = UsdViewWidget(stage=None, parent=self)
        vbox.addWidget(self._viewer)
        
        self._build_menu_bar()

    def _build_menu_bar(self):
        """Create the main menu bar and menus."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('&File')
        open_action = file_menu.addAction('&Open...')
        open_action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_file)
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
        self._viewer.set_dome_light_texture(str(texture_path) if texture_path is not None else None)

    def _on_open_file(self):
        """Open a file dialog and load the selected USD stage."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Open USD File',
            '',
            'USD Files (*.usd *.usda *.usdc);;All Files (*)'
        )
        if file_path:
            try:
                stage = Usd.Stage.Open(file_path)
                if stage:
                    self._viewer.stage = stage
                    self.setWindowTitle(f'Asset Viewer - {Path(file_path).name}')
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

    def closeEvent(self, event):
        self._viewer.closeEvent(event)
        super().closeEvent(event)
        
    
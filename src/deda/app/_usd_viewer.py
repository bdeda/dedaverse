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
__all__ = ['UsdViewWidget']


import logging
from pathlib import Path

from PySide6 import QtWidgets, QtCore

from pxr import Usd, Sdf
from pxr.Usdviewq.stageView import StageView
from pxr.Usdviewq.common import CameraMaskModes


log = logging.getLogger(__name__)


def _create_engine_wrapper(engine, view_settings_getter):
    """Wrap UsdImagingGL.Engine to inject dome light texture from viewSettings."""

    original_set_lighting = engine.SetLightingState

    def wrapped_set_lighting(lights, material, scene_ambient):
        texture_path = getattr(view_settings_getter(), 'domeLightTexturePath', None)
        if texture_path and Path(texture_path).exists():
            for light in lights:
                if hasattr(light, 'IsDomeLight') and light.IsDomeLight():
                    light.SetDomeLightTextureFile(Sdf.AssetPath(texture_path))
                    break
        return original_set_lighting(lights, material, scene_ambient)

    engine.SetLightingState = wrapped_set_lighting
    return engine


class _StageViewWithDomeTexture(StageView):
    """StageView that applies domeLightTexturePath from viewSettings to the dome light."""

    def _getRenderer(self):
        renderer = super()._getRenderer()
        if renderer and not getattr(renderer, '_dome_texture_wrapper_applied', False):
            _create_engine_wrapper(
                renderer,
                lambda: self._dataModel.viewSettings
            )
            renderer._dome_texture_wrapper_applied = True
        return renderer


class UsdViewWidget(QtWidgets.QWidget):
    """3D Viewport for rendering a USD scene."""
    
    def __init__(self, stage=None, parent=None):
        super().__init__(parent=parent)
        
        self._view = _StageViewWithDomeTexture(parent=self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)

        if stage:
            self.stage = stage
        else:
            self.stage = Usd.Stage.CreateInMemory()

        self.viewSettings.domeLightEnabled = True
        self.viewSettings.domeLightTexturesVisible = True
        self.viewSettings._cameraMaskMode = CameraMaskModes.FULL

    @property
    def viewSettings(self):
        return self._view._dataModel.viewSettings

    @property
    def stage(self):
        return self._view._dataModel.stage

    @stage.setter
    def stage(self, stage):
        """Set the USD stage for this viewport.
        
        Properly cleans up the previous stage and OpenGL resources before
        setting a new stage to prevent GL_INVALID_OPERATION errors.
        
        Args:
            stage: (Usd.Stage) The USD stage to display, or None to create an empty stage.
        """
        # Only cleanup if there's an existing stage
        if self._view._dataModel.stage is not None:
            try:
                # Clear stage first to release USD resources
                # This ensures OpenGL cleanup happens while context is still valid
                self._view._dataModel.stage = None
                # Then close renderer to clean up OpenGL resources
                self._view.closeRenderer()
            except Exception as err:
                log.warning(f'Error during stage cleanup: {err}')
        
        # Set updates disabled during stage setup to prevent rendering issues
        self._view.setUpdatesEnabled(False)
        try:
            # Set the new stage
            self._view._dataModel.stage = stage or Usd.Stage.CreateInMemory()
            
            # Configure time code
            earliest = Usd.TimeCode.EarliestTime()  # TODO: set to first frame of the stage time
            self._view._dataModel.currentFrame = Usd.TimeCode(earliest)

            # Configure view settings
            self.viewSettings.domeLightEnabled = True
            self.viewSettings.domeLightTexturesVisible = True 

            # Update the view
            self.update_view(resetCam=True, forceComputeBBox=True)
        except Exception as err:
            log.error(f'Error setting stage: {err}')
            raise
        finally:
            self._view.setUpdatesEnabled(True)


    def closeEvent(self, event):
        """Handle widget close event with proper OpenGL cleanup.
        
        Ensures that OpenGL resources are cleaned up while the context
        is still valid to prevent GL_INVALID_OPERATION errors during
        HgiGLSampler destruction.
        
        Args:
            event: (QCloseEvent) The close event.
        """
        if self._view:
            try:
                # Then close renderer to clean up OpenGL resources
                # This must happen while the OpenGL context is still valid
                self._view.closeRenderer()
                
                # Clear stage to release USD resources
                # This triggers cleanup of USD objects that hold OpenGL references
                self._view._dataModel.stage = None                
                
            except Exception as err:
                # Log but don't prevent closing - context may already be destroyed
                log.warning(f'Error during renderer cleanup in closeEvent: {err}')
        
        # Call parent closeEvent to ensure proper widget cleanup
        super().closeEvent(event)

    def set_fixed_aspect_ratio(self, width_ratio, height_ratio):
        """Set the camera mask aspect ratio for the view, or unlock if both are None.
        Uses the stage view's camera mask to letterbox/pillarbox the view to the
        selected aspect ratio without resizing the widget.

        Args:
            width_ratio: Numerator of aspect ratio (width/height), or None to unlock.
            height_ratio: Denominator of aspect ratio, or None to unlock.
        """
        vs = self.viewSettings
        if width_ratio is None or height_ratio is None:
            vs.lockFreeCameraAspect = False
            vs.cameraMaskMode = CameraMaskModes.NONE
            return
        vs.lockFreeCameraAspect = True
        vs.freeCameraAspect = width_ratio / height_ratio
        vs.cameraMaskMode = CameraMaskModes.FULL
        self.update_view(resetCam=False, forceComputeBBox=False)

    def set_dome_light_enabled(self, enabled):
        """Enable or disable the dome light.

        Args:
            enabled: Whether the dome light is on.
        """
        self.viewSettings.domeLightEnabled = bool(enabled)
        self._view.closeRenderer()
        self.update_view(resetCam=False, forceComputeBBox=False)

    def set_dome_light_texture(self, texture_path):
        """Set the dome light environment texture (HDR/EXR) path.

        Args:
            texture_path: Path to HDR or EXR texture file, or None to clear.
        """
        #setattr(
            #self.viewSettings,
            #'domeLightTexturePath',
            #None if texture_path is None else str(texture_path)
        #)
        #self._view.closeRenderer()
        self.update_view(resetCam=False, forceComputeBBox=False)

    def update_view(self, resetCam=False, forceComputeBBox=False):
        if self._view._dataModel.stage:
            self._view.updateView(resetCam=resetCam, forceComputeBBox=forceComputeBBox)

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_F:
            self.update_view(resetCam=True, forceComputeBBox=True)        
        
        

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    stage = Usd.Stage.Open('F:\\cube_from_blender.usda')
    w = UsdViewWidget()#stage=stage)
    w.show()
    w.stage = stage
    app.exec_()
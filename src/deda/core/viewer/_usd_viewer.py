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

from PySide6 import QtWidgets, QtCore, QtGui

from pxr import Gf, Usd, Sdf, UsdLux
from pxr.Usdviewq.stageView import StageView
from pxr.Usdviewq.common import CameraMaskModes

from ._annotation import AnnotationGlOverlay
from ._reticle import CameraReticleGlOverlay
from ._slate import SlateTextGlOverlay

from ._reticle import CameraReticleGlOverlay


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


def _collect_prims_with_variant_sets(prim):
    """Walk up from prim and collect all prims (including prim) that have variant sets."""
    result = []
    p = prim
    while p and p.IsValid():
        variant_sets = p.GetVariantSets()
        if variant_sets and variant_sets.GetNames():
            result.append(p)
        p = p.GetParent()
    return result


class _StageView(StageView):
    """StageView that overrides DrawAxis and adds a right-click context menu for variant switching."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__draw_axis = StageView.DrawAxis
        self._axis_enabled = False
        self._annotation_overlay = AnnotationGlOverlay()
        self._reticle_overlay = CameraReticleGlOverlay()
        self._slate_overlay = SlateTextGlOverlay()

    @property
    def annotation_overlay(self) -> AnnotationGlOverlay:
        return self._annotation_overlay

    @property
    def reticle_overlay(self) -> CameraReticleGlOverlay:
        return self._reticle_overlay

    @property
    def slate_overlay(self) -> SlateTextGlOverlay:
        return self._slate_overlay

    def DrawAxis(self, viewProjectionMatrix):
        if self._axis_enabled:
            self.__draw_axis(viewProjectionMatrix)
        return
    
    def drawHUD(self, renderer): # overriden from base class
        """We will use this to draw all overlays for annotations layers, slate layer, and hud layers.
        
        """
        # compute the time it took to render this frame,
        # so we can display it in the HUD
        #ms = self._renderTime * 1000.
        #fps = float("inf")
        #if not self._renderTime == 0:
            #fps = 1./self._renderTime
        ## put the result in the HUD string
        #self.fpsHUDInfo['Render'] = "%.2f ms (%.2f FPS)" % (ms, fps)

        #col = Gf.Vec3f(.733,.604,.333)

        ## the subtree info does not update while animating, grey it out
        #if not self._dataModel.playing:
            #subtreeCol = col
        #else:
            #subtreeCol = Gf.Vec3f(.6,.6,.6)

        ## Subtree Info
        #if self._dataModel.viewSettings.showHUD_Info:
            #self._hud.updateGroup("TopLeft", 0, 14, subtreeCol,
                                 #self.upperHUDInfo,
                                 #self.HUDStatKeys)
        #else:
            #self._hud.updateGroup("TopLeft", 0, 0, subtreeCol, {})

        ## Complexity
        #if self._dataModel.viewSettings.showHUD_Complexity:
            ## Camera name
            #camName = "Free%s" % (" AutoClip" if self.autoClip else "")
            #if self._dataModel.viewSettings.cameraPrim:
                #camName = self._dataModel.viewSettings.cameraPrim.GetName()

            #toPrint = {"Complexity" : self._dataModel.viewSettings.complexity.name,
                       #"Camera" : camName}
            #self._hud.updateGroup("BottomRight",
                                  #self.width()-210, self.height()-self._hud._HUDLineSpacing*2,
                                  #col, toPrint)
        #else:
            #self._hud.updateGroup("BottomRight", 0, 0, col, {})

        #if self._renderPauseState:
            #toPrint = {"Hydra": "(paused)"}
        #elif self._renderStopState:
            #toPrint = {"Hydra": "(stopped)"}
        #else:
            #toPrint = {"Hydra": self._rendererDisplayName}
            
        #if self._rendererAovName != "color":
            #toPrint["  AOV"] = self._rendererAovName
        #self._hud.updateGroup("TopRight", self.width()-160, 14, col,
                              #toPrint, toPrint.keys())

        ## bottom left
        #from collections import OrderedDict
        #toPrint = OrderedDict()

        ## GPU stats (TimeElapsed is in nano seconds)
        #if self._dataModel.viewSettings.showHUD_GPUstats:

            #def _addSizeMetric(toPrint, stats, label, key):
                #if key in stats:
                    #toPrint[label] = ReportMetricSize(stats[key])

            #rStats = renderer.GetRenderStats()

            #toPrint["GL prims "] = self._glPrimitiveGeneratedQuery.GetResult()
            #if not (self._renderPauseState or self._renderStopState):
                #toPrint["GPU time "] = "%.2f ms " % (self._glTimeElapsedQuery.GetResult() / 1000000.0)
            #_addSizeMetric(toPrint, rStats, "GPU mem  ", "gpuMemoryUsed")
            #_addSizeMetric(toPrint, rStats, " primvar ", "primvar")
            #_addSizeMetric(toPrint, rStats, " topology", "topology")
            #_addSizeMetric(toPrint, rStats, " shader  ", "drawingShader")
            #_addSizeMetric(toPrint, rStats, " texture ", "textureMemory")
            
            #if "numCompletedSamples" in rStats:
                #toPrint["Samples done "] = rStats["numCompletedSamples"]

        ## Playback Rate
        #if (not (self._renderPauseState or self._renderStopState)) and \
                            #self._dataModel.viewSettings.showHUD_Performance:
            #for key in self.fpsHUDKeys:
                #toPrint[key] = self.fpsHUDInfo[key]
        #self._hud.updateGroup("BottomLeft",
                              #0, self.height()-len(toPrint)*self._hud._HUDLineSpacing,
                              #col, toPrint, toPrint.keys())

        ## draw HUD
        #self._hud.draw(self)    

    def paintGL(self):
        if hasattr(StageView, "paintGL"):
            StageView.paintGL(self)
        else:
            super().paintGL()
        if self._annotation_overlay and self._annotation_overlay.enabled:
            self._annotation_overlay.draw_from_stage_view(self)
        if self._reticle_overlay and self._reticle_overlay.enabled:
            self._reticle_overlay.draw_from_stage_view(self)
        if self._slate_overlay and self._slate_overlay.enabled:
            self._slate_overlay.draw_from_stage_view(self)

    def contextMenuEvent(self, event):
        """Show context menu at click point with variant switching for the picked prim."""
        pos = event.pos()
        global_pos = self.mapToGlobal(pos)

        if not self._dataModel or not self._dataModel.stage:
            super().contextMenuEvent(event)
            return

        try:
            in_bounds, pick_frustum = self.computePickFrustum(pos.x(), pos.y())
            if not in_bounds:
                super().contextMenuEvent(event)
                return

            pick_results = self.pick(pick_frustum)
            if not pick_results or len(pick_results) < 3:
                super().contextMenuEvent(event)
                return

            selected_prim_path = pick_results[2]
            if not selected_prim_path or selected_prim_path == Sdf.Path.emptyPath:
                super().contextMenuEvent(event)
                return

            stage = self._dataModel.stage
            prim = stage.GetPrimAtPath(selected_prim_path)
            if not prim or not prim.IsValid():
                super().contextMenuEvent(event)
                return

            prims_with_variants = _collect_prims_with_variant_sets(prim)
            if not prims_with_variants:
                super().contextMenuEvent(event)
                return

            menu = QtWidgets.QMenu(self)
            for p in prims_with_variants:
                variant_sets = p.GetVariantSets()
                for vs_name in variant_sets.GetNames():
                    vs = variant_sets.GetVariantSet(vs_name)
                    variant_names = vs.GetVariantNames()
                    if not variant_names:
                        continue
                    submenu = menu.addMenu(f'{p.GetPath()} / {vs_name}')
                    current = vs.GetVariantSelection()
                    for vname in variant_names:
                        action = submenu.addAction(vname)
                        action.setCheckable(True)
                        action.setChecked(vname == current)
                        action.triggered.connect(
                            (lambda prim_path, vsn, vn: lambda: self._set_variant(
                                prim_path, vsn, vn
                            ))(p.GetPath(), vs_name, vname)
                        )
            if menu.isEmpty():
                super().contextMenuEvent(event)
                return
            menu.exec(global_pos)
        except Exception as err:
            log.warning(f'Context menu pick failed: {err}')
            super().contextMenuEvent(event)

    def _set_variant(self, prim_path, variant_set_name, variant_name):
        """Set the variant selection for a prim's variant set."""
        stage = self._dataModel.stage if self._dataModel else None
        if not stage:
            return
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            return
        variant_sets = prim.GetVariantSets()
        if not variant_sets.HasVariantSet(variant_set_name):
            return
        vs = variant_sets.GetVariantSet(variant_set_name)
        if variant_name not in vs.GetVariantNames():
            return
        stage.SetEditTarget(stage.GetSessionLayer())
        vs.SetVariantSelection(variant_name)
        self.updateView()


class UsdViewWidget(QtWidgets.QWidget):
    """3D Viewport for rendering a USD scene."""
    
    def __init__(self, stage=None, parent=None):
        super().__init__(parent=parent)
        
        self._view = _StageView(parent=self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._view)
        layout.setContentsMargins(0, 0, 0, 0)

        if stage:
            self.stage = stage
        else:
            self.stage = Usd.Stage.CreateInMemory()

        self.viewSettings.domeLightEnabled = True
        self.viewSettings.domeLightTexturesVisible = True
        self.viewSettings.ambientLightOnly = False  # Disable default camera/headlamp light
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
            self.viewSettings.ambientLightOnly = False  # Disable default camera/headlamp light

            # Update the view
            self.update_view(resetCam=True, forceComputeBBox=True)
            self._set_clipping_planes_from_stage_bounds()
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
        prim = self.stage.GetPrimAtPath('/lights/dome_light')
        light = None
        if not prim:
            self.stage.SetEditTarget(self.stage.GetSessionLayer())
            light = UsdLux.DomeLight.Define(self.stage, '/lights/dome_light')
        elif prim.IsA(UsdLux.DomeLight):
            light = UsdLux.DomeLight(prim)
        if light:
            light.OrientToStageUpAxis()
            light.CreateTextureFileAttr(texture_path)
        self._view.closeRenderer()
        self.update_view(resetCam=False, forceComputeBBox=False)

    def _set_clipping_planes_from_stage_bounds(self):
        """Set camera near/far clipping planes from stage bbox so all geometry is visible when zoomed in."""
        if not self._view._dataModel.stage:
            return
        bbox = self._view._bbox
        r = bbox.ComputeAlignedRange()
        if r.IsEmpty():
            return
        mn, mx = r.GetMin(), r.GetMax()
        size = mx - mn
        diagonal = size.GetLength()
        if diagonal <= 0:
            return
        # Near: very small so zooming in does not clip; scale with scene size for numerical stability
        near = max(0.001, diagonal / 1e6)
        # Far: encompass entire scene from any camera angle; use 2.5x diagonal for margin
        far = max(diagonal * 2.5, 100.0)
        vs = self.viewSettings
        vs.freeCameraOverrideNear = near
        vs.freeCameraOverrideFar = far
        self.update_view(resetCam=False, forceComputeBBox=False)

    def set_current_frame(self, frame):
        """Set the stage view's current frame (time code) and refresh the display.

        Before rendering, updates the camera clipping planes to encompass the
        bounding box of all geometry at the current frame, so animated geometry
        is not clipped during playback.

        Args:
            frame: Frame number to display.
        """
        if self._view._dataModel.stage:
            self._view._dataModel.currentFrame = Usd.TimeCode(frame)
            self.update_view(resetCam=False, forceComputeBBox=True)
            self._set_clipping_planes_from_stage_bounds()

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

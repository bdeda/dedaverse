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
from typing import List

try:
    import OpenGL
except ImportError:
    OpenGL = None

from PySide6 import QtWidgets, QtCore, QtGui

from pxr import Gf, Usd, Sdf, UsdLux
from pxr.Usdviewq.stageView import StageView
from pxr.Usdviewq.common import CameraMaskModes

from ._annotation import AnnotationGlOverlay, AnnotationText
from ._reticle import CameraReticleGlOverlay
from ._slate import SlateTextGlOverlay

from ._reticle import CameraReticleGlOverlay


log = logging.getLogger(__name__)


def _log_camera_attrs_hint(view) -> None:
    """Log camera-related attribute/method names on view and viewSettings for debugging."""
    try:
        view_names = [n for n in dir(view) if 'camera' in n.lower()]
        vs = getattr(view, '_dataModel', None) and getattr(view._dataModel, 'viewSettings', None)
        vs_names = [n for n in dir(vs)] if vs else []
        vs_camera = [n for n in vs_names if 'camera' in n.lower()]
        log.info(
            'get_camera_transform: no matrix found. View camera-related: %s; viewSettings camera-related: %s',
            view_names,
            vs_camera,
        )
    except Exception:
        pass


def _to_matrix4d(val):  # -> Gf.Matrix4d | None
    """Convert a value to Gf.Matrix4d if possible; return None otherwise."""
    if val is None:
        return None
    if isinstance(val, Gf.Matrix4d):
        return val
    try:
        return Gf.Matrix4d(val)
    except Exception:
        pass
    # Sequence of 16 numbers (row-major).
    if hasattr(val, '__len__') and len(val) == 16:
        try:
            return Gf.Matrix4d(*[float(x) for x in val])
        except Exception:
            pass
    return None


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


def _get_prim_info_for_hover(prim):
    """Return (prim_path_str, spec_identifier_strings) for the given prim.

    spec_identifier_strings is the list of prim spec identifiers (layer identifier
    and path) that participate in composing this prim, in strength order. Each
    entry is the Sdf.PrimSpec's layer identifier and path.
    """
    if not prim or not prim.IsValid():
        return None
    path_str = str(prim.GetPath())
    identifiers = []
    try:
        prim_index = prim.GetPrimIndex()
        if prim_index and hasattr(prim_index, 'primStack'):
            for spec in prim_index.primStack:
                if spec and spec.layer:
                    lid = spec.layer.identifier
                    path = spec.path
                    if lid:
                        identifiers.append(f"{lid} @ {path}")
    except Exception as err:
        log.debug("Prim stack iteration failed: %s", err)
    return (path_str, identifiers)


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


def _apply_viewport_gl_state():
    """Apply optional OpenGL state when the viewport is initialized.

    Enables GL_TEXTURE_CUBE_MAP_SEAMLESS (better dome/env sampling),
    GL_MULTISAMPLE (antialiasing), GL_DEPTH_CLAMP where supported,
    and optional line/polygon smooth and sample alpha-to-coverage to reduce
    aliasing on curved and reflective edges.
    Safe to call from initializeGL when context is current.
    """
    if OpenGL is None:
        return
    gl = getattr(OpenGL, "GL", None)
    if gl is None or not hasattr(gl, "glEnable"):
        return
    try:
        if hasattr(gl, "GL_TEXTURE_CUBE_MAP_SEAMLESS"):
            gl.glEnable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
    except Exception:
        pass
    try:
        if hasattr(gl, "GL_MULTISAMPLE"):
            gl.glEnable(gl.GL_MULTISAMPLE)
    except Exception:
        pass
    try:
        if hasattr(gl, "GL_DEPTH_CLAMP"):
            gl.glEnable(gl.GL_DEPTH_CLAMP)
    except Exception:
        pass
    # Reduce aliasing on edges (curves, silhouettes). May be ignored when MSAA is active.
    try:
        if hasattr(gl, "GL_LINE_SMOOTH"):
            gl.glEnable(gl.GL_LINE_SMOOTH)
    except Exception:
        pass
    try:
        if hasattr(gl, "GL_POLYGON_SMOOTH"):
            gl.glEnable(gl.GL_POLYGON_SMOOTH)
    except Exception:
        pass
    try:
        if hasattr(gl, "GL_SAMPLE_ALPHA_TO_COVERAGE"):
            gl.glEnable(gl.GL_SAMPLE_ALPHA_TO_COVERAGE)
    except Exception:
        pass


class _TextAnnotationOverlay(QtWidgets.QWidget):
    """Overlay widget for rendering text annotations using proper Qt rendering."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, False)
        self._annotation_overlay = None

    def set_annotation_overlay(self, overlay):
        """Set the annotation overlay to render."""
        self._annotation_overlay = overlay

    def paintEvent(self, event):
        """Render text annotations."""
        if not self._annotation_overlay or not self._annotation_overlay.enabled or not self._annotation_overlay.texts:
            return
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            rect = self.rect()
            self._annotation_overlay.draw_texts(painter, rect)
        finally:
            painter.end()

    def update_geometry(self):
        """Update geometry to match parent widget."""
        if self.parent():
            self.setGeometry(self.parent().rect())
            self.raise_()  # Ensure it's above the OpenGL viewport


class _PrimInfoOverlay(QtWidgets.QFrame):
    """Semi-transparent floating panel showing prim path and prim spec identifiers.
    Shown as a top-level tool window so it is not overdrawn by the OpenGL view."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet(
            "background-color: rgba(28, 28, 32, 230);"
            " border: 1px solid rgba(80, 80, 90, 200);"
            " border-radius: 4px;"
            " padding: 6px;"
            " font-family: Consolas, monospace;"
            " font-size: 11px;"
            " color: rgb(220, 220, 220);"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        self._path_label = QtWidgets.QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setTextFormat(QtCore.Qt.RichText)
        layout.addWidget(self._path_label)
        spec_label = QtWidgets.QLabel("Prim specs (composition):")
        spec_label.setStyleSheet("font-weight: bold; color: rgb(180, 180, 200);")
        layout.addWidget(spec_label)
        self._specs_text = QtWidgets.QTextEdit()
        self._specs_text.setReadOnly(True)
        self._specs_text.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._specs_text.setMaximumHeight(120)
        self._specs_text.setStyleSheet(
            "background: transparent; color: rgb(200, 200, 200); font-size: 10px;"
        )
        layout.addWidget(self._specs_text)
        self.setFixedSize(380, 200)
        self.hide()

    def set_prim_info(self, prim_path_str, spec_identifiers):
        """Set the displayed prim path and list of prim spec identifiers."""
        self._path_label.setText(f"<b>Prim:</b> {_escape_html(prim_path_str)}")
        if spec_identifiers:
            self._specs_text.setPlainText("\n".join(spec_identifiers))
        else:
            self._specs_text.setPlainText("(none)")
        self._specs_text.moveCursor(QtGui.QTextCursor.MoveOperation.Start)


def _escape_html(s):
    """Escape for use in RichText."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class _StageView(StageView):
    """StageView that overrides DrawAxis and adds a right-click context menu for variant switching."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__draw_axis = StageView.DrawAxis
        self._axis_enabled = False
        self._annotation_overlay = AnnotationGlOverlay()
        self._reticle_overlay = CameraReticleGlOverlay()
        self._slate_overlay = SlateTextGlOverlay(
            enabled=False,
            lines=["Slate layer", "Temporary text"],
        )
        self._prim_info_overlay = _PrimInfoOverlay(parent=self)
        self._prim_info_overlay.setParent(self)
        # Create text annotation overlay widget for proper Qt rendering
        self._text_annotation_overlay = _TextAnnotationOverlay(parent=self)
        self._text_annotation_overlay.setParent(self)
        self._text_annotation_overlay.set_annotation_overlay(self._annotation_overlay)
        self._text_annotation_overlay.update_geometry()
        self._text_annotation_overlay.show()
        self.setMouseTracking(True)
        self._annotation_mode_enabled = False
        self._annotation_drawing = False
        self._annotation_text_mode = False  # True when adding text instead of drawing strokes
        self._annotation_text_dragging = False  # True when dragging selected text
        self._text_drag_start_pos: Optional[QtCore.QPoint] = None  # Mouse position when drag started
        self._text_drag_start_text_positions: List[Tuple[int, float, float]] = []  # [(index, x, y), ...] for selected texts
        self._clipboard_texts: List[AnnotationText] = []  # For cut/paste operations
        # Accept focus so keyPressEvent (e.g. "a" for annotation) is received when viewport is clicked
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        # Load pencil cursor for annotation mode
        self._pencil_cursor = self._load_pencil_cursor()

    def _load_pencil_cursor(self) -> QtGui.QCursor | None:
        """Load the pencil cursor icon: scale to cursor size, rotate 270° clockwise, transparent bg.
        
        Returns:
            QCursor with pencil icon, or None if the icon file cannot be loaded.
        """
        # Standard cursor size (e.g. Windows default)
        cursor_size = 32
        icon_paths = [
            Path(__file__).parent.parent.parent / 'app' / 'icons' / 'pencil_cursor.png',
            Path(__file__).parent / 'pencil_cursor.png',
        ]
        for icon_path in icon_paths:
            if not icon_path.is_file():
                continue
            image = QtGui.QImage(str(icon_path))
            if image.isNull():
                continue
            # Ensure format has alpha so background is transparent
            if image.format() != QtGui.QImage.Format.Format_ARGB32:
                image = image.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
            # Rotate 270° clockwise (90° + 180°): -270 in Qt
            #transform = QtGui.QTransform().rotate(-270.0)
            #image = image.transformed(transform, QtCore.Qt.TransformationMode.SmoothTransformation)
            # Scale to cursor size, keeping aspect ratio, then center on cursor_size square
            #scaled = image.scaled(
            #    cursor_size,
            #    cursor_size,
            #    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            #    QtCore.Qt.TransformationMode.SmoothTransformation,
            #)
            #if scaled.format() != QtGui.QImage.Format.Format_ARGB32:
            #    scaled = scaled.convertToFormat(QtGui.QImage.Format.Format_ARGB32)
            # Use QPixmap and fill with transparent so Windows draws alpha correctly (no white bg)
            #pixmap = QtGui.QPixmap(cursor_size, cursor_size)
            #pixmap.fill(QtCore.Qt.GlobalColor.transparent)
            #x = (cursor_size - scaled.width()) // 2
            #y = (cursor_size - scaled.height()) // 2
            pixmap = QtGui.QPixmap(image)
            painter = QtGui.QPainter(pixmap)
            #painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawImage(0, 0, image)
            painter.end()
            if pixmap.isNull():
                continue
            # Hot spot at tip of pencil (after 270° CW rotation, tip is top-left)
            #ahot_x = 4
            #hot_y = 4
            return QtGui.QCursor(pixmap, 0, 0)
        log.warning("Could not load pencil cursor icon, falling back to crosshair")
        return None

    def _update_annotation_cursor(self) -> None:
        """Set cursor to pencil icon when in annotation mode, else restore default."""
        if self._annotation_mode_enabled:
            if self._pencil_cursor is not None:
                self.setCursor(self._pencil_cursor)
            else:
                # Fallback to crosshair if pencil cursor failed to load
                self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()

    def initializeGL(self):
        """Run base GL init (if any) then apply viewport enhancements."""
        super().initializeGL()
        _apply_viewport_gl_state()

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
        # Draw strokes using OpenGL
        if self._annotation_overlay and self._annotation_overlay.enabled:
            self._annotation_overlay.draw(float(self.width()), float(self.height()))
        if self._reticle_overlay and self._reticle_overlay.enabled:
            self._reticle_overlay.draw_from_stage_view(self)
        if self._slate_overlay and self._slate_overlay.enabled:
            self._slate_overlay.draw_from_stage_view(self)
        # Text annotations are rendered via _text_annotation_overlay widget in paintEvent

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

    def _try_show_prim_info_at(self, pos):
        """Pick at pos and show prim info overlay if over a prim. Hide overlay otherwise.
        pos is in widget coordinates. Returns True if overlay was shown."""
        if not self._dataModel or not self._dataModel.stage:
            self._prim_info_overlay.hide()
            return False
        try:
            in_bounds, pick_frustum = self.computePickFrustum(pos.x(), pos.y())
            if not in_bounds:
                self._prim_info_overlay.hide()
                return False
            pick_results = self.pick(pick_frustum)
            if not pick_results or len(pick_results) < 3:
                self._prim_info_overlay.hide()
                return False
            prim_path = pick_results[2]
            if not prim_path or prim_path == Sdf.Path.emptyPath:
                self._prim_info_overlay.hide()
                return False
            stage = self._dataModel.stage
            prim = stage.GetPrimAtPath(prim_path)
            info = _get_prim_info_for_hover(prim)
            if not info:
                self._prim_info_overlay.hide()
                return False
            path_str, spec_ids = info
            self._prim_info_overlay.set_prim_info(path_str, spec_ids)
            offset_x, offset_y = 16, 16
            px = pos.x() + offset_x
            py = pos.y() + offset_y
            w, h = self._prim_info_overlay.width(), self._prim_info_overlay.height()
            if px + w > self.width():
                px = pos.x() - offset_x - w
            if py + h > self.height():
                py = pos.y() - offset_y - h
            if px < 0:
                px = 8
            if py < 0:
                py = 8
            # Overlay is a top-level window; position in global coordinates
            global_pt = self.mapToGlobal(QtCore.QPoint(px, py))
            self._prim_info_overlay.move(global_pt)
            self._prim_info_overlay.show()
            return True
        except Exception as err:
            log.debug("Prim hover pick failed: %s", err)
            self._prim_info_overlay.hide()
            return False

    def mousePressEvent(self, event):
        """In annotation mode: click text to select/move; Shift+click to add text; otherwise draw stroke."""
        if (
            self._annotation_mode_enabled
            and event.button() == QtCore.Qt.MouseButton.LeftButton
            and self._annotation_overlay
        ):
            pos = event.position().toPoint() if hasattr(event.position(), 'toPoint') else event.pos()
            modifiers = event.modifiers()
            
            # Shift+click: Always add new text annotation (highest priority)
            if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
                self._annotation_overlay.enabled = True
                self._show_text_input_dialog(pos)
                event.accept()
                self.update()
                return
            
            # Check if clicking on existing text (for selection/moving)
            overlay_x = float(pos.x())
            overlay_y = self._flip_y(float(pos.y()))
            text_idx = self._annotation_overlay.get_text_at_position(overlay_x, overlay_y)
            
            if text_idx is not None:
                # Clicking on text - select it and prepare for dragging
                # Ctrl+click: Toggle text selection (multi-select)
                if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
                    if text_idx in self._annotation_overlay.selected_text_indices:
                        self._annotation_overlay.deselect_text(text_idx)
                    else:
                        self._annotation_overlay.select_text(text_idx)
                else:
                    # Regular click: Select only this text (clear others)
                    if text_idx not in self._annotation_overlay.selected_text_indices:
                        self._annotation_overlay.clear_selection()
                        self._annotation_overlay.select_text(text_idx)
                
                # Start dragging (even if already selected, allows repositioning)
                self._annotation_text_dragging = True
                self._text_drag_start_pos = pos
                # Store initial positions of all selected texts
                self._text_drag_start_text_positions = []
                for idx in self._annotation_overlay.selected_text_indices:
                    if 0 <= idx < len(self._annotation_overlay.texts):
                        text_obj = self._annotation_overlay.texts[idx]
                        self._text_drag_start_text_positions.append((idx, text_obj.x, text_obj.y))
                event.accept()
                self.update()
                if self._text_annotation_overlay:
                    self._text_annotation_overlay.update()
                return
            
            # No text clicked - check if text is selected
            # If text is selected, clicking elsewhere clears selection and starts drawing
            # If no text selected, start drawing stroke
            if self._annotation_overlay.selected_text_indices:
                # Clear selection when clicking away from text
                self._annotation_overlay.clear_selection()
                if self._text_annotation_overlay:
                    self._text_annotation_overlay.update()
            
            # Start drawing stroke
            self._annotation_overlay.enabled = True
            self._annotation_overlay.begin_stroke()
            self._annotation_overlay.add_point(overlay_x, overlay_y)
            self._annotation_drawing = True
            event.accept()
            self.update()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """When Ctrl is held, pick prim under cursor; when annotation drawing, add stroke points; when dragging text, move it."""
        # Handle text dragging
        if self._annotation_text_dragging and self._annotation_overlay and self._text_drag_start_pos is not None:
            pos = event.position().toPoint() if hasattr(event.position(), 'toPoint') else event.pos()
            # Calculate drag offset in overlay coordinates
            dx_qt = float(pos.x() - self._text_drag_start_pos.x())
            dy_qt = float(pos.y() - self._text_drag_start_pos.y())
            # Convert dy to overlay coordinates (flip y)
            dy_overlay = -dy_qt  # In overlay coords, up is positive
            
            # Update positions of all selected texts
            for idx, start_x, start_y in self._text_drag_start_text_positions:
                if 0 <= idx < len(self._annotation_overlay.texts):
                    text_obj = self._annotation_overlay.texts[idx]
                    text_obj.x = start_x + dx_qt
                    text_obj.y = start_y + dy_overlay
            self._annotation_overlay._mark_dirty()
            event.accept()
            self.update()
            if self._text_annotation_overlay:
                self._text_annotation_overlay.update()
            return
        
        # Handle stroke drawing
        if self._annotation_drawing and self._annotation_overlay:
            pos = event.position().toPoint() if hasattr(event.position(), 'toPoint') else event.pos()
            self._annotation_overlay.add_point(float(pos.x()), self._flip_y(pos.y()))
            event.accept()
            self.update()
            return
        super().mouseMoveEvent(event)
        pos = event.position().toPoint() if hasattr(event.position(), 'toPoint') else event.pos()
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self._try_show_prim_info_at(pos)
        else:
            self._prim_info_overlay.hide()

    def mouseReleaseEvent(self, event):
        """End annotation stroke or text dragging on left release when in annotation mode."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # End text dragging
            if self._annotation_text_dragging:
                self._annotation_text_dragging = False
                self._text_drag_start_pos = None
                self._text_drag_start_text_positions = []
                event.accept()
                self.update()
                if self._text_annotation_overlay:
                    self._text_annotation_overlay.update()
                return
            # End stroke drawing
            if self._annotation_drawing and self._annotation_overlay:
                self._annotation_overlay.end_stroke()
                self._annotation_drawing = False
                event.accept()
                self.update()
                return
        super().mouseReleaseEvent(event)

    def _flip_y(self, y: float) -> float:
        """Convert Qt viewport y (0 at top) to overlay coords (0 at bottom)."""
        h = self.size().height()
        return float(h - 1 - y) if h else y

    def _show_text_input_dialog(self, pos: QtCore.QPoint) -> None:
        """Show a dialog to input text for annotation at the given position."""
        if not self._annotation_overlay:
            return
        
        # Create a simple input dialog
        text, ok = QtWidgets.QInputDialog.getMultiLineText(
            self,
            "Add Text Annotation",
            "Enter text:",
            ""
        )
        
        if ok and text.strip():
            # Convert position to overlay coordinates
            # pos.y() is in Qt coordinates (top origin), we need overlay coords (bottom origin)
            # Store as baseline position: flip the y coordinate
            qt_y = float(pos.y())  # Qt coordinate (top origin)
            overlay_baseline_y = self._flip_y(qt_y)  # Overlay coordinate (bottom origin, baseline)
            overlay_x = float(pos.x())
            
            # Add text annotation
            # The y coordinate stored is the baseline position in overlay coordinates
            self._annotation_overlay.add_text(
                overlay_x,
                overlay_baseline_y,
                text,
                color=self._annotation_overlay.default_text_color,
                font_size=self._annotation_overlay.default_text_font_size,
                shadow_color=None,  # No shadow
                shadow_offset_px=None,
            )
            # Update both the main widget and the text overlay widget
            self.update()
            if self._text_annotation_overlay:
                self._text_annotation_overlay.update_geometry()
                self._text_annotation_overlay.update()

    def keyPressEvent(self, event):
        """Toggle annotation mode with 'a'; handle cut/paste; show prim info overlay when Ctrl is pressed."""
        modifiers = event.modifiers()
        key = event.key()
        
        # Cut/Copy/Paste for text annotations (Ctrl+X, Ctrl+C, Ctrl+V)
        if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
            if key == QtCore.Qt.Key.Key_X:  # Cut
                if self._annotation_mode_enabled and self._annotation_overlay:
                    self._clipboard_texts = self._annotation_overlay.cut_selected_texts()
                    if self._clipboard_texts:
                        event.accept()
                        self.update()
                        return
            elif key == QtCore.Qt.Key.Key_C:  # Copy
                if self._annotation_mode_enabled and self._annotation_overlay:
                    self._clipboard_texts = self._annotation_overlay.copy_selected_texts()
                    if self._clipboard_texts:
                        event.accept()
                        return
            elif key == QtCore.Qt.Key.Key_V:  # Paste
                if self._annotation_mode_enabled and self._annotation_overlay and self._clipboard_texts:
                    self._annotation_overlay.paste_texts(self._clipboard_texts)
                    event.accept()
                    self.update()
                    return
        
        # Toggle annotation mode with 'a'
        if key == QtCore.Qt.Key.Key_A and not modifiers:
            self._annotation_mode_enabled = not self._annotation_mode_enabled
            self._update_annotation_cursor()
            if self._annotation_mode_enabled and self._annotation_overlay:
                self._annotation_overlay.enabled = True
                parent = self.parent()
                if hasattr(parent, 'annotation_overlay_enabled_changed'):
                    parent.annotation_overlay_enabled_changed.emit(True)
            event.accept()
            self.update()
            return
        
        # Ctrl key: show prim info
        if key == QtCore.Qt.Key.Key_Control:
            pos = self.mapFromGlobal(QtGui.QCursor.pos())
            if self.rect().contains(pos):
                self._try_show_prim_info_at(pos)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Hide prim info overlay when Ctrl is released."""
        if event.key() == QtCore.Qt.Key.Key_Control:
            self._prim_info_overlay.hide()
        super().keyReleaseEvent(event)

    def show_prim_info_at_cursor(self):
        """Called from parent widget when Ctrl is pressed; show overlay at current cursor if over a prim."""
        pos = self.mapFromGlobal(QtGui.QCursor.pos())
        if self.rect().contains(pos):
            self._try_show_prim_info_at(pos)

    def resizeEvent(self, event):
        """Update text annotation overlay geometry when viewport is resized."""
        super().resizeEvent(event)
        if self._text_annotation_overlay:
            self._text_annotation_overlay.update_geometry()

    def leaveEvent(self, event):
        """Hide prim info overlay when mouse leaves the view."""
        super().leaveEvent(event)
        self._prim_info_overlay.hide()

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

    annotation_overlay_enabled_changed = QtCore.Signal(bool)

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
    def reticle_overlay(self):
        """Camera reticle overlay for this viewport."""
        return self._view.reticle_overlay

    @property
    def slate_overlay(self):
        """Slate text overlay for this viewport."""
        return self._view.slate_overlay

    @property
    def annotation_overlay(self):
        """Annotation overlay for this viewport (draw strokes with 'a' and drag)."""
        return self._view.annotation_overlay

    @property
    def annotation_mode_enabled(self) -> bool:
        """Whether annotation mode is on (mouse drag adds strokes)."""
        return self._view._annotation_mode_enabled

    @annotation_mode_enabled.setter
    def annotation_mode_enabled(self, value: bool) -> None:
        self._view._annotation_mode_enabled = bool(value)
        self._view._update_annotation_cursor()

    def capture_viewport_image(self):
        """Capture the current viewport (scene + annotations) as a QImage.

        Forces a repaint then grabs the framebuffer or widget. Call from main
        window when saving annotations to notes. Returns None if capture fails.
        """
        view = self._view
        if not view.isVisible() or view.size().width() <= 0 or view.size().height() <= 0:
            return None
        view.update()
        QtWidgets.QApplication.processEvents()
        if hasattr(view, 'grabFramebuffer'):
            return view.grabFramebuffer()
        pixmap = view.grab()
        return pixmap.toImage() if not pixmap.isNull() else None

    def get_camera_transform(self):
        """Return the free camera transform as a 4x4 row-major list of 16 floats, or None.

        Used when saving annotations to notes so the camera can be restored later.
        Tries known StageView/viewSettings names, then discovers at runtime.
        """
        view = self._view
        mat = self._get_free_camera_matrix_from_view(view)
        if mat is None:
            log.debug('get_camera_transform: no free camera matrix found on view or viewSettings')
            _log_camera_attrs_hint(view)
            return None
        try:
            if not isinstance(mat, Gf.Matrix4d):
                mat = Gf.Matrix4d(mat)
            return [float(mat.GetRow(i)[j]) for i in range(4) for j in range(4)]
        except Exception as e:
            log.debug('get_camera_transform: failed to convert matrix to list: %s', e)
            return None

    def _get_free_camera_matrix_from_view(self, view) -> "Gf.Matrix4d | None":
        """Get the free camera 4x4 matrix from the StageView or its viewSettings."""
        # Primary: viewSettings.freeCamera._camera (Gf.Camera) — the canonical source.
        camera = view._dataModel.viewSettings.freeCamera._camera
        if camera:
            return camera.transform

    def set_camera_transform(self, transform: list) -> bool:
        """Set the free camera transform from a 4x4 row-major list of 16 floats.

        Returns True if the camera was set on at least one sink, False otherwise.
        Used when loading historic notes to restore the saved view. Applies to
        all available sinks (viewSettings and view) and re-applies after the
        next event loop so the view is not overwritten by updateView().
        """
        if not transform or len(transform) != 16:
            return False
        view = self._view
        try:
            mat = Gf.Matrix4d(*transform)
        except Exception:
            return False

        def _apply_and_refresh() -> None:
            self.update_view(resetCam=False, forceComputeBBox=False)
            view.update()

        set_count = 0

        # Primary: viewSettings.freeCamera._camera (Gf.Camera) — set transform via SetTransform().
        if hasattr(view, '_dataModel') and view._dataModel is not None:
            vs = getattr(view._dataModel, 'viewSettings', None)
            if vs is not None:
                free_camera = getattr(vs, 'freeCamera', None)
                if free_camera is not None:
                    camera = getattr(free_camera, '_camera', None)
                    if camera is not None and hasattr(camera, 'SetTransform'):
                        try:
                            camera.SetTransform(mat)
                            set_count += 1
                            log.debug('set_camera_transform: set via viewSettings.freeCamera._camera.SetTransform()')
                        except Exception as e:
                            log.debug('set_camera_transform: viewSettings.freeCamera._camera.SetTransform() failed: %s', e)
                # Fallback: viewSettings attributes (usdview often uses this as source of truth).
                for attr in ('freeCameraMatrix', 'freeCameraTransform'):
                    if hasattr(vs, attr):
                        try:
                            setattr(vs, attr, mat)
                            set_count += 1
                        except Exception as e:
                            log.debug('set_camera_transform: viewSettings.%s failed: %s', attr, e)

        # StageView methods (names may vary by USD version).
        for method_name in ('SetFreeCameraMatrix', 'SetFreeCameraTransform'):
            setter = getattr(view, method_name, None)
            if callable(setter):
                try:
                    setter(mat)
                    set_count += 1
                except Exception as e:
                    log.debug('set_camera_transform: view.%s failed: %s', method_name, e)

        if set_count == 0:
            return False

        _apply_and_refresh()

        # Re-apply on next event loop in case updateView() overwrote the camera.
        self._pending_camera_transform = list(transform)
        QtCore.QTimer.singleShot(0, self._deferred_set_camera_transform)

        return True

    def _deferred_set_camera_transform(self) -> None:
        """Re-apply the last saved camera transform after the event loop (e.g. after updateView)."""
        transform = getattr(self, '_pending_camera_transform', None)
        try:
            delattr(self, '_pending_camera_transform')
        except AttributeError:
            return
        if transform is None or len(transform) != 16:
            return
        view = self._view
        try:
            mat = Gf.Matrix4d(*transform)
        except Exception:
            return
        if hasattr(view, '_dataModel') and view._dataModel is not None:
            vs = getattr(view._dataModel, 'viewSettings', None)
            if vs is not None:
                # Primary: viewSettings.freeCamera._camera (Gf.Camera).
                free_camera = getattr(vs, 'freeCamera', None)
                if free_camera is not None:
                    camera = getattr(free_camera, '_camera', None)
                    if camera is not None and hasattr(camera, 'SetTransform'):
                        try:
                            camera.SetTransform(mat)
                        except Exception:
                            pass
                # Fallback: viewSettings attributes.
                for attr in ('freeCameraMatrix', 'freeCameraTransform'):
                    if hasattr(vs, attr):
                        try:
                            setattr(vs, attr, mat)
                        except Exception:
                            pass
        for method_name in ('SetFreeCameraMatrix', 'SetFreeCameraTransform'):
            setter = getattr(view, method_name, None)
            if callable(setter):
                try:
                    setter(mat)
                except Exception:
                    pass
        self.update_view(resetCam=False, forceComputeBBox=False)
        view.update()

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
        if key == QtCore.Qt.Key.Key_F:
            self.update_view(resetCam=True, forceComputeBBox=True)
        elif key == QtCore.Qt.Key.Key_Control:
            self._view.show_prim_info_at_cursor()
        elif key == QtCore.Qt.Key.Key_A and not event.modifiers():
            # Toggle annotation mode (also handled in _StageView when it has focus)
            self._view._annotation_mode_enabled = not self._view._annotation_mode_enabled
            self._view._update_annotation_cursor()
            if self._view._annotation_mode_enabled and self._view._annotation_overlay:
                self._view._annotation_overlay.enabled = True
                self.annotation_overlay_enabled_changed.emit(True)
            event.accept()
            self.update()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Control:
            self._view._prim_info_overlay.hide()
        super().keyReleaseEvent(event)

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    stage = Usd.Stage.Open('F:\\cube_from_blender.usda')
    w = UsdViewWidget()#stage=stage)
    w.show()
    w.stage = stage
    app.exec_()

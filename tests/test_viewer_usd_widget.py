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
"""Tests for the USD viewport widget: helpers, overlays, annotation interaction, camera and stage handling.

These need a full USD build (pxr.Usdviewq) and run on the offscreen Qt platform, which has no OpenGL, so
nothing is rendered; picking is replaced with fakes.
"""
import types

import pytest

pytest.importorskip('pxr.Usdviewq', reason='the viewer needs a full USD build')

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux  # noqa: E402

from deda.core.viewer import _usd_viewer as uv  # noqa: E402


def make_stage():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, '/root')
    cube = UsdGeom.Cube.Define(stage, '/root/cube')
    cube.GetSizeAttr().Set(2.0)
    return stage


def variant_stage():
    stage = make_stage()
    prim = stage.GetPrimAtPath('/root/cube')
    variants = prim.GetVariantSets().AddVariantSet('look')
    variants.AddVariant('red')
    variants.AddVariant('blue')
    variants.SetVariantSelection('red')
    return stage


@pytest.fixture
def widget(qapp):
    w = uv.UsdViewWidget()
    w.resize(400, 300)
    w.show()
    yield w
    w.close()


@pytest.fixture
def view(widget):
    return widget.stage_view


def mouse(kind, x, y, button=QtCore.Qt.LeftButton, modifiers=QtCore.Qt.NoModifier):
    return QtGui.QMouseEvent(kind, QtCore.QPointF(x, y), QtCore.QPointF(x, y), button, button, modifiers)


def key(kind, code, modifiers=QtCore.Qt.NoModifier):
    return QtGui.QKeyEvent(kind, code, modifiers)


class TestHelpers:
    def test_to_matrix4d(self):
        identity = Gf.Matrix4d(1)
        assert uv._to_matrix4d(None) is None and uv._to_matrix4d(identity) is identity
        assert uv._to_matrix4d(Gf.Matrix4f(2)).GetRow(0)[0] == 2.0
        assert uv._to_matrix4d(list(range(16))).GetRow(1)[0] == 4.0
        assert uv._to_matrix4d('nope') is None and uv._to_matrix4d([1, 2]) is None
        assert uv._to_matrix4d(['a'] * 16) is None

    def test_gf_camera_transform_setter_supports_both_usd_apis(self):
        matrix = Gf.Matrix4d(1).SetTranslate(Gf.Vec3d(1, 2, 3))
        pulled = []
        free_camera = types.SimpleNamespace(_pullFromCameraTransform=lambda: pulled.append(True))
        modern = Gf.Camera()
        uv._set_gf_camera_transform(free_camera, modern, matrix)
        assert modern.transform == matrix and pulled == [True]

        class Legacy:
            def SetTransform(self, m):
                self.value = m

        legacy = Legacy()
        uv._set_gf_camera_transform(types.SimpleNamespace(), legacy, matrix)
        assert legacy.value == matrix

    def test_prim_info_for_hover(self):
        stage = make_stage()
        path, specs = uv._get_prim_info_for_hover(stage.GetPrimAtPath('/root/cube'))
        assert path == '/root/cube' and len(specs) == 1 and '@ /root/cube' in specs[0]
        assert uv._get_prim_info_for_hover(None) is None
        assert uv._get_prim_info_for_hover(stage.GetPrimAtPath('/nope')) is None

    def test_prims_with_variant_sets_walk_up_the_parents(self):
        stage = variant_stage()
        found = uv._collect_prims_with_variant_sets(stage.GetPrimAtPath('/root/cube'))
        assert [str(p.GetPath()) for p in found] == ['/root/cube']
        assert uv._collect_prims_with_variant_sets(stage.GetPrimAtPath('/root')) == []

    def test_escape_html(self):
        assert uv._escape_html('<a & b>') == '&lt;a &amp; b&gt;' and uv._escape_html(5) == '5'

    def test_engine_wrapper_injects_the_dome_texture(self, tmp_path):
        texture = tmp_path / 'sky.exr'
        texture.write_text('')
        recorded = []

        class Light:
            def IsDomeLight(self):
                return True

            def SetDomeLightTextureFile(self, asset):
                recorded.append(asset.path)

        class Engine:
            def SetLightingState(self, lights, material, ambient):
                recorded.append('original')
                return 'result'

        settings = types.SimpleNamespace(domeLightTexturePath=str(texture))
        engine = uv._create_engine_wrapper(Engine(), lambda: settings)
        assert engine.SetLightingState([object(), Light()], None, None) == 'result'
        assert recorded == [str(texture), 'original']
        settings.domeLightTexturePath = None
        recorded.clear()
        engine.SetLightingState([Light()], None, None)
        assert recorded == ['original']

    def test_camera_hint_logging_never_raises(self, view, caplog):
        with caplog.at_level('INFO'):
            uv._log_camera_attrs_hint(view)
        assert 'no matrix found' in caplog.text
        uv._log_camera_attrs_hint(object())

    def test_gl_state_is_applied_when_available_and_tolerates_failures(self, monkeypatch):
        calls = []

        class GL:
            GL_TEXTURE_CUBE_MAP_SEAMLESS, GL_MULTISAMPLE, GL_DEPTH_CLAMP = 1, 2, 3
            GL_LINE_SMOOTH, GL_POLYGON_SMOOTH, GL_SAMPLE_ALPHA_TO_COVERAGE = 4, 5, 6

            @staticmethod
            def glEnable(flag):
                calls.append(flag)
                if flag in (2, 5):
                    raise RuntimeError('unsupported')

        monkeypatch.setattr(uv, 'OpenGL', types.SimpleNamespace(GL=GL))
        uv._apply_viewport_gl_state()
        assert calls == [1, 2, 3, 4, 5, 6]
        monkeypatch.setattr(uv, 'OpenGL', None)
        uv._apply_viewport_gl_state()
        monkeypatch.setattr(uv, 'OpenGL', types.SimpleNamespace(GL=object()))
        uv._apply_viewport_gl_state()


class TestOverlays:
    def test_text_overlay_paints_only_when_there_is_something_to_draw(self, qapp):
        overlay = uv._TextAnnotationOverlay()
        overlay.resize(100, 60)
        assert not overlay.grab().isNull()                                # no overlay set
        annotations = uv.AnnotationGlOverlay()
        overlay.set_annotation_overlay(annotations)
        overlay.grab()
        annotations.add_text(5, 30, 'hi', color=(1, 1, 1))
        image = overlay.grab().toImage()
        assert any(image.pixelColor(x, y).alpha() > 0 for x in range(100) for y in range(60))
        annotations.enabled = False
        overlay.grab()

    def test_text_overlay_follows_its_parent(self, qapp):
        parent = QtWidgets.QWidget()
        parent.resize(150, 90)
        overlay = uv._TextAnnotationOverlay(parent=parent)
        overlay.update_geometry()
        assert overlay.geometry() == parent.rect()
        uv._TextAnnotationOverlay().update_geometry()                    # no parent: nothing happens

    def test_prim_info_panel(self, qapp):
        panel = uv._PrimInfoOverlay()
        panel.set_prim_info('/a<b>', ['layer @ /a', 'other @ /a'])
        assert '&lt;b&gt;' in panel._path_label.text() and 'other @ /a' in panel._specs_text.toPlainText()
        panel.set_prim_info('/x', [])
        assert panel._specs_text.toPlainText() == '(none)'


class TestStageViewAnnotations:
    def test_pencil_cursor_loads_and_toggles(self, view, widget):
        assert view._pencil_cursor is not None or view.cursor() is not None
        widget.annotation_mode_enabled = True
        assert widget.annotation_mode_enabled and view.cursor().shape() in (
            QtCore.Qt.CustomCursor, QtCore.Qt.BitmapCursor, QtCore.Qt.CrossCursor)
        view._pencil_cursor = None
        view._update_annotation_cursor()
        assert view.cursor().shape() == QtCore.Qt.CrossCursor
        widget.annotation_mode_enabled = False
        assert view.cursor().shape() == QtCore.Qt.ArrowCursor

    def test_missing_cursor_icon_gives_none(self, view, monkeypatch, caplog):
        monkeypatch.setattr(uv.Path, 'is_file', lambda self: False)
        with caplog.at_level('WARNING'):
            assert view._load_pencil_cursor() is None
        assert 'Could not load pencil cursor' in caplog.text

    def test_an_unreadable_cursor_icon_is_skipped(self, view, monkeypatch):
        monkeypatch.setattr(uv.Path, 'is_file', lambda self: True)
        real_image = QtGui.QImage
        monkeypatch.setattr(uv.QtGui, 'QImage', lambda *a: real_image())
        assert view._load_pencil_cursor() is None

    def test_drawing_a_stroke_with_the_mouse(self, view):
        view._annotation_mode_enabled = True
        view.mousePressEvent(mouse(QtCore.QEvent.MouseButtonPress, 10, 20))
        assert view._annotation_drawing and view.annotation_overlay.enabled
        view.mouseMoveEvent(mouse(QtCore.QEvent.MouseMove, 30, 40))
        view.mouseMoveEvent(mouse(QtCore.QEvent.MouseMove, 50, 60))
        view.mouseReleaseEvent(mouse(QtCore.QEvent.MouseButtonRelease, 50, 60))
        stroke = view.annotation_overlay.strokes[0]
        assert not view._annotation_drawing and len(stroke.points) == 3
        assert stroke.points[0] == (10.0, view._flip_y(20))

    def test_flip_y_follows_the_height(self, view):
        height = view.size().height()
        assert view._flip_y(0) == height - 1
        assert view._flip_y(height - 1) == 0

    def test_without_annotation_mode_the_press_goes_to_the_base_view(self, view, monkeypatch):
        called = []
        monkeypatch.setattr(uv.StageView, 'mousePressEvent', lambda self, e: called.append('press'))
        view.mousePressEvent(mouse(QtCore.QEvent.MouseButtonPress, 5, 5))
        assert called == ['press'] and view.annotation_overlay.strokes == []

    def test_shift_click_asks_for_text(self, view, monkeypatch):
        view._annotation_mode_enabled = True
        monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText',
                            staticmethod(lambda *a, **k: ('a note', True)))
        view.mousePressEvent(mouse(QtCore.QEvent.MouseButtonPress, 40, 50, modifiers=QtCore.Qt.ShiftModifier))
        text = view.annotation_overlay.texts[0]
        assert text.text == 'a note' and text.x == 40.0 and text.y == view._flip_y(50) and text.shadow_color is None

    def test_cancelled_or_blank_text_adds_nothing(self, view, monkeypatch):
        for answer in (('x', False), ('   ', True)):
            monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText', staticmethod(lambda *a, answer=answer, **k: answer))
            view._show_text_input_dialog(QtCore.QPoint(1, 1))
        assert view.annotation_overlay.texts == []

    def add_text(self, view):
        view._annotation_mode_enabled = True
        y = view._flip_y(100)
        return view.annotation_overlay.add_text(100, y, 'Hello', font_size=14)

    def test_clicking_text_selects_it_and_dragging_moves_it(self, view):
        text = self.add_text(view)
        view.mousePressEvent(mouse(QtCore.QEvent.MouseButtonPress, 105, 100))
        assert view.annotation_overlay.selected_text_indices == [0] and view._annotation_text_dragging
        view.mouseMoveEvent(mouse(QtCore.QEvent.MouseMove, 125, 90))
        assert text.x == 120.0 and text.y == view._flip_y(100) + 10
        view.mouseReleaseEvent(mouse(QtCore.QEvent.MouseButtonRelease, 125, 90))
        assert not view._annotation_text_dragging and view._text_drag_start_text_positions == []

    def test_ctrl_click_toggles_the_selection(self, view):
        self.add_text(view)
        view.mousePressEvent(mouse(QtCore.QEvent.MouseButtonPress, 105, 100, modifiers=QtCore.Qt.ControlModifier))
        view.mouseReleaseEvent(mouse(QtCore.QEvent.MouseButtonRelease, 105, 100))
        assert view.annotation_overlay.selected_text_indices == [0]
        view.mousePressEvent(mouse(QtCore.QEvent.MouseButtonPress, 105, 100, modifiers=QtCore.Qt.ControlModifier))
        view.mouseReleaseEvent(mouse(QtCore.QEvent.MouseButtonRelease, 105, 100))
        assert view.annotation_overlay.selected_text_indices == []

    def test_clicking_away_clears_the_selection_and_starts_a_stroke(self, view):
        self.add_text(view)
        view.annotation_overlay.select_text(0)
        view.mousePressEvent(mouse(QtCore.QEvent.MouseButtonPress, 300, 250))
        assert view.annotation_overlay.selected_text_indices == [] and view._annotation_drawing
        view.mouseReleaseEvent(mouse(QtCore.QEvent.MouseButtonRelease, 300, 250))

    def test_cut_copy_paste_shortcuts(self, view):
        self.add_text(view)
        view.annotation_overlay.select_text(0)
        view.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_C, QtCore.Qt.ControlModifier))
        assert [t.text for t in view._clipboard_texts] == ['Hello']
        view.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier))
        assert len(view.annotation_overlay.texts) == 2
        view.annotation_overlay.select_text(0)
        view.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_X, QtCore.Qt.ControlModifier))
        assert len(view.annotation_overlay.texts) == 1

    def test_shortcuts_do_nothing_outside_annotation_mode(self, view):
        view.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier))
        assert view.annotation_overlay.texts == []

    def test_the_a_key_toggles_annotation_mode_and_tells_the_parent(self, widget, view):
        seen = []
        widget.annotation_overlay_enabled_changed.connect(seen.append)
        view.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_A))
        assert view._annotation_mode_enabled and seen == [True]
        view.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_A))
        assert not view._annotation_mode_enabled

    def test_the_widget_handles_a_and_f_and_control(self, widget, view, monkeypatch):
        seen = []
        widget.annotation_overlay_enabled_changed.connect(seen.append)
        widget.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_A))
        assert widget.annotation_mode_enabled and seen == [True]
        widget.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_A))
        assert not widget.annotation_mode_enabled
        updates = []
        monkeypatch.setattr(widget, 'update_view', lambda **kw: updates.append(kw))
        widget.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_F))
        assert updates == [{'resetCam': True, 'forceComputeBBox': True}]
        shown = []
        monkeypatch.setattr(view, 'show_prim_info_at_cursor', lambda: shown.append(True))
        widget.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Control))
        assert shown == [True]
        view._prim_info_overlay.show()
        widget.keyReleaseEvent(key(QtCore.QEvent.KeyRelease, QtCore.Qt.Key_Control))
        assert not view._prim_info_overlay.isVisible()

    def test_key_events_pass_through_to_the_base_view(self, widget, view):
        widget.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Z))
        view.keyPressEvent(key(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Z))
        view.keyReleaseEvent(key(QtCore.QEvent.KeyRelease, QtCore.Qt.Key_Z))
        widget.keyReleaseEvent(key(QtCore.QEvent.KeyRelease, QtCore.Qt.Key_Z))

    def test_resize_and_leave_update_the_overlays(self, view):
        view.resize(250, 180)
        QtWidgets.QApplication.processEvents()
        assert view._text_annotation_overlay.geometry() == view.rect()
        view._prim_info_overlay.show()
        view.leaveEvent(QtCore.QEvent(QtCore.QEvent.Leave))
        assert not view._prim_info_overlay.isVisible()

    def test_the_axis_is_off_by_default(self, view):
        view.DrawAxis(Gf.Matrix4d(1))
        called = []
        view._StageView__draw_axis = lambda matrix: called.append(matrix)
        view._axis_enabled = True
        view.DrawAxis(Gf.Matrix4d(1))
        assert len(called) == 1

    def test_overlay_accessors(self, view, widget):
        assert view.reticle_overlay is widget.reticle_overlay and view.slate_overlay is widget.slate_overlay
        assert view.annotation_overlay is widget.annotation_overlay and not view.slate_overlay.enabled


class TestPickingAndVariants:
    @pytest.fixture
    def with_stage(self, widget, view):
        widget.stage = variant_stage()
        return widget

    def fake_pick(self, view, monkeypatch, path, in_bounds=True, results=None):
        monkeypatch.setattr(view, 'computePickFrustum', lambda x, y: (in_bounds, object()))
        monkeypatch.setattr(view, 'pick', lambda frustum: results if results is not None else
                            (None, None, Sdf.Path(path) if path else Sdf.Path.emptyPath))

    def test_hover_shows_the_prim_info_panel(self, with_stage, view, monkeypatch):
        self.fake_pick(view, monkeypatch, '/root/cube')
        assert view._try_show_prim_info_at(QtCore.QPoint(380, 280)) is True
        assert view._prim_info_overlay.isVisible() and '/root/cube' in view._prim_info_overlay._path_label.text()
        view._prim_info_overlay.hide()
        assert view._try_show_prim_info_at(QtCore.QPoint(2, 2)) is True      # near the corner: clamped on screen

    @pytest.mark.parametrize('setup', ['no_hit', 'out_of_bounds', 'short_result', 'unknown_prim'])
    def test_hover_hides_the_panel_when_nothing_is_picked(self, with_stage, view, monkeypatch, setup):
        view._prim_info_overlay.show()
        if setup == 'no_hit':
            self.fake_pick(view, monkeypatch, None)
        elif setup == 'out_of_bounds':
            self.fake_pick(view, monkeypatch, '/root/cube', in_bounds=False)
        elif setup == 'short_result':
            self.fake_pick(view, monkeypatch, '/root/cube', results=(1,))
        else:
            self.fake_pick(view, monkeypatch, '/missing')
        assert view._try_show_prim_info_at(QtCore.QPoint(10, 10)) is False
        assert not view._prim_info_overlay.isVisible()

    def test_hover_without_a_stage_or_with_a_failing_pick(self, view, monkeypatch):
        view._dataModel.stage = None
        assert view._try_show_prim_info_at(QtCore.QPoint(1, 1)) is False

    def test_a_failing_pick_is_swallowed(self, with_stage, view, monkeypatch):
        def boom(*a):
            raise RuntimeError('no gl')

        monkeypatch.setattr(view, 'computePickFrustum', boom)
        assert view._try_show_prim_info_at(QtCore.QPoint(1, 1)) is False

    def test_mouse_move_with_ctrl_shows_info_and_without_hides_it(self, with_stage, view, monkeypatch):
        shown = []
        monkeypatch.setattr(view, '_try_show_prim_info_at', lambda pos: shown.append(pos))
        monkeypatch.setattr(uv.StageView, 'mouseMoveEvent', lambda self, e: None)
        view.mouseMoveEvent(mouse(QtCore.QEvent.MouseMove, 20, 20, modifiers=QtCore.Qt.ControlModifier))
        assert len(shown) == 1
        view._prim_info_overlay.show()
        view.mouseMoveEvent(mouse(QtCore.QEvent.MouseMove, 20, 20))
        assert not view._prim_info_overlay.isVisible()

    def test_show_prim_info_at_cursor(self, with_stage, view, monkeypatch):
        shown = []
        monkeypatch.setattr(view, '_try_show_prim_info_at', lambda pos: shown.append(pos))
        monkeypatch.setattr(QtGui.QCursor, 'pos', staticmethod(lambda: view.mapToGlobal(QtCore.QPoint(10, 10))))
        view.show_prim_info_at_cursor()
        assert shown == [QtCore.QPoint(10, 10)]
        monkeypatch.setattr(QtGui.QCursor, 'pos', staticmethod(lambda: view.mapToGlobal(QtCore.QPoint(-50, -50))))
        view.show_prim_info_at_cursor()
        assert len(shown) == 1

    def test_set_variant_edits_the_session_layer(self, with_stage, view):
        view._set_variant(Sdf.Path('/root/cube'), 'look', 'blue')
        prim = with_stage.stage.GetPrimAtPath('/root/cube')
        assert prim.GetVariantSets().GetVariantSet('look').GetVariantSelection() == 'blue'
        assert 'blue' in with_stage.stage.GetSessionLayer().ExportToString()

    @pytest.mark.parametrize('path, variant_set, variant', [
        ('/missing', 'look', 'red'), ('/root/cube', 'nope', 'red'), ('/root/cube', 'look', 'green')])
    def test_set_variant_ignores_bad_requests(self, with_stage, view, path, variant_set, variant):
        view._set_variant(Sdf.Path(path), variant_set, variant)
        prim = with_stage.stage.GetPrimAtPath('/root/cube')
        assert prim.GetVariantSets().GetVariantSet('look').GetVariantSelection() == 'red'

    def test_set_variant_without_a_stage(self, view):
        view._dataModel.stage = None
        view._set_variant(Sdf.Path('/x'), 'a', 'b')

    def test_context_menu_lists_variants(self, with_stage, view, monkeypatch):
        self.fake_pick(view, monkeypatch, '/root/cube')
        captured = []
        real_menu = QtWidgets.QMenu

        class RecordingMenu(real_menu):
            def exec(self, pos=None):
                captured.append([(sub.title(), [a.text() for a in sub.actions()]) for sub in
                                 [act.menu() for act in self.actions()]])
                self.actions()[0].menu().actions()[1].trigger()

        monkeypatch.setattr(QtWidgets, 'QMenu', RecordingMenu)
        view.contextMenuEvent(types.SimpleNamespace(pos=lambda: QtCore.QPoint(10, 10)))
        assert captured == [[('/root/cube / look', ['blue', 'red'])]]
        assert with_stage.stage.GetPrimAtPath('/root/cube').GetVariantSets().GetVariantSet(
            'look').GetVariantSelection() == 'red'

    @pytest.mark.parametrize('setup', ['no_stage', 'out_of_bounds', 'no_hit', 'short', 'unknown', 'no_variants', 'boom'])
    def test_context_menu_falls_back_to_the_base_handler(self, with_stage, view, monkeypatch, setup):
        called = []
        monkeypatch.setattr(uv.StageView, 'contextMenuEvent', lambda self, e: called.append(setup))
        path = '/root/cube'
        if setup == 'no_stage':
            view._dataModel.stage = None
        elif setup == 'out_of_bounds':
            self.fake_pick(view, monkeypatch, path, in_bounds=False)
        elif setup == 'no_hit':
            self.fake_pick(view, monkeypatch, None)
        elif setup == 'short':
            self.fake_pick(view, monkeypatch, path, results=(1,))
        elif setup == 'unknown':
            self.fake_pick(view, monkeypatch, '/missing')
        elif setup == 'no_variants':
            self.fake_pick(view, monkeypatch, '/root')
        else:
            monkeypatch.setattr(view, 'computePickFrustum', lambda x, y: 1 / 0)
        view.contextMenuEvent(types.SimpleNamespace(pos=lambda: QtCore.QPoint(10, 10)))
        assert called == [setup]


class TestUsdViewWidget:
    def test_starts_with_an_empty_stage_and_the_expected_settings(self, widget):
        assert widget.stage is not None and widget.viewSettings.domeLightEnabled
        assert not widget.viewSettings.ambientLightOnly

    def test_setting_a_stage_replaces_the_old_one(self, widget):
        first, second = make_stage(), make_stage()
        widget.stage = first
        widget.stage = second
        assert widget.stage == second
        widget.stage = None
        assert widget.stage is not None and widget.stage != second

    def test_stage_cleanup_failures_are_logged_and_a_set_failure_is_raised(self, widget, monkeypatch, caplog):
        monkeypatch.setattr(widget._view, 'closeRenderer', lambda: 1 / 0)
        with caplog.at_level('WARNING'):
            widget.stage = make_stage()
        assert 'Error during stage cleanup' in caplog.text

        def boom(**kwargs):
            raise RuntimeError('cannot update')

        monkeypatch.setattr(widget, 'update_view', boom)
        with pytest.raises(RuntimeError, match='cannot update'):
            widget.stage = make_stage()
        assert widget._view.updatesEnabled()

    def test_clipping_planes_follow_the_stage_bounds(self, widget):
        widget.stage = make_stage()
        widget._view._bbox = widget._view._bbox       # computed by the view when the stage is set
        widget._set_clipping_planes_from_stage_bounds()
        settings = widget.viewSettings
        if not widget._view._bbox.ComputeAlignedRange().IsEmpty():
            assert settings.freeCameraOverrideNear >= 0.001 and settings.freeCameraOverrideFar >= 100.0

    def test_clipping_planes_with_an_empty_scene_are_untouched(self, widget):
        widget.stage = Usd.Stage.CreateInMemory()
        before = widget.viewSettings.freeCameraOverrideNear
        widget._set_clipping_planes_from_stage_bounds()
        assert widget.viewSettings.freeCameraOverrideNear == before

    def test_clipping_planes_use_the_bbox(self, widget, monkeypatch):
        widget.stage = make_stage()
        bbox = types.SimpleNamespace(ComputeAlignedRange=lambda: Gf.Range3d(Gf.Vec3d(0, 0, 0), Gf.Vec3d(100, 0, 0)))
        monkeypatch.setattr(widget._view, '_bbox', bbox, raising=False)
        widget._set_clipping_planes_from_stage_bounds()
        assert widget.viewSettings.freeCameraOverrideNear == 0.001 and widget.viewSettings.freeCameraOverrideFar == 250.0
        flat = types.SimpleNamespace(ComputeAlignedRange=lambda: Gf.Range3d(Gf.Vec3d(1, 1, 1), Gf.Vec3d(1, 1, 1)))
        monkeypatch.setattr(widget._view, '_bbox', flat, raising=False)
        widget.viewSettings.freeCameraOverrideFar = 7.0
        widget._set_clipping_planes_from_stage_bounds()
        assert widget.viewSettings.freeCameraOverrideFar == 7.0

    def test_frames_and_updates(self, widget, monkeypatch):
        widget.stage = make_stage()
        updates = []
        monkeypatch.setattr(widget, 'update_view', lambda **kw: updates.append(kw))
        monkeypatch.setattr(widget, '_set_clipping_planes_from_stage_bounds', lambda: updates.append('clip'))
        widget.set_current_frame(12)
        assert widget._view._dataModel.currentFrame == Usd.TimeCode(12) and updates[-1] == 'clip'
        widget._view._dataModel.stage = None
        updates.clear()
        widget.set_current_frame(3)
        assert updates == []

    def test_update_view_needs_a_stage(self, widget, monkeypatch):
        calls = []
        monkeypatch.setattr(widget._view, 'updateView', lambda **kw: calls.append(kw))
        widget.update_view(resetCam=True)
        assert calls == [{'resetCam': True, 'forceComputeBBox': False}]
        widget._view._dataModel.stage = None
        widget.update_view()
        assert len(calls) == 1

    def test_aspect_ratio_lock(self, widget):
        widget.set_fixed_aspect_ratio(16, 9)
        assert widget.viewSettings.lockFreeCameraAspect and widget.viewSettings.freeCameraAspect == pytest.approx(16 / 9)
        widget.set_fixed_aspect_ratio(None, 9)
        assert not widget.viewSettings.lockFreeCameraAspect

    def test_dome_light_toggle_and_texture(self, widget):
        widget.stage = make_stage()
        widget.set_dome_light_enabled(False)
        assert widget.viewSettings.domeLightEnabled is False
        widget.set_dome_light_texture('sky.exr')
        light = UsdLux.DomeLight(widget.stage.GetPrimAtPath('/lights/dome_light'))
        assert light.GetTextureFileAttr().Get().path == 'sky.exr'
        widget.set_dome_light_texture('other.exr')                       # an existing dome light is reused
        assert light.GetTextureFileAttr().Get().path == 'other.exr'

    def test_a_non_light_prim_at_the_dome_path_is_left_alone(self, widget):
        widget.stage = make_stage()
        UsdGeom.Xform.Define(widget.stage, '/lights/dome_light')
        widget.set_dome_light_texture('sky.exr')
        assert not widget.stage.GetPrimAtPath('/lights/dome_light').IsA(UsdLux.DomeLight)

    def test_capturing_the_viewport(self, widget, monkeypatch):
        image = widget.capture_viewport_image()
        assert image is not None
        widget.hide()
        assert widget.capture_viewport_image() is None
        widget.show()
        monkeypatch.setattr(widget._view, 'grabFramebuffer', QtGui.QImage, raising=False)
        assert widget.capture_viewport_image().isNull()

    def test_capture_falls_back_to_grabbing_the_widget(self, widget, monkeypatch):
        class Plain:
            def __init__(self):
                self._size = QtCore.QSize(10, 10)

            def isVisible(self):
                return True

            def size(self):
                return self._size

            def update(self):
                pass

            def grab(self):
                return QtGui.QPixmap(10, 10)

        widget._view = Plain()
        assert widget.capture_viewport_image().width() == 10

    def test_camera_transform_round_trip(self, widget):
        widget.stage = make_stage()
        matrix = Gf.Matrix4d(1).SetTranslate(Gf.Vec3d(1, 2, 3))
        flat = [float(matrix.GetRow(i)[j]) for i in range(4) for j in range(4)]
        assert widget.set_camera_transform(flat) is True
        assert widget.get_camera_transform() == flat
        QtWidgets.QApplication.processEvents()                            # the deferred re-apply
        assert widget.get_camera_transform() == flat
        assert not hasattr(widget, '_pending_camera_transform')

    @pytest.mark.parametrize('bad', [None, [], [1, 2, 3], ['a'] * 16])
    def test_bad_camera_transforms_are_refused(self, widget, bad):
        assert widget.set_camera_transform(bad) is False

    def test_camera_transform_without_any_setter(self, widget, monkeypatch):
        widget.stage = make_stage()
        widget._view._dataModel.viewSettings.freeCamera._camera = None
        for name in ('SetFreeCameraMatrix', 'SetFreeCameraTransform'):
            monkeypatch.setattr(widget._view, name, None, raising=False)
        assert widget.set_camera_transform([1.0 if i % 5 == 0 else 0.0 for i in range(16)]) is False
        assert widget.get_camera_transform() is None

    def test_deferred_transform_without_a_pending_value_or_with_a_bad_one(self, widget):
        widget._deferred_set_camera_transform()
        widget._pending_camera_transform = [1.0] * 3
        widget._deferred_set_camera_transform()
        widget._pending_camera_transform = ['x'] * 16
        widget._deferred_set_camera_transform()
        assert not hasattr(widget, '_pending_camera_transform')

    def test_view_setter_methods_are_used_when_present(self, widget, monkeypatch):
        widget.stage = make_stage()
        received = []
        monkeypatch.setattr(widget._view, 'SetFreeCameraMatrix', received.append, raising=False)
        monkeypatch.setattr(widget._view, 'SetFreeCameraTransform', lambda m: 1 / 0, raising=False)
        assert widget.set_camera_transform([1.0 if i % 5 == 0 else 0.0 for i in range(16)]) is True
        QtWidgets.QApplication.processEvents()
        assert len(received) == 2                                       # once now, once deferred

    def test_close_releases_the_renderer_and_stage(self, widget):
        widget.stage = make_stage()
        widget.closeEvent(QtGui.QCloseEvent())
        assert widget._view._dataModel.stage is None

    def test_close_tolerates_cleanup_errors(self, widget, monkeypatch, caplog):
        monkeypatch.setattr(widget._view, 'closeRenderer', lambda: 1 / 0)
        with caplog.at_level('WARNING'):
            widget.closeEvent(QtGui.QCloseEvent())
        assert 'Error during renderer cleanup' in caplog.text

    def test_paint_draws_the_enabled_overlays(self, view, monkeypatch):
        drawn = []
        monkeypatch.setattr(uv.StageView, 'paintGL', lambda self: drawn.append('scene'), raising=False)
        monkeypatch.setattr(view.annotation_overlay, 'draw', lambda w, h: drawn.append('annotations'))
        monkeypatch.setattr(view.reticle_overlay, 'draw_from_stage_view', lambda v: drawn.append('reticle'))
        monkeypatch.setattr(view.slate_overlay, 'draw_from_stage_view', lambda v: drawn.append('slate'))
        view.annotation_overlay.enabled = True
        view.reticle_overlay.enabled = True
        view.slate_overlay.enabled = True
        view.paintGL()
        assert drawn == ['scene', 'annotations', 'reticle', 'slate']
        drawn.clear()
        view.annotation_overlay.enabled = False
        view.reticle_overlay.enabled = False
        view.slate_overlay.enabled = False
        view.paintGL()
        assert drawn == ['scene']

    def test_initialize_gl_applies_the_viewport_state(self, view, monkeypatch):
        applied = []
        monkeypatch.setattr(uv, '_apply_viewport_gl_state', lambda: applied.append(True))
        monkeypatch.setattr(uv.StageView, 'initializeGL', lambda self: None)
        view.initializeGL()
        assert applied == [True]

    def test_hud_drawing_is_a_noop(self, view):
        assert view.drawHUD(None) is None

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
"""Tests for deda.core.viewer._uv_panel: the UV canvas, the panel and the floating dock."""
import numpy as np
import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, Vt
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from deda.core.viewer import _uv, _uv_panel

_COUNTS = [4, 4]
_INDICES = [0, 1, 4, 3, 1, 2, 5, 4]
_POINTS = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0)]
_STRIP_UVS = [(0, 0), (.5, 0), (1, 0), (0, 1), (.5, 1), (1, 1)]


def _mesh(stage, path, uv_sets=(('st', _STRIP_UVS),), interpolation='vertex'):
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in _POINTS]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(_COUNTS))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(_INDICES))
    for name, values in uv_sets:
        pv = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(name, Sdf.ValueTypeNames.TexCoord2fArray, interpolation)
        pv.Set(Vt.Vec2fArray([Gf.Vec2f(*v) for v in values]))
    return mesh


@pytest.fixture
def stage():
    stage = Usd.Stage.CreateInMemory()
    _mesh(stage, '/a', (('st', _STRIP_UVS), ('lightmap', [(u * .5, v * .5) for u, v in _STRIP_UVS])))
    _mesh(stage, '/b', ())
    return stage


@pytest.fixture
def panel(qapp, stage):
    widget = _uv_panel.UvEditorPanel()
    widget.resize(700, 500)
    widget.show()
    widget.set_stage(stage)
    yield widget
    widget.close()


@pytest.fixture
def canvas(qapp):
    widget = _uv_panel.UvCanvas()
    widget.resize(400, 300)
    widget.show()
    yield widget
    widget.close()


def _mouse_move(pos, buttons=QtCore.Qt.MouseButton.NoButton, modifiers=QtCore.Qt.KeyboardModifier.NoModifier):
    return QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(pos), QtCore.QPointF(pos),
                             QtCore.Qt.MouseButton.NoButton, buttons, modifiers,
                             QtGui.QPointingDevice.primaryPointingDevice())


def _select_set(panel, name):
    panel._set_list.setCurrentItem(panel._set_list.findItems(name, QtCore.Qt.MatchFlag.MatchExactly)[0])


def _layout_with_a_flipped_face():
    """Three quads; the last has reversed winding, so it is the flipped one."""
    quad = [(0, 0), (.3, 0), (.3, .3), (0, .3)]
    values = ([(u, v) for u, v in quad] + [(u + .4, v) for u, v in quad]
              + [(u + .4, v + .5) for u, v in quad[::-1]])
    uv_set = _uv.UvSet('st', 'faceVarying', np.array(values, dtype=float))
    return _uv.UvLayout.from_mesh(uv_set, [4, 4, 4], list(range(12)))


def _layout(values=_STRIP_UVS):
    uv_set = _uv.UvSet('st', 'vertex', np.array(values, dtype=float))
    return _uv.UvLayout.from_mesh(uv_set, _COUNTS, _INDICES)


class TestCanvas:
    def test_empty_canvas_paints(self, canvas):
        assert not canvas.grab().isNull()
        assert canvas.uv_layout is None

    def test_layout_paints(self, canvas):
        canvas.set_layout(_layout())
        assert canvas.uv_layout is not None
        assert not canvas.grab().isNull()

    def test_every_display_toggle_paints(self, canvas):
        canvas.set_layout(_layout())
        for key in ('grid', 'checker', 'shaded', 'borders', 'flipped'):
            canvas.set_shown(key, False)
            assert not canvas.is_shown(key)
            canvas.grab()
            canvas.set_shown(key, True)
            assert canvas.is_shown(key)

    def test_flipped_faces_are_painted(self, canvas):
        layout = _layout_with_a_flipped_face()
        assert layout.flipped_faces().tolist() == [False, False, True]
        canvas.set_layout(layout)
        assert not canvas._flipped_path.isEmpty()
        canvas.grab()

    def test_grid_lines_are_skipped_when_there_would_be_too_many(self, canvas):
        image = QtGui.QImage(50, 50, QtGui.QImage.Format.Format_ARGB32)
        painter = QtGui.QPainter(image)
        canvas._paint_grid_lines(painter, QtCore.QRectF(0, 0, 5000, 5000), 1.0)
        canvas._paint_grid_lines(painter, QtCore.QRectF(0, 0, 3, 3), 1.0)
        painter.end()

    def test_frame_bounds_fits_uvs_outside_the_first_tile(self, canvas):
        canvas.set_layout(_layout([(u * 5, v * 5) for u, v in _STRIP_UVS]))
        canvas.grab()
        corner = canvas.uv_to_screen(5, 5)
        assert 0 <= corner.x() <= canvas.width() and 0 <= corner.y() <= canvas.height()

    def test_frame_tile_shows_the_whole_tile(self, canvas):
        canvas.frame_tile()
        top_right = canvas.uv_to_screen(1, 1)
        assert 0 < top_right.x() < canvas.width() and 0 < top_right.y() < canvas.height()

    def test_uv_screen_round_trip(self, canvas):
        point = canvas.uv_to_screen(.25, .75)
        u, v = canvas.screen_to_uv(point)
        assert (u, v) == pytest.approx((.25, .75))

    def test_v_points_up(self, canvas):
        canvas.frame_tile()
        assert canvas.uv_to_screen(0, 1).y() < canvas.uv_to_screen(0, 0).y()

    def test_wheel_zooms_around_the_cursor(self, canvas):
        canvas.frame_tile()
        anchor = QtCore.QPointF(200, 150)
        before = canvas.screen_to_uv(anchor)
        scale = canvas.scale
        event = QtGui.QWheelEvent(anchor, canvas.mapToGlobal(anchor), QtCore.QPoint(), QtCore.QPoint(0, 120),
                                  QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
                                  QtCore.Qt.ScrollPhase.NoScrollPhase, False)
        QtWidgets.QApplication.sendEvent(canvas, event)
        assert canvas.scale > scale
        assert canvas.screen_to_uv(anchor) == pytest.approx(before)

    def test_zoom_is_clamped(self, canvas):
        anchor = QtCore.QPointF(10, 10)
        for _ in range(200):
            event = QtGui.QWheelEvent(anchor, canvas.mapToGlobal(anchor), QtCore.QPoint(), QtCore.QPoint(0, -120),
                                      QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
                                      QtCore.Qt.ScrollPhase.NoScrollPhase, False)
            QtWidgets.QApplication.sendEvent(canvas, event)
        assert canvas.scale == _uv_panel.UvCanvas._MIN_SCALE

    def test_middle_drag_pans(self, canvas):
        canvas.frame_tile()
        start = canvas.uv_to_screen(0, 0)
        QtTest.QTest.mousePress(canvas, QtCore.Qt.MouseButton.MiddleButton, pos=QtCore.QPoint(100, 100))
        move = _mouse_move(QtCore.QPointF(130, 120), QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(canvas, move)
        QtTest.QTest.mouseRelease(canvas, QtCore.Qt.MouseButton.MiddleButton, pos=QtCore.QPoint(130, 120))
        moved = canvas.uv_to_screen(0, 0)
        assert (moved.x() - start.x(), moved.y() - start.y()) == pytest.approx((30, 20))

    def test_alt_left_drag_pans_and_plain_left_does_not(self, canvas):
        canvas.frame_tile()
        start = canvas.uv_to_screen(0, 0)
        QtTest.QTest.mousePress(canvas, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(100, 100))
        move = _mouse_move(QtCore.QPointF(150, 150), QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(canvas, move)
        QtTest.QTest.mouseRelease(canvas, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(150, 150))
        assert canvas.uv_to_screen(0, 0) == start
        QtTest.QTest.mousePress(canvas, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.AltModifier,
                                QtCore.QPoint(100, 100))
        move = _mouse_move(QtCore.QPointF(150, 150), QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.AltModifier)
        QtWidgets.QApplication.sendEvent(canvas, move)
        QtTest.QTest.mouseRelease(canvas, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(150, 150))
        assert canvas.uv_to_screen(0, 0) != start

    def test_mouse_move_reports_the_uv(self, canvas):
        canvas.frame_tile()
        seen = []
        canvas.cursorMoved.connect(lambda u, v: seen.append((u, v)))
        target = canvas.uv_to_screen(.5, .5).toPoint()
        QtTest.QTest.mouseMove(canvas, target)
        move = _mouse_move(QtCore.QPointF(target), QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(canvas, move)
        assert seen[-1] == pytest.approx((.5, .5), abs=0.01)

    def test_leave_signals(self, canvas):
        left = []
        canvas.cursorLeft.connect(lambda: left.append(True))
        QtWidgets.QApplication.sendEvent(canvas, QtCore.QEvent(QtCore.QEvent.Type.Leave))
        assert left

    def test_keys_frame(self, canvas):
        canvas.set_layout(_layout([(u * 5, v * 5) for u, v in _STRIP_UVS]))
        canvas.grab()
        QtTest.QTest.keyClick(canvas, QtCore.Qt.Key.Key_Home)
        tile_scale = canvas.scale
        QtTest.QTest.keyClick(canvas, QtCore.Qt.Key.Key_F)
        assert canvas.scale < tile_scale
        QtTest.QTest.keyClick(canvas, QtCore.Qt.Key.Key_X)  # unhandled keys fall through

    def test_zoomed_in_draws_the_tenths_grid_and_tile_labels(self, canvas):
        canvas.frame_tile()
        for _ in range(8):
            wheel = QtGui.QWheelEvent(QtCore.QPointF(200, 150), QtCore.QPointF(200, 150), QtCore.QPoint(),
                                      QtCore.QPoint(0, 120), QtCore.Qt.MouseButton.NoButton,
                                      QtCore.Qt.KeyboardModifier.NoModifier, QtCore.Qt.ScrollPhase.NoScrollPhase,
                                      False)
            QtWidgets.QApplication.sendEvent(canvas, wheel)
        assert canvas.scale > 240
        canvas.grab()

    def test_zoomed_far_out_skips_the_grid(self, canvas):
        canvas.set_layout(_layout([(u * 5000, v * 5000) for u, v in _STRIP_UVS]))
        canvas.grab()

    def test_large_layout_turns_shading_off(self, canvas, monkeypatch):
        monkeypatch.setattr(_uv_panel, '_MAX_SHADED_FACES', 1)
        canvas.set_layout(_layout())
        assert not canvas.shading_available()
        canvas.grab()

    def test_set_layout_none_clears(self, canvas):
        canvas.set_layout(_layout())
        canvas.set_layout(None)
        assert canvas.uv_layout is None
        assert canvas.shading_available()
        canvas.grab()


class TestPanel:
    def test_lists_the_meshes(self, panel):
        assert panel.mesh_paths == ['/a', '/b']

    def test_first_mesh_and_first_set_are_shown(self, panel):
        assert panel.current_set_name() == 'st'
        assert panel.canvas.uv_layout.uv_set.name == 'st'
        assert panel._set_list.topLevelItemCount() == 2

    def test_status_summarises_the_layout(self, panel):
        text = panel._stats_label.text()
        assert '2 faces' in text and '1 shells' in text and '1001' in text

    def test_status_reports_flipped_and_degenerate_faces(self, panel):
        panel._show_layout(_layout([(0, 0)] * 6))
        assert '2 degenerate' in panel._stats_label.text()
        panel._show_layout(_layout_with_a_flipped_face())
        assert '1 flipped' in panel._stats_label.text()

    def test_status_notes_when_shading_is_off(self, panel, monkeypatch):
        monkeypatch.setattr(_uv_panel, '_MAX_SHADED_FACES', 1)
        panel._show_layout(_layout())
        assert 'shell tint off' in panel._stats_label.text()

    def test_status_truncates_a_long_tile_list(self, panel):
        counts, verts = [4] * 6, [i for q in range(6) for i in range(4 * q, 4 * q + 4)]
        values = [(q * 1.5 + du, dv) for q in range(6) for du, dv in ((0, 0), (.5, 0), (.5, .5), (0, .5))]
        layout = _uv.UvLayout.from_mesh(_uv.UvSet('st', 'faceVarying', np.array(values, dtype=float)), counts, verts)
        panel._show_layout(layout)
        assert 'tiles 1001, 1002, 1004, 1005 ...' in panel._stats_label.text()

    def test_picking_another_set_switches_the_canvas(self, panel):
        _select_set(panel, 'lightmap')
        assert panel.canvas.uv_layout.uv_set.name == 'lightmap'

    def test_picking_a_mesh_without_uvs(self, panel):
        panel._mesh_combo.setCurrentIndex(1)
        assert panel.canvas.uv_layout is None
        assert panel._stats_label.text() == 'No UV sets on this mesh'
        assert panel.current_set_name() is None

    def test_switching_mesh_keeps_the_set_name_when_present(self, panel, stage):
        _mesh(stage, '/c', (('st', _STRIP_UVS), ('lightmap', _STRIP_UVS)))
        panel.refresh()
        _select_set(panel, 'lightmap')
        panel._mesh_combo.setCurrentIndex(panel._mesh_combo.findData('/c'))
        assert panel.current_set_name() == 'lightmap'

    def test_refresh_keeps_the_current_mesh(self, panel, stage):
        panel._mesh_combo.setCurrentIndex(1)
        _mesh(stage, '/c')
        panel.refresh()
        assert panel._mesh_combo.currentData() == '/b'
        assert '/c' in panel.mesh_paths

    def test_refresh_after_the_mesh_is_removed(self, panel, stage):
        stage.RemovePrim('/a')
        panel.refresh()
        assert panel.mesh_paths == ['/b']

    def test_show_prim(self, panel):
        assert panel.show_prim('/b')
        assert panel._mesh_combo.currentData() == '/b'
        assert not panel.show_prim('/missing')

    def test_no_stage(self, panel):
        panel.set_stage(None)
        assert panel.mesh_paths == []
        assert panel._stats_label.text() == 'No mesh'
        assert panel.canvas.uv_layout is None

    def test_stale_prim_after_stage_edit(self, panel, stage):
        stage.RemovePrim('/a')
        panel._load_mesh()
        assert panel.canvas.uv_layout is None

    def test_display_toggles_drive_the_canvas(self, panel):
        panel._toggles['grid'].setChecked(False)
        assert not panel.canvas.is_shown('grid')
        panel._toggles['grid'].setChecked(True)
        assert panel.canvas.is_shown('grid')

    def test_cursor_readout(self, panel):
        panel._on_cursor_moved(1.25, .5)
        assert '1.2500' in panel._cursor_label.text() and '1002' in panel._cursor_label.text()
        panel.canvas.cursorLeft.emit()
        assert panel._cursor_label.text() == ''

    def test_set_change_with_no_item_is_ignored(self, panel):
        panel._on_set_changed(None, None)

    def test_set_change_with_a_stray_item_is_ignored(self, panel):
        panel._on_set_changed(QtWidgets.QTreeWidgetItem(['stray']), None)

    def test_hidden_panel_defers_reading_the_stage(self, qapp, stage):
        panel = _uv_panel.UvEditorPanel()
        panel.set_stage(stage)
        assert panel.mesh_paths == []  # not visible yet, so nothing was read
        panel.show()
        assert panel.mesh_paths == ['/a', '/b']
        panel.close()

    def test_show_prim_reads_a_deferred_stage_first(self, qapp, stage):
        panel = _uv_panel.UvEditorPanel()
        panel.set_stage(stage)
        assert panel.show_prim('/b')
        panel.close()

    def test_refresh_button(self, panel, stage):
        _mesh(stage, '/d')
        button = next(b for b in panel.findChildren(QtWidgets.QPushButton) if b.text() == 'Refresh')
        button.click()
        assert '/d' in panel.mesh_paths


class TestDock:
    def test_hidden_and_floating_by_default(self, qapp):
        dock = _uv_panel.UvEditorDock()
        assert not dock.isVisible()
        assert dock.isFloating()
        assert dock.windowTitle() == 'UV Editor'
        assert isinstance(dock.panel, _uv_panel.UvEditorPanel)

    def test_toggle_action_shows_and_hides(self, qapp):
        window = QtWidgets.QMainWindow()
        dock = _uv_panel.UvEditorDock(window)
        window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)
        dock.hide()
        action = dock.toggleViewAction()
        assert action.isCheckable() and not action.isChecked()
        action.trigger()
        assert dock.isVisible() and action.isChecked()
        action.trigger()
        assert not dock.isVisible() and not action.isChecked()
        window.close()

    def test_set_stage_reaches_the_panel(self, qapp, stage):
        dock = _uv_panel.UvEditorDock()
        dock.set_stage(stage)
        dock.show()
        assert dock.panel.mesh_paths == ['/a', '/b']
        dock.close()

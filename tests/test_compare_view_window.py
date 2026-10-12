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
"""Tests for the A|B compare view, the compare window and the compare plugin."""
import sys
import time
import types
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

import deda.app
import deda.plugins.compare as compare
from deda.plugins.compare import _view, _window


def pixmap(width, height, color='red'):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(color))
    return QtGui.QPixmap.fromImage(image)


@pytest.fixture
def view(qapp):
    widget = _view.CompareView()
    widget.resize(400, 300)
    widget.show()
    yield widget
    widget.close()


class TestCompareView:
    def test_empty_view(self, view):
        assert not view.has_images()
        view.fit_to_view()
        view.zoom_to_actual_size()
        view.zoom_in()
        view.wheelEvent(types.SimpleNamespace(angleDelta=lambda: QtCore.QPoint(0, 120)))
        assert view.scene().items() == []
        view.set_images(None, QtGui.QPixmap())
        assert not view.has_images()

    def test_a_single_image_is_shown_without_a_divider(self, view):
        view.set_images(pixmap(40, 20), None)
        assert not view.has_images() and view._scene_rect.size().toSize() == QtCore.QSize(40, 20)
        assert view._divider_line not in view.scene().items()
        view.set_images(None, pixmap(10, 10))
        assert view._item_b is not None

    def test_two_images_share_the_larger_scene_rect(self, view):
        view.set_images(pixmap(40, 20), pixmap(160, 80))
        assert view.has_images() and view._scene_rect.size().toSize() == QtCore.QSize(160, 80)
        assert view._item_a.scale() == 4.0 and view._item_b.scale() == 1.0
        assert view._divider_line in view.scene().items()

    def test_divider_fraction_is_clamped_and_reported(self, view):
        view.set_images(pixmap(100, 50), pixmap(100, 50))
        moved = []
        view.divider_moved.connect(moved.append)
        view.set_divider_fraction(2.0)
        view.set_divider_fraction(-1.0)
        view.set_divider_fraction(0.25)
        assert moved == [1.0, 0.0, 0.25] and view._divider_line.line().x1() == 25
        assert view._item_a._clip_rect.width() == 25

    def test_clipped_items_paint_with_and_without_a_clip(self, view):
        view.set_images(pixmap(60, 30, 'red'), pixmap(60, 30, 'blue'))
        image = view.grab().toImage()
        assert not image.isNull()
        view._item_a.set_clip_rect(None)
        assert not view.grab().isNull()

    def test_zoom_actions(self, view):
        view.set_images(pixmap(100, 100), pixmap(100, 100))
        zooms = []
        view.zoom_changed.connect(zooms.append)
        view.zoom_to_actual_size()
        view.zoom_in()
        view.zoom_out()
        assert zooms[0] == 1.0 and zooms[1] == pytest.approx(1.25) and zooms[2] == pytest.approx(1.0)
        view.fit_to_view()
        assert len(zooms) == 4

    def test_zoom_has_limits(self, view):
        view.set_images(pixmap(100, 100), pixmap(100, 100))
        view.zoom_to_actual_size()
        for _ in range(40):
            view.zoom_in()
        top = view.transform().m11()
        view.zoom_in()
        assert top <= view._MAX_SCALE and view.transform().m11() == top
        for _ in range(60):
            view.zoom_out()
        bottom = view.transform().m11()
        view.zoom_out()
        assert bottom >= view._MIN_SCALE and view.transform().m11() == bottom

    def test_wheel_zooms_in_and_out(self, view):
        view.set_images(pixmap(100, 100), pixmap(100, 100))
        view.zoom_to_actual_size()

        def wheel(delta):
            point = QtCore.QPointF(50, 50)
            return QtGui.QWheelEvent(point, view.mapToGlobal(point), QtCore.QPoint(), QtCore.QPoint(0, delta),
                                     QtCore.Qt.NoButton, QtCore.Qt.NoModifier, QtCore.Qt.NoScrollPhase, False)

        view.wheelEvent(wheel(120))
        assert view.transform().m11() == pytest.approx(1.25)
        view.wheelEvent(wheel(-120))
        assert view.transform().m11() == pytest.approx(1.0)
        view.wheelEvent(wheel(0))
        assert view.transform().m11() == pytest.approx(1.0)

    def test_dragging_the_divider(self, view):
        view.set_images(pixmap(100, 100), pixmap(100, 100))
        x = int(view._divider_viewport_x())
        QtTest.QTest.mousePress(view.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(x, 100))
        assert view._dragging_divider
        target = view.mapFromScene(QtCore.QPointF(25, 50)).x()
        QtTest.QTest.mouseMove(view.viewport(), QtCore.QPoint(target, 100))
        assert view._divider_fraction == pytest.approx(0.25, abs=0.03)
        QtTest.QTest.mouseRelease(view.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(target, 100))
        assert not view._dragging_divider

    def test_panning_when_away_from_the_divider(self, view):
        view.set_images(pixmap(800, 600), pixmap(800, 600))
        view.zoom_to_actual_size()
        far = QtCore.QPoint(10, 100)
        QtTest.QTest.mousePress(view.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, far)
        assert view._panning
        before = view.horizontalScrollBar().value()
        QtTest.QTest.mouseMove(view.viewport(), QtCore.QPoint(60, 140))
        assert view.horizontalScrollBar().value() != before or view.verticalScrollBar().value() != 0
        QtTest.QTest.mouseRelease(view.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(60, 140))
        assert not view._panning

    def test_hover_changes_the_cursor_near_the_divider(self, view):
        view.set_images(pixmap(100, 100), pixmap(100, 100))
        x = int(view._divider_viewport_x())
        QtTest.QTest.mouseMove(view.viewport(), QtCore.QPoint(x, 100))
        assert view.cursor().shape() == QtCore.Qt.SplitHCursor
        QtTest.QTest.mouseMove(view.viewport(), QtCore.QPoint(5, 100))
        assert view.cursor().shape() == QtCore.Qt.ArrowCursor

    def test_other_buttons_and_empty_views_do_not_start_drags(self, view):
        QtTest.QTest.mousePress(view.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, 10))
        assert not view._panning and not view._dragging_divider
        view.set_images(pixmap(10, 10), pixmap(10, 10))
        QtTest.QTest.mousePress(view.viewport(), QtCore.Qt.RightButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, 10))
        QtTest.QTest.mouseRelease(view.viewport(), QtCore.Qt.RightButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, 10))
        assert not view._panning

    def test_zero_width_scene_does_not_divide_by_zero(self, view):
        view.set_images(pixmap(10, 10), pixmap(10, 10))
        view._scene_rect = QtCore.QRectF(0, 0, 0, 10)
        view._dragging_divider = True
        point = QtCore.QPointF(5, 5)
        view.mouseMoveEvent(QtGui.QMouseEvent(QtCore.QEvent.MouseMove, point, QtCore.Qt.NoButton, QtCore.Qt.NoButton,
                                              QtCore.Qt.NoModifier))
        assert view._divider_fraction == 0.5


class TestWindowHelpers:
    def test_rotation(self, qapp):
        original = pixmap(40, 20)
        assert _window._rotated_pixmap(original, 0) is original
        assert _window._rotated_pixmap(original, 360) is original
        rotated = _window._rotated_pixmap(original, 90)
        assert (rotated.width(), rotated.height()) == (20, 40)
        empty = QtGui.QPixmap()
        assert _window._rotated_pixmap(empty, 90) is empty

    def test_load_pixmap(self, tmp_path, qapp):
        path = tmp_path / 'a.png'
        pixmap(8, 4).save(str(path))
        assert _window._load_pixmap(path).width() == 8
        assert _window._load_pixmap(tmp_path / 'missing.png').isNull()


@pytest.fixture
def messages(monkeypatch):
    seen = []
    for kind in ('warning', 'information', 'critical'):
        monkeypatch.setattr(QtWidgets.QMessageBox, kind, staticmethod(
            lambda parent, title, text, *a, _kind=kind, **k: seen.append((_kind, text))))
    return seen


@pytest.fixture
def window(qapp, messages):
    win = _window.CompareWindow()
    win.show()
    yield win
    win.close()


@pytest.fixture
def images(tmp_path):
    a, b = tmp_path / 'a.png', tmp_path / 'b.png'
    pixmap(20, 10, 'red').save(str(a))
    pixmap(40, 20, 'blue').save(str(b))
    return a, b


def pick(monkeypatch, name, value):
    monkeypatch.setattr(QtWidgets.QFileDialog, name, staticmethod(lambda *a, **k: (value, '')))


class TestWindow:
    def test_starts_empty_with_a_hint(self, window):
        assert window._path_a_edit.text() == '' and 'Open A and B' in window.statusBar().currentMessage()
        assert window._model_combo.count() == len(_window.UPSCALE_MODELS)
        assert window._model_combo.currentData() == _window.DEFAULT_UPSCALE_MODEL

    def test_load_images_shows_both_and_the_scale(self, window, images):
        window.load_images(*images)
        assert window._view.has_images() and '(2.00x)' in window.statusBar().currentMessage()
        assert window._path_a_edit.text() == str(images[0]) and window._path_b_edit.toolTip() == str(images[1])

    def test_opening_a_then_b(self, window, images, monkeypatch):
        pick(monkeypatch, 'getOpenFileName', str(images[0]))
        window._open_a()
        assert 'Open B to compare' in window.statusBar().currentMessage()
        pick(monkeypatch, 'getOpenFileName', str(images[1]))
        window._open_b()
        assert window._view.has_images()
        pick(monkeypatch, 'getOpenFileName', '')
        window._open_a()
        window._open_b()
        assert window._path_a == images[0]

    def test_opening_only_b_hints_at_a(self, window, images, monkeypatch):
        pick(monkeypatch, 'getOpenFileName', str(images[1]))
        window._open_b()
        assert 'Open A to compare' in window.statusBar().currentMessage()

    def test_rotation_is_display_only_and_resets_on_open(self, window, images, monkeypatch):
        window.load_images(*images)
        window._rotate_a(90)
        window._rotate_b(-90)
        assert (window._rotation_a, window._rotation_b) == (90, 270)
        assert window._view._scene_rect.size().toSize() == QtCore.QSize(20, 40)
        pick(monkeypatch, 'getOpenFileName', str(images[0]))
        window._open_a()
        assert window._rotation_a == 0

    def test_heic_and_raw_need_the_extras(self, window, tmp_path, monkeypatch, messages):
        monkeypatch.setattr(_window, 'raw_formats_available', lambda: (False, 'install raw_formats'))
        assert window._load_pixmap_checked(tmp_path / 'x.heic').isNull()
        assert messages == [('warning', 'install raw_formats')]
        monkeypatch.setattr(_window, 'raw_formats_available', lambda: (True, ''))
        monkeypatch.setattr(_window, '_load_pixmap', lambda path: pixmap(2, 2))
        assert window._load_pixmap_checked(tmp_path / 'x.cr2').width() == 2
        assert window._load_pixmap_checked(tmp_path / 'x.png').width() == 2

    def test_copying_a_path(self, window, images, qapp):
        window.load_images(*images)
        window._copy_path_to_clipboard(window._path_a_edit)
        assert qapp.clipboard().text() == str(images[0])
        qapp.clipboard().setText('untouched')
        window._copy_path_to_clipboard(window._path_b_edit.__class__())          # an empty field
        assert qapp.clipboard().text() == 'untouched'

    def test_unsaved_upscale_results_are_labelled(self, window):
        window._pixmap_b = pixmap(4, 4)
        window._update_path_fields()
        assert window._path_b_edit.text() == '(unsaved upscale result)'

    def test_zoom_label_follows_the_view(self, window, images):
        window.load_images(*images)
        window._view.zoom_to_actual_size()
        assert window._zoom_label.text() == '100%'

    @pytest.mark.parametrize('which, expected_suffix', [('a', 'a_edited.png'), ('b', 'b_upscaled.png')])
    def test_default_save_names_never_overwrite_the_source(self, window, images, which, expected_suffix):
        window.load_images(*images)
        assert Path(window._default_save_name(which)).name == expected_suffix

    def test_default_save_names_without_sources(self, window, images):
        assert window._default_save_name('a') == 'image_a.png' and window._default_save_name('b') == 'image_b.png'
        window._path_a = images[0]
        assert Path(window._default_save_name('b')).name == 'a_upscaled.png'

    def test_saving_nothing_explains(self, window, messages):
        window._save_image('a')
        assert 'Nothing to save' in messages[0][1]

    def test_saving_writes_the_rotated_image(self, window, images, tmp_path, monkeypatch):
        window.load_images(*images)
        window._rotate_a(90)
        target = tmp_path / 'saved.png'
        pick(monkeypatch, 'getSaveFileName', str(target))
        window._save_image('a')
        saved = QtGui.QImage(str(target))
        assert (saved.width(), saved.height()) == (10, 20) and window._path_a == target
        pick(monkeypatch, 'getSaveFileName', str(tmp_path / 'b.png'))
        window._save_image('b')
        assert 'Saved B' in window.statusBar().currentMessage()
        pick(monkeypatch, 'getSaveFileName', '')
        window._save_image('a')

    def test_failed_saves_are_reported(self, window, images, tmp_path, monkeypatch, messages):
        window.load_images(*images)
        pick(monkeypatch, 'getSaveFileName', str(tmp_path / 'no' / 'such' / 'dir' / 'x.png'))
        window._save_image('a')
        assert messages[-1][0] == 'critical' and 'Failed to save' in messages[-1][1]

    def test_upscaling_without_the_extras(self, window, images, monkeypatch, messages):
        window.load_images(*images)
        monkeypatch.setattr(_window, 'is_available', lambda: (False, 'install upscale'))
        window._upscale_a()
        assert messages == [('warning', 'install upscale')]

    def test_upscale_asks_for_an_image_when_a_is_empty(self, window, images, monkeypatch, messages):
        pick(monkeypatch, 'getOpenFileName', '')
        window._upscale_a()
        assert window._path_a is None and messages == []
        pick(monkeypatch, 'getOpenFileName', str(images[0]))
        monkeypatch.setattr(_window, 'is_available', lambda: (False, 'no extras'))
        window._upscale_a()
        assert window._path_a == images[0] and messages == [('warning', 'no extras')]

    def wait_for(self, condition, seconds=10):
        deadline = time.time() + seconds
        while time.time() < deadline and not condition():
            QtWidgets.QApplication.processEvents()
            time.sleep(0.01)
        assert condition()

    def test_upscaling_runs_in_a_thread_and_fills_b(self, window, images, monkeypatch):
        window.load_images(*images)
        window._path_b = None
        window._rotation_a = 90
        result = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_RGB32)
        result.fill(QtCore.Qt.green)

        def fake_upscale(path, model_key, progress_cb, should_cancel):
            progress_cb(1, 2)
            progress_cb(2, 2)
            return result

        monkeypatch.setattr(_window, 'is_available', lambda: (True, ''))
        monkeypatch.setattr(_window, 'upscale_image', fake_upscale)
        window._upscale_a()
        self.wait_for(lambda: window._thread is not None and not window._pixmap_b.isNull()
                      and window._progress_dialog is None)
        assert window._path_b is None and window._rotation_b == 90 and window._pixmap_b.width() == 40
        window._thread.quit()
        window._thread.wait()

    def test_a_cancelled_upscale_keeps_b(self, window, monkeypatch):
        window._on_upscale_finished(None)
        assert 'cancelled' in window.statusBar().currentMessage()

    def test_a_failed_upscale_is_reported(self, window, images, monkeypatch, messages):
        window.load_images(*images)

        def boom(*args, **kwargs):
            raise RuntimeError('out of memory')

        monkeypatch.setattr(_window, 'is_available', lambda: (True, ''))
        monkeypatch.setattr(_window, 'upscale_image', boom)
        window._upscale_a()
        self.wait_for(lambda: any(kind == 'critical' for kind, _ in messages))
        assert 'out of memory' in messages[-1][1]
        window._thread.quit()
        window._thread.wait()

    def test_progress_and_results_without_a_dialog_are_ignored(self, window):
        window._progress_dialog = None
        window._on_upscale_progress(1, 2)
        window._on_upscale_failed('x')

    def test_worker_cancel_flag(self, qapp, images, monkeypatch):
        seen = []
        worker = _window._UpscaleWorker(images[0], 'ultrasharp')

        def fake(path, model_key, progress_cb, should_cancel):
            seen.append(should_cancel())
            worker.cancel()
            seen.append(should_cancel())
            return None

        monkeypatch.setattr(_window, 'upscale_image', fake)
        done = []
        worker.finished.connect(done.append)
        worker.run()
        assert seen == [False, True] and done == [None]


class TestPlugin:
    def test_load_adds_a_menu_action(self, qapp, monkeypatch):
        menu = QtWidgets.QMenu()
        monkeypatch.setattr(deda.app, 'get_main_menu', lambda: menu)
        tool = compare.Compare('Compare', compare.__version__, compare.__vendor__)
        assert tool.load() is True and [a.text() for a in menu.actions()] == ['Compare']

    def test_initialize_window(self, monkeypatch):
        built = []
        module = types.ModuleType('deda.plugins.compare._window')
        module.CompareWindow = lambda parent: built.append(parent) or 'window'
        monkeypatch.setitem(sys.modules, 'deda.plugins.compare._window', module)
        assert compare.Compare('Compare').initialize_window('parent') == 'window' and built == ['parent']

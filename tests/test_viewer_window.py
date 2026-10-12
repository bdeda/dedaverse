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
"""Tests for the viewer's main window: opening files, menus, 2D playback, notes and settings.

These need a full USD build (pxr.Usdviewq); they are skipped without one. The window is built on the
offscreen Qt platform, which has no OpenGL, so nothing is rendered; the logic is what is tested.
"""
import json
import types
from pathlib import Path

import pytest

pytest.importorskip('pxr.Usdviewq', reason='the viewer needs a full USD build')

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from pxr import Sdf, Usd, UsdGeom  # noqa: E402

from deda.core.viewer import _dedacam, _window  # noqa: E402


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    """A MainWindow whose settings live in an ini file and whose dialogs record instead of blocking."""
    real = QtCore.QSettings

    class IniSettings:
        def __new__(cls, organization, application):
            return real(str(tmp_path / 'viewer.ini'), real.IniFormat)

    monkeypatch.setattr(_window.QtCore, 'QSettings', IniSettings)
    dialogs = []
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', staticmethod(
        lambda parent, title, text, *a, **k: dialogs.append(('warning', title, text)) or
        QtWidgets.QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QtWidgets.QMessageBox, 'information', staticmethod(
        lambda parent, title, text, *a, **k: dialogs.append(('information', title, text))))
    monkeypatch.setattr(_window, '_get_hdr_images_dir', lambda: tmp_path / 'no_hdr')
    win = _window.MainWindow()
    win.dialogs = dialogs
    win.settings_file = tmp_path / 'viewer.ini'
    win.show()
    yield win
    win.close()


@pytest.fixture
def stage_file(tmp_path):
    path = tmp_path / 'scene.usda'
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.Camera.Define(stage, '/shot_cam')
    UsdGeom.Camera.Define(stage, '/other_cam')
    UsdGeom.Cube.Define(stage, '/cube')
    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(10)
    stage.SetTimeCodesPerSecond(30)
    stage.GetRootLayer().Save()
    return path


@pytest.fixture
def png_sequence(tmp_path):
    folder = tmp_path / 'seq'
    folder.mkdir()
    for frame in range(1, 5):
        image = QtGui.QImage(16, 12, QtGui.QImage.Format.Format_RGBA8888)
        image.fill(QtGui.QColor(frame * 50, 20, 20))
        image.save(str(folder / f'shot.{frame:04d}.png'))
    return folder


def trigger(menu_action_text, menu):
    for action in menu.actions():
        if action.text() == menu_action_text:
            action.trigger()
            return action
    raise AssertionError(f'{menu_action_text!r} not in {[a.text() for a in menu.actions()]}')


class TestHelpers:
    def test_flatten_camera_transform(self):
        flat = list(range(16))
        nested = [[float(r * 4 + c) for c in range(4)] for r in range(4)]
        assert _window._flatten_camera_transform(flat) == [float(i) for i in flat]
        assert _window._flatten_camera_transform(nested) == [float(i) for i in flat]
        for bad in (None, [], 'x', [1, 2, 3], [[1, 2], [3, 4], [5, 6], [7, 8]], [['a'] * 4] * 4 + [1]):
            assert _window._flatten_camera_transform(bad) is None

    def test_hdr_dir_prefers_the_project_setting_then_the_default(self, tmp_path, monkeypatch):
        from deda.core import _config
        hdr = tmp_path / 'hdr'
        hdr.mkdir()
        project = types.SimpleNamespace(hdr_images_dir=str(hdr))
        monkeypatch.setattr(_config.LayeredConfig, 'instance', classmethod(
            lambda cls: types.SimpleNamespace(current_project=project)))
        assert _window._get_hdr_images_dir() == hdr
        project.hdr_images_dir = str(tmp_path / 'missing')
        assert _window._get_hdr_images_dir() == _window._DEFAULT_HDR_IMAGES_DIR
        monkeypatch.setattr(_config.LayeredConfig, 'instance', classmethod(lambda cls: 1 / 0))
        assert _window._get_hdr_images_dir() == _window._DEFAULT_HDR_IMAGES_DIR

    def test_loading_overlay_animates_and_paints(self, qapp):
        overlay = _window.LoadingOverlay()
        overlay.resize(80, 80)
        overlay.show()
        angle = overlay._angle if hasattr(overlay, '_angle') else None
        overlay._tick()
        assert not overlay.grab().isNull()
        overlay.hide()
        overlay.resize(100, 100)
        del angle


class TestOpening:
    def test_starts_in_3d_with_the_3d_menu_items_enabled(self, window):
        assert window.mode == '3d'
        assert window._dome_light_action.isEnabled() and not window._media_actions[0].isEnabled()

    def test_open_stage_sets_title_playbar_and_recent_files(self, window, stage_file):
        window._open_path(str(stage_file))
        assert window.mode == '3d' and window.windowTitle().endswith('scene.usda')
        assert window._playbar.frameRange() == (1, 10)
        assert window._recent_files == [str(stage_file.resolve())]
        assert window.opened_entity is None and window.rootdir == Path()
        assert window._get_stage_fps() == 30

    def test_stage_without_a_timeline_gets_a_default_range(self, window, tmp_path):
        path = tmp_path / 'static.usda'
        stage = Usd.Stage.CreateNew(str(path))
        stage.GetRootLayer().Save()
        window._open_path(str(path))
        assert window._playbar.frameRange() == (0, 100)

    def test_unreadable_stage_warns(self, window, tmp_path):
        bad = tmp_path / 'bad.usda'
        bad.write_text('this is not usd')
        window._open_path(str(bad))
        assert window.dialogs and window.dialogs[0][1] == 'Open Failed'

    def test_open_image_sequence_switches_to_2d(self, window, png_sequence):
        window._open_path(str(png_sequence / 'shot.0002.png'))
        assert window.mode == '2d' and window._playbar.frameRange() == (1, 4)
        assert 'shot' in window.windowTitle() and window._media_actions[0].isEnabled()
        assert not window._dome_light_action.isEnabled()
        assert window._playbar.isVisible()

    def test_single_image_hides_the_playbar(self, window, tmp_path):
        image = QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGBA8888)
        image.fill(QtCore.Qt.red)
        path = tmp_path / 'still.png'
        image.save(str(path))
        window._open_path(str(path))
        assert window.mode == '2d' and not window._playbar.isVisible()

    def test_unreadable_media_warns_and_keeps_the_mode(self, window, tmp_path):
        bad = tmp_path / 'broken.png'
        bad.write_bytes(b'not a png')
        window._open_path(str(bad))
        assert window.mode == '3d' and window.dialogs[0][1] == 'Open Failed'

    def test_going_back_to_3d_from_2d(self, window, png_sequence, stage_file):
        window._open_path(str(png_sequence / 'shot.0001.png'))
        window._open_path(str(stage_file))
        assert window.mode == '3d' and window._dome_light_action.isEnabled()

    def test_open_file_dialog(self, window, stage_file, monkeypatch):
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (str(stage_file), '')))
        window._on_open_file()
        assert window.windowTitle().endswith('scene.usda')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('', '')))
        window._on_open_file()

    def test_drag_and_drop(self, window, png_sequence):
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(str(png_sequence / 'shot.0001.png'))])

        class Event:
            def __init__(self, data):
                self._mime = data
                self.accepted = False

            def mimeData(self):
                return self._mime

            def acceptProposedAction(self):
                self.accepted = True

        enter = Event(mime)
        window.dragEnterEvent(enter)
        assert enter.accepted
        refused = Event(QtCore.QMimeData())
        window.dragEnterEvent(refused)
        assert not refused.accepted
        window.dropEvent(Event(mime))
        assert window.mode == '2d'
        window.dropEvent(Event(QtCore.QMimeData()))           # no urls: nothing happens
        assert window.mode == '2d'


class TestRecentFiles:
    def test_list_is_deduplicated_limited_and_listed_in_the_menu(self, window, tmp_path):
        paths = []
        for i in range(12):
            p = tmp_path / f'f{i}.usda'
            p.write_text('')
            paths.append(p)
            window._add_to_recent_files(str(p))
        window._add_to_recent_files(str(paths[5]))
        assert len(window._recent_files) == _window._MAX_RECENT_FILES
        assert window._recent_files[0] == str(paths[5].resolve())
        assert window._recent_files.count(str(paths[5].resolve())) == 1
        assert len(window._recent_files_menu.actions()) == _window._MAX_RECENT_FILES

    def test_missing_recent_file_is_pruned_with_a_warning(self, window, tmp_path):
        gone = tmp_path / 'gone.usda'
        window._recent_files = [str(gone)]
        window._on_open_recent_file(str(gone))
        assert window._recent_files == [] and 'no longer exists' in window.dialogs[0][2]

    def test_existing_recent_file_is_opened(self, window, stage_file):
        window._on_open_recent_file(str(stage_file))
        assert window.windowTitle().endswith('scene.usda')

    def test_recent_files_persist_between_windows(self, window, stage_file, qapp):
        window._add_to_recent_files(str(stage_file))
        window._save_view_settings()
        assert str(stage_file.resolve()) in _window.MainWindow()._recent_files

    def test_loading_a_single_string_setting(self, window):
        window._settings.setValue(_window._KEY_RECENT_FILES, 'only.usda')
        assert window._load_recent_files() == ['only.usda']
        window._settings.setValue(_window._KEY_RECENT_FILES, '')
        assert window._load_recent_files() == []


class TestCameraMenu:
    def test_lists_the_free_camera_and_stage_cameras(self, window, stage_file):
        window._open_path(str(stage_file))
        window._populate_camera_menu()
        assert [a.text() for a in window._camera_menu.actions()] == ['Free Camera', '/shot_cam', '/other_cam']
        assert window._camera_menu.actions()[0].isChecked()

    def test_choosing_a_camera_and_going_back_to_the_free_camera(self, window, stage_file):
        window._open_path(str(stage_file))
        window._populate_camera_menu()
        window._camera_menu.actions()[1].trigger()
        assert window._viewer.viewSettings.cameraPrim.GetPath() == Sdf.Path('/shot_cam')
        window._populate_camera_menu()
        assert window._camera_menu.actions()[1].isChecked() and not window._camera_menu.actions()[0].isChecked()
        window._camera_menu.actions()[0].trigger()
        assert window._viewer.viewSettings.cameraPrim is None or not window._viewer.viewSettings.cameraPrim

    def test_no_stage_means_no_cameras(self, window):
        assert window._stage_camera_paths() == []


class TestMediaMenus:
    def test_channels_and_exposure(self, window, png_sequence):
        window._open_path(str(png_sequence / 'shot.0001.png'))
        window._channel_actions['r'].trigger()
        assert window._media_view.channel == 'r'
        window._on_exposure_step(1.0)
        window._on_exposure_step(1.0)
        assert window._media_view.exposure == 2.0
        window._on_exposure_step(None)
        assert window._media_view.exposure == 0.0

    def test_frame_all_fits_the_image_in_2d(self, window, png_sequence, monkeypatch):
        fitted = []
        window._open_path(str(png_sequence / 'shot.0001.png'))
        monkeypatch.setattr(window._media_view, 'fit', lambda: fitted.append(True))
        window._on_frame_all()
        assert fitted == [True]

    def test_frame_all_in_3d_resets_the_camera(self, window, monkeypatch):
        calls = []
        monkeypatch.setattr(window._viewer, 'update_view', lambda **kw: calls.append(kw))
        window._on_frame_all()
        assert calls == [{'resetCam': True, 'forceComputeBBox': True}]


class TestPlayback2D:
    def test_playbar_follows_and_drives_the_image_sequence(self, window, png_sequence):
        window._open_path(str(png_sequence / 'shot.0001.png'))
        window._playbar.setFrame(3)
        assert window._media_view.frame_number == 3

    def test_timer_playback_advances_and_loops(self, window, png_sequence):
        window._open_path(str(png_sequence / 'shot.0001.png'))
        window._on_play_clicked()
        assert window._play_timer.isActive()
        window._on_play_tick()
        assert window._playbar.frame() == 2
        window._playbar.setFrame(4)
        window._on_play_tick()
        assert window._playbar.frame() == 1
        window._on_stop_clicked()
        assert not window._play_timer.isActive()

    def test_single_frame_media_cannot_play(self, window, tmp_path):
        image = QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGBA8888)
        image.fill(QtCore.Qt.red)
        image.save(str(tmp_path / 'still.png'))
        window._open_path(str(tmp_path / 'still.png'))
        window._on_play_clicked()
        assert not window._play_timer.isActive()

    def test_video_playback_streams_frames(self, window, monkeypatch):
        played = []
        events = []

        class FakeVideo:
            kind = 'video'
            first_frame, last_frame, frame_count, fps = 1, 10, 10, 25.0
            name = 'clip.mp4'

            def play(self, callback):
                played.append(callback)

            def pause(self):
                events.append('pause')

            def close(self):
                pass

        monkeypatch.setattr(window._media_view, '_source', FakeVideo(), raising=False)
        monkeypatch.setattr(type(window._media_view), 'source', property(lambda self: self._source))
        monkeypatch.setattr(window._media_view, 'set_frame', lambda f: events.append(('set_frame', f)))
        monkeypatch.setattr(window._media_view, 'show_decoded', lambda image, frame: events.append(('show', frame)))
        window._mode = '2d'
        window._playbar.setFrameRange(1, 10)
        window._playbar.setFrame(10)
        window._on_play_clicked()
        assert played == [window._on_video_frame] and ('set_frame', 1) in events      # restarts from the top
        window._on_video_frame('image', 5)
        assert window._playbar.frame() == 5 and ('show', 5) in events
        before = events.count('pause')
        window._on_video_frame('image', 10)                                           # last frame stops playback
        assert events.count('pause') > before


class TestPlayback3D:
    def test_timer_interval_follows_the_stage_fps(self, window, stage_file):
        window._open_path(str(stage_file))
        window._on_play_clicked()
        assert window._play_timer.interval() == int(1000 / 30)
        window._on_stop_clicked()

    def test_default_fps_without_a_stage(self, window):
        assert window._get_stage_fps() == _window._DEFAULT_FPS

    def test_playbar_frame_changes_set_the_stage_frame(self, window, stage_file, monkeypatch):
        window._open_path(str(stage_file))
        frames = []
        monkeypatch.setattr(window._viewer, 'set_current_frame', frames.append)
        window._on_playbar_frame_changed(7)
        assert frames == [7]


class TestViewToggles:
    def test_toggles_write_through_to_the_view_settings(self, window):
        window._show_hud_action.setChecked(False)
        window._on_show_hud_toggled()
        assert window._viewer.viewSettings.showHUD is False
        window._show_bboxes_action.setChecked(False)
        window._on_show_bboxes_toggled()
        assert window._viewer.viewSettings.showBBoxes is False
        window._mask_opaque_action.setChecked(False)
        window._on_mask_opaque_toggled()
        window._dome_light_action.setChecked(False)
        window._on_dome_light_toggled()
        assert window._viewer.viewSettings.domeLightEnabled is False

    def test_reticle_and_slate_toggles_are_remembered(self, window):
        window._reticle_enabled_action.setChecked(True)
        window._on_reticle_enabled_toggled()
        assert window._viewer.reticle_overlay.enabled and window._settings.value(
            _window._KEY_RETICLE_ENABLED, type=bool) is True
        window._on_reticle_style_changed('grid')
        assert window._viewer.reticle_overlay.style == 'grid' and window._reticle_style_actions['grid'].isChecked()
        assert not window._reticle_style_actions['frame'].isChecked()
        window._slate_layer_action.setChecked(True)
        window._on_slate_layer_toggled()
        assert window._viewer.slate_overlay.enabled

    def test_annotation_layer_toggle(self, window):
        window._annotation_layer_action.setChecked(True)
        window._on_annotation_layer_toggled()
        assert window._viewer.annotation_overlay.enabled
        window._viewer.annotation_mode_enabled = True
        window._annotation_layer_action.setChecked(False)
        window._on_annotation_layer_toggled()
        assert not window._viewer.annotation_overlay.enabled and not window._viewer.annotation_mode_enabled
        window._on_annotation_overlay_enabled_changed(True)
        assert window._annotation_layer_action.isChecked()

    @pytest.mark.parametrize('handler, attr', [
        ('_on_annotation_color', 'default_color'), ('_on_annotation_text_color', 'default_text_color')])
    def test_annotation_colors_come_from_the_color_dialog(self, window, monkeypatch, handler, attr):
        monkeypatch.setattr(QtWidgets.QColorDialog, 'getColor',
                            staticmethod(lambda initial, parent, title: QtGui.QColor(0, 255, 0)))
        getattr(window, handler)()
        assert getattr(window._viewer.annotation_overlay, attr)[:3] == (0.0, 1.0, 0.0)
        monkeypatch.setattr(QtWidgets.QColorDialog, 'getColor',
                            staticmethod(lambda initial, parent, title: QtGui.QColor()))      # cancelled
        getattr(window, handler)()
        assert getattr(window._viewer.annotation_overlay, attr)[:3] == (0.0, 1.0, 0.0)

    def test_aspect_ratio_locks_and_unlocks(self, window):
        window._on_set_aspect_ratio(16, 9)
        assert window._viewer.viewSettings.lockFreeCameraAspect and window._mask_opaque_action.isChecked()
        window._on_set_aspect_ratio(None, None)
        assert not window._viewer.viewSettings.lockFreeCameraAspect

    def test_environment_texture(self, window, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(window._viewer, 'set_dome_light_texture', calls.append)
        window._on_set_environment_texture(tmp_path / 'sky.exr')
        window._on_set_environment_texture(None)
        assert calls == [str(tmp_path / 'sky.exr'), None] and not window._loading_overlay.isVisible()

    def test_environment_menu_lists_hdr_files(self, qapp, tmp_path, monkeypatch):
        hdr = tmp_path / 'hdr'
        hdr.mkdir()
        (hdr / 'studio.hdr').write_text('')
        (hdr / 'sky.exr').write_text('')
        monkeypatch.setattr(_window, '_get_hdr_images_dir', lambda: hdr)
        real = QtCore.QSettings
        monkeypatch.setattr(_window.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'e.ini'), real.IniFormat))
        win = _window.MainWindow()
        menu = [m for m in win.menuBar().findChildren(QtWidgets.QMenu) if m.title() == '&Environment Texture'][0]
        assert [a.text() for a in menu.actions() if a.text()][1:] == ['sky', 'studio']
        win.close()

    def test_loading_overlay_follows_the_viewer_size(self, window):
        window._show_loading_overlay()
        assert window._loading_overlay.isVisible()
        window._viewer.resize(300, 200)
        QtWidgets.QApplication.processEvents()
        assert window._loading_overlay.geometry() == window._viewer.rect()
        window._hide_loading_overlay()
        assert not window._loading_overlay.isVisible()


class TestSettings:
    def test_view_settings_round_trip(self, window, qapp, tmp_path, monkeypatch):
        window._viewer.set_dome_light_enabled(False)
        window._viewer.viewSettings.showHUD = False
        window._viewer.viewSettings.showBBoxes = False
        window._viewer.viewSettings.lockFreeCameraAspect = True
        window._viewer.viewSettings.freeCameraAspect = 1.5
        window._viewer.reticle_overlay.enabled = True
        window._viewer.reticle_overlay.style = 'frame'
        window._viewer.slate_overlay.enabled = True
        window._save_view_settings()
        again = _window.MainWindow()
        assert again._viewer.viewSettings.domeLightEnabled is False and again._viewer.viewSettings.showHUD is False
        assert again._viewer.viewSettings.lockFreeCameraAspect and again._viewer.viewSettings.freeCameraAspect == 1.5
        assert again._viewer.reticle_overlay.enabled and again._viewer.reticle_overlay.style == 'frame'
        assert again._viewer.slate_overlay.enabled and again._reticle_style_actions['frame'].isChecked()
        again._settings.setValue(_window._KEY_RETICLE_STYLE, 'nonsense')
        again._restore_view_settings()
        assert again._viewer.reticle_overlay.style == 'crosshair'
        again.close()

    def test_environment_texture_setting_is_restored_when_the_file_exists(self, window, tmp_path, monkeypatch):
        texture = tmp_path / 'sky.exr'
        texture.write_text('')
        window._settings.setValue(_window._KEY_ENV_TEXTURE, str(texture))
        calls = []
        monkeypatch.setattr(window._viewer, 'set_dome_light_texture', calls.append)
        window._restore_view_settings()
        assert calls == [str(texture)] and window._env_texture_path == str(texture)

    def test_geometry_is_restored(self, window):
        window.resize(777, 555)
        window._save_view_settings()
        window.resize(300, 300)
        window._restore_geometry()
        assert window.width() == 777


@pytest.fixture
def entity(window, tmp_path):
    root = tmp_path / 'asset_root'
    root.mkdir()
    window._opened_entity = types.SimpleNamespace(rootdir=root)
    return root


class TestNotes:
    def test_saving_requires_a_project_entity(self, window):
        window._on_save_annotations_to_notes()
        assert 'not under a Dedaverse project' in window.dialogs[0][2]

    def test_saving_writes_json_and_a_snapshot(self, window, entity, monkeypatch):
        monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText',
                            staticmethod(lambda *a, **k: ('  needs more glow  ', True)))
        monkeypatch.setattr(window._viewer, 'capture_viewport_image', lambda: QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGB32))
        monkeypatch.setattr(window._viewer, 'get_camera_transform', lambda: [1.0] * 16)
        window._viewer.annotation_overlay.add_text(1, 2, 'fix this')
        window._on_save_annotations_to_notes()
        notes = entity / 'notes'
        payload = json.loads(next(notes.glob('annotations_*.json')).read_text())
        assert payload['description'] == 'needs more glow' and payload['camera_transform'] == [1.0] * 16
        assert payload['texts'][0]['text'] == 'fix this' and 'user' in payload
        assert next(notes.glob('snapshot_*.png')).is_file()
        assert window.dialogs[-1][0] == 'information' and not window._viewer.annotation_overlay.dirty

    def test_saving_without_a_snapshot_warns(self, window, entity, monkeypatch):
        monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText', staticmethod(lambda *a, **k: ('', False)))
        monkeypatch.setattr(window._viewer, 'capture_viewport_image', lambda: None)
        window._on_save_annotations_to_notes()
        assert 'could not capture viewport image' in window.dialogs[-1][2]

    def test_saving_with_a_snapshot_that_fails_to_write_warns(self, window, entity, monkeypatch):
        class Unsavable:
            def isNull(self):
                return False

            def save(self, path):
                return False

        monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText', staticmethod(lambda *a, **k: ('', True)))
        monkeypatch.setattr(window._viewer, 'capture_viewport_image', lambda: Unsavable())
        window._on_save_annotations_to_notes()
        assert 'failed to save PNG' in window.dialogs[-1][2]

    def test_saving_without_a_content_root_warns(self, window, tmp_path):
        window._opened_entity = types.SimpleNamespace(rootdir=tmp_path / 'does_not_exist')
        window._on_save_annotations_to_notes()
        assert 'content root' in window.dialogs[-1][2]

    def test_notes_dir_and_load_menu(self, window, entity, stage_file, monkeypatch):
        assert window._get_notes_dir() is None                       # no stage open
        window._populate_load_notes_menu()
        assert window._load_notes_menu.actions()[0].text() == '(No notes for current element)'
        window._open_path(str(stage_file))
        monkeypatch.setattr(_window.Project, 'from_path', staticmethod(lambda p: types.SimpleNamespace(rootdir=entity)))
        assert window._get_notes_dir() is None                       # no notes folder yet
        notes = entity / 'notes'
        notes.mkdir()
        window._populate_load_notes_menu()
        assert window._load_notes_menu.actions()[0].text() == '(No saved notes)'
        (notes / 'annotations_20250101_000000.json').write_text(json.dumps({'user': 'ben', 'strokes': [], 'texts': []}))
        (notes / 'annotations_20250102_000000.json').write_text('{ broken')
        window._populate_load_notes_menu()
        labels = [a.text() for a in window._load_notes_menu.actions()]
        assert len(labels) == 2 and any('ben' in label for label in labels) and any('(unknown)' in label for label in labels)

    def test_loading_historic_notes_restores_annotations_and_camera(self, window, tmp_path, monkeypatch):
        path = tmp_path / 'notes.json'
        path.write_text(json.dumps({'strokes': [], 'texts': [{'text': 'old note', 'x': 1, 'y': 2}],
                                    'camera_transform': [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]}))
        transforms = []
        monkeypatch.setattr(window._viewer, 'set_camera_transform', transforms.append)
        window._on_load_historic_notes(str(path))
        assert window._viewer.annotation_overlay.texts[0].text == 'old note'
        assert window._viewer.annotation_overlay.enabled and window._annotation_layer_action.isChecked()
        assert len(transforms) == 1 and len(transforms[0]) == 16

    def test_loading_asks_before_discarding_unsaved_notes(self, window, tmp_path, monkeypatch):
        path = tmp_path / 'notes.json'
        path.write_text(json.dumps({'texts': [{'text': 'loaded'}]}))
        window._viewer.annotation_overlay.add_text(0, 0, 'unsaved')
        monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', staticmethod(
            lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Cancel))
        window._on_load_historic_notes(str(path))
        assert window._viewer.annotation_overlay.texts[0].text == 'unsaved'
        monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', staticmethod(
            lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Ok))
        window._on_load_historic_notes(str(path))
        assert window._viewer.annotation_overlay.texts[0].text == 'loaded'

    def test_loading_a_missing_or_unreadable_file_warns(self, window, tmp_path):
        window._on_load_historic_notes(str(tmp_path / 'missing.json'))
        assert 'File not found' in window.dialogs[-1][2]
        bad = tmp_path / 'bad.json'
        bad.write_text('{ nope')
        window._on_load_historic_notes(str(bad))
        assert 'Could not read notes' in window.dialogs[-1][2]


class TestDedacamMenu:
    def test_modes_and_quality_actions_exist(self, window):
        assert set(window._dedacam_mode_actions) == set(_dedacam.MODES)
        assert window._dedacam_mode_actions['off'].isChecked()
        assert window._dedacam_quality_actions['cinematic'].isChecked()

    def test_missing_dedacam_warns_and_resets_to_off(self, window, monkeypatch):
        def unavailable(mode):
            raise _dedacam.DedacamUnavailable('no build')

        monkeypatch.setattr(window._dedacam, 'set_mode', unavailable)
        window._on_dedacam_mode_selected('dof')
        assert window.dialogs[-1][1] == 'Dedacam is not available' and window._dedacam_mode_actions['off'].isChecked()

    def test_free_camera_gets_a_status_hint_and_a_stage_camera_does_not(self, window, stage_file, monkeypatch):
        hook = types.SimpleNamespace(set_view=lambda view, mode: None, set_quality=lambda tier: None)
        monkeypatch.setattr(window._dedacam, '_loader', lambda: hook)
        window._open_path(str(stage_file))
        window._on_dedacam_mode_selected('dof')
        assert 'free camera' in window.statusBar().currentMessage()
        window.statusBar().clearMessage()
        window._on_camera_selected(Sdf.Path('/shot_cam'))
        window._on_dedacam_mode_selected('zones')
        assert window.statusBar().currentMessage() == ''

    def test_quality_changes_apply_and_refresh_only_when_active(self, window, monkeypatch):
        hook = types.SimpleNamespace(set_view=lambda view, mode: None, set_quality=lambda tier: None)
        monkeypatch.setattr(window._dedacam, '_loader', lambda: hook)
        updates = []
        monkeypatch.setattr(window._viewer, 'update_view', lambda **kw: updates.append(kw))
        window._on_dedacam_quality_selected('low')
        assert window._dedacam.quality == 'low' and updates == []
        window._on_dedacam_mode_selected('dof')
        updates.clear()
        window._on_dedacam_quality_selected('high')
        assert len(updates) == 1

    def test_unavailable_menu_has_a_tooltip(self, window, monkeypatch, qapp):
        monkeypatch.setattr(_dedacam.DedacamController, 'is_available', staticmethod(lambda: False))
        menu = QtWidgets.QMenu()
        window._build_dedacam_menu(menu)
        assert _dedacam.ENV_BUILD_DIR in menu.actions()[0].menu().toolTip()


def test_close_event_saves_settings_and_stops_playback(window, png_sequence):
    window._open_path(str(png_sequence / 'shot.0001.png'))
    window._on_play_clicked()
    window.close()
    window._settings.sync()
    assert not window._play_timer.isActive() and window.settings_file.is_file()

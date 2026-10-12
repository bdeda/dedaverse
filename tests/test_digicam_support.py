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
"""Tests for digicam's metadata helpers, application launcher, thumbnail grid and plugin."""
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

import deda.app
import deda.plugins.digicam as digicam
from deda.plugins.digicam import _grid, _launch, _metadata


@pytest.fixture
def photos(tmp_path):
    folder = tmp_path / 'photos'
    (folder / 'sub').mkdir(parents=True)
    for name in ('b.png', 'a.JPG', 'sub/c.png'):
        image = QtGui.QImage(20, 10, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtCore.Qt.blue)
        image.save(str(folder / name))
    (folder / 'notes.txt').write_text('x')
    (folder / 'sub' / 'movie.mp4').write_text('x')
    return folder


class TestMetadata:
    def test_iter_image_files_is_recursive_sorted_and_filtered(self, photos):
        names = [p.relative_to(photos).as_posix() for p in _metadata.iter_image_files(photos)]
        assert names == sorted(names) and set(names) == {'a.JPG', 'b.png', 'sub/c.png'}

    def test_thumbnails(self, photos, qapp):
        thumb = _metadata.load_thumbnail(photos / 'b.png', max_size=8)
        assert max(thumb.width(), thumb.height()) == 8
        assert _metadata.load_thumbnail(photos / 'notes.txt').isNull()

    @pytest.mark.parametrize('size, expected', [
        ((6000, 4000), '3:2'), ((1920, 1080), '16:9'), ((1000, 1000), '1:1'),
        ((6001, 4003), '1.50:1'), ((0, 10), 'unknown'), ((10, -1), 'unknown'),
    ])
    def test_aspect_ratio(self, size, expected):
        assert _metadata.aspect_ratio_str(*size) == expected

    def test_print_sizes(self):
        assert _metadata.max_print_size_in(6000, 4500) == (40.0, 30.0)
        assert _metadata.max_print_size_in(300, 300, dpi=300) == (1.0, 1.0)
        assert _metadata.format_print_size(6000, 4000) == '40.0" x 26.7" @ 150 DPI'


class TestLaunch:
    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch, tmp_path):
        for name in _launch._ENV_VARS.values():
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv('PROGRAMFILES', str(tmp_path / 'pf'))
        monkeypatch.delenv('PROGRAMFILES(X86)', raising=False)

    def make_exe(self, base, relative):
        exe = Path(base) / relative
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_text('')
        return str(exe)

    def test_environment_override_wins(self, monkeypatch, tmp_path):
        exe = self.make_exe(tmp_path, 'custom/ps.exe')
        monkeypatch.setenv('DIGICAM_PHOTOSHOP_EXE', exe)
        self.make_exe(tmp_path / 'pf', 'Adobe/Adobe Photoshop 2025/Photoshop.exe')
        assert _launch.find_app('photoshop') == exe

    def test_a_bad_override_falls_back_to_the_install_location(self, monkeypatch, tmp_path):
        monkeypatch.setenv('DIGICAM_PHOTOSHOP_EXE', str(tmp_path / 'gone.exe'))
        installed = self.make_exe(tmp_path / 'pf', 'Adobe/Adobe Photoshop 2025/Photoshop.exe')
        assert Path(_launch.find_app('photoshop')) == Path(installed)

    @pytest.mark.parametrize('key, relative', [
        ('lightroom_classic', 'Adobe/Adobe Lightroom Classic/Lightroom.exe'),
        ('lightroom', 'Adobe/Adobe Lightroom/Lightroom.exe'),
    ])
    def test_other_apps(self, tmp_path, key, relative):
        installed = self.make_exe(tmp_path / 'pf', relative)
        assert Path(_launch.find_app(key)) == Path(installed)

    def test_not_installed(self):
        assert _launch.find_app('photoshop') is None

    def test_program_files_defaults(self, monkeypatch):
        monkeypatch.delenv('PROGRAMFILES', raising=False)
        assert _launch._program_files_dirs() == [r'C:\Program Files', r'C:\Program Files (x86)']
        monkeypatch.setenv('PROGRAMFILES(X86)', 'D:/x86')
        assert _launch._program_files_dirs() == ['D:/x86']

    def test_open_in_app_launches_the_executable(self, monkeypatch, tmp_path):
        exe = self.make_exe(tmp_path / 'pf', 'Adobe/Adobe Photoshop 2025/Photoshop.exe')
        launched = []
        monkeypatch.setattr(_launch.subprocess, 'Popen', lambda cmd: launched.append(cmd))
        _launch.open_in_app('photoshop', tmp_path / 'img.png')
        assert [Path(launched[0][0]), launched[0][1]] == [Path(exe), str(tmp_path / 'img.png')]

    def test_open_in_app_explains_a_missing_install(self, tmp_path):
        with pytest.raises(FileNotFoundError, match='DIGICAM_LIGHTROOM_EXE'):
            _launch.open_in_app('lightroom', tmp_path / 'img.png')

    def test_labels_cover_every_app(self):
        assert set(_launch.APP_LABELS) == set(_launch._ENV_VARS) == set(_launch._GLOB_PATTERNS)


class TestPhotoTile:
    def test_shows_name_captions_and_a_thumbnail(self, photos, qapp):
        tile = _grid.PhotoTile(photos / 'b.png', caption_lines=['20 x 10', '3:2'])
        labels = [label.text() for label in tile.findChildren(QtWidgets.QLabel)]
        assert 'b.png' in labels and '20 x 10' in labels and tile.path == photos / 'b.png'
        assert any(label.pixmap() and not label.pixmap().isNull() for label in tile.findChildren(QtWidgets.QLabel))

    def test_unreadable_images_show_a_placeholder(self, photos, qapp):
        tile = _grid.PhotoTile(photos / 'notes.txt')
        assert '?' in [label.text() for label in tile.findChildren(QtWidgets.QLabel)]

    def test_checkable_tiles_toggle_on_click(self, photos, qapp):
        tile = _grid.PhotoTile(photos / 'b.png', checkable=True)
        tile.show()
        seen = []
        tile.toggled.connect(lambda path, checked: seen.append(checked))
        QtTest.QTest.mouseClick(tile, QtCore.Qt.LeftButton)
        QtTest.QTest.mouseClick(tile, QtCore.Qt.LeftButton)
        assert seen == [True, False]
        tile.set_checked(True)
        assert '2px' in tile.styleSheet()
        tile.close()

    def test_plain_tiles_do_not_toggle(self, photos, qapp):
        tile = _grid.PhotoTile(photos / 'b.png')
        tile.show()
        seen = []
        tile.toggled.connect(lambda *a: seen.append(a))
        QtTest.QTest.mouseClick(tile, QtCore.Qt.LeftButton)
        assert seen == []
        tile.close()

    def test_double_click_activates_and_context_menu_reports_a_position(self, photos, qapp):
        tile = _grid.PhotoTile(photos / 'b.png')
        tile.show()
        activated, menus = [], []
        tile.activated.connect(activated.append)
        tile.context_menu_requested.connect(lambda path, pos: menus.append(path))
        QtTest.QTest.mouseDClick(tile, QtCore.Qt.LeftButton)
        tile.customContextMenuRequested.emit(QtCore.QPoint(1, 1))
        tile.mouseDoubleClickEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonDblClick, QtCore.QPointF(1, 1), QtCore.Qt.RightButton, QtCore.Qt.RightButton,
            QtCore.Qt.NoModifier))
        assert activated == [photos / 'b.png'] and menus == [photos / 'b.png']
        tile.close()


class TestPhotoGrid:
    def test_set_paths_builds_tiles_and_forwards_signals(self, photos, qapp):
        grid = _grid.PhotoGrid(tile_size=100, checkable=True, caption_fn=lambda p: [p.stem])
        grid.resize(450, 300)
        grid.show()
        paths = sorted(_metadata.iter_image_files(photos))
        grid.set_paths(paths)
        assert grid.paths == paths and len(grid._tiles) == 3
        toggled, activated, menus = [], [], []
        grid.tile_toggled.connect(lambda p, c: toggled.append((p.name, c)))
        grid.tile_activated.connect(activated.append)
        grid.tile_context_menu_requested.connect(lambda p, pos: menus.append(p))
        tile = grid._tiles[0]
        tile.show()
        QtTest.QTest.mouseClick(tile, QtCore.Qt.LeftButton)
        tile.activated.emit(tile.path)
        tile.context_menu_requested.emit(tile.path, QtCore.QPoint())
        assert toggled == [(tile.path.name, True)] and activated == [tile.path] and menus == [tile.path]
        grid.clear_checked()
        assert not tile._checked
        grid.close()

    def test_replacing_paths_and_reflow_on_resize(self, photos, qapp):
        grid = _grid.PhotoGrid(tile_size=100)
        grid.resize(450, 300)
        grid.show()
        paths = sorted(_metadata.iter_image_files(photos))
        grid.set_paths(paths)
        wide = {grid._layout.getItemPosition(i)[0] for i in range(grid._layout.count())}
        grid.resize(120, 300)
        QtWidgets.QApplication.processEvents()
        narrow = {grid._layout.getItemPosition(i)[0] for i in range(grid._layout.count())}
        assert len(narrow) > len(wide)
        grid.set_paths(paths[:1])
        assert len(grid._tiles) == 1 and grid._layout.count() == 1
        grid.close()


class TestDigicamPlugin:
    def test_load_adds_a_menu_action(self, qapp, monkeypatch):
        menu = QtWidgets.QMenu()
        monkeypatch.setattr(deda.app, 'get_main_menu', lambda: menu)
        tool = digicam.Digicam('Digicam', digicam.__version__, digicam.__vendor__)
        assert tool.load() is True and tool.loaded
        assert [a.text() for a in menu.actions()] == ['Digicam']

    def test_initialize_window_builds_the_digicam_window(self, qapp, monkeypatch):
        import sys
        import types
        built = []
        module = types.ModuleType('deda.plugins.digicam._window')
        module.DigicamWindow = lambda parent: built.append(parent) or 'window'
        monkeypatch.setitem(sys.modules, 'deda.plugins.digicam._window', module)
        assert digicam.Digicam('Digicam').initialize_window('parent') == 'window' and built == ['parent']

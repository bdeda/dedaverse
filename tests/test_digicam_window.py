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
"""Tests for the digicam window: scanning a folder, copying to the printable library, browsing it."""
import types
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from deda.plugins.digicam import _window


@pytest.fixture
def settings(tmp_path):
    return QtCore.QSettings(str(tmp_path / 'digicam.ini'), QtCore.QSettings.IniFormat)


@pytest.fixture
def dialogs(monkeypatch):
    seen = []
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', staticmethod(
        lambda parent, title, text, *a, **k: seen.append(('warning', text))))
    monkeypatch.setattr(QtWidgets.QMessageBox, 'information', staticmethod(
        lambda parent, title, text, *a, **k: seen.append(('information', text))))
    return seen


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / 'camera'
    folder.mkdir()
    for name in ('one.png', 'two.png', 'three.png'):
        image = QtGui.QImage(30, 20, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtCore.Qt.green)
        image.save(str(folder / name))
    return folder


@pytest.fixture
def review(qapp, settings):
    tab = _window._ReviewTab(settings)
    yield tab
    tab.close()


@pytest.fixture
def library(qapp, settings):
    tab = _window._LibraryTab(settings)
    yield tab
    tab.close()


class TestReviewTab:
    def test_scanning_needs_a_valid_folder(self, review, dialogs):
        review._source_edit.setText('')
        review._scan()
        assert dialogs == [('warning', 'Choose a valid source folder first.')]

    def test_scanning_lists_images_and_remembers_the_folder(self, review, source, settings):
        review._source_edit.setText(str(source))
        review._scan()
        assert len(review._grid.paths) == 3 and review._status_label.text() == '3 images found'
        assert settings.value(_window._SETTINGS_SOURCE_DIR) == str(source)

    def test_captions_show_the_pixel_size(self, review, source, tmp_path):
        assert review._caption_for(source / 'one.png') == ['30 x 20']
        assert review._caption_for(tmp_path / 'missing.png') == []

    def test_selection_drives_the_copy_button(self, review, source):
        review._source_edit.setText(str(source))
        review._scan()
        first, second = review._grid.paths[:2]
        review._on_tile_toggled(first, True)
        review._on_tile_toggled(second, True)
        assert review._copy_btn.isEnabled() and review._copy_btn.text() == 'Copy Selected to Library (2)'
        review._on_tile_toggled(second, False)
        review._on_tile_toggled(second, False)
        assert review._copy_btn.text() == 'Copy Selected to Library (1)'
        review._on_tile_toggled(first, False)
        assert not review._copy_btn.isEnabled()

    def test_copying_needs_a_destination(self, review, dialogs):
        review._dest_edit.setText('  ')
        review._copy_selected()
        assert dialogs == [('warning', 'Choose a printable library folder first.')]

    def test_copying_skips_files_already_in_the_library(self, review, source, tmp_path, dialogs):
        dest = tmp_path / 'library'
        dest.mkdir()
        (dest / 'one.png').write_bytes(b'already here')
        review._source_edit.setText(str(source))
        review._dest_edit.setText(str(dest))
        review._scan()
        copied = []
        review.copied_to_library.connect(copied.append)
        for path in review._grid.paths:
            review._on_tile_toggled(path, True)
        review._copy_selected()
        assert sorted(p.name for p in dest.iterdir()) == ['one.png', 'three.png', 'two.png']
        assert (dest / 'one.png').read_bytes() == b'already here'
        kind, message = dialogs[-1]
        assert kind == 'information' and 'Copied 2 image(s)' in message and 'Skipped 1 already present: one.png' in message
        assert copied == [str(dest)] and not review._selected and not review._copy_btn.isEnabled()

    def test_many_skipped_files_are_abbreviated(self, review, source, tmp_path, dialogs):
        dest = tmp_path / 'library'
        dest.mkdir()
        names = [f'img{i}.png' for i in range(7)]
        for name in names:
            (dest / name).write_bytes(b'x')
            (source / name).write_bytes(b'y')
        review._dest_edit.setText(str(dest))
        review._selected = {source / name for name in names}
        review._copy_selected()
        assert 'Skipped 7 already present' in dialogs[-1][1] and dialogs[-1][1].endswith('...')

    def test_browsing_for_folders(self, review, monkeypatch, settings, tmp_path):
        chosen = []
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory',
                            staticmethod(lambda *a, **k: str(tmp_path / 'picked')))
        review.dest_dir_changed.connect(chosen.append)
        review._browse_source()
        review._browse_dest()
        assert review._source_edit.text() == str(tmp_path / 'picked') == review._dest_edit.text()
        assert chosen == [str(tmp_path / 'picked')]
        assert settings.value(_window._SETTINGS_DEST_DIR) == str(tmp_path / 'picked')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
        review._browse_source()
        review._browse_dest()
        assert review._source_edit.text() == str(tmp_path / 'picked')

    def test_saved_folders_are_restored(self, qapp, tmp_path):
        stored = QtCore.QSettings(str(tmp_path / 'saved.ini'), QtCore.QSettings.IniFormat)
        stored.setValue(_window._SETTINGS_SOURCE_DIR, 'S:/cam')
        stored.setValue(_window._SETTINGS_DEST_DIR, 'D:/lib')
        tab = _window._ReviewTab(stored)
        assert tab._source_edit.text() == 'S:/cam' and tab._dest_edit.text() == 'D:/lib'


class TestLibraryTab:
    def test_refresh_without_a_folder(self, library):
        library.refresh()
        assert library._grid.paths == [] and 'Choose a printable library folder' in library._status_label.text()

    def test_refresh_lists_the_library(self, library, source):
        library.set_directory(str(source))
        assert len(library._grid.paths) == 3 and library._status_label.text() == '3 images in library'

    def test_captions_include_aspect_and_print_size(self, library, source, tmp_path):
        lines = library._caption_for(source / 'one.png')
        assert lines[0] == '30 x 20  (3:2)' and lines[1] == '0.2" x 0.1" @ 150 DPI'
        assert library._caption_for(tmp_path / 'missing.png') == ['size unknown']

    def test_browse(self, library, monkeypatch, source, settings):
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(source)))
        library._browse()
        assert len(library._grid.paths) == 3 and settings.value(_window._SETTINGS_DEST_DIR) == str(source)
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
        library._browse()
        assert len(library._grid.paths) == 3

    def test_context_menu_offers_every_app(self, library, source, monkeypatch):
        shown = []

        class FakeAction:
            def __init__(self, text):
                self.text = text
                self.triggered = types.SimpleNamespace(connect=lambda fn: shown.append(('connected', text)))

        class FakeMenu:
            def __init__(self, parent=None):
                self.actions = []

            def addAction(self, text):
                action = FakeAction(text)
                self.actions.append(action)
                return action

            def exec(self, pos):
                shown.append(('exec', [a.text for a in self.actions], pos))

        monkeypatch.setattr(_window.QtWidgets, 'QMenu', FakeMenu)
        library._show_context_menu(source / 'one.png', QtCore.QPoint(3, 4))
        assert shown[-1] == ('exec', ['Open in Photoshop', 'Open in Lightroom Classic', 'Open in Lightroom'],
                             QtCore.QPoint(3, 4))

    def test_open_in_launches_or_warns(self, library, source, monkeypatch, dialogs):
        launched = []
        monkeypatch.setattr(_window, 'open_in_app', lambda key, path: launched.append((key, path)))
        library._open_in('photoshop', source / 'one.png')
        assert launched == [('photoshop', source / 'one.png')]

        def missing(key, path):
            raise FileNotFoundError('no Photoshop')

        monkeypatch.setattr(_window, 'open_in_app', missing)
        library._open_in('photoshop', source / 'one.png')
        assert dialogs == [('warning', 'no Photoshop')]


class TestWindow:
    @pytest.fixture
    def ini(self, tmp_path, monkeypatch):
        real = QtCore.QSettings
        path = str(tmp_path / 'window.ini')
        monkeypatch.setattr(_window.QtCore, 'QSettings', lambda *a: real(path, real.IniFormat))
        return real(path, real.IniFormat)

    def test_builds_both_tabs(self, qapp, ini):
        window = _window.DigicamWindow()
        tabs = window.centralWidget()
        assert [tabs.tabText(i) for i in range(tabs.count())] == ['Review Source', 'Printable Library']
        window.close()

    def test_a_saved_library_is_listed_on_open(self, qapp, ini, source):
        ini.setValue(_window._SETTINGS_DEST_DIR, str(source))
        window = _window.DigicamWindow()
        assert len(window._library_tab._grid.paths) == 3
        window.close()

    def test_choosing_or_filling_the_library_updates_the_library_tab(self, qapp, ini, source):
        window = _window.DigicamWindow()
        window._review_tab.dest_dir_changed.emit(str(source))
        assert len(window._library_tab._grid.paths) == 3
        window._library_tab.set_directory('')
        window._review_tab.copied_to_library.emit(str(source))
        assert len(window._library_tab._grid.paths) == 3
        window.close()

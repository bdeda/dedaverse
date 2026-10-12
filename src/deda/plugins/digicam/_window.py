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
"""Digicam tool window: review a source folder and curate a printable-image library."""
__all__ = ['DigicamWindow']

import logging
import shutil
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ._grid import PhotoGrid
from ._launch import APP_LABELS, open_in_app
from ._metadata import aspect_ratio_str, format_print_size, iter_image_files, read_image_size

log = logging.getLogger(__name__)

_SETTINGS_SOURCE_DIR = 'digicam/source_dir'
_SETTINGS_DEST_DIR = 'digicam/dest_dir'


class _ReviewTab(QtWidgets.QWidget):
    """Scan a source folder and manually mark images to copy into the printable library."""

    dest_dir_changed = QtCore.Signal(str)
    copied_to_library = QtCore.Signal(str)

    def __init__(self, settings: QtCore.QSettings, parent=None):
        super().__init__(parent=parent)
        self._settings = settings
        self._selected: set[Path] = set()

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QGridLayout()
        layout.addLayout(form)

        self._source_edit = QtWidgets.QLineEdit(settings.value(_SETTINGS_SOURCE_DIR, ''))
        source_browse = QtWidgets.QPushButton('Browse...')
        source_browse.clicked.connect(self._browse_source)
        form.addWidget(QtWidgets.QLabel('Source folder:'), 0, 0)
        form.addWidget(self._source_edit, 0, 1)
        form.addWidget(source_browse, 0, 2)

        self._dest_edit = QtWidgets.QLineEdit(settings.value(_SETTINGS_DEST_DIR, ''))
        dest_browse = QtWidgets.QPushButton('Browse...')
        dest_browse.clicked.connect(self._browse_dest)
        form.addWidget(QtWidgets.QLabel('Printable library folder:'), 1, 0)
        form.addWidget(self._dest_edit, 1, 1)
        form.addWidget(dest_browse, 1, 2)

        scan_row = QtWidgets.QHBoxLayout()
        layout.addLayout(scan_row)
        scan_btn = QtWidgets.QPushButton('Scan Source Folder')
        scan_btn.clicked.connect(self._scan)
        scan_row.addWidget(scan_btn)
        scan_row.addStretch()
        self._status_label = QtWidgets.QLabel('')
        scan_row.addWidget(self._status_label)

        self._grid = PhotoGrid(checkable=True, caption_fn=self._caption_for)
        self._grid.tile_toggled.connect(self._on_tile_toggled)
        layout.addWidget(self._grid, stretch=1)

        copy_row = QtWidgets.QHBoxLayout()
        layout.addLayout(copy_row)
        copy_row.addStretch()
        self._copy_btn = QtWidgets.QPushButton('Copy Selected to Library (0)')
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy_selected)
        copy_row.addWidget(self._copy_btn)

    def _caption_for(self, path: Path) -> list[str]:
        size = read_image_size(path)
        if not size:
            return []
        return [f'{size[0]} x {size[1]}']

    def _browse_source(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose Source Folder', self._source_edit.text())
        if directory:
            self._source_edit.setText(directory)
            self._settings.setValue(_SETTINGS_SOURCE_DIR, directory)

    def _browse_dest(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Printable Library Folder', self._dest_edit.text()
        )
        if directory:
            self._dest_edit.setText(directory)
            self._settings.setValue(_SETTINGS_DEST_DIR, directory)
            self.dest_dir_changed.emit(directory)

    def _scan(self) -> None:
        source_text = self._source_edit.text().strip()
        source = Path(source_text)
        if not source_text or not source.is_dir():  # Path('') is the current directory, not "nothing chosen"
            QtWidgets.QMessageBox.warning(self, 'Digicam', 'Choose a valid source folder first.')
            return
        self._settings.setValue(_SETTINGS_SOURCE_DIR, str(source))
        paths = list(iter_image_files(source))
        self._selected.clear()
        self._update_copy_button()
        self._grid.set_paths(paths)
        self._status_label.setText(f'{len(paths)} images found')

    def _on_tile_toggled(self, path: Path, checked: bool) -> None:
        if checked:
            self._selected.add(path)
        else:
            self._selected.discard(path)
        self._update_copy_button()

    def _update_copy_button(self) -> None:
        count = len(self._selected)
        self._copy_btn.setText(f'Copy Selected to Library ({count})')
        self._copy_btn.setEnabled(count > 0)

    def _copy_selected(self) -> None:
        dest_text = self._dest_edit.text().strip()
        if not dest_text:
            QtWidgets.QMessageBox.warning(self, 'Digicam', 'Choose a printable library folder first.')
            return
        dest = Path(dest_text)
        dest.mkdir(parents=True, exist_ok=True)
        self._settings.setValue(_SETTINGS_DEST_DIR, str(dest))

        copied = 0
        skipped = []
        for path in sorted(self._selected):
            target = dest / path.name
            if target.exists():
                skipped.append(path.name)
                continue
            shutil.copy2(path, target)
            copied += 1

        self._selected.clear()
        self._update_copy_button()
        self._grid.clear_checked()

        message = f'Copied {copied} image(s) to {dest}.'
        if skipped:
            shown = ', '.join(skipped[:5]) + ('...' if len(skipped) > 5 else '')
            message += f'\nSkipped {len(skipped)} already present: {shown}'
        QtWidgets.QMessageBox.information(self, 'Digicam', message)
        self.copied_to_library.emit(str(dest))


class _LibraryTab(QtWidgets.QWidget):
    """Browse the printable library folder, showing aspect ratio and max print size per image."""

    def __init__(self, settings: QtCore.QSettings, parent=None):
        super().__init__(parent=parent)
        self._settings = settings

        layout = QtWidgets.QVBoxLayout(self)

        top_row = QtWidgets.QHBoxLayout()
        layout.addLayout(top_row)
        top_row.addWidget(QtWidgets.QLabel('Printable library folder:'))
        self._dir_edit = QtWidgets.QLineEdit(settings.value(_SETTINGS_DEST_DIR, ''))
        self._dir_edit.setReadOnly(True)
        top_row.addWidget(self._dir_edit, stretch=1)
        browse_btn = QtWidgets.QPushButton('Browse...')
        browse_btn.clicked.connect(self._browse)
        top_row.addWidget(browse_btn)
        refresh_btn = QtWidgets.QPushButton('Refresh')
        refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(refresh_btn)

        self._grid = PhotoGrid(checkable=False, caption_fn=self._caption_for)
        self._grid.tile_context_menu_requested.connect(self._show_context_menu)
        layout.addWidget(self._grid, stretch=1)

        self._status_label = QtWidgets.QLabel('')
        layout.addWidget(self._status_label)

    def _caption_for(self, path: Path) -> list[str]:
        size = read_image_size(path)
        if not size:
            return ['size unknown']
        width, height = size
        return [
            f'{width} x {height}  ({aspect_ratio_str(width, height)})',
            format_print_size(width, height),
        ]

    def set_directory(self, directory: str) -> None:
        self._dir_edit.setText(directory)
        self.refresh()

    def _browse(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Printable Library Folder', self._dir_edit.text()
        )
        if directory:
            self._settings.setValue(_SETTINGS_DEST_DIR, directory)
            self.set_directory(directory)

    def refresh(self) -> None:
        directory = self._dir_edit.text().strip()
        if not directory or not Path(directory).is_dir():
            self._grid.set_paths([])
            self._status_label.setText('Choose a printable library folder.')
            return
        paths = list(iter_image_files(Path(directory)))
        self._grid.set_paths(paths)
        self._status_label.setText(f'{len(paths)} images in library')

    def _show_context_menu(self, path: Path, global_pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        for app_key, label in APP_LABELS.items():
            action = menu.addAction(f'Open in {label}')
            action.triggered.connect(lambda checked=False, k=app_key, p=path: self._open_in(k, p))
        menu.exec(global_pos)

    def _open_in(self, app_key: str, path: Path) -> None:
        try:
            open_in_app(app_key, path)
        except FileNotFoundError as err:
            QtWidgets.QMessageBox.warning(self, 'Digicam', str(err))


class DigicamWindow(QtWidgets.QMainWindow):
    """Main window for the digicam plugin: review source photos, then browse the printable library."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle('Digicam')
        self.resize(1000, 700)

        settings = QtCore.QSettings('DedaFX', 'Dedaverse')

        tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(tabs)

        self._review_tab = _ReviewTab(settings)
        self._library_tab = _LibraryTab(settings)
        self._review_tab.dest_dir_changed.connect(self._library_tab.set_directory)
        self._review_tab.copied_to_library.connect(self._library_tab.set_directory)

        tabs.addTab(self._review_tab, 'Review Source')
        tabs.addTab(self._library_tab, 'Printable Library')

        if settings.value(_SETTINGS_DEST_DIR, ''):
            self._library_tab.refresh()

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
"""Compare tool window: A|B slider comparison, with selectable-model upscaling of A into B."""
__all__ = ['CompareWindow']

import logging
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from deda.core._image_io import (
    HEIC_EXTENSIONS,
    RAW_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    is_available as raw_formats_available,
    load_full_qimage,
)

from ._upscale import DEFAULT_UPSCALE_MODEL, UPSCALE_MODELS, is_available, upscale_image
from ._view import CompareView

log = logging.getLogger(__name__)

_IMAGE_FILE_FILTER = 'Images (' + ' '.join(f'*{ext}' for ext in sorted(SUPPORTED_EXTENSIONS)) + ')'
_SAVE_FILE_FILTER = 'PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;TIFF Image (*.tif *.tiff);;Bitmap Image (*.bmp)'
_NEEDS_RAW_FORMATS_EXTRAS = HEIC_EXTENSIONS | RAW_EXTENSIONS


def _load_pixmap(path) -> QtGui.QPixmap:
    """Load path as a QPixmap via the shared image loader (EXIF orientation, HEIC, camera RAW)."""
    image = load_full_qimage(path)
    if image.isNull():
        return QtGui.QPixmap()
    return QtGui.QPixmap.fromImage(image)


def _rotated_pixmap(pixmap: QtGui.QPixmap, degrees: int) -> QtGui.QPixmap:
    """Return pixmap rotated by degrees (multiple of 90), or pixmap unchanged if degrees % 360 == 0."""
    if pixmap.isNull() or degrees % 360 == 0:
        return pixmap
    transform = QtGui.QTransform().rotate(degrees)
    return pixmap.transformed(transform, QtCore.Qt.TransformationMode.SmoothTransformation)


class _UpscaleWorker(QtCore.QObject):
    """Runs upscale_image on a background thread and reports progress/results via signals."""

    progress = QtCore.Signal(int, int)
    finished = QtCore.Signal(object)  # QImage, or None if cancelled
    failed = QtCore.Signal(str)

    def __init__(self, image_path: Path, model_key: str):
        super().__init__()
        self._image_path = image_path
        self._model_key = model_key
        self._cancelled = False

    @QtCore.Slot()
    def cancel(self) -> None:
        self._cancelled = True

    @QtCore.Slot()
    def run(self) -> None:
        try:
            result = upscale_image(
                self._image_path,
                model_key=self._model_key,
                progress_cb=lambda done, total: self.progress.emit(done, total),
                should_cancel=lambda: self._cancelled,
            )
            self.finished.emit(result)
        except Exception as err:
            log.exception('Upscale failed')
            self.failed.emit(str(err))


class CompareWindow(QtWidgets.QMainWindow):
    """Tool window for A|B comparing two images, with a built-in, selectable-model upscale action."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle('Compare')
        self.resize(1100, 750)

        self._path_a: Path | None = None
        self._path_b: Path | None = None
        self._pixmap_a = QtGui.QPixmap()
        self._pixmap_b = QtGui.QPixmap()
        self._rotation_a = 0  # degrees, display-only -- does not touch the file or _pixmap_a itself
        self._rotation_b = 0
        self._thread: QtCore.QThread | None = None
        self._worker: _UpscaleWorker | None = None
        self._progress_dialog: QtWidgets.QProgressDialog | None = None

        self._view = CompareView()
        self._view.zoom_changed.connect(self._on_zoom_changed)

        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        path_bar = QtWidgets.QWidget()
        path_layout = QtWidgets.QGridLayout(path_bar)
        path_layout.setContentsMargins(6, 4, 6, 4)
        self._path_a_edit = self._make_path_field(path_layout, 0, 'A:', self._rotate_a)
        self._path_b_edit = self._make_path_field(path_layout, 1, 'B:', self._rotate_b)
        central_layout.addWidget(path_bar)

        central_layout.addWidget(self._view, stretch=1)
        self.setCentralWidget(central)

        toolbar = self.addToolBar('Compare')
        toolbar.setMovable(False)
        toolbar.addAction('Open A...', self._open_a)
        toolbar.addAction('Open B...', self._open_b)
        toolbar.addSeparator()
        toolbar.addAction('Save A...', lambda: self._save_image('a'))
        toolbar.addAction('Save B...', lambda: self._save_image('b'))
        toolbar.addSeparator()
        self._model_combo = QtWidgets.QComboBox()
        for key, entry in UPSCALE_MODELS.items():
            self._model_combo.addItem(entry['label'], userData=key)
        self._model_combo.setCurrentIndex(max(0, self._model_combo.findData(DEFAULT_UPSCALE_MODEL)))
        toolbar.addWidget(self._model_combo)
        toolbar.addAction('Upscale A...', self._upscale_a)
        toolbar.addSeparator()
        toolbar.addAction('Fit', self._view.fit_to_view)
        toolbar.addAction('100%', self._view.zoom_to_actual_size)
        toolbar.addAction('Zoom In', self._view.zoom_in)
        toolbar.addAction('Zoom Out', self._view.zoom_out)

        self._zoom_label = QtWidgets.QLabel('')
        self.statusBar().addPermanentWidget(self._zoom_label)
        self.statusBar().showMessage('Open A and B to compare, or Open A then Upscale.')

    def _make_path_field(
        self, layout: QtWidgets.QGridLayout, row: int, label_text: str, rotate_cb
    ) -> QtWidgets.QLineEdit:
        """Add a "label: path [Copy] [rotate-left] [rotate-right]" row to layout; return the path QLineEdit."""
        label = QtWidgets.QLabel(label_text)
        edit = QtWidgets.QLineEdit()
        edit.setReadOnly(True)
        edit.setPlaceholderText('(no image loaded)')
        copy_btn = QtWidgets.QPushButton('Copy')
        copy_btn.setFixedWidth(50)
        copy_btn.clicked.connect(lambda: self._copy_path_to_clipboard(edit))
        rotate_left_btn = QtWidgets.QPushButton('↶')
        rotate_left_btn.setFixedWidth(30)
        rotate_left_btn.setToolTip('Rotate left 90°')
        rotate_left_btn.clicked.connect(lambda: rotate_cb(-90))
        rotate_right_btn = QtWidgets.QPushButton('↷')
        rotate_right_btn.setFixedWidth(30)
        rotate_right_btn.setToolTip('Rotate right 90°')
        rotate_right_btn.clicked.connect(lambda: rotate_cb(90))
        layout.addWidget(label, row, 0)
        layout.addWidget(edit, row, 1)
        layout.addWidget(copy_btn, row, 2)
        layout.addWidget(rotate_left_btn, row, 3)
        layout.addWidget(rotate_right_btn, row, 4)
        return edit

    def _rotate_a(self, delta: int) -> None:
        self._rotation_a = (self._rotation_a + delta) % 360
        self._refresh_view()

    def _rotate_b(self, delta: int) -> None:
        self._rotation_b = (self._rotation_b + delta) % 360
        self._refresh_view()

    def _copy_path_to_clipboard(self, edit: QtWidgets.QLineEdit) -> None:
        text = edit.text()
        if not text or text.startswith('('):
            return
        QtWidgets.QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f'Copied to clipboard: {text}', 3000)

    def _update_path_fields(self) -> None:
        for edit, path, pixmap in (
            (self._path_a_edit, self._path_a, self._pixmap_a),
            (self._path_b_edit, self._path_b, self._pixmap_b),
        ):
            if path is not None:
                edit.setText(str(path))
                edit.setToolTip(str(path))
            elif not pixmap.isNull():
                edit.setText('(unsaved upscale result)')
                edit.setToolTip('')
            else:
                edit.setText('')
                edit.setToolTip('')

    def _load_pixmap_checked(self, path) -> QtGui.QPixmap:
        """Load path, warning (once per call) if it needs the raw_formats extras and they're missing."""
        if Path(path).suffix.lower() in _NEEDS_RAW_FORMATS_EXTRAS:
            available, hint = raw_formats_available()
            if not available:
                QtWidgets.QMessageBox.warning(self, 'Compare', hint)
                return QtGui.QPixmap()
        return _load_pixmap(path)

    def load_images(self, path_a: Path, path_b: Path) -> None:
        """Load two images from disk to compare directly (e.g. from another plugin)."""
        self._path_a, self._path_b = Path(path_a), Path(path_b)
        self._pixmap_a = _load_pixmap(self._path_a)
        self._pixmap_b = _load_pixmap(self._path_b)
        self._rotation_a = 0
        self._rotation_b = 0
        self._refresh_view()

    def _open_a(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Image A', '', _IMAGE_FILE_FILTER)
        if not path:
            return
        self._path_a = Path(path)
        self._pixmap_a = self._load_pixmap_checked(path)
        self._rotation_a = 0
        self._refresh_view()

    def _open_b(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Image B', '', _IMAGE_FILE_FILTER)
        if not path:
            return
        self._path_b = Path(path)
        self._pixmap_b = self._load_pixmap_checked(path)
        self._rotation_b = 0
        self._refresh_view()

    def _default_save_name(self, which: str) -> str:
        """Suggest a save filename that never defaults to silently overwriting the source file."""
        source_path = self._path_a if which == 'a' else self._path_b
        suffix = 'upscaled' if which == 'b' else 'edited'
        if source_path is not None:
            return str(source_path.with_name(f'{source_path.stem}_{suffix}.png'))
        if which == 'b' and self._path_a is not None:
            return str(self._path_a.with_name(f'{self._path_a.stem}_upscaled.png'))
        return f'image_{which}.png'

    def _save_image(self, which: str) -> None:
        pixmap = self._pixmap_a if which == 'a' else self._pixmap_b
        rotation = self._rotation_a if which == 'a' else self._rotation_b
        label = 'A' if which == 'a' else 'B'

        if pixmap.isNull():
            QtWidgets.QMessageBox.information(self, 'Compare', f'Nothing to save -- open or create image {label} first.')
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f'Save Image {label} As', self._default_save_name(which), _SAVE_FILE_FILTER
        )
        if not path:
            return

        display_pixmap = _rotated_pixmap(pixmap, rotation)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            saved = display_pixmap.save(path, quality=95)  # quality is ignored for lossless formats
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        if not saved:
            QtWidgets.QMessageBox.critical(self, 'Compare', f'Failed to save image to:\n{path}')
            return

        if which == 'a':
            self._path_a = Path(path)
        else:
            self._path_b = Path(path)
        self._update_path_fields()
        self.statusBar().showMessage(f'Saved {label} to {path}', 5000)

    def _refresh_view(self) -> None:
        display_a = _rotated_pixmap(self._pixmap_a, self._rotation_a)
        display_b = _rotated_pixmap(self._pixmap_b, self._rotation_b)
        self._view.set_images(display_a, display_b)
        self._update_path_fields()

        have_a = not display_a.isNull()
        have_b = not display_b.isNull()
        if have_a and have_b:
            scale = display_b.width() / display_a.width() if display_a.width() else 0
            message = (
                f'A: {display_a.width()}x{display_a.height()}   '
                f'B: {display_b.width()}x{display_b.height()}   ({scale:.2f}x)'
            )
        elif have_a:
            message = f'A: {display_a.width()}x{display_a.height()}   Open B to compare.'
        elif have_b:
            message = f'B: {display_b.width()}x{display_b.height()}   Open A to compare.'
        else:
            message = 'Open A and B to compare, or Open A then Upscale.'
        self.statusBar().showMessage(message)

    def _on_zoom_changed(self, scale: float) -> None:
        self._zoom_label.setText(f'{scale * 100:.0f}%')

    def _upscale_a(self) -> None:
        if self._path_a is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Choose Image to Upscale', '', _IMAGE_FILE_FILTER)
            if not path:
                return
            self._path_a = Path(path)
            self._pixmap_a = self._load_pixmap_checked(path)
            self._rotation_a = 0
            self._refresh_view()

        available, hint = is_available()
        if not available:
            QtWidgets.QMessageBox.warning(self, 'Compare', hint)
            return

        model_key = self._model_combo.currentData()
        model_label = UPSCALE_MODELS[model_key]['label']

        self._progress_dialog = QtWidgets.QProgressDialog(f'Upscaling with {model_label}...', 'Cancel', 0, 0, self)
        self._progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)

        self._thread = QtCore.QThread(self)
        self._worker = _UpscaleWorker(self._path_a, model_key)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_upscale_progress)
        self._worker.finished.connect(self._on_upscale_finished)
        self._worker.failed.connect(self._on_upscale_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._progress_dialog.canceled.connect(self._worker.cancel)
        self._thread.start()
        self._progress_dialog.show()

    def _on_upscale_progress(self, done: int, total: int) -> None:
        if self._progress_dialog is None:
            return
        if total and self._progress_dialog.maximum() != total:
            self._progress_dialog.setRange(0, total)
        self._progress_dialog.setValue(done)

    def _on_upscale_finished(self, image: QtGui.QImage | None) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        if image is None:
            self.statusBar().showMessage('Upscale cancelled.')
            return
        self._pixmap_b = QtGui.QPixmap.fromImage(image)
        self._path_b = None
        self._rotation_b = self._rotation_a  # B is derived from A's file, so match A's current rotation
        self._refresh_view()

    def _on_upscale_failed(self, message: str) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        QtWidgets.QMessageBox.critical(self, 'Compare', f'Upscaling failed:\n{message}')

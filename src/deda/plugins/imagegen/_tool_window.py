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
"""PySide6 UI for the image generation tool."""
import logging
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ._api_client import (
    ImageGenBackend,
    ImageGenClient,
    ImageGenRequest,
    ImageGenResult,
)

log = logging.getLogger(__name__)

_SETTINGS_ORG = 'DedaFX'
_SETTINGS_APP = 'Dedaverse'
_SETTINGS_PREFIX = 'imagegen/'


class _ImageDropArea(QtWidgets.QListWidget):
    """List widget that accepts image files via drag-and-drop."""

    images_added = QtCore.Signal(list)  # list[str]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setToolTip('Drag reference images here, or use the Add button')
        self.setMinimumHeight(80)
        self.setMaximumHeight(160)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        added = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}:
                self._add_path(path)
                added.append(path)
        if added:
            self.images_added.emit(added)
        event.acceptProposedAction()

    def add_path(self, path: str) -> None:
        self._add_path(path)

    def _add_path(self, path: str) -> None:
        # Avoid duplicates
        for i in range(self.count()):
            if self.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == path:
                return
        item = QtWidgets.QListWidgetItem(Path(path).name)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, path)
        item.setToolTip(path)
        self.addItem(item)

    def selected_paths(self) -> list[str]:
        return [
            item.data(QtCore.Qt.ItemDataRole.UserRole)
            for item in self.selectedItems()
        ]

    def all_paths(self) -> list[str]:
        return [
            self.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
            for i in range(self.count())
        ]


class _ThumbnailWidget(QtWidgets.QLabel):
    """Clickable image thumbnail."""

    clicked = QtCore.Signal(str)  # emits file path

    def __init__(self, path: str, size: int = 200, parent=None):
        super().__init__(parent)
        self._path = path
        self.setFixedSize(size, size)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.setToolTip(path)
        self.setStyleSheet('border: 1px solid #555; background: #222;')
        self._load_pixmap(size)

    def _load_pixmap(self, size: int) -> None:
        pix = QtGui.QPixmap(self._path)
        if pix.isNull():
            self.setText('(no preview)')
        else:
            self.setPixmap(pix.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                       QtCore.Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)
        super().mousePressEvent(event)


class _GenerateWorker(QtCore.QThread):
    """Background thread for image generation."""

    finished = QtCore.Signal(object)   # ImageGenResult
    error = QtCore.Signal(str)

    def __init__(self, client: ImageGenClient, request: ImageGenRequest, parent=None):
        super().__init__(parent)
        self._client = client
        self._request = request

    def run(self) -> None:
        try:
            result = self._client.generate(self._request)
            self.finished.emit(result)
        except Exception as exc:
            log.error(f'Image generation failed: {exc}', exc_info=True)
            self.error.emit(str(exc))


class _BackendSettingsWidget(QtWidgets.QWidget):
    """Stacked settings panel that swaps content based on the active backend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stack = QtWidgets.QStackedWidget()

        # -- Gemini panel ---------------------------------------------------
        gemini_panel = QtWidgets.QWidget()
        gemini_layout = QtWidgets.QFormLayout(gemini_panel)
        gemini_layout.setContentsMargins(0, 0, 0, 0)
        self._gemini_key = QtWidgets.QLineEdit()
        self._gemini_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._gemini_key.setPlaceholderText('GEMINI_API_KEY (or set env var)')
        self._gemini_model = QtWidgets.QLineEdit()
        self._gemini_model.setPlaceholderText('imagen-3.0-generate-002')
        gemini_layout.addRow('API Key:', self._gemini_key)
        gemini_layout.addRow('Model:', self._gemini_model)

        # -- Ollama panel ---------------------------------------------------
        ollama_panel = QtWidgets.QWidget()
        ollama_layout = QtWidgets.QFormLayout(ollama_panel)
        ollama_layout.setContentsMargins(0, 0, 0, 0)
        self._ollama_url = QtWidgets.QLineEdit()
        self._ollama_url.setPlaceholderText('http://localhost:11434')
        self._ollama_model = QtWidgets.QLineEdit()
        self._ollama_model.setPlaceholderText('stable-diffusion')
        ollama_layout.addRow('Ollama URL:', self._ollama_url)
        ollama_layout.addRow('Model:', self._ollama_model)

        # -- Generic panel --------------------------------------------------
        generic_panel = QtWidgets.QWidget()
        generic_layout = QtWidgets.QFormLayout(generic_panel)
        generic_layout.setContentsMargins(0, 0, 0, 0)
        self._generic_endpoint = QtWidgets.QLineEdit()
        self._generic_endpoint.setPlaceholderText('http://localhost:7860/sdapi/v1/txt2img')
        self._generic_auth = QtWidgets.QLineEdit()
        self._generic_auth.setPlaceholderText('Bearer <token>  (optional)')
        self._generic_image_key = QtWidgets.QLineEdit()
        self._generic_image_key.setPlaceholderText('images  (dot-path to base64 list in response)')
        self._generic_image_key.setText('images')
        self._generic_format = QtWidgets.QLineEdit()
        self._generic_format.setPlaceholderText('png')
        self._generic_format.setText('png')
        generic_layout.addRow('Endpoint URL:', self._generic_endpoint)
        generic_layout.addRow('Auth Header:', self._generic_auth)
        generic_layout.addRow('Image JSON Path:', self._generic_image_key)
        generic_layout.addRow('Image Format:', self._generic_format)

        self._stack.addWidget(gemini_panel)   # index 0
        self._stack.addWidget(ollama_panel)   # index 1
        self._stack.addWidget(generic_panel)  # index 2

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def show_backend(self, backend: ImageGenBackend) -> None:
        index_map = {
            ImageGenBackend.GEMINI: 0,
            ImageGenBackend.OLLAMA: 1,
            ImageGenBackend.GENERIC: 2,
        }
        self._stack.setCurrentIndex(index_map.get(backend, 0))

    # -- Getters ------------------------------------------------------------

    def gemini_key(self) -> str:
        return self._gemini_key.text().strip()

    def gemini_model(self) -> str:
        return self._gemini_model.text().strip()

    def ollama_url(self) -> str:
        return self._ollama_url.text().strip()

    def ollama_model(self) -> str:
        return self._ollama_model.text().strip()

    def generic_endpoint(self) -> str:
        return self._generic_endpoint.text().strip()

    def generic_auth(self) -> str:
        return self._generic_auth.text().strip()

    def generic_image_key(self) -> str:
        return self._generic_image_key.text().strip() or 'images'

    def generic_format(self) -> str:
        return self._generic_format.text().strip() or 'png'

    # -- Save / restore settings --------------------------------------------

    def save_settings(self, settings: QtCore.QSettings) -> None:
        settings.setValue(f'{_SETTINGS_PREFIX}gemini_model', self._gemini_model.text())
        settings.setValue(f'{_SETTINGS_PREFIX}ollama_url', self._ollama_url.text())
        settings.setValue(f'{_SETTINGS_PREFIX}ollama_model', self._ollama_model.text())
        settings.setValue(f'{_SETTINGS_PREFIX}generic_endpoint', self._generic_endpoint.text())
        settings.setValue(f'{_SETTINGS_PREFIX}generic_auth', self._generic_auth.text())
        settings.setValue(f'{_SETTINGS_PREFIX}generic_image_key', self._generic_image_key.text())
        settings.setValue(f'{_SETTINGS_PREFIX}generic_format', self._generic_format.text())
        # NOTE: API key intentionally not persisted to QSettings for security.

    def restore_settings(self, settings: QtCore.QSettings) -> None:
        self._gemini_model.setText(settings.value(f'{_SETTINGS_PREFIX}gemini_model', ''))
        self._ollama_url.setText(settings.value(f'{_SETTINGS_PREFIX}ollama_url', ''))
        self._ollama_model.setText(settings.value(f'{_SETTINGS_PREFIX}ollama_model', ''))
        self._generic_endpoint.setText(settings.value(f'{_SETTINGS_PREFIX}generic_endpoint', ''))
        self._generic_auth.setText(settings.value(f'{_SETTINGS_PREFIX}generic_auth', ''))
        self._generic_image_key.setText(settings.value(f'{_SETTINGS_PREFIX}generic_image_key', 'images'))
        self._generic_format.setText(settings.value(f'{_SETTINGS_PREFIX}generic_format', 'png'))


class ImageGenToolWindow(QtWidgets.QMainWindow):
    """Main window for the image generation tool.

    Layout (left | right split):
      Left: inputs (prompt, docs, reference images, settings)
      Right: generated image thumbnails grid
    """

    def __init__(self, service=None, parent=None):
        super().__init__(parent)
        self._service = service
        self._worker: _GenerateWorker | None = None
        self._settings = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)

        self.setWindowTitle('Image Generation')
        self.setMinimumSize(960, 640)

        self._build_ui()
        self._restore_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)
        root.setSpacing(8)

        root.addWidget(self._build_left_panel(), stretch=2)
        root.addWidget(self._build_right_panel(), stretch=3)

    def _build_left_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setSpacing(6)

        # -- Backend selector ----------------------------------------------
        backend_row = QtWidgets.QHBoxLayout()
        backend_row.addWidget(QtWidgets.QLabel('Backend:'))
        self._backend_combo = QtWidgets.QComboBox()
        for b in ImageGenBackend:
            self._backend_combo.addItem(b.value.capitalize(), userData=b)
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        backend_row.addWidget(self._backend_combo, 1)
        layout.addLayout(backend_row)

        # -- Backend-specific settings -------------------------------------
        self._backend_settings = _BackendSettingsWidget()
        settings_group = QtWidgets.QGroupBox('Connection')
        sg_layout = QtWidgets.QVBoxLayout(settings_group)
        sg_layout.addWidget(self._backend_settings)
        layout.addWidget(settings_group)

        # -- Prompt --------------------------------------------------------
        prompt_group = QtWidgets.QGroupBox('Prompt')
        pg_layout = QtWidgets.QVBoxLayout(prompt_group)
        self._prompt_edit = QtWidgets.QPlainTextEdit()
        self._prompt_edit.setPlaceholderText('Describe the image to generate…')
        self._prompt_edit.setMaximumHeight(100)
        pg_layout.addWidget(self._prompt_edit)

        self._neg_prompt_edit = QtWidgets.QLineEdit()
        self._neg_prompt_edit.setPlaceholderText('Negative prompt (optional)')
        pg_layout.addWidget(QtWidgets.QLabel('Negative prompt:'))
        pg_layout.addWidget(self._neg_prompt_edit)
        layout.addWidget(prompt_group)

        # -- Design documentation ------------------------------------------
        doc_group = QtWidgets.QGroupBox('Design Documentation')
        doc_group.setCheckable(True)
        doc_group.setChecked(False)
        dg_layout = QtWidgets.QVBoxLayout(doc_group)
        self._doc_edit = QtWidgets.QPlainTextEdit()
        self._doc_edit.setPlaceholderText(
            'Paste design notes, art direction, or style guide text here. '
            'This will be prepended to the prompt as context.'
        )
        self._doc_edit.setMaximumHeight(120)
        dg_layout.addWidget(self._doc_edit)
        layout.addWidget(doc_group)
        self._doc_group = doc_group

        # -- Reference images ----------------------------------------------
        ref_group = QtWidgets.QGroupBox('Reference Images')
        rg_layout = QtWidgets.QVBoxLayout(ref_group)
        self._ref_list = _ImageDropArea()
        rg_layout.addWidget(self._ref_list)

        ref_btns = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton('Add…')
        add_btn.clicked.connect(self._on_add_reference)
        remove_btn = QtWidgets.QPushButton('Remove Selected')
        remove_btn.clicked.connect(self._on_remove_reference)
        ref_btns.addWidget(add_btn)
        ref_btns.addWidget(remove_btn)
        rg_layout.addLayout(ref_btns)
        layout.addWidget(ref_group)

        # -- Output options ------------------------------------------------
        out_group = QtWidgets.QGroupBox('Output')
        og_layout = QtWidgets.QFormLayout(out_group)

        out_dir_row = QtWidgets.QHBoxLayout()
        self._out_dir_edit = QtWidgets.QLineEdit()
        default_out = str(Path.home() / 'dedaverse' / 'imagegen')
        self._out_dir_edit.setText(default_out)
        browse_btn = QtWidgets.QPushButton('…')
        browse_btn.setFixedWidth(28)
        browse_btn.clicked.connect(self._on_browse_output)
        out_dir_row.addWidget(self._out_dir_edit)
        out_dir_row.addWidget(browse_btn)
        og_layout.addRow('Save to:', out_dir_row)

        self._prefix_edit = QtWidgets.QLineEdit('imagegen')
        og_layout.addRow('Filename prefix:', self._prefix_edit)

        size_row = QtWidgets.QHBoxLayout()
        self._width_spin = QtWidgets.QSpinBox()
        self._width_spin.setRange(256, 4096)
        self._width_spin.setSingleStep(64)
        self._width_spin.setValue(1024)
        self._height_spin = QtWidgets.QSpinBox()
        self._height_spin.setRange(256, 4096)
        self._height_spin.setSingleStep(64)
        self._height_spin.setValue(1024)
        size_row.addWidget(self._width_spin)
        size_row.addWidget(QtWidgets.QLabel('×'))
        size_row.addWidget(self._height_spin)
        og_layout.addRow('Size (px):', size_row)

        self._count_spin = QtWidgets.QSpinBox()
        self._count_spin.setRange(1, 8)
        self._count_spin.setValue(1)
        og_layout.addRow('Count:', self._count_spin)

        layout.addWidget(out_group)

        # -- Generate button -----------------------------------------------
        self._generate_btn = QtWidgets.QPushButton('Generate')
        self._generate_btn.setMinimumHeight(36)
        font = self._generate_btn.font()
        font.setPointSize(font.pointSize() + 1)
        self._generate_btn.setFont(font)
        self._generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self._generate_btn)

        # -- Progress bar --------------------------------------------------
        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        layout.addStretch()
        return panel

    def _build_right_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel('Generated Images'))
        header.addStretch()
        clear_btn = QtWidgets.QPushButton('Clear')
        clear_btn.clicked.connect(self._on_clear_results)
        open_folder_btn = QtWidgets.QPushButton('Open Folder')
        open_folder_btn.clicked.connect(self._on_open_output_folder)
        header.addWidget(open_folder_btn)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._results_container = QtWidgets.QWidget()
        self._results_layout = QtWidgets.QGridLayout(self._results_container)
        self._results_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self._results_layout.setSpacing(8)
        scroll.setWidget(self._results_container)
        layout.addWidget(scroll)

        self._status_label = QtWidgets.QLabel('Ready')
        self._status_label.setStyleSheet('color: #888;')
        layout.addWidget(self._status_label)

        return panel

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_backend_changed(self, index: int) -> None:
        backend = self._backend_combo.itemData(index)
        self._backend_settings.show_backend(backend)

    def _on_add_reference(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'Select Reference Images',
            '',
            'Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)',
        )
        for p in paths:
            self._ref_list.add_path(p)

    def _on_remove_reference(self) -> None:
        for item in self._ref_list.selectedItems():
            self._ref_list.takeItem(self._ref_list.row(item))

    def _on_browse_output(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Output Directory', self._out_dir_edit.text()
        )
        if directory:
            self._out_dir_edit.setText(directory)

    def _on_generate(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        prompt = self._prompt_edit.toPlainText().strip()
        if not prompt:
            QtWidgets.QMessageBox.warning(self, 'Missing Prompt', 'Please enter a prompt.')
            return

        client = self._build_client()
        if client is None:
            return

        request = ImageGenRequest(
            prompt=prompt,
            negative_prompt=self._neg_prompt_edit.text().strip(),
            reference_images=[Path(p) for p in self._ref_list.all_paths()],
            documentation=self._doc_edit.toPlainText().strip() if self._doc_group.isChecked() else '',
            width=self._width_spin.value(),
            height=self._height_spin.value(),
            num_images=self._count_spin.value(),
            output_dir=Path(self._out_dir_edit.text().strip() or str(Path.home() / 'dedaverse' / 'imagegen')),
            filename_prefix=self._prefix_edit.text().strip() or 'imagegen',
        )

        self._generate_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_label.setText('Generating…')

        self._worker = _GenerateWorker(client, request, parent=self)
        self._worker.finished.connect(self._on_generation_done)
        self._worker.error.connect(self._on_generation_error)
        self._worker.start()

    def _on_generation_done(self, result: ImageGenResult) -> None:
        self._generate_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status_label.setText(
            f'Done — {len(result.images)} image(s) saved via {result.backend} ({result.model})'
        )
        self._add_thumbnails(result.images)

    def _on_generation_error(self, message: str) -> None:
        self._generate_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status_label.setText(f'Error: {message}')
        QtWidgets.QMessageBox.critical(self, 'Generation Failed', message)

    def _on_clear_results(self) -> None:
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_open_output_folder(self) -> None:
        folder = self._out_dir_edit.text().strip()
        if not folder:
            return
        import subprocess
        import sys
        path = Path(folder)
        if path.exists():
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', str(path)])
            else:
                subprocess.Popen(['xdg-open', str(path)])

    def _on_thumbnail_clicked(self, path: str) -> None:
        """Open the image in the system default viewer."""
        import subprocess
        import sys
        if sys.platform == 'win32':
            subprocess.Popen(['start', '', path], shell=True)
        else:
            subprocess.Popen(['xdg-open', path])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_client(self) -> ImageGenClient | None:
        """Construct an ImageGenClient from current UI state."""
        backend: ImageGenBackend = self._backend_combo.currentData()

        if self._service:
            client = self._service.client
            client.backend = backend
        else:
            client = ImageGenClient(backend=backend)

        bs = self._backend_settings
        if backend == ImageGenBackend.GEMINI:
            key = bs.gemini_key()
            if not key:
                import os
                key = os.getenv('GEMINI_API_KEY', '')
            if not key:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Missing API Key',
                    'Enter a Gemini API key or set the GEMINI_API_KEY environment variable.',
                )
                return None
            client.configure_gemini(api_key=key, model=bs.gemini_model())

        elif backend == ImageGenBackend.OLLAMA:
            client.configure_ollama(url=bs.ollama_url(), model=bs.ollama_model())

        elif backend == ImageGenBackend.GENERIC:
            endpoint = bs.generic_endpoint()
            if not endpoint:
                QtWidgets.QMessageBox.warning(self, 'Missing Endpoint', 'Enter the web service endpoint URL.')
                return None
            client.configure_generic(
                endpoint=endpoint,
                auth_header=bs.generic_auth(),
                image_json_path=bs.generic_image_key(),
                image_format=bs.generic_format(),
            )

        return client

    def _add_thumbnails(self, paths: list[Path]) -> None:
        columns = 3
        current_count = self._results_layout.count()
        for i, path in enumerate(paths):
            thumb = _ThumbnailWidget(str(path))
            thumb.clicked.connect(self._on_thumbnail_clicked)
            row, col = divmod(current_count + i, columns)
            self._results_layout.addWidget(thumb, row, col)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _save_settings(self) -> None:
        s = self._settings
        s.setValue(f'{_SETTINGS_PREFIX}geometry', self.saveGeometry())
        s.setValue(f'{_SETTINGS_PREFIX}backend', self._backend_combo.currentIndex())
        s.setValue(f'{_SETTINGS_PREFIX}prompt', self._prompt_edit.toPlainText())
        s.setValue(f'{_SETTINGS_PREFIX}neg_prompt', self._neg_prompt_edit.text())
        s.setValue(f'{_SETTINGS_PREFIX}doc_visible', self._doc_group.isChecked())
        s.setValue(f'{_SETTINGS_PREFIX}out_dir', self._out_dir_edit.text())
        s.setValue(f'{_SETTINGS_PREFIX}prefix', self._prefix_edit.text())
        s.setValue(f'{_SETTINGS_PREFIX}width', self._width_spin.value())
        s.setValue(f'{_SETTINGS_PREFIX}height', self._height_spin.value())
        s.setValue(f'{_SETTINGS_PREFIX}count', self._count_spin.value())
        self._backend_settings.save_settings(s)

    def _restore_settings(self) -> None:
        s = self._settings
        geometry = s.value(f'{_SETTINGS_PREFIX}geometry')
        if geometry:
            self.restoreGeometry(geometry)
        backend_idx = s.value(f'{_SETTINGS_PREFIX}backend', 0, type=int)
        self._backend_combo.setCurrentIndex(backend_idx)
        self._prompt_edit.setPlainText(s.value(f'{_SETTINGS_PREFIX}prompt', ''))
        self._neg_prompt_edit.setText(s.value(f'{_SETTINGS_PREFIX}neg_prompt', ''))
        doc_visible = s.value(f'{_SETTINGS_PREFIX}doc_visible', False, type=bool)
        self._doc_group.setChecked(doc_visible)
        out_dir = s.value(f'{_SETTINGS_PREFIX}out_dir', '')
        if out_dir:
            self._out_dir_edit.setText(out_dir)
        prefix = s.value(f'{_SETTINGS_PREFIX}prefix', 'imagegen')
        self._prefix_edit.setText(prefix)
        self._width_spin.setValue(s.value(f'{_SETTINGS_PREFIX}width', 1024, type=int))
        self._height_spin.setValue(s.value(f'{_SETTINGS_PREFIX}height', 1024, type=int))
        self._count_spin.setValue(s.value(f'{_SETTINGS_PREFIX}count', 1, type=int))
        self._backend_settings.restore_settings(s)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._save_settings()
        super().closeEvent(event)

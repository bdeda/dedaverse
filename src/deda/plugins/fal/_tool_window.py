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
"""The fal.ai window: choose a task and model, set up the inputs and parameters, run, and review the results."""
import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ._client import ENV_API_KEY, DEFAULT_OUTPUT_DIR, FalClient, FalRequest
from ._models import IMAGE, TASKS, TEXT_TO_SPEECH, FalModel, Param, models_for, recommend
from ._notes import load_notes

log = logging.getLogger(__name__)

_IMAGE_FILTER = 'Images (*.png *.jpg *.jpeg *.webp *.bmp)'
_VIDEO_FILTER = 'Videos (*.mp4 *.mov *.webm *.mkv *.avi)'
_SPEEDS = (('Recommended', None), ('Fast', 'fast'), ('Balanced', 'balanced'), ('Best quality', 'quality'))


class _RunWorker(QtCore.QThread):
    """Runs a request off the UI thread."""

    status = QtCore.Signal(str)
    done = QtCore.Signal(object)    # FalResult
    failed = QtCore.Signal(str)

    def __init__(self, client: FalClient, request: FalRequest, parent=None):
        super().__init__(parent)
        self._client = client
        self._request = request

    def run(self) -> None:
        try:
            self.done.emit(self._client.run(self._request, on_status=self.status.emit))
        except Exception as err:  # pylint: disable=broad-except
            log.error(f'fal.ai run failed: {err}', exc_info=True)
            self.failed.emit(str(err))


class _ParamForm(QtWidgets.QWidget):
    """Editors for a model's parameters, rebuilt whenever the model changes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QtWidgets.QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._editors: dict[str, tuple[Param, QtWidgets.QWidget]] = {}

    def set_model(self, model: FalModel | None) -> None:
        """Show editors for ``model``'s parameters."""
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._editors = {}
        for param in (model.params if model else ()):
            editor = self._make_editor(param)
            self._layout.addRow(param.label + ':', editor)
            self._editors[param.name] = (param, editor)

    @staticmethod
    def _make_editor(param: Param) -> QtWidgets.QWidget:
        if param.kind == 'bool':
            editor = QtWidgets.QCheckBox()
            editor.setChecked(bool(param.default))
        elif param.kind == 'choice':
            editor = QtWidgets.QComboBox()
            if param.default is None:
                editor.addItem('(default)', None)
            for choice in param.choices:
                editor.addItem(str(choice), choice)
            editor.setCurrentIndex(max(0, editor.findData(param.default)))
        elif param.kind == 'text':
            editor = QtWidgets.QLineEdit('' if param.default is None else str(param.default))
        elif param.kind == 'int':
            editor = QtWidgets.QSpinBox()
            low = int(param.minimum if param.minimum is not None else 0)
            high = int(param.maximum if param.maximum is not None else 10 ** 6)
            if param.default is None:
                # One step below the range means "not set": the argument is left out and the model decides.
                editor.setRange(low - 1, high)
                editor.setSpecialValueText('Random' if param.name == 'seed' else 'Auto')
                editor.setValue(low - 1)
            else:
                editor.setRange(low, high)
                editor.setValue(int(param.default))
        else:
            editor = QtWidgets.QDoubleSpinBox()
            editor.setDecimals(2)
            editor.setSingleStep(0.1)
            low = float(param.minimum if param.minimum is not None else 0.0)
            high = float(param.maximum if param.maximum is not None else 1000.0)
            if param.default is None:
                editor.setRange(low - 0.1, high)
                editor.setSpecialValueText('Auto')
                editor.setValue(low - 0.1)
            else:
                editor.setRange(low, high)
                editor.setValue(float(param.default))
        if param.help:
            editor.setToolTip(param.help)
        return editor

    def values(self) -> dict:
        """The current value of every parameter; the random seed and ``(default)`` choices are left out."""
        values = {}
        for name, (param, editor) in self._editors.items():
            if isinstance(editor, QtWidgets.QCheckBox):
                value = editor.isChecked()
            elif isinstance(editor, QtWidgets.QComboBox):
                value = editor.currentData()
            elif isinstance(editor, QtWidgets.QLineEdit):
                value = editor.text().strip() or None
            elif param.default is None and editor.value() == editor.minimum():
                value = None
            else:
                value = editor.value()
            if value is not None:
                values[name] = value
        return values


class _Thumbnail(QtWidgets.QLabel):
    clicked = QtCore.Signal(str)

    def __init__(self, path: str, size: int = 180, parent=None):
        super().__init__(parent)
        self._path = path
        self.setFixedSize(size, size)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(path)
        self.setStyleSheet('border: 1px solid #555; background: #222;')
        pixmap = QtGui.QPixmap(path)
        if pixmap.isNull():
            self.setText(Path(path).name)
        else:
            self.setPixmap(pixmap.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                         QtCore.Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)
        super().mousePressEvent(event)


class FalToolWindow(QtWidgets.QMainWindow):
    """Run fal.ai models on a prompt, source image, reference image and art direction."""

    _SETTINGS_PREFIX = 'fal/'

    def __init__(self, service=None, parent=None):
        super().__init__(parent)
        self._service = service
        self._client = service.client if service is not None else FalClient()
        self._worker: _RunWorker | None = None
        self._settings = QtCore.QSettings('DedaFX', 'Dedaverse')
        self.setWindowTitle('fal.ai - Images and 3D')
        self.setMinimumSize(980, 680)
        self._build_ui()
        self._restore_settings()
        self._on_task_changed()

    # ------------------------------------------------------------------ construction

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)
        root.addWidget(self._build_inputs(), 2)
        root.addWidget(self._build_results(), 3)

    def _build_inputs(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)

        task_group = QtWidgets.QGroupBox('Task and model')
        form = QtWidgets.QFormLayout(task_group)
        self._task_combo = QtWidgets.QComboBox()
        for key, label in TASKS.items():
            self._task_combo.addItem(label, key)
        self._task_combo.currentIndexChanged.connect(self._on_task_changed)
        form.addRow('Task:', self._task_combo)
        self._speed_combo = QtWidgets.QComboBox()
        for label, speed in _SPEEDS:
            self._speed_combo.addItem(label, speed)
        self._speed_combo.currentIndexChanged.connect(self._on_task_changed)
        form.addRow('Prefer:', self._speed_combo)
        self._model_combo = QtWidgets.QComboBox()
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        form.addRow('Model:', self._model_combo)
        self._model_note = QtWidgets.QLabel()
        self._model_note.setWordWrap(True)
        self._model_note.setStyleSheet('color: #888;')
        form.addRow(self._model_note)
        self._key_edit = QtWidgets.QLineEdit()
        self._key_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText(f'{ENV_API_KEY} (or set the environment variable)')
        form.addRow('API key:', self._key_edit)
        layout.addWidget(task_group)

        self._inputs_group = QtWidgets.QGroupBox('Inputs')
        inputs = QtWidgets.QFormLayout(self._inputs_group)
        self._prompt_edit = QtWidgets.QPlainTextEdit()
        self._prompt_edit.setMaximumHeight(80)
        self._prompt_edit.setPlaceholderText('Describe the image, or the change to make')
        self._prompt_label = QtWidgets.QLabel('Prompt:')
        inputs.addRow(self._prompt_label, self._prompt_edit)
        self._negative_edit = QtWidgets.QLineEdit()
        self._negative_edit.setPlaceholderText('Things to avoid (models that support it)')
        self._negative_label = QtWidgets.QLabel('Avoid:')
        inputs.addRow(self._negative_label, self._negative_edit)
        self._direction_edit = QtWidgets.QPlainTextEdit()
        self._direction_edit.setMaximumHeight(70)
        self._direction_edit.setPlaceholderText('Art direction: look, mood, references (added to the prompt)')
        self._direction_label = QtWidgets.QLabel('Direction:')
        inputs.addRow(self._direction_label, self._direction_edit)
        load_notes_btn = QtWidgets.QPushButton('Use Viewer Notes...')
        load_notes_btn.setToolTip('Take the text and the snapshot from notes saved in the Dedaverse viewer')
        load_notes_btn.clicked.connect(self._on_use_notes)
        inputs.addRow('', load_notes_btn)
        self._image_edit, self._image_label = self._path_row(inputs, 'Source image:', self._on_browse_image)
        self._video_edit, self._video_label = self._path_row(inputs, 'Source video:', self._on_browse_video)
        self._reference_edit, self._reference_label = self._path_row(
            inputs, 'Reference image:', self._on_browse_reference)
        self._reference_edit.setPlaceholderText('Moodboard, sketch or annotated snapshot (optional)')
        layout.addWidget(self._inputs_group)

        self._params_group = QtWidgets.QGroupBox('Parameters')
        params_layout = QtWidgets.QVBoxLayout(self._params_group)
        self._params = _ParamForm()
        params_layout.addWidget(self._params)
        layout.addWidget(self._params_group)

        out_group = QtWidgets.QGroupBox('Output')
        out_form = QtWidgets.QFormLayout(out_group)
        row = QtWidgets.QHBoxLayout()
        self._out_dir_edit = QtWidgets.QLineEdit(str(DEFAULT_OUTPUT_DIR))
        browse = QtWidgets.QPushButton('Browse...')
        browse.clicked.connect(self._on_browse_output)
        row.addWidget(self._out_dir_edit)
        row.addWidget(browse)
        out_form.addRow('Folder:', row)
        self._prefix_edit = QtWidgets.QLineEdit('fal')
        out_form.addRow('Name prefix:', self._prefix_edit)
        layout.addWidget(out_group)

        self._run_btn = QtWidgets.QPushButton('Run')
        self._run_btn.setMinimumHeight(34)
        self._run_btn.clicked.connect(self._on_run)
        layout.addWidget(self._run_btn)
        layout.addStretch()
        return panel

    @staticmethod
    def _path_row(form: QtWidgets.QFormLayout, label: str, browse_cb):
        row = QtWidgets.QHBoxLayout()
        edit = QtWidgets.QLineEdit()
        button = QtWidgets.QPushButton('Browse...')
        button.clicked.connect(browse_cb)
        row.addWidget(edit)
        row.addWidget(button)
        text = QtWidgets.QLabel(label)
        form.addRow(text, row)
        return edit, text

    def _build_results(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel('Results'))
        header.addStretch()
        clear = QtWidgets.QPushButton('Clear')
        clear.clicked.connect(self._on_clear)
        header.addWidget(clear)
        layout.addLayout(header)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        self._results_container = QtWidgets.QWidget()
        self._results_layout = QtWidgets.QGridLayout(self._results_container)
        self._results_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._results_container)
        layout.addWidget(scroll)
        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status = QtWidgets.QLabel('Ready')
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        return panel

    # ------------------------------------------------------------------ state

    @property
    def model(self) -> FalModel | None:
        """The model selected in the window."""
        return self._model_combo.currentData()

    def _on_task_changed(self) -> None:
        """List the models for the task, selecting the recommended one for the preferred speed."""
        task = self._task_combo.currentData()
        models = models_for(task)
        has_reference = bool(self._reference_edit.text().strip())
        chosen = None
        if models:
            chosen = recommend(task, speed=self._speed_combo.currentData(), has_reference=has_reference,
                               models=models)
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for model in models:
            star = '  (recommended)' if chosen is not None and model.endpoint == chosen.endpoint else ''
            self._model_combo.addItem(model.label + star, model)
        if chosen is not None:
            self._model_combo.setCurrentIndex(max(0, [m.endpoint for m in models].index(chosen.endpoint)))
        self._model_combo.blockSignals(False)
        self._on_model_changed()

    def _on_model_changed(self) -> None:
        model = self.model
        self._params.set_model(model)
        self._model_note.setText('' if model is None else
                                 ' '.join(part for part in (model.description, model.notes) if part))
        has_prompt = bool(model and model.prompt_arg)
        has_image = bool(model and model.image_arg)
        speaks = bool(model and model.task == TEXT_TO_SPEECH)
        self._prompt_label.setText('Text to speak:' if speaks else 'Prompt:')
        for widget in (self._direction_edit, self._direction_label):
            widget.setVisible(bool(model and model.direction_in_prompt))
        for widget in (self._video_edit, self._video_label):
            widget.setVisible(bool(model and model.video_arg))
        for widget in (self._prompt_edit, self._prompt_label):
            widget.setVisible(has_prompt)
        for widget in (self._negative_edit, self._negative_label):
            widget.setVisible(bool(model and model.negative_prompt_arg))
        for widget in (self._image_edit, self._image_label):
            widget.setVisible(has_image)
        for widget in (self._reference_edit, self._reference_label):
            widget.setVisible(bool(model and model.reference_arg))
        self._params_group.setVisible(bool(model and model.params))

    def _build_request(self) -> FalRequest:
        model = self.model
        if model is None:
            raise ValueError('No model is selected')
        return FalRequest(
            model=model, prompt=self._prompt_edit.toPlainText(), annotations=self._direction_edit.toPlainText(),
            negative_prompt=self._negative_edit.text(),
            image=Path(self._image_edit.text().strip()) if self._image_edit.text().strip() else None,
            video=Path(self._video_edit.text().strip()) if self._video_edit.text().strip() else None,
            reference_image=Path(self._reference_edit.text().strip()) if self._reference_edit.text().strip() else None,
            params=self._params.values(),
            output_dir=Path(self._out_dir_edit.text().strip() or str(DEFAULT_OUTPUT_DIR)),
            filename_prefix=self._prefix_edit.text().strip() or 'fal')

    # ------------------------------------------------------------------ actions

    def _on_browse_image(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Source image', '', _IMAGE_FILTER)
        if path:
            self._image_edit.setText(path)

    def _on_browse_video(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Source video', '', _VIDEO_FILTER)
        if path:
            self._video_edit.setText(path)

    def _on_browse_reference(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Reference image', '', _IMAGE_FILTER)
        if path:
            self._reference_edit.setText(path)
            self._on_task_changed()

    def _on_browse_output(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Output folder', self._out_dir_edit.text())
        if folder:
            self._out_dir_edit.setText(folder)

    def _on_use_notes(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Viewer notes', '', 'Notes (annotations_*.json)')
        if not path:
            return
        try:
            direction, snapshot = load_notes(path)
        except (OSError, ValueError) as err:
            QtWidgets.QMessageBox.warning(self, 'Viewer notes', str(err))
            return
        self._direction_edit.setPlainText(direction)
        if snapshot is not None:
            self._reference_edit.setText(str(snapshot))
            self._on_task_changed()
        self._status.setText(f'Loaded notes from {Path(path).name}' + ('' if snapshot else ' (no snapshot found)'))

    def _on_run(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        key = self._key_edit.text().strip()
        if key:
            self._client.set_api_key(key)
        if not self._client.has_key:
            QtWidgets.QMessageBox.warning(
                self, 'fal.ai API key', f'Enter your fal.ai API key or set the {ENV_API_KEY} environment variable.')
            return
        try:
            request = self._build_request()
            self._client.build_arguments(request, 'x' if request.model.image_arg else None, None,
                                         'x' if request.model.video_arg else None)
            if request.model.image_arg and (request.image is None or not request.image.is_file()):
                raise ValueError('Choose a source image that exists')
            if request.model.video_arg and (request.video is None or not request.video.is_file()):
                raise ValueError('Choose a source video that exists')
        except ValueError as err:
            QtWidgets.QMessageBox.warning(self, 'fal.ai', str(err))
            return
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status.setText('Starting...')
        self._worker = _RunWorker(self._client, request, parent=self)
        self._worker.status.connect(self._status.setText)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_done(self, result) -> None:
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        seed = f', seed {result.seed}' if result.seed is not None else ''
        self._status.setText(f'Done: {len(result.paths)} file(s) from {result.model.label}{seed}')
        self._show_results(result)

    def _on_failed(self, message: str) -> None:
        self._run_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText(f'Error: {message}')
        QtWidgets.QMessageBox.critical(self, 'fal.ai', message)

    def _show_results(self, result) -> None:
        for path in result.paths:
            index = self._results_layout.count()
            if result.model.output_kind != IMAGE:
                verb = 'Play' if result.model.output_kind in ('audio', 'video') else 'Open'
                button = QtWidgets.QPushButton(f'{path.name}\n{verb}')
                button.setFixedSize(180, 80)
                button.setToolTip(str(path))
                button.clicked.connect(lambda checked=False, p=str(path): self._open(p))
                widget = button
            else:
                widget = _Thumbnail(str(path))
                widget.clicked.connect(self._open)
            self._results_layout.addWidget(widget, index // 3, index % 3)

    def _on_clear(self) -> None:
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _open(path: str) -> None:
        """Open a result in the system's default application."""
        if sys.platform == 'win32':
            os.startfile(path)  # nosec B606 - opens a file this tool just saved, with its default app
        else:
            subprocess.Popen(['xdg-open', path])  # nosec B603 B607

    # ------------------------------------------------------------------ settings

    def _save_settings(self) -> None:
        s = self._settings
        s.setValue(f'{self._SETTINGS_PREFIX}task', self._task_combo.currentData())
        s.setValue(f'{self._SETTINGS_PREFIX}speed', self._speed_combo.currentIndex())
        s.setValue(f'{self._SETTINGS_PREFIX}out_dir', self._out_dir_edit.text())
        s.setValue(f'{self._SETTINGS_PREFIX}prefix', self._prefix_edit.text())
        # The API key is deliberately not stored.

    def _restore_settings(self) -> None:
        s = self._settings
        self._task_combo.blockSignals(True)
        self._speed_combo.blockSignals(True)
        index = self._task_combo.findData(s.value(f'{self._SETTINGS_PREFIX}task', ''))
        self._task_combo.setCurrentIndex(max(0, index))
        self._speed_combo.setCurrentIndex(s.value(f'{self._SETTINGS_PREFIX}speed', 0, type=int))
        self._task_combo.blockSignals(False)
        self._speed_combo.blockSignals(False)
        self._out_dir_edit.setText(s.value(f'{self._SETTINGS_PREFIX}out_dir', str(DEFAULT_OUTPUT_DIR)))
        self._prefix_edit.setText(s.value(f'{self._SETTINGS_PREFIX}prefix', 'fal'))

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)

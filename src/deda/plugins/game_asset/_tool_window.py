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
"""Game asset optimizer window: pick a mesh, set the budget, run Blender in the background."""
__all__ = ['GameAssetWindow']

import logging
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ._options import NORMAL_CONVENTIONS, SOURCE_SUFFIXES, TEXTURE_SIZES, UV_METHODS, OptimizeError, \
    OptimizeOptions, OptimizeResult
from ._runner import default_output_dir, optimize

log = logging.getLogger(__name__)


class GameAssetWindow(QtWidgets.QMainWindow):  # pylint: disable=too-many-instance-attributes
    """Tool window that optimizes one mesh on a background thread and logs Blender's progress."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle('Game Asset Optimizer')
        self.resize(720, 520)
        self._thread: QtCore.QThread | None = None
        self._worker: _OptimizeWorker | None = None

        central = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(central)

        self._source_edit = QtWidgets.QLineEdit()
        self._source_edit.setPlaceholderText('Mesh to optimize (.usdz, .glb, .fbx, .obj, ...)')
        self._source_edit.textChanged.connect(self._on_source_changed)
        source_button = QtWidgets.QPushButton('Browse...')
        source_button.clicked.connect(self._browse_source)

        self._output_edit = QtWidgets.QLineEdit()
        self._output_edit.setPlaceholderText('Output directory')
        self._output_edit.textChanged.connect(self._update_run_enabled)
        output_button = QtWidgets.QPushButton('Browse...')
        output_button.clicked.connect(self._browse_output)

        self._tris_spin = QtWidgets.QSpinBox()
        self._tris_spin.setRange(100, 2_000_000)
        self._tris_spin.setSingleStep(1000)
        self._tris_spin.setValue(OptimizeOptions.target_tris)
        self._size_combo = QtWidgets.QComboBox()
        for size in TEXTURE_SIZES:
            self._size_combo.addItem(str(size), size)
        self._size_combo.setCurrentIndex(TEXTURE_SIZES.index(OptimizeOptions.texture_size))
        self._normals_combo = QtWidgets.QComboBox()
        self._normals_combo.addItems(['OpenGL (Blender, Unity, Godot)', 'DirectX (Unreal)'])
        self._uv_combo = QtWidgets.QComboBox()
        for method, label in zip(UV_METHODS, ('Auto', 'Symmetry (flat assets)', 'Seams (round shapes)')):
            self._uv_combo.addItem(label, method)
        self._keep_blend_check = QtWidgets.QCheckBox('Keep .blend')

        self._run_button = QtWidgets.QPushButton('Optimize')
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self.run)

        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)

        settings = QtWidgets.QHBoxLayout()
        for label, widget in (('Triangles:', self._tris_spin), ('Textures:', self._size_combo),
                              ('Normals:', self._normals_combo), ('UVs:', self._uv_combo)):
            settings.addWidget(QtWidgets.QLabel(label))
            settings.addWidget(widget)
        settings.addWidget(self._keep_blend_check)
        settings.addStretch()

        layout.addWidget(QtWidgets.QLabel('Mesh:'), 0, 0)
        layout.addWidget(self._source_edit, 0, 1)
        layout.addWidget(source_button, 0, 2)
        layout.addWidget(QtWidgets.QLabel('Output:'), 1, 0)
        layout.addWidget(self._output_edit, 1, 1)
        layout.addWidget(output_button, 1, 2)
        layout.addLayout(settings, 2, 0, 1, 3)
        layout.addWidget(self._run_button, 3, 1)
        layout.addWidget(self._log, 4, 0, 1, 3)
        self.setCentralWidget(central)

    def closeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Wait for a running job so the thread is not destroyed while active."""
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        super().closeEvent(event)

    def options(self) -> OptimizeOptions:
        """The options chosen in the window."""
        return OptimizeOptions(target_tris=self._tris_spin.value(), texture_size=self._size_combo.currentData(),
                               normal_convention=NORMAL_CONVENTIONS[self._normals_combo.currentIndex()],
                               uv_method=self._uv_combo.currentData(), keep_blend=self._keep_blend_check.isChecked())

    def run(self) -> None:
        """Start optimizing the chosen mesh; progress and results are appended to the log."""
        if self._thread is not None:
            return
        source = Path(self._source_edit.text().strip())
        output = Path(self._output_edit.text().strip())
        self._run_button.setEnabled(False)
        self._append(f'Optimizing {source} -> {output}')
        self._thread = QtCore.QThread(self)
        self._worker = _OptimizeWorker(source, output, self.options())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.output.connect(self._append)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    @QtCore.Slot(str)
    def _append(self, text: str) -> None:
        self._log.appendPlainText(text)

    def _browse_output(self) -> None:  # pragma: no cover - modal file dialog
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Output directory', self._output_edit.text())
        if path:
            self._output_edit.setText(path)

    def _browse_source(self) -> None:  # pragma: no cover - modal file dialog
        patterns = ' '.join(f'*{suffix}' for suffix in SOURCE_SUFFIXES)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open mesh', self._source_edit.text(),
                                                        f'Meshes ({patterns})')
        if path:
            self._source_edit.setText(path)

    def _finish_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._update_run_enabled()

    @QtCore.Slot(object)
    def _on_finished(self, result: OptimizeResult) -> None:
        self._append(f'Done: {result.summary()}')
        for path in result.meshes + list(result.textures.values()):
            self._append(f'  wrote {path}')
        for warning in result.warnings:
            self._append(f'warning: {warning}')
        self._finish_thread()

    @QtCore.Slot(str)
    def _on_failed(self, message: str) -> None:
        self._append(f'FAILED: {message}')
        self._finish_thread()

    def _on_source_changed(self, text: str) -> None:
        """Default the output to ``<stem>_game`` next to the source, unless the user set one."""
        if text.strip() and not self._output_edit.isModified():
            self._output_edit.setText(str(default_output_dir(Path(text.strip()))))
            self._output_edit.setModified(False)
        self._update_run_enabled()

    def _update_run_enabled(self) -> None:
        ready = (self._thread is None and bool(self._source_edit.text().strip())
                 and bool(self._output_edit.text().strip()))
        self._run_button.setEnabled(ready)


class _OptimizeWorker(QtCore.QObject):
    """Runs :func:`optimize` off the GUI thread and reports through signals."""

    output = QtCore.Signal(str)
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, source: Path, output_dir: Path, options: OptimizeOptions):
        super().__init__()
        self._source = source
        self._output_dir = output_dir
        self._options = options

    @QtCore.Slot()
    def run(self) -> None:
        """Optimize, emitting ``finished`` with the result or ``failed`` with a message."""
        try:
            self.finished.emit(optimize(self._source, self._output_dir, self._options, on_output=self.output.emit))
        except OptimizeError as err:
            log.error('Optimizing %s failed: %s', self._source, err)
            self.failed.emit(str(err))

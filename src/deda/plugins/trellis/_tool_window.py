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
"""UI tool window for interacting with Trellis 3D generation."""
import logging
from pathlib import Path
from typing import Dict, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ._api_client import TrellisApiClient

log = logging.getLogger(__name__)


class ImageDropLabel(QtWidgets.QLabel):
    """QLabel that accepts image file drops."""
    
    image_dropped = QtCore.Signal(str)  # Emits image file path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drag_over = False
    
    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
            for url in urls:
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in image_extensions:
                        self._drag_over = True
                        self.setStyleSheet('border: 2px dashed green; background-color: #e0ffe0;')
                        event.acceptProposedAction()
                        return
        event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event."""
        if self._drag_over:
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self._drag_over = False
        self.setStyleSheet('border: 2px dashed gray; background-color: #f0f0f0;')
        super().dragLeaveEvent(event)
    
    def dropEvent(self, event):
        """Handle drop event."""
        self._drag_over = False
        self.setStyleSheet('border: 2px dashed gray; background-color: #f0f0f0;')
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
            for url in urls:
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in image_extensions and path.exists():
                        self.image_dropped.emit(str(path))
                        event.acceptProposedAction()
                        return
        
        event.ignore()


class TrellisToolWindow(QtWidgets.QMainWindow):
    """Main window for Trellis 3D generation."""

    def __init__(self, service=None, parent=None):
        super().__init__(parent=parent)
        self._service = service
        self._api_client = None
        
        # Initialize QSettings for window state persistence
        self._settings = QtCore.QSettings('DedaFX', 'Dedaverse')
        
        base_url = 'http://127.0.0.1:7860'
        if service and hasattr(service, 'get_base_url'):
            base_url = service.get_base_url()
        
        try:
            self._api_client = TrellisApiClient(base_url=base_url)
        except ImportError:
            log.error('requests package not available for Trellis API client')
        
        self.setWindowTitle('Trellis - 3D Model Generation from Images')
        self.setMinimumSize(800, 600)
        
        # Enable drag and drop for the window
        self.setAcceptDrops(True)
        
        # Restore window geometry (before creating widgets)
        self._restore_window_geometry()
        
        # Create central widget
        central_widget = QtWidgets.QWidget()
        central_widget.setAcceptDrops(True)
        self.setCentralWidget(central_widget)
        
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Connection status bar
        self._status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self._status_bar)
        self._update_connection_status()
        
        # Create main content
        self._create_main_content(layout)
        
        # Restore window state after widgets are created
        self._restore_window_state()
        
        # Connect show event to restore cursor
        self._shown = False

    def _create_main_content(self, parent_layout):
        """Create the main content area."""
        # Input section
        input_group = QtWidgets.QGroupBox('Input Image')
        input_layout = QtWidgets.QVBoxLayout(input_group)
        
        # Image path input
        image_layout = QtWidgets.QHBoxLayout()
        self._image_path_edit = QtWidgets.QLineEdit()
        self._image_path_edit.setPlaceholderText('Select an image file...')
        browse_image_btn = QtWidgets.QPushButton('Browse...')
        
        def browse_image():
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                'Select Image',
                '',
                'Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp)'
            )
            if path:
                self._image_path_edit.setText(path)
        
        browse_image_btn.clicked.connect(browse_image)
        image_layout.addWidget(QtWidgets.QLabel('Image:'))
        image_layout.addWidget(self._image_path_edit)
        image_layout.addWidget(browse_image_btn)
        input_layout.addLayout(image_layout)
        
        # Image preview (with drag-and-drop support)
        self._image_preview = ImageDropLabel()
        self._image_preview.setMinimumHeight(200)
        self._image_preview.setAlignment(QtCore.Qt.AlignCenter)
        self._image_preview.setText('Drag and drop an image here\nor use Browse to select an image')
        self._image_preview.setStyleSheet('border: 2px dashed gray; background-color: #f0f0f0;')
        self._image_preview.setScaledContents(False)  # We'll handle scaling manually to preserve aspect ratio
        self._image_preview.setAcceptDrops(True)
        input_layout.addWidget(self._image_preview)
        
        # Update preview when path changes
        self._image_path_edit.textChanged.connect(self._update_image_preview)
        
        # Handle image drop on preview
        def on_image_dropped(image_path):
            self._image_path_edit.setText(image_path)
            self._update_image_preview()
        
        self._image_preview.image_dropped.connect(on_image_dropped)
        
        parent_layout.addWidget(input_group)
        
        # Generation settings
        settings_group = QtWidgets.QGroupBox('Generation Settings')
        settings_layout = QtWidgets.QFormLayout(settings_group)
        
        # Seed
        seed_layout = QtWidgets.QHBoxLayout()
        self._seed_spin = QtWidgets.QSpinBox()
        self._seed_spin.setRange(0, 2147483647)
        self._seed_spin.setValue(0)
        self._randomize_seed_check = QtWidgets.QCheckBox('Randomize Seed')
        self._randomize_seed_check.setChecked(True)
        seed_layout.addWidget(self._seed_spin)
        seed_layout.addWidget(self._randomize_seed_check)
        seed_layout.addStretch()
        settings_layout.addRow('Seed:', seed_layout)
        
        # Stage 1: Sparse Structure
        settings_layout.addRow(QtWidgets.QLabel('<b>Stage 1: Sparse Structure Generation</b>'))
        self._ss_guidance_spin = QtWidgets.QDoubleSpinBox()
        self._ss_guidance_spin.setRange(0.0, 10.0)
        self._ss_guidance_spin.setValue(7.5)
        self._ss_guidance_spin.setSingleStep(0.1)
        settings_layout.addRow('Guidance Strength:', self._ss_guidance_spin)
        
        self._ss_steps_spin = QtWidgets.QSpinBox()
        self._ss_steps_spin.setRange(1, 50)
        self._ss_steps_spin.setValue(12)
        settings_layout.addRow('Sampling Steps:', self._ss_steps_spin)
        
        # Stage 2: Structured Latent
        settings_layout.addRow(QtWidgets.QLabel('<b>Stage 2: Structured Latent Generation</b>'))
        self._slat_guidance_spin = QtWidgets.QDoubleSpinBox()
        self._slat_guidance_spin.setRange(0.0, 10.0)
        self._slat_guidance_spin.setValue(3.0)
        self._slat_guidance_spin.setSingleStep(0.1)
        settings_layout.addRow('Guidance Strength:', self._slat_guidance_spin)
        
        self._slat_steps_spin = QtWidgets.QSpinBox()
        self._slat_steps_spin.setRange(1, 50)
        self._slat_steps_spin.setValue(12)
        settings_layout.addRow('Sampling Steps:', self._slat_steps_spin)
        
        parent_layout.addWidget(settings_group)
        
        # Generate button
        generate_btn = QtWidgets.QPushButton('Generate 3D Model')
        generate_btn.setStyleSheet('font-size: 14px; font-weight: bold; padding: 8px;')
        generate_btn.clicked.connect(self._on_generate_clicked)
        parent_layout.addWidget(generate_btn)
        
        # Progress bar
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setVisible(False)
        parent_layout.addWidget(self._progress_bar)
        
        # Output section
        output_group = QtWidgets.QGroupBox('Output')
        output_layout = QtWidgets.QVBoxLayout(output_group)
        
        # Output path
        output_path_layout = QtWidgets.QHBoxLayout()
        self._output_path_edit = QtWidgets.QLineEdit()
        self._output_path_edit.setPlaceholderText('Output path for GLB file...')
        browse_output_btn = QtWidgets.QPushButton('Browse...')
        
        def browse_output():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                'Save GLB File',
                '',
                'GLB Files (*.glb)'
            )
            if path:
                self._output_path_edit.setText(path)
        
        browse_output_btn.clicked.connect(browse_output)
        output_path_layout.addWidget(QtWidgets.QLabel('Output Path:'))
        output_path_layout.addWidget(self._output_path_edit)
        output_path_layout.addWidget(browse_output_btn)
        output_layout.addLayout(output_path_layout)
        
        # GLB extraction settings
        glb_settings_layout = QtWidgets.QFormLayout()
        self._mesh_simplify_spin = QtWidgets.QDoubleSpinBox()
        self._mesh_simplify_spin.setRange(0.9, 0.98)
        self._mesh_simplify_spin.setValue(0.95)
        self._mesh_simplify_spin.setSingleStep(0.01)
        glb_settings_layout.addRow('Mesh Simplify:', self._mesh_simplify_spin)
        
        self._texture_size_spin = QtWidgets.QSpinBox()
        self._texture_size_spin.setRange(512, 2048)
        self._texture_size_spin.setValue(1024)
        self._texture_size_spin.setSingleStep(512)
        glb_settings_layout.addRow('Texture Size:', self._texture_size_spin)
        output_layout.addLayout(glb_settings_layout)
        
        # Extract buttons
        extract_btn_layout = QtWidgets.QHBoxLayout()
        self._extract_glb_btn = QtWidgets.QPushButton('Extract GLB')
        self._extract_glb_btn.setEnabled(False)
        self._extract_glb_btn.clicked.connect(self._on_extract_glb_clicked)
        extract_btn_layout.addWidget(self._extract_glb_btn)
        
        self._extract_usd_btn = QtWidgets.QPushButton('Extract USD')
        self._extract_usd_btn.setEnabled(False)
        self._extract_usd_btn.clicked.connect(self._on_extract_usd_clicked)
        extract_btn_layout.addWidget(self._extract_usd_btn)
        
        self._extract_gaussian_btn = QtWidgets.QPushButton('Extract Gaussian (PLY)')
        self._extract_gaussian_btn.setEnabled(False)
        self._extract_gaussian_btn.clicked.connect(self._on_extract_gaussian_clicked)
        extract_btn_layout.addWidget(self._extract_gaussian_btn)
        output_layout.addLayout(extract_btn_layout)
        
        # Status display
        self._status_text = QtWidgets.QTextEdit()
        self._status_text.setReadOnly(True)
        self._status_text.setPlaceholderText('Status and results will appear here...')
        self._status_text.setMaximumHeight(150)
        output_layout.addWidget(self._status_text)
        
        parent_layout.addWidget(output_group)
        
        parent_layout.addStretch()
        
        # Store generated state
        self._generated_state = None
        
        # Store thread and worker references to prevent garbage collection
        self._generation_thread = None
        self._generation_worker = None

    def _update_image_preview(self):
        """Update the image preview when path changes."""
        path = self._image_path_edit.text()
        if path and Path(path).exists():
            pixmap = QtGui.QPixmap(path)
            if not pixmap.isNull():
                # Scale to fit preview area while maintaining aspect ratio
                preview_size = self._image_preview.size()
                if preview_size.width() > 0 and preview_size.height() > 0:
                    # Calculate scaled size maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        preview_size,
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation
                    )
                    self._image_preview.setPixmap(scaled_pixmap)
                    # Clear text since we're showing an image
                    self._image_preview.setText('')
                    return
        # No image or invalid path - show placeholder
        self._image_preview.clear()
        self._image_preview.setText('Drag and drop an image here\nor use Browse to select an image')

    def _update_connection_status(self):
        """Update the connection status bar."""
        if self._api_client:
            if self._api_client.check_connection():
                self._status_bar.showMessage('Connected to Trellis', 5000)
                self._status_bar.setStyleSheet('color: green;')
            else:
                self._status_bar.showMessage('Not connected to Trellis. Make sure Trellis server is running.', 0)
                self._status_bar.setStyleSheet('color: red;')
        else:
            self._status_bar.showMessage('Trellis API client not available', 0)
            self._status_bar.setStyleSheet('color: red;')

    def _on_generate_clicked(self):
        """Handle generate button click."""
        image_path = self._image_path_edit.text()
        if not image_path or not Path(image_path).exists():
            QtWidgets.QMessageBox.warning(self, 'Missing Image', 'Please select a valid image file.')
            return
        
        if not self._api_client:
            QtWidgets.QMessageBox.warning(self, 'Not Connected', 'Trellis API client not available.')
            return
        
        # Check connection before attempting generation
        if not self._api_client.check_connection():
            QtWidgets.QMessageBox.warning(
                self,
                'Connection Failed',
                f'Cannot connect to Trellis server at {self._api_client.base_url}.\n\n'
                'Please ensure the Trellis server is running and accessible.'
            )
            return
        
        # Disable buttons during generation
        self._extract_glb_btn.setEnabled(False)
        self._extract_usd_btn.setEnabled(False)
        self._extract_gaussian_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._status_text.clear()
        self._status_text.append('Generating 3D model from image... This may take several minutes.')
        
        # Get parameters
        seed = None if self._randomize_seed_check.isChecked() else self._seed_spin.value()
        
        # Run generation in background thread
        from PySide6.QtCore import QThread, QObject, Signal
        
        class GenerationWorker(QObject):
            finished = Signal(bool, str, dict)
            
            def __init__(self, api_client, image_path, **kwargs):
                super().__init__()
                self._api_client = api_client
                self._image_path = image_path
                self._kwargs = kwargs
            
            def run(self):
                try:
                    log.info(f'Starting 3D generation for image: {self._image_path}')
                    result = self._api_client.generate_3d_from_image(
                        self._image_path,
                        **self._kwargs
                    )
                    log.info('3D generation completed successfully')
                    self.finished.emit(True, 'Generation completed successfully!', result)
                except Exception as e:
                    log.error(f'Generation failed: {e}', exc_info=True)
                    self.finished.emit(False, str(e), {})
                finally:
                    # Ensure we always emit finished signal
                    log.debug('Generation worker run() completed')
        
        # Clean up any existing thread/worker
        if self._generation_thread and self._generation_thread.isRunning():
            log.warning('Previous generation still running, cancelling...')
            self._generation_thread.quit()
            self._generation_thread.wait()
        
        worker = GenerationWorker(
            self._api_client,
            image_path,
            seed=seed,
            randomize_seed=self._randomize_seed_check.isChecked(),
            ss_guidance_strength=self._ss_guidance_spin.value(),
            ss_sampling_steps=self._ss_steps_spin.value(),
            slat_guidance_strength=self._slat_guidance_spin.value(),
            slat_sampling_steps=self._slat_steps_spin.value(),
        )
        
        thread = QThread()
        worker.moveToThread(thread)
        
        # Store references to prevent garbage collection
        self._generation_thread = thread
        self._generation_worker = worker
        
        # Connect signals (use QueuedConnection for thread safety)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_generation_finished, QtCore.Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit, QtCore.Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._cleanup_generation_thread)
        thread.start()

    def _cleanup_generation_thread(self):
        """Clean up generation thread and worker after completion."""
        if self._generation_thread:
            self._generation_thread.deleteLater()
            self._generation_thread = None
        if self._generation_worker:
            self._generation_worker.deleteLater()
            self._generation_worker = None

    def _on_generation_finished(self, success: bool, message: str, result: Dict):
        """Handle generation completion."""
        self._progress_bar.setVisible(False)
        
        if success:
            self._status_text.append(message)
            self._generated_state = result.get('state')
            if self._generated_state:
                self._extract_glb_btn.setEnabled(True)
                self._extract_usd_btn.setEnabled(True)
                self._extract_gaussian_btn.setEnabled(True)
                self._status_text.append('3D model generated! You can now extract GLB, USD, or Gaussian files.')
            else:
                self._status_text.append('Warning: No state data returned from generation.')
        else:
            self._status_text.append(f'Error: {message}')
            QtWidgets.QMessageBox.critical(self, 'Generation Failed', message)

    def _on_extract_glb_clicked(self):
        """Handle extract GLB button click."""
        if not self._generated_state:
            QtWidgets.QMessageBox.warning(self, 'No Model', 'Please generate a 3D model first.')
            return
        
        output_path = self._output_path_edit.text()
        if not output_path:
            QtWidgets.QMessageBox.warning(self, 'Missing Output Path', 'Please specify an output path for the GLB file.')
            return
        
        self._status_text.append('Extracting GLB file...')
        self._extract_glb_btn.setEnabled(False)
        
        try:
            glb_data = self._api_client.extract_glb(
                self._generated_state,
                mesh_simplify=self._mesh_simplify_spin.value(),
                texture_size=self._texture_size_spin.value(),
            )
            
            if glb_data:
                output_path_obj = Path(output_path)
                output_path_obj.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path_obj, 'wb') as f:
                    f.write(glb_data)
                self._status_text.append(f'GLB file saved to: {output_path}')
                QtWidgets.QMessageBox.information(self, 'Success', f'GLB file saved to:\n{output_path}')
            else:
                self._status_text.append('Warning: No GLB data returned.')
        except Exception as e:
            log.error(f'Failed to extract GLB: {e}', exc_info=True)
            self._status_text.append(f'Error extracting GLB: {str(e)}')
            QtWidgets.QMessageBox.critical(self, 'Extraction Failed', str(e))
        finally:
            self._extract_glb_btn.setEnabled(True)

    def _on_extract_usd_clicked(self):
        """Handle extract USD button click."""
        if not self._generated_state:
            QtWidgets.QMessageBox.warning(self, 'No Model', 'Please generate a 3D model first.')
            return
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Save USD File',
            '',
            'USD Files (*.usd *.usda *.usdc)'
        )
        
        if not path:
            return
        
        self._status_text.append('Extracting USD file...')
        self._extract_usd_btn.setEnabled(False)
        
        try:
            usd_data = self._api_client.extract_usd(
                self._generated_state,
                mesh_simplify=self._mesh_simplify_spin.value(),
                texture_size=self._texture_size_spin.value(),
            )
            
            if usd_data:
                path_obj = Path(path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                with open(path_obj, 'wb') as f:
                    f.write(usd_data)
                self._status_text.append(f'USD file saved to: {path}')
                QtWidgets.QMessageBox.information(self, 'Success', f'USD file saved to:\n{path}')
            else:
                self._status_text.append('Warning: No USD data returned.')
        except ImportError as e:
            log.error(f'USD dependencies not available: {e}', exc_info=True)
            self._status_text.append(f'Error: USD Python bindings (pxr) are required for USD export.')
            QtWidgets.QMessageBox.critical(
                self,
                'Missing Dependencies',
                'USD Python bindings (pxr) are required for USD export.\n\n'
                'Please install usd-core or pixar-usd package.'
            )
        except Exception as e:
            log.error(f'Failed to extract USD: {e}', exc_info=True)
            self._status_text.append(f'Error extracting USD: {str(e)}')
            QtWidgets.QMessageBox.critical(self, 'Extraction Failed', str(e))
        finally:
            self._extract_usd_btn.setEnabled(True)

    def _on_extract_gaussian_clicked(self):
        """Handle extract Gaussian button click."""
        if not self._generated_state:
            QtWidgets.QMessageBox.warning(self, 'No Model', 'Please generate a 3D model first.')
            return
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Save PLY File',
            '',
            'PLY Files (*.ply)'
        )
        
        if not path:
            return
        
        self._status_text.append('Extracting Gaussian (PLY) file...')
        self._extract_gaussian_btn.setEnabled(False)
        
        try:
            ply_data = self._api_client.extract_gaussian(self._generated_state)
            
            if ply_data:
                path_obj = Path(path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                with open(path_obj, 'wb') as f:
                    f.write(ply_data)
                self._status_text.append(f'PLY file saved to: {path}')
                QtWidgets.QMessageBox.information(self, 'Success', f'PLY file saved to:\n{path}')
            else:
                self._status_text.append('Warning: No PLY data returned.')
        except Exception as e:
            log.error(f'Failed to extract Gaussian: {e}', exc_info=True)
            self._status_text.append(f'Error extracting PLY: {str(e)}')
            QtWidgets.QMessageBox.critical(self, 'Extraction Failed', str(e))
        finally:
            self._extract_gaussian_btn.setEnabled(True)

    def showEvent(self, event):
        """Handle window show event to restore cursor."""
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            # Restore cursor after window is shown
            QtCore.QTimer.singleShot(50, lambda: QtWidgets.QApplication.restoreOverrideCursor())
    
    def resizeEvent(self, event):
        """Handle window resize to update image preview."""
        super().resizeEvent(event)
        # Update image preview when window is resized to maintain aspect ratio
        if hasattr(self, '_image_path_edit') and self._image_path_edit.text():
            self._update_image_preview()

    def closeEvent(self, event):
        """Handle window close event to save window state."""
        # Clean up any running generation thread
        if self._generation_thread and self._generation_thread.isRunning():
            log.info('Stopping generation thread before closing window...')
            self._generation_thread.quit()
            if not self._generation_thread.wait(3000):  # Wait up to 3 seconds
                log.warning('Generation thread did not finish in time, terminating...')
                self._generation_thread.terminate()
                self._generation_thread.wait()
        
        self._save_window_state()
        super().closeEvent(event)

    def _save_window_state(self):
        """Save window geometry and state to QSettings."""
        try:
            geometry = self.saveGeometry()
            state = self.saveState()
            self._settings.setValue('trellis_tool_window/geometry', geometry)
            self._settings.setValue('trellis_tool_window/state', state)
            log.debug('Saved Trellis tool window state')
        except Exception as e:
            log.error(f'Failed to save Trellis tool window state: {e}')

    def _restore_window_geometry(self):
        """Restore window geometry from QSettings."""
        try:
            geometry = self._settings.value('trellis_tool_window/geometry')
            if geometry:
                self.restoreGeometry(geometry)
                log.debug('Restored Trellis tool window geometry')
        except Exception as e:
            log.debug(f'Failed to restore Trellis tool window geometry: {e}')

    def _restore_window_state(self):
        """Restore window state from QSettings."""
        try:
            state = self._settings.value('trellis_tool_window/state')
            if state:
                self.restoreState(state)
            log.debug('Restored Trellis tool window state')
        except Exception as e:
            log.debug(f'Failed to restore Trellis tool window state: {e}')


    def dragEnterEvent(self, event):
        """Handle drag enter event for file dropping on window."""
        if event.mimeData().hasUrls():
            # Check if any URL is an image file
            urls = event.mimeData().urls()
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
            for url in urls:
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in image_extensions:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dragMoveEvent(self, event):
        """Handle drag move event."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
            for url in urls:
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in image_extensions:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event):
        """Handle drop event to load image files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
            image_paths = []
            for url in urls:
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in image_extensions and path.exists():
                        image_paths.append(str(path))
            
            if image_paths:
                # Use the first image
                image_path = image_paths[0]
                self._image_path_edit.setText(image_path)
                self._update_image_preview()
                event.acceptProposedAction()
                return
        
        event.ignore()

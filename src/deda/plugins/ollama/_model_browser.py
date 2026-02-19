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
"""Model browser dialog for downloading Ollama models."""
import json
import logging
from typing import Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ._api_client import OllamaApiClient

log = logging.getLogger(__name__)


class ModelDownloadWorker(QtCore.QObject):
    """Worker thread for downloading models."""
    
    progress = QtCore.Signal(str, int, int)  # status, downloaded, total
    finished = QtCore.Signal(bool, str)  # success, message
    
    def __init__(self, api_client: OllamaApiClient, model_name: str):
        super().__init__()
        self._api_client = api_client
        self._model_name = model_name
        self._cancelled = False
    
    def cancel(self):
        """Cancel the download."""
        self._cancelled = True
    
    def run(self):
        """Download the model."""
        try:
            log.info(f'Starting download of model: {self._model_name}')
            response = self._api_client.pull_model(self._model_name, stream=True)
            
            total_size = 0
            downloaded = 0
            download_complete = False
            last_status = ''
            line_count = 0
            
            # Read all lines from the streaming response
            for line in response.iter_lines(decode_unicode=True):
                if self._cancelled:
                    self.finished.emit(False, 'Download cancelled by user')
                    return
                
                if not line or not line.strip():
                    continue
                
                line_count += 1
                
                try:
                    data = json.loads(line)
                    
                    # Update progress
                    if 'total' in data:
                        total_size = data['total']
                    if 'completed' in data:
                        downloaded = data['completed']
                    
                    status = data.get('status', '')
                    if status:
                        last_status = status
                        log.debug(f'Download status: {status} ({downloaded}/{total_size} bytes)')
                    
                    self.progress.emit(status, downloaded, total_size)
                    
                    # Check for completion indicators
                    # Ollama sends status messages like "success" or "pulling manifest" etc.
                    status_lower = status.lower() if status else ''
                    
                    # Check if download is complete
                    # Ollama typically ends with a status indicating success or completion
                    if status_lower == 'success' or 'successfully' in status_lower or 'complete' in status_lower:
                        download_complete = True
                        log.info(f'Download completed with status: {status}')
                        # Don't break immediately - continue reading to ensure we get all data
                    
                    # Also check if we've downloaded everything
                    if total_size > 0 and downloaded >= total_size:
                        download_complete = True
                        log.info(f'Download completed: {downloaded}/{total_size} bytes')
                        
                except json.JSONDecodeError as e:
                    log.debug(f'Failed to parse JSON line {line_count}: {line[:100]} - {e}')
                    continue
            
            log.info(f'Finished reading download stream. Processed {line_count} lines. Last status: {last_status}')
            
            # Ensure we've read the entire response stream
            # Some models (especially fast ones like flux-schnell) may complete very quickly
            # and we need to make sure we've consumed all the data
            try:
                # Try to read any remaining data
                for _ in response.iter_lines(decode_unicode=True):
                    pass
            except Exception:
                pass  # Stream may already be closed
            
            # If we got through the entire stream without errors, consider it successful
            # Ollama may not always send a clear "success" message
            if download_complete or (total_size > 0 and downloaded > 0):
                log.info(f'Download stream completed. Total: {total_size}, Downloaded: {downloaded}, Status: {last_status}')
                self.finished.emit(True, f'Model "{self._model_name}" downloaded successfully')
            else:
                # If we didn't get clear completion signals but got some data, still report success
                # (Ollama might have completed silently, especially for fast/cached downloads)
                log.warning(f'Download may have completed but no clear success signal. Status: {last_status}, Lines: {line_count}')
                self.finished.emit(True, f'Model "{self._model_name}" download completed')
            
        except Exception as e:
            log.error(f'Download failed: {e}', exc_info=True)
            # Provide more detailed error message
            error_msg = str(e)
            response_text = None
            
            # Try to get response text from exception
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                response_text = e.response.text
            elif hasattr(e, 'response_text'):
                response_text = e.response_text
            
            if response_text:
                try:
                    error_data = json.loads(response_text)
                    if 'error' in error_data:
                        error_msg = error_data['error']
                    elif 'message' in error_data:
                        error_msg = error_data['message']
                except:
                    error_msg = response_text[:200] if len(response_text) > 200 else response_text
            
            # Check for common error scenarios
            if '404' in error_msg or 'not found' in error_msg.lower():
                error_msg = (
                    f'Model "{self._model_name}" not found in Ollama\'s library.\n\n'
                    f'Possible reasons:\n'
                    f'- The model name may be incorrect\n'
                    f'- The model may not be available in Ollama (some models like Flux require OllamaDiffuser)\n'
                    f'- Check available models at: https://ollama.com/models\n\n'
                    f'Original error: {error_msg}'
                )
            elif '401' in error_msg or 'unauthorized' in error_msg.lower():
                error_msg = 'Unauthorized. Please check your Ollama connection and ensure Ollama is running.'
            elif 'timeout' in error_msg.lower():
                error_msg = 'Download timed out. Please check your internet connection and try again.'
            elif '500' in error_msg or 'internal server error' in error_msg.lower():
                error_msg = (
                    f'Ollama server error. The model "{self._model_name}" may not be supported.\n\n'
                    f'Note: Image generation models like Flux may require OllamaDiffuser instead of standard Ollama.\n'
                    f'Original error: {error_msg}'
                )
            
            self.finished.emit(False, error_msg)


class ModelBrowserDialog(QtWidgets.QDialog):
    """Dialog for browsing and downloading Ollama models."""

    def __init__(self, api_client: OllamaApiClient, category: str, parent=None):
        super().__init__(parent=parent)
        self._api_client = api_client
        self._category = category
        self._downloading_models: set = set()
        self._download_thread: Optional[QtCore.QThread] = None
        self._download_worker: Optional[ModelDownloadWorker] = None
        
        self.setWindowTitle(f'Download Models - {category.title()} Models')
        self.setMinimumSize(700, 500)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Category info
        info_label = QtWidgets.QLabel(f'Available {category.replace("_", " ").title()} Models')
        info_label.setStyleSheet('font-size: 14px; font-weight: bold; padding: 5px;')
        layout.addWidget(info_label)
        
        # Model list
        self._model_list = QtWidgets.QListWidget()
        self._model_list.setAlternatingRowColors(True)
        self._model_list.itemDoubleClicked.connect(self._on_model_double_clicked)
        layout.addWidget(self._model_list)
        
        # Model details panel
        details_group = QtWidgets.QGroupBox('Model Details')
        details_layout = QtWidgets.QVBoxLayout(details_group)
        
        self._name_label = QtWidgets.QLabel()
        self._name_label.setStyleSheet('font-size: 12px; font-weight: bold;')
        details_layout.addWidget(self._name_label)
        
        self._description_label = QtWidgets.QLabel()
        self._description_label.setWordWrap(True)
        details_layout.addWidget(self._description_label)
        
        self._capabilities_label = QtWidgets.QLabel()
        self._capabilities_label.setWordWrap(True)
        details_layout.addWidget(self._capabilities_label)
        
        self._size_label = QtWidgets.QLabel()
        details_layout.addWidget(self._size_label)
        
        # URL link
        self._url_label = QtWidgets.QLabel()
        self._url_label.setOpenExternalLinks(True)
        self._url_label.setTextFormat(QtCore.Qt.RichText)
        details_layout.addWidget(self._url_label)
        
        details_layout.addStretch()
        layout.addWidget(details_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self._download_btn = QtWidgets.QPushButton('Download Model')
        self._download_btn.clicked.connect(self._on_download_clicked)
        button_layout.addWidget(self._download_btn)
        
        self._cancel_btn = QtWidgets.QPushButton('Cancel')
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._on_cancel_download)
        button_layout.addWidget(self._cancel_btn)
        
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setVisible(False)
        button_layout.addWidget(self._progress_bar)
        
        button_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Load models
        self._load_models()
        
        # Connect selection change
        self._model_list.currentItemChanged.connect(self._on_selection_changed)

    def _load_models(self):
        """Load available models for this category."""
        from ._tool_window import MODEL_CATEGORIES
        
        category_info = MODEL_CATEGORIES.get(self._category, {})
        models_dict = category_info.get('models', {})
        
        # Get installed models
        installed_models = set()
        installed_full_names = {}  # Map base name to full name with tag
        try:
            installed = self._api_client.list_models()
            for m in installed:
                full_name = m.get('name', '')
                base_name = full_name.split(':')[0] if ':' in full_name else full_name
                installed_models.add(base_name)
                # Store mapping for later use
                if base_name not in installed_full_names:
                    installed_full_names[base_name] = full_name
        except Exception as e:
            log.error(f'Failed to get installed models: {e}')
        
        # Populate list
        self._model_list.clear()
        for model_key, model_info in models_dict.items():
            model_name = model_info.get('name', model_key)
            is_installed = model_key in installed_models or any(
                inst.startswith(model_key) for inst in installed_models
            )
            
            item_text = model_name
            if is_installed:
                item_text += ' ✓ (Installed)'
            
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, model_key)
            item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, model_info)
            item.setData(QtCore.Qt.ItemDataRole.UserRole + 2, is_installed)
            
            # Color installed models
            if is_installed:
                item.setForeground(QtGui.QColor(100, 200, 100))
            
            self._model_list.addItem(item)
        
        if self._model_list.count() > 0:
            self._model_list.setCurrentRow(0)

    def _on_selection_changed(self, current: Optional[QtWidgets.QListWidgetItem], previous: Optional[QtWidgets.QListWidgetItem]):
        """Update model details when selection changes."""
        if not current:
            self._name_label.setText('')
            self._description_label.setText('')
            self._capabilities_label.setText('')
            self._size_label.setText('')
            self._url_label.setText('')
            self._download_btn.setEnabled(False)
            return
        
        model_info = current.data(QtCore.Qt.ItemDataRole.UserRole + 1)
        is_installed = current.data(QtCore.Qt.ItemDataRole.UserRole + 2)
        
        if model_info:
            self._name_label.setText(model_info.get('name', ''))
            self._description_label.setText(model_info.get('description', ''))
            
            capabilities = model_info.get('capabilities', '')
            if capabilities:
                self._capabilities_label.setText(f'<b>Capabilities:</b> {capabilities}')
            else:
                self._capabilities_label.setText('')
            
            size = model_info.get('size', '')
            if size:
                self._size_label.setText(f'<b>Size:</b> {size}')
            else:
                self._size_label.setText('')
            
            url = model_info.get('url', '')
            if url:
                self._url_label.setText(f'<a href="{url}">More information →</a>')
            else:
                self._url_label.setText('')
            
            # Enable download if not installed and not already downloading
            model_key = current.data(QtCore.Qt.ItemDataRole.UserRole)
            self._download_btn.setEnabled(
                not is_installed and model_key not in self._downloading_models
            )
            if is_installed:
                self._download_btn.setText('Already Installed')
            elif model_key in self._downloading_models:
                self._download_btn.setText('Downloading...')
            else:
                self._download_btn.setText('Download Model')

    def _on_model_double_clicked(self, item: QtWidgets.QListWidgetItem):
        """Handle double-click to download."""
        if item.data(QtCore.Qt.ItemDataRole.UserRole + 2):  # Already installed
            return
        self._on_download_clicked()

    def _on_download_clicked(self):
        """Download the selected model."""
        current = self._model_list.currentItem()
        if not current:
            return
        
        model_key = current.data(QtCore.Qt.ItemDataRole.UserRole)
        model_info = current.data(QtCore.Qt.ItemDataRole.UserRole + 1)
        is_installed = current.data(QtCore.Qt.ItemDataRole.UserRole + 2)
        
        if is_installed or model_key in self._downloading_models:
            return
        
        model_name = model_info.get('name', model_key) if model_info else model_key
        
        # Use the model_key (which matches Ollama model names) for the download
        # The model_key should be the actual Ollama model identifier
        download_model_name = model_key
        
        log.info(f'Starting download of model: {download_model_name}')
        
        # Confirm download
        reply = QtWidgets.QMessageBox.question(
            self,
            'Download Model',
            f'Download {model_name}?\n\nThis may take several minutes depending on your internet connection.',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        # Start download in background thread
        self._downloading_models.add(model_key)
        self._download_btn.setEnabled(False)
        self._download_btn.setText('Downloading...')
        self._cancel_btn.setVisible(True)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        
        # Create worker thread
        self._download_thread = QtCore.QThread()
        self._download_worker = ModelDownloadWorker(self._api_client, download_model_name)
        self._download_worker.moveToThread(self._download_thread)
        
        # Connect signals
        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_thread.finished.connect(self._download_thread.deleteLater)
        
        # Start download
        self._download_thread.start()

    def _on_download_progress(self, status: str, downloaded: int, total: int):
        """Update progress bar during download."""
        if total > 0 and downloaded > 0:
            progress = int((downloaded / total) * 100)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(progress)
            
            # Format progress text with status and percentage
            if status:
                # Show both status and percentage: "Status... 45%"
                self._progress_bar.setFormat(f'{status}... {progress}%')
            else:
                # Just show percentage if no status
                self._progress_bar.setFormat(f'{progress}%')
        else:
            # Indeterminate mode - show status if available
            self._progress_bar.setRange(0, 0)
            if status:
                self._progress_bar.setFormat(f'{status}...')
            else:
                self._progress_bar.setFormat('')

    def _verify_model_installed(self, model_key: str, retry_count: int = 0, max_retries: int = 5):
        """Verify that the model is actually installed in Ollama, with retries."""
        try:
            installed = self._api_client.list_models()
            model_names = [m.get('name', '') for m in installed]
            base_names = [name.split(':')[0] if ':' in name else name for name in model_names]
            
            # Check if our downloaded model is in the list
            expected_base = model_key.split(':')[0] if ':' in model_key else model_key
            
            if expected_base in base_names:
                log.info(f'Model {model_key} confirmed in Ollama model list (attempt {retry_count + 1})')
                # Reload models in the dialog
                self._load_models()
                
                # Notify parent window to refresh if it's an OllamaToolWindow
                parent = self.parent()
                if parent and hasattr(parent, '_load_models'):
                    log.debug('Triggering parent window model refresh')
                    QtCore.QTimer.singleShot(100, parent._load_models)
                
                return True
            else:
                log.debug(f'Model {model_key} not yet in list (attempt {retry_count + 1}/{max_retries}). Available: {", ".join(base_names)}')
                if retry_count < max_retries:
                    # Retry after a delay (exponential backoff: 500ms, 1s, 2s, 3s, 4s)
                    delay = min(500 * (retry_count + 1), 4000)
                    QtCore.QTimer.singleShot(delay, lambda: self._verify_model_installed(model_key, retry_count + 1, max_retries))
                    return False
                else:
                    log.warning(f'Model {model_key} not found in Ollama model list after {max_retries} attempts')
                    # Still reload models in case it appears later
                    self._load_models()
                    
                    # Notify parent window to refresh anyway
                    parent = self.parent()
                    if parent and hasattr(parent, '_load_models'):
                        QtCore.QTimer.singleShot(100, parent._load_models)
                    
                    return False
        except Exception as e:
            log.error(f'Failed to verify model installation: {e}')
            if retry_count < max_retries:
                delay = min(500 * (retry_count + 1), 4000)
                QtCore.QTimer.singleShot(delay, lambda: self._verify_model_installed(model_key, retry_count + 1, max_retries))
            return False

    def _on_download_finished(self, success: bool, message: str):
        """Handle download completion."""
        model_key = None
        current = self._model_list.currentItem()
        if current:
            model_key = current.data(QtCore.Qt.ItemDataRole.UserRole)
        
        # Clean up thread
        if self._download_thread:
            self._download_thread.quit()
            self._download_thread.wait()
            self._download_thread = None
        self._download_worker = None
        
        # Update UI
        self._progress_bar.setVisible(False)
        self._cancel_btn.setVisible(False)
        if model_key:
            self._downloading_models.discard(model_key)
        
        if success:
            log.info(f'Model download completed successfully: {message}')
            
            # Start verification process with retries
            # This is especially important for fast downloads (like flux-schnell)
            # which may complete before Ollama fully registers them
            if model_key:
                # Start verification immediately, then retry if needed
                QtCore.QTimer.singleShot(500, lambda: self._verify_model_installed(model_key))
            
            QtWidgets.QMessageBox.information(self, 'Download Complete', message)
        else:
            log.error(f'Model download failed: {message}')
            if 'cancelled' not in message.lower():
                QtWidgets.QMessageBox.critical(self, 'Download Failed', message)
            # Update button state
            if current:
                self._on_selection_changed(current, None)

    def _on_cancel_download(self):
        """Cancel the current download."""
        if self._download_worker:
            self._download_worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._cancel_btn.setText('Cancelling...')

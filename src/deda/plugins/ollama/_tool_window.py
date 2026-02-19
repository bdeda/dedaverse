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
"""UI tool window for interacting with Ollama models."""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6 import QtCore, QtGui, QtWidgets

from ._api_client import OllamaApiClient

log = logging.getLogger(__name__)

# Model recommendations by task type with metadata
MODEL_CATEGORIES = {
    'text': {
        'recommended': ['llama3.2', 'llama3.1', 'llama3', 'llama2', 'mistral', 'mixtral', 'phi3', 'codellama', 'deepseek-coder'],
        'keywords': ['llama', 'mistral', 'mixtral', 'phi', 'codellama', 'deepseek', 'qwen', 'gemma', 'neural-chat'],
        'description': 'Text generation and chat models',
        'models': {
            'llama3.2': {
                'name': 'Llama 3.2',
                'description': 'Latest Llama model with improved performance and efficiency. Good for general text tasks.',
                'capabilities': 'Text generation, chat, code completion, reasoning',
                'url': 'https://ollama.com/library/llama3.2',
                'size': '~2GB'
            },
            'llama3.1': {
                'name': 'Llama 3.1',
                'description': 'High-performance Llama model with strong reasoning capabilities.',
                'capabilities': 'Text generation, chat, complex reasoning, code',
                'url': 'https://ollama.com/library/llama3.1',
                'size': '~4.7GB'
            },
            'llama3': {
                'name': 'Llama 3',
                'description': 'Meta\'s Llama 3 model with strong general capabilities.',
                'capabilities': 'Text generation, chat, instruction following',
                'url': 'https://ollama.com/library/llama3',
                'size': '~4.7GB'
            },
            'mistral': {
                'name': 'Mistral',
                'description': 'Fast and efficient model from Mistral AI.',
                'capabilities': 'Text generation, chat, quick responses',
                'url': 'https://ollama.com/library/mistral',
                'size': '~4.1GB'
            },
            'mixtral': {
                'name': 'Mixtral',
                'description': 'Mixture of experts model with excellent performance.',
                'capabilities': 'Text generation, chat, complex tasks',
                'url': 'https://ollama.com/library/mixtral',
                'size': '~26GB'
            },
            'phi3': {
                'name': 'Phi-3',
                'description': 'Microsoft\'s efficient small language model.',
                'capabilities': 'Text generation, chat, code, reasoning',
                'url': 'https://ollama.com/library/phi3',
                'size': '~2.3GB'
            },
            'codellama': {
                'name': 'CodeLlama',
                'description': 'Specialized for code generation and understanding.',
                'capabilities': 'Code generation, code completion, code explanation',
                'url': 'https://ollama.com/library/codellama',
                'size': '~3.8GB'
            },
            'deepseek-coder': {
                'name': 'DeepSeek Coder',
                'description': 'Advanced code generation model.',
                'capabilities': 'Code generation, programming assistance',
                'url': 'https://ollama.com/library/deepseek-coder',
                'size': '~3.8GB'
            },
        }
    },
    'vision': {
        'recommended': ['llava', 'bakllava', 'llava-phi3', 'moondream'],
        'keywords': ['llava', 'bakllava', 'moondream', 'vision', 'visual'],
        'description': 'Vision models for image understanding',
        'models': {
            'llava': {
                'name': 'LLaVA',
                'description': 'Large Language and Vision Assistant. Understands images and answers questions about them.',
                'capabilities': 'Image understanding, visual question answering, image description',
                'url': 'https://ollama.com/library/llava',
                'size': '~4.7GB'
            },
            'bakllava': {
                'name': 'BakLLaVA',
                'description': 'Vision model based on LLaMA architecture.',
                'capabilities': 'Image understanding, visual analysis',
                'url': 'https://ollama.com/library/bakllava',
                'size': '~4.7GB'
            },
            'llava-phi3': {
                'name': 'LLaVA Phi-3',
                'description': 'Efficient vision model using Phi-3 architecture.',
                'capabilities': 'Image understanding, smaller model size',
                'url': 'https://ollama.com/library/llava-phi3',
                'size': '~2.3GB'
            },
            'moondream': {
                'name': 'Moondream',
                'description': 'Small, efficient vision model for image understanding.',
                'capabilities': 'Image understanding, fast inference',
                'url': 'https://ollama.com/library/moondream',
                'size': '~1.6GB'
            },
        }
    },
    'image_gen': {
        'recommended': [],
        'keywords': ['image-gen'],
        'description': 'Image generation models (Note: Flux models require OllamaDiffuser, not standard Ollama)',
        'models': {
            # Note: Flux and other image generation models are NOT available in standard Ollama
            # They require OllamaDiffuser (https://ollamadiffuser.com/) which is a separate tool
            # Standard Ollama focuses on language models, not image generation
            # If you need image generation, consider using OllamaDiffuser or other specialized tools
        }
    },
    '3d': {
        'recommended': [],
        'keywords': ['shap', 'point', '3d', 'mesh'],
        'description': '3D model generation (limited availability)',
        'models': {
            # Note: 3D generation from images is not widely available in Ollama yet
            # These are placeholders for future models
        }
    }
}


class OllamaToolWindow(QtWidgets.QMainWindow):
    """Main window for Ollama tool interactions."""

    def __init__(self, service=None, parent=None):
        super().__init__(parent=parent)
        self._service = service
        self._api_client = None
        
        # Initialize QSettings for window state persistence
        self._settings = QtCore.QSettings('DedaFX', 'Dedaverse')
        
        base_url = 'http://localhost:11434'
        if service and hasattr(service, 'get_base_url'):
            base_url = service.get_base_url()
        
        try:
            self._api_client = OllamaApiClient(base_url=base_url)
        except ImportError:
            log.error('requests package not available for Ollama API client')
        
        self.setWindowTitle('Ollama - Local AI Models')
        self.setMinimumSize(800, 600)
        
        # Restore window geometry (before creating widgets)
        self._restore_window_geometry()
        
        # Create central widget with tabs
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Connection status bar
        self._status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self._status_bar)
        self._update_connection_status()
        
        # Tab widget for different modes
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.addTab(self._create_text_tab(), 'Text Processing')
        self._tabs.addTab(self._create_image_processing_tab(), 'Image Processing')
        # Image Generation and 3D from Image tabs hidden - will be used elsewhere in the future
        # self._tabs.addTab(self._create_image_generation_tab(), 'Image Generation')
        # self._tabs.addTab(self._create_3d_generation_tab(), '3D from Image')
        self._tabs.addTab(self._create_settings_tab(), 'Settings')
        
        layout.addWidget(self._tabs)
        
        # Store all models and filtered lists
        self._all_models: List[Dict] = []
        self._current_category = 'text'
        
        # Load models on startup (after window is shown)
        QtCore.QTimer.singleShot(100, self._load_models)
        
        # Connect tab change to filter models and save tab selection
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.currentChanged.connect(self._on_tab_index_changed)
        
        # Restore window state (including tab index) after tabs are created
        self._restore_window_state()
        
        # Connect show event to restore cursor
        self._shown = False

    def _on_tab_index_changed(self, index: int):
        """Save current tab index when tab changes."""
        try:
            self._settings.setValue('ollama_tool_window/current_tab', index)
        except Exception as e:
            log.debug(f'Failed to save tab index: {e}')

    def showEvent(self, event):
        """Handle window show event to restore cursor."""
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            # Restore cursor after window is shown
            QtCore.QTimer.singleShot(50, lambda: QtWidgets.QApplication.restoreOverrideCursor())

    def closeEvent(self, event):
        """Handle window close event to save window state."""
        self._save_window_state()
        super().closeEvent(event)

    def _save_window_state(self):
        """Save window geometry and state to QSettings."""
        try:
            geometry = self.saveGeometry()
            state = self.saveState()
            self._settings.setValue('ollama_tool_window/geometry', geometry)
            self._settings.setValue('ollama_tool_window/state', state)
            # Also save current tab index
            if hasattr(self, '_tabs') and self._tabs:
                self._settings.setValue('ollama_tool_window/current_tab', self._tabs.currentIndex())
            log.debug('Saved Ollama tool window state')
        except Exception as e:
            log.error(f'Failed to save Ollama tool window state: {e}')

    def _restore_window_geometry(self):
        """Restore window geometry from QSettings."""
        try:
            geometry = self._settings.value('ollama_tool_window/geometry')
            if geometry:
                self.restoreGeometry(geometry)
                log.debug('Restored Ollama tool window geometry')
        except Exception as e:
            log.debug(f'Failed to restore Ollama tool window geometry: {e}')

    def _restore_window_state(self):
        """Restore window state (including tab index) from QSettings."""
        try:
            state = self._settings.value('ollama_tool_window/state')
            if state:
                self.restoreState(state)
            
            # Restore current tab index
            tab_index = self._settings.value('ollama_tool_window/current_tab', 0, type=int)
            if hasattr(self, '_tabs') and self._tabs and 0 <= tab_index < self._tabs.count():
                self._tabs.setCurrentIndex(tab_index)
            
            log.debug('Restored Ollama tool window state')
        except Exception as e:
            log.debug(f'Failed to restore Ollama tool window state: {e}')

    def _update_connection_status(self):
        """Update the connection status bar."""
        if self._api_client:
            if self._api_client.check_connection():
                self._status_bar.showMessage('Connected to Ollama', 5000)
                self._status_bar.setStyleSheet('color: green;')
            else:
                self._status_bar.showMessage('Not connected to Ollama. Make sure Ollama is running.', 0)
                self._status_bar.setStyleSheet('color: red;')
        else:
            self._status_bar.showMessage('Ollama API client not available', 0)
            self._status_bar.setStyleSheet('color: red;')

    def _load_models(self):
        """Load available models from Ollama."""
        if not self._api_client:
            return
        
        try:
            # Force refresh by getting fresh model list
            self._all_models = self._api_client.list_models()
            log.info(f'Loaded {len(self._all_models)} models from Ollama')
            
            # Log model names for debugging
            if self._all_models:
                model_names = [m.get('name', '') for m in self._all_models]
                log.debug(f'Available models: {", ".join(model_names)}')
            
            # Update all model combo boxes with filtered lists
            self._update_model_combos()
        except Exception as e:
            log.error(f'Failed to load models: {e}', exc_info=True)
            self._status_bar.showMessage(f'Failed to load models: {e}', 5000)

    def _on_tab_changed(self, index: int):
        """Handle tab change to update model filters."""
        if not self._tabs:
            return
        
        tab_name = self._tabs.tabText(index).lower()
        if 'text' in tab_name:
            self._current_category = 'text'
        elif 'image processing' in tab_name or 'vision' in tab_name:
            self._current_category = 'vision'
        elif 'image generation' in tab_name or 'image gen' in tab_name:
            self._current_category = 'image_gen'
        elif '3d' in tab_name:
            self._current_category = '3d'
        else:
            self._current_category = 'text'
        
        # Update model combos when switching tabs
        self._update_model_combos()

    def _filter_models_for_category(self, category: str) -> List[str]:
        """Filter models for a specific category."""
        if not self._all_models:
            log.debug(f'No models available for category {category}')
            return []
        
        category_info = MODEL_CATEGORIES.get(category, MODEL_CATEGORIES['text'])
        recommended = category_info.get('recommended', [])
        keywords = category_info.get('keywords', [])
        
        # Get all model names (remove tags like :latest for comparison)
        all_model_names = []
        for m in self._all_models:
            name = m.get('name', '')
            if not name:
                continue
            # Remove tag suffix (e.g., "deepseek-coder:latest" -> "deepseek-coder")
            base_name = name.split(':')[0] if ':' in name else name
            all_model_names.append((name, base_name))  # Store both full name and base name
        
        log.debug(f'Filtering {len(all_model_names)} models for category {category}')
        
        # Filter models: recommended first, then keyword matches, then all others
        recommended_models = []
        keyword_matches = []
        other_models = []
        seen_models = set()  # Track which models we've already added
        
        for full_name, base_name in all_model_names:
            if full_name in seen_models:
                continue
                
            model_lower = base_name.lower()
            # Check if recommended (match base name)
            is_recommended = any(rec.lower() in model_lower or model_lower == rec.lower() for rec in recommended)
            # Check if matches keywords
            matches_keyword = any(keyword.lower() in model_lower for keyword in keywords)
            
            if is_recommended:
                recommended_models.append(full_name)
                seen_models.add(full_name)
                log.debug(f'Model {full_name} added to recommended list')
            elif matches_keyword:
                keyword_matches.append(full_name)
                seen_models.add(full_name)
                log.debug(f'Model {full_name} added to keyword matches')
            else:
                # Include ALL models, even if they don't match keywords
                # This ensures downloaded models always appear
                other_models.append(full_name)
                seen_models.add(full_name)
                log.debug(f'Model {full_name} added to other models')
        
        # Combine: recommended first, then keyword matches, then others
        filtered = recommended_models + keyword_matches + other_models
        log.debug(f'Filtered to {len(filtered)} models: {len(recommended_models)} recommended, {len(keyword_matches)} keyword matches, {len(other_models)} others')
        return filtered

    def _update_model_combos(self):
        """Update all model combo boxes with filtered models."""
        if not self._all_models:
            return
        
        # Update each combo box based on its category
        text_combo = self.findChild(QtWidgets.QComboBox, 'model_text')
        vision_combo = self.findChild(QtWidgets.QComboBox, 'model_vision')
        image_gen_combo = self.findChild(QtWidgets.QComboBox, 'model_image_gen')
        model_3d_combo = self.findChild(QtWidgets.QComboBox, 'model_3d')
        
        if text_combo:
            self._update_combo_with_filter(text_combo, 'text')
        if vision_combo:
            self._update_combo_with_filter(vision_combo, 'vision')
        if image_gen_combo:
            self._update_combo_with_filter(image_gen_combo, 'image_gen')
        if model_3d_combo:
            self._update_combo_with_filter(model_3d_combo, '3d')

    def _update_combo_with_filter(self, combo: QtWidgets.QComboBox, category: str):
        """Update a combo box with filtered models for a category."""
        current = combo.currentText()
        filtered_models = self._filter_models_for_category(category)
        
        combo.clear()
        if filtered_models:
            combo.addItems(filtered_models)
            # Adjust width to fit longest item
            self._adjust_combo_width(combo, filtered_models)
            # Try to restore previous selection
            if current in filtered_models:
                combo.setCurrentText(current)
            else:
                # Select first recommended model if available
                category_info = MODEL_CATEGORIES.get(category, {})
                recommended = category_info.get('recommended', [])
                for rec in recommended:
                    matching = [m for m in filtered_models if rec.lower() in m.lower()]
                    if matching:
                        combo.setCurrentText(matching[0])
                        break
                else:
                    combo.setCurrentIndex(0)
        else:
            # Fallback to all models if no matches
            all_models = [m.get('name', '') for m in self._all_models]
            combo.addItems(all_models)
            self._adjust_combo_width(combo, all_models)
            if current in all_models:
                combo.setCurrentText(current)

    def _adjust_combo_width(self, combo: QtWidgets.QComboBox, items: List[str]):
        """Adjust combobox width to fit the longest item."""
        if not items:
            return
        
        # Calculate width needed for longest item
        font_metrics = combo.fontMetrics()
        max_width = 0
        for item in items:
            width = font_metrics.horizontalAdvance(item)
            max_width = max(max_width, width)
        
        # Add padding for dropdown arrow and margins (about 50px)
        needed_width = max_width + 50
        
        # Set minimum width, but don't exceed reasonable maximum
        combo.setMinimumWidth(min(needed_width, 400))

    def _show_model_browser(self, category: str):
        """Show the model browser dialog for downloading models."""
        if not self._api_client:
            QtWidgets.QMessageBox.warning(
                self,
                'Not Connected',
                'Cannot download models: Ollama API client not available.'
            )
            return
        
        try:
            from ._model_browser import ModelBrowserDialog
            dialog = ModelBrowserDialog(self._api_client, category, parent=self)
            result = dialog.exec()
            
            # Always reload models after dialog closes (whether download happened or not)
            # Use a longer delay to give Ollama time to update its internal model registry
            # after a download completes, especially for fast downloads
            # Try multiple times with increasing delays to catch models that register slowly
            QtCore.QTimer.singleShot(1000, self._load_models)
            QtCore.QTimer.singleShot(3000, self._load_models)  # Second refresh after 3 seconds
            QtCore.QTimer.singleShot(6000, self._load_models)  # Third refresh after 6 seconds
        except Exception as e:
            log.error(f'Failed to show model browser: {e}', exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                'Error',
                f'Failed to open model browser:\n{str(e)}'
            )

    def _create_text_tab(self) -> QtWidgets.QWidget:
        """Create the text processing tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Model selection
        model_layout = QtWidgets.QHBoxLayout()
        model_layout.addWidget(QtWidgets.QLabel('Model:'))
        model_combo = QtWidgets.QComboBox()
        model_combo.setObjectName('model_text')
        model_combo.setEditable(True)
        model_combo.setToolTip('Recommended: llama3.2, llama3.1, mistral, mixtral, phi3')
        model_combo.setMinimumWidth(200)
        model_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Fixed)
        model_layout.addWidget(model_combo)
        
        # Add info label
        info_label = QtWidgets.QLabel('(Text models)')
        info_label.setStyleSheet('color: gray; font-size: 10px;')
        model_layout.addWidget(info_label)
        
        # Download models button
        download_btn = QtWidgets.QPushButton('📥 Download Models...')
        download_btn.setToolTip('Browse and download text models')
        download_btn.clicked.connect(lambda: self._show_model_browser('text'))
        model_layout.addWidget(download_btn)
        model_layout.addStretch()
        layout.addLayout(model_layout)
        
        # Chat interface
        chat_widget = QtWidgets.QWidget()
        chat_layout = QtWidgets.QVBoxLayout(chat_widget)
        
        # Messages display
        messages_text = QtWidgets.QTextEdit()
        messages_text.setReadOnly(True)
        messages_text.setPlaceholderText('Chat messages will appear here...')
        chat_layout.addWidget(messages_text)
        
        # Input area
        input_layout = QtWidgets.QHBoxLayout()
        input_text = QtWidgets.QLineEdit()
        input_text.setPlaceholderText('Type your message...')
        send_btn = QtWidgets.QPushButton('Send')
        
        def send_message():
            model = model_combo.currentText()
            message = input_text.text()
            if not model or not message:
                return
            
            # Add user message to display
            messages_text.append(f'<b>You:</b> {message}')
            input_text.clear()
            
            # Disable input while processing
            send_btn.setEnabled(False)
            input_text.setEnabled(False)
            
            # Send to Ollama
            try:
                # Get conversation history (simplified - in production, maintain proper history)
                messages = [{'role': 'user', 'content': message}]
                response = self._api_client.chat(model=model, messages=messages)
                messages_text.append(f'<b>Assistant:</b> {response}')
            except Exception as e:
                messages_text.append(f'<b>Error:</b> {str(e)}')
            finally:
                send_btn.setEnabled(True)
                input_text.setEnabled(True)
                input_text.setFocus()
        
        input_text.returnPressed.connect(send_message)
        send_btn.clicked.connect(send_message)
        
        input_layout.addWidget(input_text)
        input_layout.addWidget(send_btn)
        chat_layout.addLayout(input_layout)
        
        layout.addWidget(chat_widget)
        
        return widget

    def _create_image_processing_tab(self) -> QtWidgets.QWidget:
        """Create the image processing tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Model selection
        model_layout = QtWidgets.QHBoxLayout()
        model_layout.addWidget(QtWidgets.QLabel('Vision Model:'))
        model_combo = QtWidgets.QComboBox()
        model_combo.setObjectName('model_vision')
        model_combo.setEditable(True)
        model_combo.setToolTip('Recommended: llava, bakllava, llava-phi3, moondream')
        model_combo.setMinimumWidth(200)
        model_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Fixed)
        model_layout.addWidget(model_combo)
        
        # Add info label
        info_label = QtWidgets.QLabel('(Vision models)')
        info_label.setStyleSheet('color: gray; font-size: 10px;')
        model_layout.addWidget(info_label)
        
        # Download models button
        download_btn = QtWidgets.QPushButton('📥 Download Models...')
        download_btn.setToolTip('Browse and download vision models')
        download_btn.clicked.connect(lambda: self._show_model_browser('vision'))
        model_layout.addWidget(download_btn)
        model_layout.addStretch()
        layout.addLayout(model_layout)
        
        # Image selection
        image_layout = QtWidgets.QHBoxLayout()
        image_path_edit = QtWidgets.QLineEdit()
        image_path_edit.setPlaceholderText('Select an image file...')
        browse_btn = QtWidgets.QPushButton('Browse...')
        
        def browse_image():
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                'Select Image',
                '',
                'Image Files (*.png *.jpg *.jpeg *.gif *.bmp)'
            )
            if path:
                image_path_edit.setText(path)
        
        browse_btn.clicked.connect(browse_image)
        image_layout.addWidget(QtWidgets.QLabel('Image:'))
        image_layout.addWidget(image_path_edit)
        image_layout.addWidget(browse_btn)
        layout.addLayout(image_layout)
        
        # Prompt
        prompt_layout = QtWidgets.QVBoxLayout()
        prompt_layout.addWidget(QtWidgets.QLabel('Prompt:'))
        prompt_text = QtWidgets.QTextEdit()
        prompt_text.setPlaceholderText('Describe what you want to know about the image...')
        prompt_text.setMaximumHeight(100)
        prompt_layout.addWidget(prompt_text)
        layout.addLayout(prompt_layout)
        
        # Process button
        process_btn = QtWidgets.QPushButton('Process Image')
        
        # Results display
        results_text = QtWidgets.QTextEdit()
        results_text.setReadOnly(True)
        results_text.setPlaceholderText('Results will appear here...')
        layout.addWidget(results_text)
        
        def process_image():
            model = model_combo.currentText()
            image_path = image_path_edit.text()
            prompt = prompt_text.toPlainText()
            
            if not model or not image_path or not prompt:
                QtWidgets.QMessageBox.warning(self, 'Missing Information', 'Please select a model, image, and enter a prompt.')
                return
            
            process_btn.setEnabled(False)
            results_text.clear()
            results_text.append('Processing image...')
            
            try:
                response = self._api_client.process_image(
                    model=model,
                    prompt=prompt,
                    image_path=image_path
                )
                results_text.clear()
                results_text.append(response)
            except Exception as e:
                results_text.clear()
                results_text.append(f'Error: {str(e)}')
            finally:
                process_btn.setEnabled(True)
        
        process_btn.clicked.connect(process_image)
        layout.addWidget(process_btn)
        
        return widget

    def _create_image_generation_tab(self) -> QtWidgets.QWidget:
        """Create the image generation tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Model selection
        model_layout = QtWidgets.QHBoxLayout()
        model_layout.addWidget(QtWidgets.QLabel('Image Model:'))
        model_combo = QtWidgets.QComboBox()
        model_combo.setObjectName('model_image_gen')
        model_combo.setEditable(True)
        model_combo.setToolTip('Recommended: flux, flux-schnell, flux-dev (fast image generation)')
        model_combo.setMinimumWidth(200)
        model_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Fixed)
        model_layout.addWidget(model_combo)
        
        # Add info label
        info_label = QtWidgets.QLabel('(Image generation models)')
        info_label.setStyleSheet('color: gray; font-size: 10px;')
        model_layout.addWidget(info_label)
        
        # Download models button
        download_btn = QtWidgets.QPushButton('📥 Download Models...')
        download_btn.setToolTip('Browse and download image generation models')
        download_btn.clicked.connect(lambda: self._show_model_browser('image_gen'))
        model_layout.addWidget(download_btn)
        model_layout.addStretch()
        layout.addLayout(model_layout)
        
        # Add recommendation note
        note_label = QtWidgets.QLabel(
            '💡 Tip: flux-schnell is fastest, flux-dev offers more control. '
            'Click "Download Models" to browse available models.'
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet('color: rgb(150, 150, 150); font-size: 10px; padding: 5px;')
        layout.addWidget(note_label)
        
        # Prompt
        prompt_layout = QtWidgets.QVBoxLayout()
        prompt_layout.addWidget(QtWidgets.QLabel('Prompt:'))
        prompt_text = QtWidgets.QTextEdit()
        prompt_text.setPlaceholderText('Describe the image you want to generate...')
        prompt_text.setMaximumHeight(100)
        prompt_layout.addWidget(prompt_text)
        layout.addLayout(prompt_layout)
        
        # Output path
        output_layout = QtWidgets.QHBoxLayout()
        output_path_edit = QtWidgets.QLineEdit()
        output_path_edit.setPlaceholderText('Output path (optional)...')
        browse_btn = QtWidgets.QPushButton('Browse...')
        
        def browse_output():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                'Save Generated Image',
                '',
                'Image Files (*.png *.jpg *.jpeg)'
            )
            if path:
                output_path_edit.setText(path)
        
        browse_btn.clicked.connect(browse_output)
        output_layout.addWidget(QtWidgets.QLabel('Save to:'))
        output_layout.addWidget(output_path_edit)
        output_layout.addWidget(browse_btn)
        layout.addLayout(output_layout)
        
        # Generate button
        generate_btn = QtWidgets.QPushButton('Generate Image')
        
        # Preview area
        preview_label = QtWidgets.QLabel('Generated image will appear here...')
        preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_label.setMinimumHeight(300)
        preview_label.setStyleSheet('border: 1px solid gray; background-color: rgb(40, 40, 40);')
        layout.addWidget(preview_label)
        
        def generate_image():
            model = model_combo.currentText()
            prompt = prompt_text.toPlainText()
            output_path = output_path_edit.text() or None
            
            if not model or not prompt:
                QtWidgets.QMessageBox.warning(self, 'Missing Information', 'Please select a model and enter a prompt.')
                return
            
            generate_btn.setEnabled(False)
            preview_label.setText('Generating image...')
            
            try:
                image_data = self._api_client.generate_image(
                    model=model,
                    prompt=prompt,
                    output_path=output_path
                )
                
                # Display image
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_data)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        preview_label.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation
                    )
                    preview_label.setPixmap(scaled)
                    preview_label.setText('')
                else:
                    preview_label.setText('Failed to load generated image')
            except Exception as e:
                preview_label.setText(f'Error: {str(e)}')
            finally:
                generate_btn.setEnabled(True)
        
        generate_btn.clicked.connect(generate_image)
        layout.addWidget(generate_btn)
        
        return widget

    def _create_3d_generation_tab(self) -> QtWidgets.QWidget:
        """Create the 3D generation from image tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Model selection
        model_layout = QtWidgets.QHBoxLayout()
        model_layout.addWidget(QtWidgets.QLabel('3D Model:'))
        model_combo = QtWidgets.QComboBox()
        model_combo.setObjectName('model_3d')
        model_combo.setEditable(True)
        model_combo.setToolTip('3D generation models (limited availability in Ollama)')
        model_combo.setMinimumWidth(200)
        model_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Fixed)
        model_layout.addWidget(model_combo)
        
        # Add info label
        info_label = QtWidgets.QLabel('(3D models)')
        info_label.setStyleSheet('color: gray; font-size: 10px;')
        model_layout.addWidget(info_label)
        
        # Download models button
        download_btn = QtWidgets.QPushButton('📥 Download Models...')
        download_btn.setToolTip('Browse and download 3D models')
        download_btn.clicked.connect(lambda: self._show_model_browser('3d'))
        model_layout.addWidget(download_btn)
        model_layout.addStretch()
        layout.addLayout(model_layout)
        
        # Add note about 3D model availability
        note_label = QtWidgets.QLabel(
            '⚠️ Note: 3D model generation from images is experimental. '
            'You may need to use specialized models or external tools. '
            'Some vision models (llava) can describe 3D structure from images.'
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet('color: rgb(200, 150, 100); font-size: 10px; padding: 5px;')
        layout.addWidget(note_label)
        
        # Image selection
        image_layout = QtWidgets.QHBoxLayout()
        image_path_edit = QtWidgets.QLineEdit()
        image_path_edit.setPlaceholderText('Select an input image...')
        browse_btn = QtWidgets.QPushButton('Browse...')
        
        def browse_image():
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                'Select Input Image',
                '',
                'Image Files (*.png *.jpg *.jpeg *.gif *.bmp)'
            )
            if path:
                image_path_edit.setText(path)
        
        browse_btn.clicked.connect(browse_image)
        image_layout.addWidget(QtWidgets.QLabel('Input Image:'))
        image_layout.addWidget(image_path_edit)
        image_layout.addWidget(browse_btn)
        layout.addLayout(image_layout)
        
        # Optional prompt
        prompt_layout = QtWidgets.QVBoxLayout()
        prompt_layout.addWidget(QtWidgets.QLabel('Optional Prompt:'))
        prompt_text = QtWidgets.QTextEdit()
        prompt_text.setPlaceholderText('Additional instructions for 3D generation...')
        prompt_text.setMaximumHeight(80)
        prompt_layout.addWidget(prompt_text)
        layout.addLayout(prompt_layout)
        
        # Output path
        output_layout = QtWidgets.QHBoxLayout()
        output_path_edit = QtWidgets.QLineEdit()
        output_path_edit.setPlaceholderText('Output path for 3D model...')
        browse_output_btn = QtWidgets.QPushButton('Browse...')
        
        def browse_output():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                'Save 3D Model',
                '',
                '3D Model Files (*.obj *.glb *.gltf *.ply)'
            )
            if path:
                output_path_edit.setText(path)
        
        browse_output_btn.clicked.connect(browse_output)
        output_layout.addWidget(QtWidgets.QLabel('Save to:'))
        output_layout.addWidget(output_path_edit)
        output_layout.addWidget(browse_output_btn)
        layout.addLayout(output_layout)
        
        # Generate button
        generate_btn = QtWidgets.QPushButton('Generate 3D Model')
        
        # Status display
        status_text = QtWidgets.QTextEdit()
        status_text.setReadOnly(True)
        status_text.setPlaceholderText('Status and results will appear here...')
        layout.addWidget(status_text)
        
        def generate_3d():
            model = model_combo.currentText()
            image_path = image_path_edit.text()
            prompt = prompt_text.toPlainText() or None
            output_path = output_path_edit.text() or None
            
            if not model or not image_path:
                QtWidgets.QMessageBox.warning(self, 'Missing Information', 'Please select a model and input image.')
                return
            
            if not output_path:
                QtWidgets.QMessageBox.warning(self, 'Missing Output', 'Please specify an output path for the 3D model.')
                return
            
            generate_btn.setEnabled(False)
            status_text.clear()
            status_text.append('Generating 3D model from image...')
            
            try:
                model_data = self._api_client.generate_3d_from_image(
                    model=model,
                    image_path=image_path,
                    prompt=prompt,
                    output_path=output_path
                )
                status_text.append(f'Success! Generated 3D model saved to: {output_path}')
                status_text.append(f'Model size: {len(model_data)} bytes')
            except Exception as e:
                status_text.append(f'Error: {str(e)}')
            finally:
                generate_btn.setEnabled(True)
        
        generate_btn.clicked.connect(generate_3d)
        layout.addWidget(generate_btn)
        
        return widget

    def _create_settings_tab(self) -> QtWidgets.QWidget:
        """Create the settings tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Base URL setting
        url_layout = QtWidgets.QHBoxLayout()
        url_layout.addWidget(QtWidgets.QLabel('Ollama API URL:'))
        url_edit = QtWidgets.QLineEdit()
        if self._api_client:
            url_edit.setText(self._api_client.base_url)
        url_edit.setPlaceholderText('http://localhost:11434')
        url_layout.addWidget(url_edit)
        
        def update_url():
            new_url = url_edit.text().strip()
            if new_url and self._api_client:
                self._api_client.base_url = new_url.rstrip('/')
                if self._service and hasattr(self._service, 'set_base_url'):
                    self._service.set_base_url(new_url)
                self._update_connection_status()
                self._load_models()
                QtWidgets.QMessageBox.information(self, 'Settings Updated', 'Ollama URL updated. Reconnecting...')
        
        update_btn = QtWidgets.QPushButton('Update')
        update_btn.clicked.connect(update_url)
        url_layout.addWidget(update_btn)
        layout.addLayout(url_layout)
        
        # Test connection button
        test_btn = QtWidgets.QPushButton('Test Connection')
        
        def test_connection():
            if self._api_client:
                if self._api_client.check_connection():
                    QtWidgets.QMessageBox.information(self, 'Connection Test', 'Successfully connected to Ollama!')
                else:
                    QtWidgets.QMessageBox.warning(self, 'Connection Test', 'Failed to connect to Ollama. Make sure it is running.')
            else:
                QtWidgets.QMessageBox.warning(self, 'Connection Test', 'Ollama API client not available.')
        
        test_btn.clicked.connect(test_connection)
        layout.addWidget(test_btn)
        
        layout.addStretch()
        
        return widget

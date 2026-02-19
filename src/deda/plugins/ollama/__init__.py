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
"""
Ollama service plugin for interacting with locally hosted Ollama models.

Supports:
- Text processing (chat, completion)
- Image processing (vision models)
- Image generation
- 3D model generation from images
"""
import logging
from pathlib import Path

from deda.core import PluginRegistry, Service, Tool

log = logging.getLogger(__name__)


class OllamaService(Service):
    """Service plugin for Ollama API integration."""

    def __init__(self):
        super().__init__(
            name='ollama',
            url='http://localhost:11434',  # Default Ollama API endpoint
            description='Local Ollama models for text, image, and 3D processing',
        )
        self._base_url = 'http://localhost:11434'
        self._api_client = None

    def load(self):
        """Initialize the Ollama service."""
        try:
            # Try to connect to Ollama API
            import requests
            response = requests.get(f'{self._base_url}/api/tags', timeout=2)
            if response.status_code == 200:
                self._loaded = True
                log.info(f'Ollama service loaded successfully at {self._base_url}')
                return True
            else:
                log.warning(f'Ollama service at {self._base_url} returned status {response.status_code}')
                return False
        except Exception as e:
            log.debug(f'Ollama service not available at {self._base_url}: {e}')
            # Service can still be registered even if not running
            self._loaded = True
            return True

    def get_base_url(self) -> str:
        """Get the base URL for Ollama API."""
        return self._base_url

    def set_base_url(self, url: str) -> None:
        """Set the base URL for Ollama API."""
        self._base_url = url
        if hasattr(self, 'url'):
            self.url = url


class OllamaTool(Tool):
    """UI tool for interacting with Ollama models."""

    def __init__(self):
        super().__init__(
            name='ollama',  # Match service name exactly (lowercase)
            description='Interact with local Ollama models for text, image, and 3D processing',
        )
        self._service = None
        self._window_instance = None

    def load(self):
        """Load the Ollama tool."""
        # Find the Ollama service
        self._service = PluginRegistry().get('ollama')
        if not self._service:
            log.warning('Ollama service not found in registry')
        self._loaded = True
        return True

    def initialize_window(self, parent):
        """Initialize the Ollama tool window."""
        from ._tool_window import OllamaToolWindow
        if self._window_instance is None:
            self._window_instance = OllamaToolWindow(
                service=self._service,
                parent=parent
            )
        return self._window_instance

    def launch(self):
        """Launch the Ollama tool window."""
        # Use the base class launch method which handles initialization properly
        if not self._window_instance:
            import deda.app
            parent_window = deda.app.get_top_window()
            self._window_instance = self.initialize_window(parent=parent_window)
        if not self._window_instance:
            log.error(f'{self.name} did not return a window instance from initialize_window!')
            return
        
        # Show window and ensure it's visible before restoring cursor
        self._window_instance.show()
        self._window_instance.raise_()
        self._window_instance.activateWindow()
        
        # Process events to ensure window is painted before cursor is restored
        from PySide6 import QtWidgets
        QtWidgets.QApplication.processEvents()


# Register plugins
def _register_plugins():
    """Register Ollama plugins."""
    try:
        service = OllamaService()
        PluginRegistry().register(service)
        log.info(f'Ollama service plugin registered: {service.name}')
        
        tool = OllamaTool()
        PluginRegistry().register(tool)
        log.info(f'Ollama tool plugin registered: {tool.name}')
        
        log.info('Ollama plugins registered successfully')
    except Exception as e:
        log.error(f'Failed to register Ollama plugins: {e}', exc_info=True)


# Auto-register on import
_register_plugins()

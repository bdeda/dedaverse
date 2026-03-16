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
Trellis service plugin for generating 3D textured models from images.

Trellis is an AI model for generating 3D textured models from images.
This plugin communicates with a Trellis server (typically running via Gradio).
"""
import logging
from pathlib import Path

from deda.core import PluginRegistry, Service, Tool

log = logging.getLogger(__name__)


class TrellisService(Service):
    """Service plugin for Trellis API integration."""

    def __init__(self):
        super().__init__(
            name='trellis',
            url='http://127.0.0.1:7860',  # Default Trellis server endpoint (Gradio default port)
            description='Trellis AI model for generating 3D textured models from images',
        )
        self._base_url = 'http://127.0.0.1:7860'
        self._api_client = None

    def load(self):
        """Initialize the Trellis service."""
        try:
            # Try to connect to Trellis API (Gradio)
            import requests
            response = requests.get(f'{self._base_url}/', timeout=2)
            if response.status_code == 200:
                self._loaded = True
                log.info(f'Trellis service loaded successfully at {self._base_url}')
                return True
            else:
                log.warning(f'Trellis service at {self._base_url} returned status {response.status_code}')
                return False
        except Exception as e:
            log.debug(f'Trellis service not available at {self._base_url}: {e}')
            # Service can still be registered even if not running
            self._loaded = True
            return True

    def get_base_url(self) -> str:
        """Get the base URL for Trellis API."""
        return self._base_url

    def set_base_url(self, url: str) -> None:
        """Set the base URL for Trellis API."""
        self._base_url = url
        if hasattr(self, 'url'):
            self.url = url


class TrellisTool(Tool):
    """UI tool for interacting with Trellis 3D generation."""

    def __init__(self):
        super().__init__(
            name='trellis',  # Match service name exactly
            description='Generate 3D textured models from images using Trellis',
        )
        self._service = None
        self._window_instance = None

    def load(self):
        """Load the Trellis tool."""
        # Find the Trellis service
        self._service = PluginRegistry().get('trellis')
        if not self._service:
            log.warning('Trellis service not found in registry')
        self._loaded = True
        return True

    def initialize_window(self, parent):
        """Initialize the Trellis tool window."""
        from ._tool_window import TrellisToolWindow
        if self._window_instance is None:
            self._window_instance = TrellisToolWindow(
                service=self._service,
                parent=parent
            )
        return self._window_instance

    def launch(self):
        """Launch the Trellis tool window."""
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
    """Register Trellis plugins."""
    try:
        service = TrellisService()
        PluginRegistry().register(service)
        log.info(f'Trellis service plugin registered: {service.name}')
        
        tool = TrellisTool()
        PluginRegistry().register(tool)
        log.info(f'Trellis tool plugin registered: {tool.name}')
        
        log.info('Trellis plugins registered successfully')
    except Exception as e:
        log.error(f'Failed to register Trellis plugins: {e}', exc_info=True)


# Auto-register on import
_register_plugins()

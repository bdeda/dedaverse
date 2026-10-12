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
Image generation plugin for Dedaverse.

Supports multiple backends:
  - Google Gemini / Imagen 3  (requires google-genai or google-generativeai)
  - Ollama (local, requires a compatible model)
  - Generic REST web service  (Automatic1111, ComfyUI, StabilityAI, Replicate, etc.)

Generated images are downloaded and saved to the local filesystem.
"""
import logging
import os
from pathlib import Path

from deda.core import PluginRegistry, Service, Tool

from ._api_client import ImageGenBackend, ImageGenClient

log = logging.getLogger(__name__)

_ENV_GEMINI_API_KEY = 'GEMINI_API_KEY'
_ENV_IMAGEGEN_BACKEND = 'DEDAVERSE_IMAGEGEN_BACKEND'
_ENV_IMAGEGEN_MODEL = 'DEDAVERSE_IMAGEGEN_MODEL'
_ENV_OLLAMA_URL = 'OLLAMA_URL'
_ENV_GENERIC_ENDPOINT = 'DEDAVERSE_IMAGEGEN_ENDPOINT'


class ImageGenService(Service):
    """Service plugin that owns the image generation client and backend configuration.

    Environment variables (all optional):
        GEMINI_API_KEY             Google API key for Gemini / Imagen backends.
        DEDAVERSE_IMAGEGEN_BACKEND  Active backend: gemini | ollama | generic
        DEDAVERSE_IMAGEGEN_MODEL    Default model name for the active backend.
        OLLAMA_URL                 Base URL for Ollama (default http://localhost:11434).
        DEDAVERSE_IMAGEGEN_ENDPOINT Full endpoint URL for generic web service backend.
    """

    PLUGIN_NAME = 'imagegen'

    def __init__(self):
        super().__init__(
            name=self.PLUGIN_NAME,
            description='Multi-backend image generation (Gemini, Ollama, generic REST)',
        )
        self._client: ImageGenClient | None = None

    def load(self) -> bool:
        """Initialize service from environment / defaults."""
        backend_name = os.getenv(_ENV_IMAGEGEN_BACKEND, ImageGenBackend.GEMINI)
        try:
            backend = ImageGenBackend(backend_name)
        except ValueError:
            log.warning(f'Unknown backend "{backend_name}", falling back to gemini')
            backend = ImageGenBackend.GEMINI

        self._client = ImageGenClient(
            backend=backend,
            gemini_api_key=os.getenv(_ENV_GEMINI_API_KEY, ''),
            gemini_model=os.getenv(_ENV_IMAGEGEN_MODEL, ''),
            ollama_url=os.getenv(_ENV_OLLAMA_URL, ''),
            ollama_model=os.getenv(_ENV_IMAGEGEN_MODEL, ''),
            generic_endpoint=os.getenv(_ENV_GENERIC_ENDPOINT, ''),
        )

        self._loaded = True
        log.info(f'ImageGen service loaded (backend={backend})')
        return True

    @property
    def client(self) -> ImageGenClient:
        """Return the underlying ImageGenClient."""
        if self._client is None:
            self.load()
        return self._client

    @property
    def backend(self) -> ImageGenBackend:
        return self.client.backend

    @backend.setter
    def backend(self, value: ImageGenBackend) -> None:
        self.client.backend = value

    def configure_gemini(self, api_key: str = '', model: str = '') -> None:
        self.client.configure_gemini(api_key=api_key, model=model)

    def configure_ollama(self, url: str = '', model: str = '') -> None:
        self.client.configure_ollama(url=url, model=model)

    def configure_generic(self, endpoint: str = '', auth_header: str = '', **kwargs) -> None:
        self.client.configure_generic(endpoint=endpoint, auth_header=auth_header, **kwargs)


class ImageGenTool(Tool):
    """UI tool for interacting with the image generation service."""

    def __init__(self):
        super().__init__(
            name='imagegen',
            description='Generate images from prompts, reference art, and design docs',
        )
        self._service: ImageGenService | None = None

    def load(self) -> bool:
        self._service = PluginRegistry().get(ImageGenService.PLUGIN_NAME)
        if not self._service:
            log.warning('ImageGen service not found in registry')
        self._loaded = True
        return True

    def initialize_window(self, parent):
        from ._tool_window import ImageGenToolWindow
        if self._window_instance is None:
            self._window_instance = ImageGenToolWindow(
                service=self._service,
                parent=parent,
            )
        return self._window_instance

    def launch(self):
        if not self._window_instance:
            import deda.app
            parent_window = deda.app.get_top_window()
            self._window_instance = self.initialize_window(parent=parent_window)
        if not self._window_instance:
            log.error('ImageGen tool did not return a window instance')
            return
        self._window_instance.show()
        self._window_instance.raise_()
        self._window_instance.activateWindow()

        from PySide6 import QtWidgets
        QtWidgets.QApplication.processEvents()


def _register_plugins():
    try:
        service = ImageGenService()
        PluginRegistry().register(service)
        log.info(f'ImageGen service plugin registered: {service.name}')

        tool = ImageGenTool()
        PluginRegistry().register(tool)
        log.info(f'ImageGen tool plugin registered: {tool.name}')
    except Exception as exc:
        log.error(f'Failed to register ImageGen plugins: {exc}', exc_info=True)


_register_plugins()

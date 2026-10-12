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
"""Tests for the imagegen service and tool plugins."""
import sys
import types

import pytest

import deda.plugins.imagegen as imagegen
from deda.plugins.imagegen._api_client import ImageGenBackend


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (imagegen._ENV_GEMINI_API_KEY, imagegen._ENV_IMAGEGEN_BACKEND, imagegen._ENV_IMAGEGEN_MODEL,
                 imagegen._ENV_OLLAMA_URL, imagegen._ENV_GENERIC_ENDPOINT):
        monkeypatch.delenv(name, raising=False)


class TestService:
    def test_load_reads_the_environment(self, monkeypatch):
        monkeypatch.setenv(imagegen._ENV_IMAGEGEN_BACKEND, 'ollama')
        monkeypatch.setenv(imagegen._ENV_OLLAMA_URL, 'http://box:11434')
        monkeypatch.setenv(imagegen._ENV_IMAGEGEN_MODEL, 'sdxl')
        monkeypatch.setenv(imagegen._ENV_GEMINI_API_KEY, 'key')
        service = imagegen.ImageGenService()
        assert service.load() is True and service.loaded
        assert service.backend == ImageGenBackend.OLLAMA
        assert service.client._ollama_url == 'http://box:11434' and service.client._ollama_model == 'sdxl'
        assert service.client._gemini_api_key == 'key'

    def test_unknown_backend_falls_back_to_gemini(self, monkeypatch, caplog):
        monkeypatch.setenv(imagegen._ENV_IMAGEGEN_BACKEND, 'carrier-pigeon')
        with caplog.at_level('WARNING'):
            service = imagegen.ImageGenService()
            service.load()
        assert service.backend == ImageGenBackend.GEMINI and 'Unknown backend' in caplog.text

    def test_client_loads_lazily_and_settings_pass_through(self):
        service = imagegen.ImageGenService()
        assert service._client is None
        assert service.client is service.client and service._client is not None
        service.backend = ImageGenBackend.GENERIC
        service.configure_generic(endpoint='http://g', auth_header='Bearer x')
        service.configure_gemini(api_key='k', model='imagen-x')
        service.configure_ollama(url='http://o', model='m')
        assert service.backend == ImageGenBackend.GENERIC
        assert service.client._generic_endpoint == 'http://g' and service.client._gemini_model == 'imagen-x'
        assert service.client._ollama_url == 'http://o'


class TestTool:
    def test_load_finds_the_service(self):
        service = imagegen.ImageGenService()
        registry = imagegen.PluginRegistry()
        registry.register(service)
        try:
            tool = imagegen.ImageGenTool()
            assert tool.load() is True and tool._service is service
        finally:
            imagegen.PluginRegistry._registry_.pop(service.name, None)

    def test_load_without_a_service_warns(self, monkeypatch, caplog):
        monkeypatch.setattr(imagegen.PluginRegistry, 'get', lambda self, name: None)
        with caplog.at_level('WARNING'):
            assert imagegen.ImageGenTool().load() is True
        assert 'service not found' in caplog.text

    def test_window_is_built_once(self, monkeypatch):
        built = []

        class FakeWindow:
            def __init__(self, service, parent):
                built.append((service, parent))

        module = types.ModuleType('deda.plugins.imagegen._tool_window')
        module.ImageGenToolWindow = FakeWindow
        monkeypatch.setitem(sys.modules, 'deda.plugins.imagegen._tool_window', module)
        tool = imagegen.ImageGenTool()
        first = tool.initialize_window('parent')
        assert tool.initialize_window('parent') is first and len(built) == 1

    def test_launch_shows_the_window(self, monkeypatch):
        import deda.app
        from PySide6 import QtWidgets
        shown = []

        class Window:
            def show(self):
                shown.append('show')

            def raise_(self):
                shown.append('raise')

            def activateWindow(self):
                shown.append('activate')

        monkeypatch.setattr(deda.app, 'get_top_window', lambda: None, raising=False)
        monkeypatch.setattr(QtWidgets.QApplication, 'processEvents', staticmethod(lambda *a: shown.append('events')))
        tool = imagegen.ImageGenTool()
        monkeypatch.setattr(tool, 'initialize_window', lambda parent: Window())
        tool.launch()
        assert shown[:3] == ['show', 'raise', 'activate'] and shown[-1] == 'events'

    def test_launch_without_a_window_logs(self, monkeypatch, caplog):
        import deda.app
        monkeypatch.setattr(deda.app, 'get_top_window', lambda: None, raising=False)
        tool = imagegen.ImageGenTool()
        monkeypatch.setattr(tool, 'initialize_window', lambda parent: None)
        with caplog.at_level('ERROR'):
            tool.launch()
        assert 'did not return a window instance' in caplog.text


def test_registration_survives_a_failure(monkeypatch, caplog):
    def broken():
        raise RuntimeError('boom')

    monkeypatch.setattr(imagegen, 'ImageGenService', broken)
    with caplog.at_level('ERROR'):
        imagegen._register_plugins()
    assert 'Failed to register' in caplog.text

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
"""Tests for the Ollama service and tool plugins."""
import sys
import types

import pytest
import requests

import deda.plugins.ollama as ollama


@pytest.fixture
def service():
    return ollama.OllamaService()


class TestService:
    def test_base_url(self, service):
        assert service.get_base_url() == 'http://localhost:11434'
        service.set_base_url('http://box:1234')
        assert service.get_base_url() == 'http://box:1234'

    @pytest.mark.parametrize('status, expected', [(200, True), (500, False)])
    def test_load_by_status(self, service, monkeypatch, status, expected):
        monkeypatch.setattr(requests, 'get', lambda url, timeout: types.SimpleNamespace(status_code=status))
        assert service.load() is expected and service.loaded is expected

    def test_load_succeeds_when_ollama_is_not_running(self, service, monkeypatch):
        def refuse(url, timeout):
            raise requests.ConnectionError('down')

        monkeypatch.setattr(requests, 'get', refuse)
        assert service.load() is True and service.loaded


class TestTool:
    def test_load_finds_the_service(self, service):
        registry = ollama.PluginRegistry()
        registry.register(service)
        try:
            tool = ollama.OllamaTool()
            assert tool.load() is True and tool._service is service
        finally:
            ollama.PluginRegistry._registry_.pop(service.name, None)

    def test_load_without_a_service_warns(self, monkeypatch, caplog):
        monkeypatch.setattr(ollama.PluginRegistry, 'get', lambda self, name: None)
        with caplog.at_level('WARNING'):
            assert ollama.OllamaTool().load() is True
        assert 'service not found' in caplog.text

    def test_window_is_built_once(self, monkeypatch):
        built = []

        class FakeWindow:
            def __init__(self, service, parent):
                built.append((service, parent))

        module = types.ModuleType('deda.plugins.ollama._tool_window')
        module.OllamaToolWindow = FakeWindow
        monkeypatch.setitem(sys.modules, 'deda.plugins.ollama._tool_window', module)
        tool = ollama.OllamaTool()
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
        tool = ollama.OllamaTool()
        monkeypatch.setattr(tool, 'initialize_window', lambda parent: Window())
        tool.launch()
        assert shown == ['show', 'raise', 'activate', 'events']

    def test_launch_without_a_window_logs(self, monkeypatch, caplog):
        import deda.app
        monkeypatch.setattr(deda.app, 'get_top_window', lambda: None, raising=False)
        tool = ollama.OllamaTool()
        monkeypatch.setattr(tool, 'initialize_window', lambda parent: None)
        with caplog.at_level('ERROR'):
            tool.launch()
        assert 'did not return a window instance' in caplog.text


def test_registration_survives_a_failure(monkeypatch, caplog):
    def broken():
        raise RuntimeError('boom')

    monkeypatch.setattr(ollama, 'OllamaService', broken)
    with caplog.at_level('ERROR'):
        ollama._register_plugins()
    assert 'Failed to register' in caplog.text

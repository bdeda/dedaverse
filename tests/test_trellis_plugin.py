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
"""Tests for the Trellis service/tool plugins and the remaining TRELLIS.2 server helpers."""
import subprocess
import sys
import types

import pytest
import requests

import deda.plugins.trellis as trellis
from deda.plugins.trellis import _trellis2


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(trellis.atexit, 'register', lambda fn: None)
    return trellis.TrellisService()


class TestService:
    def test_defaults(self, service):
        assert service.get_base_url() == 'http://127.0.0.1:7860'
        service.set_base_url('http://other:9000')
        assert service.get_base_url() == 'http://other:9000'
        assert service.log_path() == _trellis2.LOG_PATH

    @pytest.mark.parametrize('status, expected', [(200, True), (503, False)])
    def test_load_by_status(self, service, monkeypatch, status, expected):
        monkeypatch.setattr(requests, 'get', lambda url, timeout: types.SimpleNamespace(status_code=status))
        assert service.load() is expected
        assert service.loaded is (status == 200)

    def test_load_succeeds_when_the_server_is_not_running(self, service, monkeypatch):
        def refuse(url, timeout):
            raise requests.ConnectionError('down')

        monkeypatch.setattr(requests, 'get', refuse)
        assert service.load() is True and service.loaded

    def test_server_lifecycle(self, service, monkeypatch, tmp_path):
        started = []

        class FakeServer:
            running = False

            def __init__(self, install, port):
                started.append(('init', install, port))

            def start(self):
                started.append('start')
                FakeServer.running = True

            def stop(self):
                started.append('stop')

        monkeypatch.setattr(_trellis2, 'Trellis2Server', FakeServer)
        monkeypatch.setattr(_trellis2, 'find_install', lambda path=None: None)
        assert not service.can_start_server() and not service.server_running()
        service.stop_server()                       # nothing started yet: a no-op
        with pytest.raises(FileNotFoundError, match=_trellis2.ENV_DIR):
            service.start_server()

        monkeypatch.setattr(_trellis2, 'find_install', lambda path=None: tmp_path)
        assert service.can_start_server()
        service.set_base_url('http://127.0.0.1:9100')
        service.start_server()
        service.start_server()                      # the same server object is reused
        assert started == [('init', tmp_path, 9100), 'start', 'start']
        assert service.server_running()
        service.stop_server()
        assert started[-1] == 'stop'

    def test_default_port_when_the_url_has_none(self, service, monkeypatch, tmp_path):
        ports = []

        class FakeServer:
            running = False

            def __init__(self, install, port):
                ports.append(port)

            def start(self):
                pass

        monkeypatch.setattr(_trellis2, 'Trellis2Server', FakeServer)
        monkeypatch.setattr(_trellis2, 'find_install', lambda path=None: tmp_path)
        service.set_base_url('http://trellis.local')
        service.start_server()
        assert ports == [_trellis2.DEFAULT_PORT]


class TestTool:
    def test_load_finds_the_service_in_the_registry(self, service):
        registry = trellis.PluginRegistry()
        registry.register(service)
        try:
            tool = trellis.TrellisTool()
            assert tool.load() is True and tool._service is service
        finally:
            trellis.PluginRegistry._registry_.pop(service.name, None)

    def test_load_without_a_service_warns(self, monkeypatch, caplog):
        monkeypatch.setattr(trellis.PluginRegistry, 'get', lambda self, name: None)
        with caplog.at_level('WARNING'):
            assert trellis.TrellisTool().load() is True
        assert 'service not found' in caplog.text

    def test_initialize_window_builds_it_once(self, monkeypatch):
        built = []

        class FakeWindow:
            def __init__(self, service, parent):
                built.append((service, parent))

        module = types.ModuleType('deda.plugins.trellis._tool_window')
        module.TrellisToolWindow = FakeWindow
        monkeypatch.setitem(sys.modules, 'deda.plugins.trellis._tool_window', module)
        monkeypatch.setattr(trellis, '_tool_window', module, raising=False)
        tool = trellis.TrellisTool()
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
        tool = trellis.TrellisTool()
        monkeypatch.setattr(tool, 'initialize_window', lambda parent: Window())
        tool.launch()
        assert shown == ['show', 'raise', 'activate', 'events']

    def test_launch_without_a_window_logs(self, monkeypatch, caplog):
        import deda.app
        monkeypatch.setattr(deda.app, 'get_top_window', lambda: None, raising=False)
        tool = trellis.TrellisTool()
        monkeypatch.setattr(tool, 'initialize_window', lambda parent: None)
        with caplog.at_level('ERROR'):
            tool.launch()
        assert 'did not return a window' in caplog.text


def test_register_plugins_survives_a_failure(monkeypatch, caplog):
    def broken():
        raise RuntimeError('no service')

    monkeypatch.setattr(trellis, 'TrellisService', broken)
    with caplog.at_level('ERROR'):
        trellis._register_plugins()
    assert 'Failed to register' in caplog.text


class TestTrellis2Helpers:
    def test_wsl_path_without_a_drive_is_unchanged(self):
        assert _trellis2.to_wsl_path('/home/me/TRELLIS.2') == '/home/me/TRELLIS.2'

    def test_probe_rejects_unparseable_output(self, tmp_path, monkeypatch):
        (tmp_path / 'trellis2').mkdir()
        monkeypatch.setattr(subprocess, 'run', lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout='no number here', stderr=''))
        ok, message = _trellis2.probe(tmp_path)
        assert not ok and 'Unexpected output' in message

    def test_probe_failure_without_output_reports_the_exit_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(subprocess, 'run', lambda *a, **k: types.SimpleNamespace(
            returncode=3, stdout='', stderr=''))
        ok, message = _trellis2.probe(tmp_path)
        assert not ok and 'exit code 3' in message

    def test_is_ready_follows_http(self, tmp_path, monkeypatch):
        server = _trellis2.Trellis2Server(tmp_path, log_path=tmp_path / 'log.txt')
        monkeypatch.setattr(requests, 'get', lambda url, timeout: types.SimpleNamespace(status_code=200))
        assert server.is_ready()

        def refuse(url, timeout):
            raise requests.ConnectionError('down')

        monkeypatch.setattr(requests, 'get', refuse)
        assert not server.is_ready()

    def test_wait_until_ready_returns_true_when_ready_and_false_on_timeout(self, tmp_path, monkeypatch):
        server = _trellis2.Trellis2Server(tmp_path, log_path=tmp_path / 'log.txt')
        monkeypatch.setattr(server, 'is_ready', lambda: True)
        assert server.wait_until_ready(timeout=5, poll=0)
        monkeypatch.setattr(server, 'is_ready', lambda: False)
        monkeypatch.setattr(_trellis2.Trellis2Server, 'running', property(lambda self: True))
        monkeypatch.setattr(_trellis2.time, 'sleep', lambda s: None)
        assert not server.wait_until_ready(timeout=0.01, poll=0)

    def test_stop_kills_a_server_that_ignores_terminate(self, tmp_path):
        calls = []

        class Stubborn:
            def poll(self):
                return None

            def terminate(self):
                calls.append('terminate')

            def wait(self, timeout):
                calls.append('wait')
                raise subprocess.TimeoutExpired('x', timeout)

            def kill(self):
                calls.append('kill')

        server = _trellis2.Trellis2Server(tmp_path, log_path=tmp_path / 'log.txt')
        server._process = Stubborn()
        server.stop()
        assert calls == ['terminate', 'wait', 'kill'] and server._process is None
        server.stop()                                # already stopped: no-op

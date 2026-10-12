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
"""Tests for the command line entry points and the application run loop."""
import signal
import types

import pytest
from click.testing import CliRunner

from deda.app import _app
from deda.app import __main__ as app_main
from deda.core.operation import __main__ as operation_main


class TestOperationMain:
    def test_parse_args_defaults_and_overrides(self, tmp_path):
        args = operation_main._parse_args([])
        assert args.env_file is None and args.host is None and args.port is None and args.log_level == 'INFO'
        args = operation_main._parse_args(['--env-file', str(tmp_path / '.env'), '--host', '0.0.0.0',
                                           '--port', '9000', '--log-level', 'DEBUG'])
        assert (args.host, args.port, args.log_level) == ('0.0.0.0', 9000, 'DEBUG')
        assert args.env_file == tmp_path / '.env'

    @pytest.fixture
    def harness(self, monkeypatch):
        """Replace the server, signals and the blocking wait so main() returns immediately."""
        state = types.SimpleNamespace(started=None, stopped=False, handlers={}, env_loaded=None, reloaded=False)

        class Server:
            def stop(self):
                state.stopped = True

        def start_server(host, port):
            state.started = (host, port)
            return Server()

        class Event:
            def wait(self):
                state.handlers[signal.SIGINT](signal.SIGINT, None)   # simulate Ctrl-C

            def set(self):
                state.interrupted = True

        monkeypatch.setattr(operation_main, 'start_server', start_server)
        monkeypatch.setattr(operation_main.threading, 'Event', Event)
        monkeypatch.setattr(operation_main.signal, 'signal',
                            lambda number, handler: state.handlers.__setitem__(number, handler))
        monkeypatch.setattr(operation_main._config, 'load_env',
                            lambda env_file, override: setattr(state, 'env_loaded', (env_file, override)))
        monkeypatch.setattr(operation_main._config, 'reload_config', lambda: setattr(state, 'reloaded', True))
        return state

    def test_main_uses_config_values_and_stops_the_server(self, harness, monkeypatch):
        monkeypatch.setattr(operation_main._config, 'HOST', 'cfg-host')
        monkeypatch.setattr(operation_main._config, 'PORT', 1234)
        assert operation_main.main([]) == 0
        assert harness.started == ('cfg-host', 1234) and harness.stopped and harness.interrupted
        assert harness.env_loaded is None and not harness.reloaded
        assert signal.SIGINT in harness.handlers

    def test_command_line_overrides_and_env_file(self, harness, tmp_path):
        env = tmp_path / '.env'
        assert operation_main.main(['--env-file', str(env), '--host', 'h', '--port', '5']) == 0
        assert harness.started == ('h', 5) and harness.env_loaded == (env, True) and harness.reloaded


class TestAppCli:
    def test_viewer_command_shows_the_window_and_exits_with_the_event_loop_code(self, monkeypatch):
        pytest.importorskip('pxr.Usdviewq', reason='the viewer needs a full USD build')
        import deda.app
        from deda.core.viewer import _window
        shown = []

        class FakeApp:
            @staticmethod
            def instance():
                return None

            def exec(self):
                return 7

        class FakeWindow:
            def show(self):
                shown.append(True)

        monkeypatch.setattr(deda.app, 'Application', FakeApp)
        monkeypatch.setattr(_window, 'MainWindow', FakeWindow)
        result = CliRunner().invoke(app_main.app, ['viewer'])
        assert result.exit_code == 7 and shown == [True]


class TestApplicationRun:
    @pytest.fixture
    def run_env(self, monkeypatch):
        state = types.SimpleNamespace(plugins=[], window=None, updates=[], exec_code=3)

        class FakeWindow:
            def __init__(self, app_name):
                state.window = self

            def _on_update_check_result(self, *args):
                state.updates.append(args)

        class FakeApp:
            def exec_(self):
                return state.exec_code

        monkeypatch.setattr(_app.deda.log, 'initialize', lambda loglevel: None)
        monkeypatch.setattr(_app.deda.core, 'initialize', lambda: None)
        monkeypatch.setattr(_app, 'Application', FakeApp)
        monkeypatch.setattr(_app, 'MainWindow', FakeWindow)
        monkeypatch.setattr(_app.deda.core.PluginRegistry, '__iter__', lambda self: iter(state.plugins))
        monkeypatch.setattr(_app, 'is_dev_mode', lambda: True)
        return state

    def plugin(self, error=None, name='p'):
        def load():
            if error:
                raise error

        return types.SimpleNamespace(name=name, load=load)

    def test_plugin_load_failures_do_not_stop_the_app(self, run_env, caplog):
        run_env.plugins = [self.plugin(ImportError('x'), 'a'), self.plugin(RuntimeError('y'), 'b'), self.plugin()]
        with caplog.at_level('ERROR'):
            assert _app.run() == 3
        assert 'Failed to load plugin a' in caplog.text and 'Unexpected error loading plugin b' in caplog.text

    def test_installed_builds_check_for_updates_in_a_thread(self, run_env, monkeypatch, qapp):
        monkeypatch.setattr(_app, 'is_dev_mode', lambda: False)
        started = []
        monkeypatch.setattr(_app.QtCore.QThread, 'start', lambda self, *a: started.append(self))
        assert _app.run() == 3
        assert len(started) == 1 and run_env.window._update_check_worker is not None


class TestUpdateWorker:
    def test_result_is_emitted(self, qapp, monkeypatch):
        worker = _app._UpdateCheckWorker()
        seen = []
        worker.result.connect(lambda available, latest: seen.append((available, latest)))
        monkeypatch.setattr(_app, 'check_for_updates', lambda: (True, '2.0'))
        worker.run()
        assert seen == [(True, '2.0')]

    def test_failures_report_no_update(self, qapp, monkeypatch):
        worker = _app._UpdateCheckWorker()
        seen = []
        worker.result.connect(lambda available, latest: seen.append((available, latest)))

        def boom():
            raise RuntimeError('offline')

        monkeypatch.setattr(_app, 'check_for_updates', boom)
        worker.run()
        assert seen == [(False, None)]

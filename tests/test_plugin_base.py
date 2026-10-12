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
"""Tests for plugin discovery, the abstract plugin interfaces and update checking."""
import sys
import types

import pytest
import requests

from deda.core import _check_for_updates as updates
from deda.core import _plugin


class FakeLoader:
    """Mimics a pkgutil module finder entry: find_spec(...) -> spec whose loader loads the module."""

    path = 'fake/path'

    def __init__(self, behaviour):
        self.behaviour = behaviour

    def find_spec(self, name, path):
        if self.behaviour == 'nospec':
            return None
        if self.behaviour == 'noloader':
            return types.SimpleNamespace(loader=None)
        behaviour = self.behaviour

        class ModuleLoader:
            def load_module(self, module_name):
                if behaviour == 'import_error':
                    raise ImportError('missing dependency')
                if behaviour == 'boom':
                    raise RuntimeError('plugin exploded')
                return types.ModuleType(module_name)

        return types.SimpleNamespace(loader=ModuleLoader())


class TestInitializePlugins:
    @pytest.fixture
    def walk(self, monkeypatch):
        entries = []
        monkeypatch.setattr(_plugin.pkgutil, 'walk_packages', lambda paths: iter(entries))
        monkeypatch.delenv('DEDAVERSE_PLUGIN_DIRS', raising=False)
        yield entries
        for name in ('good_plugin', 'dup_plugin'):
            sys.modules.pop(f'deda.plugins.{name}', None)
            sys.modules.pop(f'dedaverse.plugins.{name}', None)

    def test_a_good_plugin_is_registered_under_both_namespaces(self, walk):
        walk.append((FakeLoader('ok'), 'good_plugin', True))
        _plugin.initialize_plugins()
        assert sys.modules['deda.plugins.good_plugin'] is sys.modules['dedaverse.plugins.good_plugin']

    def test_extra_directories_come_from_the_environment(self, walk, monkeypatch, tmp_path):
        seen = []
        monkeypatch.setenv('DEDAVERSE_PLUGIN_DIRS', str(tmp_path))
        monkeypatch.setattr(_plugin.pkgutil, 'walk_packages', lambda paths: seen.extend(paths) or iter([]))
        _plugin.initialize_plugins()
        assert seen[-1] == str(tmp_path) and seen[0].endswith('plugins')

    def test_already_loaded_plugins_are_skipped(self, walk, caplog):
        sys.modules['deda.plugins.dup_plugin'] = types.ModuleType('dup')
        walk.append((FakeLoader('ok'), 'dup_plugin', True))
        with caplog.at_level('WARNING'):
            _plugin.initialize_plugins()
        assert 'already loaded' in caplog.text

    @pytest.mark.parametrize('behaviour', ['nospec', 'noloader', 'import_error', 'boom'])
    def test_broken_plugins_are_logged_not_raised(self, walk, behaviour):
        walk.append((FakeLoader(behaviour), 'good_plugin', True))
        _plugin.initialize_plugins()
        assert 'deda.plugins.good_plugin' not in sys.modules


class TestPluginClasses:
    def test_plugin_properties_and_abstract_load(self):
        plugin = _plugin.Plugin('p', version='1.2.3', vendor='v', description=None, image='i.png')
        assert (plugin.name, plugin.vendor, plugin.image, plugin.description) == ('p', 'v', 'i.png', '')
        assert str(plugin.version) == '1.2.3' and plugin.loaded is False
        with pytest.raises(NotImplementedError):
            plugin.load()

    def test_registry_registers_gets_and_filters_by_type(self):
        registry = _plugin.PluginRegistry()
        tool = _plugin.Tool('zz-tool')
        service = _plugin.Service('zz-service', url='u')
        registry.register(tool)
        registry.register(service)
        try:
            assert registry.get('zz-tool') is tool and registry.get('nope') is None
            assert tool in list(registry) and service in list(registry)
            assert tool in list(registry.iter_plugins(_plugin.Tool))
            assert service not in list(registry.iter_plugins(_plugin.Tool))
        finally:
            _plugin.PluginRegistry._registry_.pop('zz-tool')
            _plugin.PluginRegistry._registry_.pop('zz-service')

    def test_abstract_interfaces_raise(self):
        fm = _plugin.FileManager('fm')
        calls = [
            lambda: fm.can_handle([]), lambda: fm.add([]), lambda: fm.rename('a', 'b'), lambda: fm.delete([]),
            lambda: fm.get_latest([]), lambda: fm.get_version('a', 1), lambda: fm.checkout([]),
            lambda: fm.commit([], 'm'),
            lambda: _plugin.NotificationSystem('n').notify('t', 'm'),
            lambda: _plugin.TaskManager('t').get_task({}), lambda: _plugin.TaskManager('t').update_task(None),
            lambda: _plugin.Tool('t').initialize_window(None),
            lambda: _plugin.Application('a').find(),
        ]
        for call in calls:
            with pytest.raises(NotImplementedError):
                call()

    def test_application_executable_and_default_env(self):
        app = _plugin.Application('a')
        app.set_executable('C:/bin/a.exe')
        with pytest.raises(TypeError):
            app.set_executable(5)
        assert app.setup_env({'A': '1'}) == {'A': '1'}

    def test_application_launch_passes_args_and_env(self, monkeypatch):
        captured = {}

        def run(cmd, capture_output, env):
            captured.update(cmd=cmd, env=env)
            return 'done'

        monkeypatch.setattr(_plugin.subprocess, 'run', run)
        app = _plugin.Application('a', executable='C:/bin/a.exe')
        assert app.launch('-x', 3, mode='fast') == 'done'
        assert captured['cmd'] == ['C:/bin/a.exe', '-x', '3', 'mode=fast']
        assert isinstance(captured['env'], dict)


class TestToolLaunch:
    class FakeWindow:
        def __init__(self):
            self.calls = []

        def show(self):
            self.calls.append('show')

        def raise_(self):
            self.calls.append('raise')

        def activateWindow(self):
            self.calls.append('activate')

    def test_launch_builds_the_window_once_then_shows_it(self, monkeypatch):
        import deda.app
        monkeypatch.setattr(deda.app, 'get_top_window', lambda: 'top', raising=False)
        window = self.FakeWindow()
        built = []

        class MyTool(_plugin.Tool):
            def initialize_window(self, parent):
                built.append(parent)
                return window

        tool = MyTool('t')
        tool.launch()
        tool.launch()
        assert built == ['top'] and window.calls == ['show', 'raise', 'activate'] * 2

    def test_launch_without_a_window_logs_an_error(self, monkeypatch, caplog):
        import deda.app
        monkeypatch.setattr(deda.app, 'get_top_window', lambda: None, raising=False)

        class Empty(_plugin.Tool):
            def initialize_window(self, parent):
                return None

        with caplog.at_level('ERROR'):
            Empty('empty').launch()
        assert 'did not return a window' in caplog.text


class TestUpdateCheck:
    def test_installed_version_and_dev_mode(self, monkeypatch):
        monkeypatch.setattr(updates, 'get_package_version', lambda name: '1.0.0')
        assert updates.get_installed_version() == '1.0.0' and not updates.is_dev_mode()

        def missing(name):
            raise updates.PackageNotFoundError(name)

        monkeypatch.setattr(updates, 'get_package_version', missing)
        assert updates.get_installed_version() is None and updates.is_dev_mode()

    @pytest.fixture
    def release(self, monkeypatch):
        def respond(tag='v2.0.0', status=200, error=None):
            class Response:
                status_code = status

                def raise_for_status(self):
                    if status >= 400:
                        raise requests.HTTPError('bad')

                def json(self):
                    return {'tag_name': tag}

            def get(url, timeout):
                if error:
                    raise error
                respond.url = url
                return Response()

            monkeypatch.setattr(updates.requests, 'get', get)
        return respond

    def test_latest_release_variants(self, release, monkeypatch):
        monkeypatch.delenv('DEDAVERSE_GITHUB_API_ROOT_URL', raising=False)
        monkeypatch.delenv('DEDAVERSE_GITUB_API_ROOT_URL', raising=False)
        release('v2.1.0')
        assert str(updates.get_latest_release_name('o', 'r')) == '2.1.0'
        assert release.url == 'https://api.github.com/repos/o/r/releases/latest'
        release(status=404)
        assert updates.get_latest_release_name('o', 'r') is None
        release(status=500)
        assert updates.get_latest_release_name('o', 'r') is None
        release(tag='not a version')
        assert updates.get_latest_release_name('o', 'r') is None
        release(error=requests.ConnectionError('offline'))
        assert updates.get_latest_release_name('o', 'r') is None

    def test_enterprise_root_without_a_scheme_gets_https(self, release, monkeypatch):
        monkeypatch.setenv('DEDAVERSE_GITHUB_API_ROOT_URL', 'ghe.example.com/api/v3/')
        release('1.0.0')
        updates.get_latest_release_name('o', 'r')
        assert release.url == 'https://ghe.example.com/api/v3/repos/o/r/releases/latest'

    def test_check_for_updates_paths(self, monkeypatch):
        monkeypatch.setattr(updates, 'get_installed_version', lambda: None)
        assert updates.check_for_updates() == (False, None)
        monkeypatch.setattr(updates, 'get_installed_version', lambda: 'garbage')
        monkeypatch.setattr(updates, 'is_dev_mode', lambda: False)
        assert updates.check_for_updates() == (False, None)
        monkeypatch.setattr(updates, 'get_installed_version', lambda: '1.0.0')
        monkeypatch.setattr(updates, 'get_latest_release_name', lambda o, r: None)
        assert updates.check_for_updates() == (False, None)
        monkeypatch.setattr(updates, 'get_latest_release_name', lambda o, r: updates.Version('1.0.0'))
        assert updates.check_for_updates() == (False, None)
        monkeypatch.setattr(updates, 'get_latest_release_name', lambda o, r: updates.Version('1.2.0'))
        assert updates.check_for_updates() == (True, '1.2.0')

    def test_check_with_no_installed_version_string(self, monkeypatch):
        monkeypatch.setattr(updates, 'is_dev_mode', lambda: False)
        monkeypatch.setattr(updates, 'get_installed_version', lambda: '')
        assert updates.check_for_updates() == (False, None)

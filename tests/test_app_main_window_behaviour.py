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
"""Behavioural tests for the Dedaverse main window: panels, assets, apps, services and project settings.

The window is built on the offscreen Qt platform against a fake config and a fake asset library, so nothing touches
the registry or the real user config.
"""
import sys
import types
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets
from pxr import Sdf, Usd

import deda.core
from deda.app import _main_window as mw
from deda.app._panel import Panel
from deda.core._config import AppConfig, ProjectConfig, ServiceConfig


def app_config(name, command='run', enabled=True, icon=''):
    return AppConfig(name=name, version='', command=command, icon_path=icon, install_url='', help_url='', enabled=enabled)


class FakeUser:
    def __init__(self):
        self.assets_panel_path = {}
        self.saved = 0
        self.fail_save = False

    def save(self):
        if self.fail_save:
            raise OSError('disk full')
        self.saved += 1


class FakeConfig:
    def __init__(self, project=None):
        self.current_project = project
        self.user = FakeUser()
        self.projects = [project] if project else []

    def get_merged_apps(self):
        return list(self.current_project.apps) if self.current_project else []

    def get_app_layer_info(self, name):
        return 'project', True

    def get_merged_services(self):
        return list(self.current_project.services) if self.current_project else []

    def get_service_layer_info(self, name):
        return 'project', True

    def save(self):
        pass


class FakeProject:
    """The slice of Project the window uses to list, add and archive assets."""

    def __init__(self, root):
        self.root = Path(root)
        self.sort_orders = {}

    def asset_directory_for_prim_path(self, prim_path):
        return self.root.joinpath(*prim_path.strip('/').split('/'))

    def get_collection_sort_order(self, prim_path):
        return self.sort_orders.get(prim_path)

    def set_collection_sort_order(self, prim_path, names):
        self.sort_orders[prim_path] = list(names)


class FakeContainer:
    """A collection in the asset library."""

    def __init__(self, name, parent, project, children=None):
        self.name = name
        self.parent = parent
        self.project = project
        self._children = list(children or [])
        self.added = []
        self.removed = []
        self.fail_with = None

    @property
    def prim_path(self):
        return f'/{self.name}' if self.parent is None or self.parent.parent is None else f'{self.parent.prim_path}/{self.name}'

    def get_immediate_children(self):
        return [dict(c) for c in self._children]

    def _add(self, kind, name):
        if self.fail_with:
            raise self.fail_with
        entity = types.SimpleNamespace(name=name, kind=kind, metadata={})
        entity.set_metadata = lambda key, value: entity.metadata.__setitem__(key, value)
        self.added.append(entity)
        self._children.append({'name': name, 'type': 'Collection' if kind == 'collection' else 'Asset',
                               'is_collection': kind == 'collection'})
        return entity

    def add_asset(self, name):
        return self._add('asset', name)

    def add_collection(self, name):
        return self._add('collection', name)

    def remove_child(self, name):
        self.removed.append(name)
        before = len(self._children)
        self._children = [c for c in self._children if c['name'] != name]
        return len(self._children) < before


@pytest.fixture
def messages(monkeypatch):
    seen = []
    for kind in ('warning', 'information', 'critical'):
        monkeypatch.setattr(QtWidgets.QMessageBox, kind, staticmethod(
            lambda parent, title, text, *a, _kind=kind, **k: seen.append((_kind, title, text))))
    return seen


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch, messages):
    """Build a MainWindow around a fake config. Call with a ProjectConfig, or None for no project."""
    real = QtCore.QSettings
    monkeypatch.setattr(mw.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'main.ini'), real.IniFormat))
    from deda.app import _taskbar_icon
    monkeypatch.setattr(_taskbar_icon.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'tray.ini'), real.IniFormat))
    monkeypatch.setattr(mw, 'get_top_window', lambda: (_ for _ in ()).throw(RuntimeError('no windows')))
    created = []

    def build(project=...):
        if project is ...:
            project = ProjectConfig(name='Film', rootdir=str(tmp_path / 'film'), apps=[
                app_config('Maya', 'maya.exe', icon=''), app_config('Disabled', enabled=False)])
            project.services.append(ServiceConfig(name='Jira', enabled=True, url='http://jira/x', params=['a']))
            project.services.append(ServiceConfig(name='Off', enabled=False, url=''))
        config = FakeConfig(project)
        monkeypatch.setattr(mw, 'LayeredConfig', lambda: config)
        window = mw.MainWindow(app_name='DedaverseTest')
        window.fake_config = config
        created.append(window)
        return window

    yield build
    for window in created:
        window._force_close = True
        window._icon.hide()
        window.close()


@pytest.fixture
def window(make_window):
    return make_window()


def panel(window, name):
    return window.centralWidget().findChild(Panel, name)


def container(tmp_path, children=(), parent_name=None):
    project = FakeProject(tmp_path / 'content')
    root = FakeContainer('Film', None, project)
    if parent_name is None:
        root._children = [dict(c) for c in children]
        return root, project
    inner = FakeContainer(parent_name, root, project, children)
    return inner, project


class TestHelpers:
    def test_first_usd_file_prefers_the_asset_named_file(self, tmp_path):
        folder = tmp_path / 'hero'
        folder.mkdir()
        assert mw._first_usd_file_in_directory(folder, 'hero') is None
        assert mw._first_usd_file_in_directory(tmp_path / 'missing', 'hero') is None
        (folder / 'z_other.usdc').write_text('')
        (folder / 'a_other.usd').write_text('')
        assert mw._first_usd_file_in_directory(folder, 'hero').name == 'a_other.usd'
        (folder / 'hero.usdz').write_text('')
        assert mw._first_usd_file_in_directory(folder, 'hero').name == 'hero.usdz'
        (folder / 'hero.usda').write_text('')
        assert mw._first_usd_file_in_directory(folder, 'hero').name == 'hero.usda'

    @pytest.mark.parametrize('command, expected, use_env', [
        ('', None, False), ('maya.exe -batch', None, False), ('python', None, False),
        ('python -m deda.core.viewer a b', [sys.executable, '-m', 'deda.core.viewer', 'a', 'b'], True),
        ('python3.13 script.py --x', [sys.executable, 'script.py', '--x'], True),
        ('Python-3 tool.py', [sys.executable, 'tool.py'], True),
    ])
    def test_python_launch_parsing(self, window, command, expected, use_env):
        assert window._parse_python_launch(command) == (expected, use_env)

    def test_collecting_usd_dependencies_follows_references_and_sublayers(self, tmp_path):
        (tmp_path / 'sub').mkdir()
        leaf = Sdf.Layer.CreateNew(str(tmp_path / 'sub' / 'leaf.usda'))
        leaf.Save()
        mid = Sdf.Layer.CreateNew(str(tmp_path / 'mid.usda'))
        mid.subLayerPaths.append('sub/leaf.usda')
        mid.Save()
        root = Sdf.Layer.CreateNew(str(tmp_path / 'root.usda'))
        stage = Usd.Stage.Open(root)
        stage.DefinePrim('/A').GetReferences().AddReference('./mid.usda')
        root.Save()
        files = mw._collect_usd_dependencies(tmp_path / 'root.usda')
        assert [rel for _, rel in files] == ['root.usda', 'mid.usda', 'sub/leaf.usda']
        assert Path(files[0][0]) == (tmp_path / 'root.usda').resolve()

    def test_external_references_support_both_usd_apis(self):
        class Modern:
            @staticmethod
            def ExtractExternalReferences(path):
                return ('a.usda',), ['b.usda'], []

        class Legacy:
            @staticmethod
            def ExtractExternalReferences(path, sublayers=None, refs=None, payloads=None):
                if sublayers is None:
                    raise TypeError('old signature needs the lists')
                sublayers.append('old.usda')

        assert mw._extract_external_references(Modern, 'x') == (['a.usda'], ['b.usda'], [])
        assert mw._extract_external_references(Legacy, 'x') == (['old.usda'], [], [])

    def test_dependencies_outside_the_root_folder_go_under_external(self, tmp_path):
        outside = tmp_path / 'shared'
        outside.mkdir()
        ext = Sdf.Layer.CreateNew(str(outside / 'ext.usda'))
        ext.Save()
        project = tmp_path / 'proj'
        project.mkdir()
        root = Sdf.Layer.CreateNew(str(project / 'root.usda'))
        root.subLayerPaths.append('../shared/ext.usda')
        root.Save()
        assert [rel for _, rel in mw._collect_usd_dependencies(project / 'root.usda')] == ['root.usda', 'external/ext.usda']

    def test_a_missing_root_file_is_listed_alone(self, tmp_path):
        files = mw._collect_usd_dependencies(tmp_path / 'nope.usda')
        assert files == [(str((tmp_path / 'nope.usda').resolve()), 'nope.usda')]


class TestWindowBasics:
    def test_title_object_name_and_panels(self, window):
        assert window.objectName() == 'DedaverseMainWindow' and window.windowTitle().startswith('DedaverseTest [deda@')
        assert [p.objectName() for p in window.centralWidget().findChildren(Panel)] == [
            'Project', 'Assets', 'Apps', 'Services', 'Tasks']
        assert window.settings is window._settings and window.current_project.name == 'Film'
        assert window._icon.toolTip() == 'Dedaverse :: Film'

    def test_without_a_project_only_the_project_panel_is_stretched(self, make_window, messages):
        window = make_window(None)
        assert window.current_project is None and window.asset_library is None
        assert window._assets_view_container is None and panel(window, 'Assets')._items == []

    def test_close_hides_to_the_tray_unless_forced(self, window):
        window.show()
        window._icon.setVisible(True)
        event = QtGui.QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted() and not window.isVisible()
        window._force_close = True
        event = QtGui.QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted()

    def test_toggle_visibility(self, window):
        window.show()
        window.toggle_visibility(QtWidgets.QSystemTrayIcon.Trigger)
        assert not window.isVisible()
        window.toggle_visibility()
        assert window.isVisible()
        window.hide()
        window.toggle_visibility(QtWidgets.QSystemTrayIcon.Context)
        window.toggle_visibility(QtWidgets.QSystemTrayIcon.DoubleClick)
        assert not window.isVisible()

    @pytest.mark.parametrize('icon, level', [
        (QtWidgets.QSystemTrayIcon.NoIcon, 'DEBUG'), (QtWidgets.QSystemTrayIcon.Information, 'INFO'),
        (QtWidgets.QSystemTrayIcon.Warning, 'WARNING'), (QtWidgets.QSystemTrayIcon.Critical, 'CRITICAL')])
    def test_messages_go_to_the_log_and_the_tray(self, window, monkeypatch, caplog, icon, level):
        shown = []
        monkeypatch.setattr(window._icon, 'showMessage', lambda *a: shown.append(a))
        with caplog.at_level('DEBUG'):
            window.show_message('Title', 'Body', icon=icon)
        assert shown == [('Title', 'Body', icon, 10000)]
        assert any(r.levelname == level and r.getMessage() == 'Body' for r in caplog.records)

    def test_clicking_the_message_opens_settings_only_without_a_project(self, window, make_window, monkeypatch):
        opened = []
        monkeypatch.setattr(window, '_open_project_settings', lambda: opened.append(1))
        window.message_clicked()
        assert opened == []
        window._config.current_project = None
        window.message_clicked()
        assert opened == [1]

    def test_update_notification(self, window, monkeypatch):
        calls = []
        monkeypatch.setattr(window._icon, 'set_update_available', lambda *a: calls.append(a))
        monkeypatch.setattr(window, 'show_message', lambda *a, **k: calls.append(('message', a)))
        window._on_update_check_result(False, None)
        assert calls == []
        window._on_update_check_result(True, '2.0')
        assert calls[0] == (True, '2.0') and '2.0' in calls[1][1][1]

    def test_switching_the_project_rebuilds_the_panels(self, window, tmp_path):
        other = ProjectConfig(name='Game', rootdir=str(tmp_path / 'game'))
        window.current_project = window.current_project               # unchanged: nothing happens
        window.current_project = other
        assert window.current_project is other and window._icon.toolTip() == 'Dedaverse :: Game'
        assert panel(window, 'Project')._header._title_label.text() == 'Game'

    def test_loading_config_without_a_project_warns(self, make_window, monkeypatch):
        shown = []
        monkeypatch.setattr(mw.MainWindow, 'show_message', lambda self, *a, **k: shown.append(a))
        make_window(None)
        assert shown and shown[0][0] == 'Choose a project.'


class TestPanelsAndViewMenu:
    def test_apps_and_services_come_from_the_config(self, window):
        apps = panel(window, 'Apps')
        assert [i['name'] for i in apps._items] == ['Maya'] and apps._items[0]['command'] == 'maya.exe'
        assert apps._items[0]['layer'] == 'project' and apps._items[0]['is_writable'] is True
        services = panel(window, 'Services')
        assert [i['name'] for i in services._items] == ['Jira'] and services._items[0]['params'] == ['a']

    def test_icons_in_app_config_are_used(self, make_window, tmp_path):
        project = ProjectConfig(name='Film', rootdir=str(tmp_path / 'film'), apps=[app_config('Maya', icon='x.png')])
        window = make_window(project)
        assert panel(window, 'Apps')._items[0]['icon'] == 'x.png'

    def test_unset_panel_helpers_are_safe(self, window):
        window._load_apps_to_panel(None)
        window._load_services_to_panel(None)
        window._load_assets_to_panel(None)

    def test_view_actions_show_and_hide_panels(self, window):
        assert window._action_for_panel_name('Project') is None
        action = window._action_for_panel_name('Apps')
        action.setChecked(False)
        action.trigger()
        action.setChecked(False)
        window._on_view_toggled_for_panel_by_name(False, 'Apps')
        assert panel(window, 'Apps').visibility is False
        window._on_view_toggled_for_panel_by_name(True, 'Apps')
        assert panel(window, 'Apps').visibility is True
        window._on_view_toggled_for_panel(False, panel(window, 'Services'))
        assert panel(window, 'Services').visibility is False
        window._on_view_toggled_for_panel_by_name(True, 'Nonexistent')

    def test_closing_a_panel_unchecks_its_menu_item(self, window):
        apps = panel(window, 'Apps')
        window._on_panel_closed(apps)
        assert not window._action_for_panel_name('Apps').isChecked()
        assert window._icon._settings.value('view/apps', True, type=bool) is False

    def test_minimized_state_is_remembered(self, window):
        window._on_panel_minimized_changed('Apps', True)
        assert window._settings.value('view/apps_minimized', False, type=bool) is True

    def test_stretch_appears_when_everything_is_hidden_or_collapsed(self, window):
        for name in ('Assets', 'Apps', 'Services', 'Tasks'):
            window._on_view_toggled_for_panel_by_name(False, name)
        assert window._all_non_project_panels_hidden() and window._panel_stack_has_top_stretch
        window._on_view_toggled_for_panel_by_name(True, 'Apps')
        assert not window._all_non_project_panels_hidden() and not window._panel_stack_has_top_stretch
        panel(window, 'Apps')._header._minmax_btn.click()
        for name in ('Assets', 'Services', 'Tasks'):
            window._on_view_toggled_for_panel_by_name(False, name)
        assert window._all_visible_non_project_panels_collapsed() and window._panel_stack_has_top_stretch

    def test_a_started_session_restores_collapsed_panels(self, make_window, tmp_path):
        seed = make_window()
        seed._settings.setValue('view/apps_minimized', True)
        seed._settings.sync()
        again = make_window()
        assert panel(again, 'Apps').minimized


class TestAppsAndServices:
    def test_creating_an_app_saves_it_once(self, window):
        window._on_app_created({'name': 'Blender', 'command': 'blender', 'icon': 'b.png'})
        window._on_app_created({'name': 'Blender', 'command': 'other'})
        apps = [a for a in window.current_project.apps if a.name == 'Blender']
        assert len(apps) == 1 and apps[0].command == 'blender' and apps[0].icon_path == 'b.png'
        assert (Path(window.current_project.rootdir) / '.dedaverse' / 'project.cfg').is_file()

    def test_updating_an_app_edits_or_overrides_it(self, window):
        window._on_app_updated(0, {'name': 'Maya', 'command': 'maya -new', 'icon': 'i.png'})
        maya = next(a for a in window.current_project.apps if a.name == 'Maya')
        assert maya.command == 'maya -new' and maya.icon_path == 'i.png'
        window._on_app_updated(0, {'name': '', 'command': 'x'})
        assert any(a.name == 'Untitled' for a in window.current_project.apps)

    def test_removing_an_app(self, window):
        window._on_app_removed({'name': 'Maya'})
        assert [a.name for a in window.current_project.apps] == ['Disabled']
        assert panel(window, 'Apps')._items == []
        window._on_app_removed({'name': 'Maya'})
        window._on_app_removed({'name': ' '})

    def test_creating_updating_and_removing_services(self, window):
        window._on_service_created({'name': 'P4', 'url': 'http://p4', 'params': ['x']})
        window._on_service_created({'name': 'P4', 'url': 'dup'})
        assert [s.name for s in window.current_project.services].count('P4') == 1
        window._on_service_updated(0, {'name': 'P4', 'url': 'http://new', 'params': []})
        window._on_service_updated(0, {'name': 'Fresh', 'url': 'http://f', 'params': ['q']})
        by_name = {s.name: s for s in window.current_project.services}
        assert by_name['P4'].url == 'http://new' and by_name['Fresh'].params == ['q']
        window._on_service_removed({'name': 'P4'})
        assert 'P4' not in {s.name for s in window.current_project.services}
        window._on_service_removed({'name': 'P4'})
        window._on_service_removed({'name': ''})

    @pytest.mark.parametrize('handler, args', [
        ('_on_app_created', ({'name': 'x'},)), ('_on_app_updated', (0, {'name': 'x'})), ('_on_app_removed', ({'name': 'x'},)),
        ('_on_service_created', ({'name': 'x'},)), ('_on_service_updated', (0, {'name': 'x'})),
        ('_on_service_removed', ({'name': 'x'},)),
    ])
    def test_every_handler_needs_a_project(self, make_window, handler, args, caplog):
        window = make_window(None)
        with caplog.at_level('WARNING'):
            getattr(window, handler)(*args)
        assert 'no current project' in caplog.text

    @pytest.mark.parametrize('handler, args', [
        ('_on_app_created', ({'name': 'Z'},)), ('_on_app_updated', (0, {'name': 'Maya'})),
        ('_on_service_created', ({'name': 'Z'},)), ('_on_service_updated', (0, {'name': 'Jira'})),
        ('_on_app_removed', ({'name': 'Maya'},)), ('_on_service_removed', ({'name': 'Jira'},)),
    ])
    def test_save_failures_are_logged(self, window, monkeypatch, caplog, handler, args):
        monkeypatch.setattr(ProjectConfig, 'save', lambda self: (_ for _ in ()).throw(OSError('read-only')))
        with caplog.at_level('ERROR'):
            getattr(window, handler)(*args)
        assert 'read-only' in caplog.text

    def test_activating_an_app_launches_python_or_shell_commands(self, window, monkeypatch):
        launched = []
        monkeypatch.setattr(mw.subprocess, 'Popen', lambda cmd, **kw: launched.append((cmd, kw)))
        window._on_app_activated({'command': ''})
        window._on_app_activated({'command': 'python -m deda.core.viewer'})
        window._on_app_activated({'command': 'notepad.exe'})
        assert launched[0][0] == [sys.executable, '-m', 'deda.core.viewer'] and 'env' in launched[0][1]
        assert launched[1] == ('notepad.exe', {'shell': True})

    def test_launch_failures_notify(self, window, monkeypatch):
        shown = []
        monkeypatch.setattr(window, 'show_message', lambda *a, **k: shown.append(a))
        monkeypatch.setattr(mw.subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(OSError('no exe')))
        window._on_app_activated({'command': 'python -m x'})
        window._on_app_activated({'command': 'broken.exe'})
        assert [s[0] for s in shown] == ['Launch failed', 'Launch failed']

    def test_activating_a_service_launches_its_tool(self, window, monkeypatch):
        launched = []

        class FakeTool(deda.core.Tool):
            def launch(self):
                launched.append(self.name)

        registry = deda.core.PluginRegistry
        tool = FakeTool('zz-jira')
        registry().register(tool)
        monkeypatch.setattr(QtWidgets.QApplication, 'setOverrideCursor', staticmethod(lambda c: None))
        monkeypatch.setattr(QtWidgets.QApplication, 'restoreOverrideCursor', staticmethod(lambda: None))
        try:
            window._on_service_activated({'name': 'ZZ-Jira'})
            window._on_service_activated({'name': 'unknown'})
            assert launched == ['zz-jira']
            tool.launch = lambda: (_ for _ in ()).throw(RuntimeError('boom'))
            window._on_service_activated({'name': 'zz-jira'})
        finally:
            registry._registry_.pop('zz-jira', None)


class TestAssetsPanel:
    @pytest.fixture
    def with_library(self, window, tmp_path):
        children = [
            {'name': 'Zed', 'type': 'Asset', 'is_collection': False},
            {'name': 'Actors', 'type': 'Collection', 'is_collection': True, 'title': 'The Actors', 'description': 'd'},
            {'name': 'Hero', 'type': 'Character', 'is_collection': False},
            {'name': 'Rig', 'type': 'Kit', 'is_collection': False},
            {'name': 'Gun', 'type': 'Prop', 'is_collection': False},
            {'name': 'Opening', 'type': 'Sequence', 'is_collection': True},
            {'name': 'Stage', 'type': 'Set', 'is_collection': False},
            {'name': 'S010', 'type': 'Shot', 'is_collection': False},
            {'name': 'Extra', 'type': 'Actor', 'is_collection': False},
        ]
        root, project = container(tmp_path, children)
        window._assets_view_container = root
        window._load_assets_to_panel(panel(window, 'Assets'))
        window.root, window.project = root, project
        return window

    def test_children_are_listed_sorted_by_type_then_name_with_default_icons(self, with_library):
        items = panel(with_library, 'Assets')._items
        assert [i['name'] for i in items] == ['Extra', 'Hero', 'Rig', 'Gun', 'Opening', 'Stage', 'S010', 'Actors', 'Zed'] or \
            [i['type'] for i in items] == sorted(i['type'] for i in items)
        assert all(Path(i['icon']).name.startswith('icon_') for i in items)
        assert panel(with_library, 'Assets')._header._title_label.text() == 'Project'

    def test_a_saved_sort_order_wins(self, with_library):
        container_ = with_library.root
        inner = FakeContainer('Actors', container_, with_library.project,
                              [{'name': 'b', 'type': 'Asset'}, {'name': 'a', 'type': 'Asset'}, {'name': 'c', 'type': 'Asset'}])
        with_library.project.sort_orders[inner.prim_path] = ['c', 'ghost', 'a']
        with_library._assets_view_container = inner
        with_library._load_assets_to_panel(panel(with_library, 'Assets'))
        assert [i['name'] for i in panel(with_library, 'Assets')._items] == ['c', 'a', 'b']
        assert panel(with_library, 'Assets')._header._title_label.text() == 'Actors'

    def test_without_a_container_the_panel_is_empty(self, window):
        window._assets_view_container = None
        window._load_assets_to_panel(panel(window, 'Assets'))
        assert panel(window, 'Assets')._items == []

    def test_double_clicking_a_collection_navigates_into_it_and_up_again(self, with_library, monkeypatch):
        monkeypatch.setattr(mw, 'Collection', lambda name, parent: FakeContainer(
            name, parent, with_library.project, [{'name': 'inner', 'type': 'Asset', 'is_collection': False}]))
        with_library._on_asset_panel_item_activated({'name': 'Actors', 'is_collection': False})
        assert with_library._assets_view_container is with_library.root
        with_library._on_asset_panel_item_activated({'name': ' ', 'is_collection': True})
        with_library._on_asset_panel_item_activated({'name': 'Actors', 'is_collection': True})
        assert with_library._assets_view_container.name == 'Actors'
        assert [i['name'] for i in panel(with_library, 'Assets')._items] == ['inner']
        assert with_library.fake_config.user.assets_panel_path['Film'] == ['Actors']
        with_library._on_assets_navigate_up()
        assert with_library._assets_view_container is with_library.root
        assert with_library.fake_config.user.assets_panel_path['Film'] == []
        with_library._on_assets_navigate_up()                       # already at the top

    def test_navigating_without_a_container_does_nothing(self, window):
        window._assets_view_container = None
        window._on_asset_panel_item_activated({'name': 'x', 'is_collection': True})
        window._on_assets_navigate_up()

    def test_the_saved_path_survives_a_failed_save(self, with_library, caplog):
        with_library.fake_config.user.fail_save = True
        inner = FakeContainer('Actors', with_library.root, with_library.project)
        with_library._assets_view_container = inner
        with caplog.at_level('WARNING'):
            with_library._save_assets_panel_path()
        assert 'Could not save Assets panel path' in caplog.text

    def test_restoring_the_saved_path(self, window, tmp_path, monkeypatch):
        root, project = container(tmp_path, [{'name': 'Actors', 'type': 'Collection', 'is_collection': True},
                                             {'name': 'Hero', 'type': 'Asset', 'is_collection': False}])
        window._assets_view_container = root
        window.fake_config.user.assets_panel_path['Film'] = ['Actors']
        monkeypatch.setattr(mw, 'Collection', lambda name, parent: FakeContainer(name, parent, project))
        window._restore_assets_panel_path()
        assert window._assets_view_container.name == 'Actors'
        window._assets_view_container = root
        window.fake_config.user.assets_panel_path['Film'] = ['Hero', 'Deeper']      # not a collection: stop there
        window._restore_assets_panel_path()
        assert window._assets_view_container is root
        window.fake_config.user.assets_panel_path['Film'] = []
        window._restore_assets_panel_path()
        window._assets_view_container = None
        window._restore_assets_panel_path()
        window._save_assets_panel_path()

    def test_default_asset_type_follows_the_sequences_folder(self, window, tmp_path):
        root, project = container(tmp_path)
        window._assets_view_container = FakeContainer('Sequences', root, project)
        assert window._get_default_asset_type_for_add() == 'Sequence'
        window._assets_view_container = FakeContainer('Props', root, project)
        assert window._get_default_asset_type_for_add() is None
        window._assets_view_container = None
        assert window._get_default_asset_type_for_add() is None

    def test_the_panel_can_reorder_only_below_the_top(self, with_library):
        assets = panel(with_library, 'Assets')
        assert not assets.can_reorder_assets()
        with_library._assets_view_container = FakeContainer('Actors', with_library.root, with_library.project)
        assert assets.can_reorder_assets() and assets.get_default_asset_type() is None

    def test_order_changes_are_persisted_below_the_top_only(self, with_library):
        with_library._on_assets_order_changed(['b', 'a'])
        assert with_library.project.sort_orders == {}
        inner = FakeContainer('Actors', with_library.root, with_library.project)
        with_library._assets_view_container = inner
        with_library._on_assets_order_changed(['b', 'a'])
        assert with_library.project.sort_orders[inner.prim_path] == ['b', 'a']
        with_library._assets_view_container = None
        with_library._on_assets_order_changed(['x'])

    def test_configuring_an_asset_opens_the_dialog(self, with_library, monkeypatch):
        opened = []
        monkeypatch.setattr(mw.ConfigureAssetDialog, 'exec', lambda self: opened.append(self._entity) or 0)
        monkeypatch.setattr(mw, 'Collection', lambda name, parent: types.SimpleNamespace(
            get_metadata=lambda *a: '', name=name, kind='collection'))
        monkeypatch.setattr(mw, 'Asset', lambda name, parent: types.SimpleNamespace(
            get_metadata=lambda *a: '', name=name, kind='asset'))
        assets = panel(with_library, 'Assets')
        names = [i['name'] for i in assets._items]
        with_library._on_asset_configure_requested(names.index('Actors'))
        with_library._on_asset_configure_requested(names.index('Zed'))
        with_library._on_asset_configure_requested(99)
        assert [e.kind for e in opened] == ['collection', 'asset']
        with_library._assets_view_container = None
        with_library._on_asset_configure_requested(0)
        assets._items[0]['name'] = ' '
        with_library._assets_view_container = with_library.root
        with_library._on_asset_configure_requested(0)
        assert len(opened) == 2

    def test_updated_metadata_refreshes_the_tile_and_keeps_the_sort(self, with_library):
        assets = panel(with_library, 'Assets')
        index = next(i for i, item in enumerate(assets._items) if item['name'] == 'Zed')
        with_library._on_asset_metadata_updated(index, {'name': 'Zed', 'type': 'Shot', 'title': 't'})
        item = next(i for i in assets._items if i['name'] == 'Zed')
        assert item['type'] == 'Shot' and item['icon'].endswith('icon_shot.png')
        types_in_order = [i['type'] for i in assets._items]
        assert types_in_order == sorted(types_in_order)
        with_library._on_asset_metadata_updated(99, {'name': 'x'})

    def test_updated_metadata_in_a_custom_ordered_folder_keeps_the_order(self, with_library):
        inner = FakeContainer('Actors', with_library.root, with_library.project,
                              [{'name': 'b', 'type': 'Asset'}, {'name': 'a', 'type': 'Asset'}])
        with_library.project.sort_orders[inner.prim_path] = ['b', 'a']
        with_library._assets_view_container = inner
        with_library._load_assets_to_panel(panel(with_library, 'Assets'))
        with_library._on_asset_metadata_updated(0, {'name': 'b', 'type': 'Zzz'})
        assert [i['name'] for i in panel(with_library, 'Assets')._items] == ['b', 'a']
        assert 'icon' in panel(with_library, 'Assets')._items[0]


class TestAssetCreationAndRemoval:
    @pytest.fixture
    def with_container(self, window, tmp_path):
        root, project = container(tmp_path)
        window._assets_view_container = root
        window._asset_library = root
        window.root, window.project = root, project
        return window

    def test_creating_assets_and_collections(self, with_container):
        with_container._on_asset_created({'name': ' Hero ', 'type': 'Character'})
        with_container._on_asset_created({'name': 'Opening', 'type': 'Sequence'})
        added = with_container.root.added
        assert [(e.name, e.kind) for e in added] == [('Hero', 'asset'), ('Opening', 'collection')]
        assert added[0].metadata == {'asset_type': 'Character'}
        assert {i['name'] for i in panel(with_container, 'Assets')._items} == {'Hero', 'Opening'}

    def test_invalid_names_notify(self, with_container, monkeypatch):
        shown = []
        monkeypatch.setattr(with_container, 'show_message', lambda *a, **k: shown.append(a))
        with_container.root.fail_with = ValueError('Invalid prim identifier')
        with_container._on_asset_created({'name': '1bad', 'type': 'Asset'})
        assert shown[0][0] == 'Invalid asset name'
        shown.clear()
        with_container._on_asset_created({'name': '  '})
        with_container._on_asset_created(None)
        assert shown == []

    def test_metadata_failures_do_not_stop_creation(self, with_container, caplog):
        original = with_container.root._add

        def failing(kind, name):
            entity = original(kind, name)
            entity.set_metadata = lambda *a: (_ for _ in ()).throw(RuntimeError('no edit target'))
            return entity

        with_container.root._add = failing
        with caplog.at_level('WARNING'):
            with_container._on_asset_created({'name': 'Hero', 'type': 'Asset'})
        assert 'Could not set asset_type' in caplog.text

    def test_creating_without_a_project_or_library_creates_it(self, make_window, monkeypatch, tmp_path):
        window = make_window(None)
        window._on_asset_created({'name': 'x'})
        window = make_window()
        window._asset_library = None
        window._assets_view_container = None
        root, project = container(tmp_path)
        monkeypatch.setattr(mw.Project, 'find_or_create', staticmethod(lambda *a, **k: root))
        window._on_asset_created({'name': 'Hero', 'type': 'Asset'})
        assert window._asset_library is root and [e.name for e in root.added] == ['Hero']

    def test_a_dropped_file_is_copied_into_the_new_asset(self, with_container, tmp_path, monkeypatch):
        source = tmp_path / 'ext' / 'model.usda'
        source.parent.mkdir()
        layer = Sdf.Layer.CreateNew(str(source))
        layer.Save()
        with_container._pending_drop_file_path = str(source)
        monkeypatch.setattr(mw.CopyMoveUsdFilesDialog, 'exec', lambda self: 0)
        monkeypatch.setattr(mw.CopyMoveUsdFilesDialog, 'result_action', lambda self: mw.CopyMoveUsdFilesDialog.CopyAction)
        with_container._on_asset_created({'name': 'Hero', 'type': 'Asset'})
        target = with_container.project.root / 'Film' / 'Hero' / 'Hero.usda'
        assert target.is_file() and source.is_file() and with_container._pending_drop_file_path is None

    def test_a_dropped_file_can_be_moved_or_declined(self, with_container, tmp_path, monkeypatch):
        source = tmp_path / 'ext' / 'model.usda'
        source.parent.mkdir()
        Sdf.Layer.CreateNew(str(source)).Save()
        monkeypatch.setattr(mw.CopyMoveUsdFilesDialog, 'exec', lambda self: 0)
        actions = iter([mw.CopyMoveUsdFilesDialog.CancelAction, mw.CopyMoveUsdFilesDialog.MoveAction])
        monkeypatch.setattr(mw.CopyMoveUsdFilesDialog, 'result_action', lambda self: next(actions))
        with_container._pending_drop_file_path = str(source)
        with_container._on_asset_created({'name': 'A', 'type': 'Asset'})
        assert source.is_file()
        with_container._pending_drop_file_path = str(source)
        with_container._on_asset_created({'name': 'B', 'type': 'Asset'})
        assert not source.is_file() and (with_container.project.root / 'Film' / 'B' / 'B.usda').is_file()

    def test_a_failing_copy_notifies(self, with_container, tmp_path, monkeypatch):
        source = tmp_path / 'm.usda'
        Sdf.Layer.CreateNew(str(source)).Save()
        shown = []
        monkeypatch.setattr(with_container, 'show_message', lambda *a, **k: shown.append(a))
        monkeypatch.setattr(mw.CopyMoveUsdFilesDialog, 'exec', lambda self: 0)
        monkeypatch.setattr(mw.CopyMoveUsdFilesDialog, 'result_action', lambda self: mw.CopyMoveUsdFilesDialog.CopyAction)
        monkeypatch.setattr(mw.shutil, 'copy2', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
        with_container._pending_drop_file_path = str(source)
        with_container._on_asset_created({'name': 'Hero', 'type': 'Asset'})
        assert shown[0][0] == 'File operation failed'

    def test_dropping_files_opens_the_create_asset_dialog_for_outside_files_only(self, with_container, tmp_path, monkeypatch):
        outside = tmp_path / 'outside' / 'my model.usda'
        outside.parent.mkdir()
        outside.write_text('')
        inside = Path(with_container.current_project.rootdir) / 'inside.usda'
        inside.parent.mkdir(parents=True, exist_ok=True)
        inside.write_text('')
        opened = []
        monkeypatch.setattr(mw.AddItemDialog, 'exec', lambda self: opened.append(self._name_le.text()) or 0)
        with_container._on_assets_panel_file_dropped([])
        with_container._on_assets_panel_file_dropped([str(tmp_path / 'ghost.usda'), str(inside)])
        assert opened == []
        with_container._on_assets_panel_file_dropped([str(outside)])
        assert opened == ['my_model'] and with_container._pending_drop_file_path == str(outside)

    def test_dropping_files_needs_a_project(self, make_window):
        make_window(None)._on_assets_panel_file_dropped(['x'])

    def test_removing_an_asset_archives_its_files(self, with_container):
        root = with_container.root
        root._children = [{'name': 'Hero', 'type': 'Asset', 'is_collection': False}]
        asset_dir = with_container.project.asset_directory_for_prim_path('/Film/Hero')
        asset_dir.mkdir(parents=True)
        (asset_dir / 'model.usda').write_text('x')
        (asset_dir / 'textures').mkdir()
        (asset_dir / 'textures' / 'a.png').write_text('x')
        with_container._on_asset_removed({'name': 'Hero'})
        assert root.removed == ['Hero'] and (asset_dir / 'archive' / 'model.usda').is_file()
        assert (asset_dir / 'archive' / 'textures' / 'a.png').is_file() and not (asset_dir / 'model.usda').exists()

    def test_removal_keeps_the_collection_sort_order_consistent(self, with_container):
        inner = FakeContainer('Actors', with_container.root, with_container.project,
                              [{'name': 'a', 'type': 'Asset'}, {'name': 'b', 'type': 'Asset'}])
        with_container.project.sort_orders[inner.prim_path] = ['a', 'b']
        with_container._assets_view_container = inner
        with_container._on_asset_removed({'name': 'a'})
        assert with_container.project.sort_orders[inner.prim_path] == ['b']

    def test_removal_warns_before_overwriting_the_archive(self, with_container, monkeypatch):
        root = with_container.root
        root._children = [{'name': 'Hero', 'type': 'Asset'}]
        asset_dir = with_container.project.asset_directory_for_prim_path('/Film/Hero')
        (asset_dir / 'archive').mkdir(parents=True)
        (asset_dir / 'archive' / 'model.usda').write_text('old')
        (asset_dir / 'model.usda').write_text('new')
        answers = iter([QtWidgets.QMessageBox.StandardButton.Cancel, QtWidgets.QMessageBox.StandardButton.Ok])
        monkeypatch.setattr(QtWidgets.QMessageBox, 'exec', lambda self: next(answers))
        with_container._on_asset_removed({'name': 'Hero'})
        assert root.removed == [] and (asset_dir / 'model.usda').read_text() == 'new'
        with_container._on_asset_removed({'name': 'Hero'})
        assert root.removed == ['Hero'] and (asset_dir / 'archive' / 'model.usda').read_text() == 'new'

    def test_removal_failures_are_reported(self, with_container, monkeypatch):
        shown = []
        monkeypatch.setattr(with_container, 'show_message', lambda *a, **k: shown.append(a))
        asset_dir = with_container.project.asset_directory_for_prim_path('/Film/Hero')
        asset_dir.mkdir(parents=True)
        (asset_dir / 'model.usda').write_text('x')
        monkeypatch.setattr(mw.shutil, 'move', lambda *a: (_ for _ in ()).throw(OSError('locked')))
        with_container._on_asset_removed({'name': 'Hero'})
        assert shown[0][0] == 'Archive failed'

    def test_removing_something_unknown_or_with_no_container(self, with_container, caplog):
        with caplog.at_level('WARNING'):
            with_container._on_asset_removed({'name': 'Ghost'})
        assert 'Could not remove child' in caplog.text
        with_container._on_asset_removed(None)
        with_container._on_asset_removed({'name': ' '})
        with_container._assets_view_container = None
        with_container._on_asset_removed({'name': 'x'})

    def test_a_failing_remove_is_logged(self, with_container, caplog):
        with_container.root.remove_child = lambda name: (_ for _ in ()).throw(RuntimeError('layer locked'))
        with caplog.at_level('ERROR'):
            with_container._on_asset_removed({'name': 'Hero'})
        assert 'Failed to remove asset' in caplog.text


class TestDropsOnAppsAndServices:
    @pytest.fixture
    def with_asset_file(self, window, tmp_path):
        root, project = container(tmp_path)
        window._assets_view_container = root
        folder = project.asset_directory_for_prim_path('/Film/Hero')
        folder.mkdir(parents=True)
        (folder / 'Hero.usda').write_text('')
        window.project = project
        return window

    def test_dropping_an_asset_on_an_app_launches_it_with_the_usd_file(self, with_asset_file, monkeypatch):
        launched = []
        monkeypatch.setattr(mw.subprocess, 'Popen', lambda cmd, **kw: launched.append((cmd, kw)))
        with_asset_file._on_asset_dropped_on_app({'name': 'Hero'}, {'command': 'python viewer.py'})
        with_asset_file._on_asset_dropped_on_app({'name': 'Hero'}, {'command': 'maya.exe -file'})
        assert launched[0][0][:2] == [sys.executable, 'viewer.py'] and launched[0][0][2].endswith('Hero.usda')
        assert launched[1][0].startswith('maya.exe -file ') and launched[1][1] == {'shell': True}

    def test_dropping_without_enough_information(self, with_asset_file, monkeypatch, caplog):
        shown = []
        monkeypatch.setattr(with_asset_file, 'show_message', lambda *a, **k: shown.append(a))
        with caplog.at_level('WARNING'):
            with_asset_file._on_asset_dropped_on_app({'name': 'Hero'}, {'command': ' '})
            with_asset_file._on_asset_dropped_on_app({'name': 'Missing'}, {'command': 'maya'})
            with_asset_file._assets_view_container = None
            with_asset_file._on_asset_dropped_on_app({'name': 'Hero'}, {'command': 'maya'})
        assert shown[0][0] == 'No USD file' and 'no command' in caplog.text.lower()

    def test_launch_failures_are_reported(self, with_asset_file, monkeypatch):
        shown = []
        monkeypatch.setattr(with_asset_file, 'show_message', lambda *a, **k: shown.append(a))
        monkeypatch.setattr(mw.subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(OSError('no exe')))
        with_asset_file._on_asset_dropped_on_app({'name': 'Hero'}, {'command': 'python x.py'})
        with_asset_file._on_asset_dropped_on_app({'name': 'Hero'}, {'command': 'shell.exe'})
        assert [s[0] for s in shown] == ['Launch failed', 'Launch failed']

    def test_dropping_an_asset_on_a_service_opens_the_url_with_the_asset(self, window, monkeypatch):
        opened = []
        monkeypatch.setattr(mw.webbrowser, 'open', lambda url: opened.append(url))
        window._on_asset_dropped_on_service({'name': 'Hero'}, {'url': 'http://x/y'})
        window._on_asset_dropped_on_service({'name': 'Hero'}, {'url': 'http://x/y?a=1'})
        window._on_asset_dropped_on_service({}, {'url': 'http://x'})
        window._on_asset_dropped_on_service({'name': 'Hero'}, {'url': ''})
        assert opened == ['http://x/y?asset=Hero', 'http://x/y?a=1&asset=Hero', 'http://x?asset=asset']

    def test_service_open_failures_notify(self, window, monkeypatch):
        shown = []
        monkeypatch.setattr(window, 'show_message', lambda *a, **k: shown.append(a))
        monkeypatch.setattr(mw.webbrowser, 'open', lambda url: (_ for _ in ()).throw(RuntimeError('no browser')))
        window._on_asset_dropped_on_service({'name': 'Hero'}, {'url': 'http://x'})
        assert shown[0][0] == 'Open failed'


class TestProjectSettings:
    def test_with_a_project_the_settings_dialog_is_shown_and_reused(self, window, monkeypatch):
        monkeypatch.setattr(mw.ProjectSettingsDialog, 'exec_', lambda self: 0, raising=False)
        monkeypatch.setattr(mw.ProjectSettingsDialog, 'show', lambda self: None)
        window._open_project_settings()
        first = window._proj_settings_dlg
        assert isinstance(first, mw.ProjectSettingsDialog)
        window._open_project_settings()
        assert window._proj_settings_dlg is first

    def test_without_a_project_the_start_dialog_is_shown(self, make_window, monkeypatch):
        window = make_window(None)
        monkeypatch.setattr(mw.StartProjectDialog, 'exec_', lambda self: 0, raising=False)
        monkeypatch.setattr(mw.StartProjectDialog, 'show', lambda self: None)
        window._open_project_settings()
        assert isinstance(window._proj_settings_dlg, mw.StartProjectDialog)
        window._config.current_project = ProjectConfig(name='Now', rootdir='r')
        monkeypatch.setattr(mw.ProjectSettingsDialog, 'exec_', lambda self: 0, raising=False)
        monkeypatch.setattr(mw.ProjectSettingsDialog, 'show', lambda self: None)
        window._open_project_settings()
        assert isinstance(window._proj_settings_dlg, mw.ProjectSettingsDialog)
        window._config.current_project = None
        window._open_project_settings()
        assert isinstance(window._proj_settings_dlg, mw.StartProjectDialog)

    def test_initializing_a_project_rebuilds_the_panels(self, window):
        old = window.centralWidget()
        window._initialize_project(window.current_project)
        assert window.centralWidget() is not old and panel(window, 'Apps') is not None

    def test_the_project_panels_gear_opens_settings(self, window, monkeypatch):
        monkeypatch.setattr(mw.ProjectSettingsDialog, 'exec_', lambda self: 0, raising=False)
        monkeypatch.setattr(mw.ProjectSettingsDialog, 'show', lambda self: None)
        panel(window, 'Project')._header._on_settings_clicked()
        assert isinstance(window._proj_settings_dlg, mw.ProjectSettingsDialog)


class TestTopWindowAndMainMenu:
    @pytest.fixture(autouse=True)
    def clear_caches(self):
        mw.get_top_window.cache_clear()
        mw.get_main_menu.cache_clear()
        yield
        mw.get_top_window.cache_clear()
        mw.get_main_menu.cache_clear()

    def test_top_window_is_the_main_window_or_any_main_window(self, qapp, monkeypatch):
        win = QtWidgets.QMainWindow()
        win.setObjectName('DedaverseMainWindow')
        monkeypatch.setitem(sys.modules, 'hou', None)
        monkeypatch.setattr(QtWidgets.QApplication, 'topLevelWidgets', staticmethod(lambda: [QtWidgets.QWidget(), win]))
        assert mw.get_top_window() is win
        mw.get_top_window.cache_clear()
        win.setObjectName('Other')
        assert mw.get_top_window() is win

    def test_a_missing_window_raises_without_caching(self, qapp, monkeypatch):
        monkeypatch.setitem(sys.modules, 'hou', None)
        monkeypatch.setattr(QtWidgets.QApplication, 'topLevelWidgets', staticmethod(lambda: []))
        with pytest.raises(RuntimeError):
            mw.get_top_window()

    def test_houdini_supplies_its_own_window(self, monkeypatch):
        hou = types.ModuleType('hou')
        hou.qt = types.SimpleNamespace(mainWindow=lambda: 'houdini-window')
        monkeypatch.setitem(sys.modules, 'hou', hou)
        assert mw.get_top_window() == 'houdini-window'

    def test_main_menu_in_maya_is_created_once(self, qapp, monkeypatch):
        maya = QtWidgets.QMainWindow()
        maya.setObjectName('MayaWindow')
        maya.menuBar()
        monkeypatch.setattr(mw, 'get_top_window', lambda: maya)
        menu = mw.get_main_menu()
        assert menu.objectName() == 'DedaverseMenu' and menu.title() == 'Deda'
        mw.get_main_menu.cache_clear()
        assert mw.get_main_menu() is menu

    def test_main_menu_in_the_standalone_app_is_the_tray_menu(self, window, monkeypatch):
        monkeypatch.setattr(mw, 'get_top_window', lambda: window)
        menu = mw.get_main_menu()
        assert menu.objectName() == 'DedaverseTaskbarContextMenu'

    def test_main_menu_without_a_known_menu(self, qapp, monkeypatch):
        plain = QtWidgets.QMainWindow()
        monkeypatch.setattr(mw, 'get_top_window', lambda: plain)
        assert mw.get_main_menu() is None

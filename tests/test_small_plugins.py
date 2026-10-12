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
"""Tests for the Maya, Perforce, Godot, Plugin Manager and Project Manager plugins and the app finders."""
import os
import sys
import types
from pathlib import Path

import pytest
from PySide6 import QtGui, QtWidgets

import deda.app
import deda.core
import deda.plugins.maya as maya_plugin
import deda.plugins.perforce as perforce
import deda.plugins.godot as godot
import deda.plugins.plugin_manager as plugin_manager
import deda.plugins.project_manager as project_manager
from deda.core.finder import _adobe, _unreal


class TestMayaLauncher:
    @pytest.fixture
    def fake_install(self, tmp_path, monkeypatch):
        exe = tmp_path / 'Maya2027' / 'bin' / 'maya.exe'
        exe.parent.mkdir(parents=True)
        exe.write_text('')
        monkeypatch.setenv('MAYA_2027_LOCATION', str(tmp_path / 'Maya2027'))
        return exe

    def test_find_uses_the_location_env_var(self, fake_install):
        app = maya_plugin.Maya('Maya 2027')
        assert app.find() == str(fake_install)

    def test_find_reports_a_missing_install(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv('MAYA_2027_LOCATION', str(tmp_path / 'nowhere'))
        with caplog.at_level('WARNING'):
            assert maya_plugin.Maya('Maya 2027').find() is None
        assert 'not found' in caplog.text

    def test_find_falls_back_to_the_default_location(self, tmp_path, monkeypatch):
        monkeypatch.delenv('MAYA_2027_LOCATION', raising=False)
        monkeypatch.setattr(maya_plugin, '_DEFAULT_LOCATION', tmp_path / 'absent')
        assert maya_plugin.Maya('Maya 2027').find() is None

    def test_load(self, fake_install, tmp_path, monkeypatch):
        app = maya_plugin.Maya('Maya 2027')
        assert app.load() is True and app.loaded
        monkeypatch.setenv('MAYA_2027_LOCATION', str(tmp_path / 'nowhere'))
        assert maya_plugin.Maya('Maya 2027').load() is False

    def test_launch_starts_maya_without_blocking(self, fake_install, monkeypatch):
        captured = {}
        monkeypatch.setattr(maya_plugin.subprocess, 'Popen',
                            lambda cmd, env: captured.update(cmd=cmd, env=env) or 'process')
        assert maya_plugin.Maya('Maya 2027').launch('scene.ma', 3) == 'process'
        assert captured['cmd'] == [str(fake_install), 'scene.ma', '3'] and 'PYTHONPATH' in captured['env']

    def test_launch_without_maya_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv('MAYA_2027_LOCATION', str(tmp_path / 'nowhere'))
        with pytest.raises(FileNotFoundError):
            maya_plugin.Maya('Maya 2027').launch()

    def test_env_warns_about_missing_pieces(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(maya_plugin, '_DEDACAM_BUILD_DIR', tmp_path / 'no-dedacam')
        monkeypatch.setattr(maya_plugin, '_DEPS_DIR', tmp_path / 'no-deps')
        monkeypatch.setattr(maya_plugin, '_USD_ROOT', tmp_path / 'no-usd')
        monkeypatch.delenv(maya_plugin.ENV_MAYAUSD_DIR, raising=False)
        with caplog.at_level('WARNING'):
            env = maya_plugin.Maya('Maya 2027').setup_env({'PATH': ''})
        assert 'Dedacam Maya module not found' in caplog.text and 'dependencies not found' in caplog.text
        assert 'MAYA_MODULE_PATH' not in env

    def test_unreadable_path_entries_are_kept(self, monkeypatch):
        def deny(self, pattern):
            raise PermissionError('protected')

        monkeypatch.setattr(Path, 'glob', deny)
        assert maya_plugin._is_foreign_usd('C:/Program Files/WindowsApps') is False
        assert maya_plugin._strip_usd(os.pathsep.join(['a', 'b'])) == os.pathsep.join(['a', 'b'])


class TestPerforce:
    def test_missing_p4python_is_explained(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'P4', None)
        with pytest.raises(ModuleNotFoundError, match='p4python'):
            with perforce.P4Connection():
                pass

    def test_connection_connects_and_always_disconnects(self, monkeypatch):
        events = []

        class FakeP4:
            def connect(self):
                events.append('connect')

            def disconnect(self):
                events.append('disconnect')

        module = types.ModuleType('P4')
        module.P4 = FakeP4
        monkeypatch.setitem(sys.modules, 'P4', module)
        with pytest.raises(RuntimeError):
            with perforce.P4Connection() as p4c:
                assert isinstance(p4c, FakeP4)
                raise RuntimeError('work failed')
        assert events == ['connect', 'disconnect']

    def test_file_manager_interface_is_not_implemented_yet(self):
        manager = perforce.PerforceFileManager('perforce')
        manager.load()
        calls = [lambda: manager.can_handle([]), lambda: manager.add([]), lambda: manager.rename('a', 'b'),
                 lambda: manager.delete([]), lambda: manager.get_latest([]), lambda: manager.get_version('a', 1),
                 lambda: manager.checkout([]), lambda: manager.commit([], 'm')]
        for call in calls:
            with pytest.raises(NotImplementedError):
                call()


class TestGodot:
    def test_load_registers_cleanly(self):
        plugin = deda.core.PluginRegistry().get('Godot')
        assert isinstance(plugin, godot.Godot)
        plugin.load()


@pytest.fixture
def main_menu(qapp, monkeypatch):
    menu = QtWidgets.QMenu()
    monkeypatch.setattr(deda.app, 'get_main_menu', lambda: menu)
    return menu


class TestMenuPlugins:
    @pytest.mark.parametrize('module, cls', [(project_manager, 'ProjectManager'), (plugin_manager, 'PluginManager')])
    def test_load_adds_a_launch_action_first(self, main_menu, module, cls):
        main_menu.addAction('Existing')
        tool = getattr(module, cls)('tool')
        tool.load()
        assert [a.text() for a in main_menu.actions()][1:] == ['Existing'] and len(main_menu.actions()) == 2

    @pytest.mark.parametrize('module, cls', [(project_manager, 'ProjectManager'), (plugin_manager, 'PluginManager')])
    def test_load_into_an_empty_menu(self, main_menu, module, cls):
        getattr(module, cls)('tool').load()
        assert len(main_menu.actions()) == 1

    def test_project_dialog_accepts(self, qapp):
        dialog = project_manager.ProjectManagerDialog()
        assert 'Project Manager' in dialog.windowTitle()
        dialog.accept()
        assert dialog.result() == QtWidgets.QDialog.Accepted
        assert isinstance(project_manager.ProjectManager('p').initialize_window(None),
                          project_manager.ProjectManagerDialog)


class TestPluginManager:
    def fake_plugin(self, image=None, description='desc', name='demo'):
        return types.SimpleNamespace(name=name, version='1.0', image=image, description=description,
                                     loaded=False, _loaded=False)

    def test_widget_shows_title_description_and_default_image(self, qapp):
        widget = plugin_manager.PluginWidget(self.fake_plugin(description=''))
        assert widget._title_lbl.text() == 'demo v1.0' and 'No Description' in widget._desc_lbl.text()

    def test_widget_uses_the_plugin_image_when_it_exists(self, qapp, tmp_path):
        image = tmp_path / 'p.png'
        QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGB32).save(str(image))
        widget = plugin_manager.PluginWidget(self.fake_plugin(image=str(image)))
        assert widget.layout().columnMinimumWidth(0) == 8

    def test_hover_and_click_restyle_and_toggle_loading(self, qapp):
        from PySide6 import QtCore, QtTest
        plugin = self.fake_plugin()
        widget = plugin_manager.PluginWidget(plugin)
        widget.enterEvent(None)
        assert 'rgba(20,20,20,255)' in widget.styleSheet()
        widget.leaveEvent(None)
        assert 'rgba(20,20,20,128)' in widget.styleSheet()
        widget.show()
        QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)
        assert plugin._loaded is True
        widget.close()

    def test_context_menu_is_built(self, qapp, monkeypatch):
        shown = []
        monkeypatch.setattr(QtWidgets.QMenu, 'exec_', lambda self, pos=None: shown.append(
            [a.text() for a in self.actions()]))
        widget = plugin_manager.PluginWidget(self.fake_plugin())
        widget.show_context_menu(widget.rect().center())
        assert shown == [['Check for Updates']]

    def test_dialog_lists_registered_plugins(self, qapp, monkeypatch):
        registry = deda.core.PluginRegistry
        monkeypatch.setattr(registry, '_registry_', {'demo': self.fake_plugin()})
        dialog = plugin_manager.PluginManagerDialog()
        assert len(dialog.findChildren(plugin_manager.PluginWidget)) == 1

    def test_tool_window_requires_a_writable_project(self, qapp, caplog):
        tool = plugin_manager.PluginManager('pm')

        def parent_with(project):
            widget = QtWidgets.QWidget()
            widget.current_project = project
            return widget

        with caplog.at_level('ERROR'):
            assert tool.initialize_window(parent_with(None)) is None
            assert tool.initialize_window(parent_with(types.SimpleNamespace(is_writable=False))) is None
        assert 'Choose a project' in caplog.text and 'not writable' in caplog.text
        window = tool.initialize_window(parent_with(types.SimpleNamespace(is_writable=True)))
        assert isinstance(window, plugin_manager.PluginManagerDialog)

    def test_tool_window_without_a_project_attribute(self, qapp):
        assert isinstance(plugin_manager.PluginManager('pm').initialize_window(None),
                          plugin_manager.PluginManagerDialog)


class TestFinders:
    @pytest.fixture
    def program_files(self, tmp_path, monkeypatch):
        """Make the finders' hard-coded C:/Program Files folders point into tmp_path."""
        real_path = Path

        def fake_path(*parts):
            text = str(parts[0]) if parts else '.'
            if text.startswith('C:/Program Files'):
                return real_path(tmp_path / text.replace('C:/', '', 1))
            return real_path(*parts)

        for module in (_adobe, _unreal):
            monkeypatch.setattr(module, 'Path', fake_path)
            monkeypatch.setattr(module.platform, 'system', lambda: 'Windows')
        return tmp_path

    def test_non_windows_finds_nothing(self, monkeypatch):
        for module in (_adobe, _unreal):
            monkeypatch.setattr(module.platform, 'system', lambda: 'Linux')
        assert list(_adobe.iter_photoshop_installs()) == [] and list(_unreal.iter_unreal_installs()) == []

    def test_missing_install_roots_find_nothing(self, program_files):
        assert list(_adobe.iter_photoshop_installs()) == [] and list(_unreal.iter_unreal_installs()) == []

    def test_photoshop_installs(self, program_files):
        good = program_files / 'Program Files' / 'Adobe' / 'Adobe Photoshop 2025'
        good.mkdir(parents=True)
        (good / 'Photoshop.exe').write_text('')
        (program_files / 'Program Files' / 'Adobe' / 'Adobe Photoshop 2020').mkdir()      # no exe
        (program_files / 'Program Files' / 'Adobe' / 'Illustrator').mkdir()               # not Photoshop
        (program_files / 'Program Files' / 'Adobe' / 'notes.txt').write_text('')           # not a directory
        assert list(_adobe.iter_photoshop_installs()) == [('Adobe Photoshop 2025', str(good / 'Photoshop.exe'))]

    def test_unreal_installs(self, program_files):
        root = program_files / 'Program Files' / 'Epic Games'
        editor = root / 'UE_5.5' / 'Engine' / 'Binaries' / 'Win64'
        editor.mkdir(parents=True)
        (editor / 'UnrealEditor.exe').write_text('')
        (root / 'UE_4.27').mkdir()                                                          # no editor
        (root / 'launcher.txt').write_text('')                                              # not a directory
        assert list(_unreal.iter_unreal_installs()) == [('UE_5.5', str(editor / 'UnrealEditor.exe'))]

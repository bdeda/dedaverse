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
"""Behavioural tests for the start-project and project-settings dialogs."""
import pytest
from PySide6 import QtWidgets

import deda.core
from deda.app import _project_settings as ps
from deda.core import ProjectConfig


class FakeUser:
    def __init__(self):
        self.projects = {}

    def add_project(self, project):
        self.projects[project.name] = project


class FakeConfig:
    """The slice of LayeredConfig the dialogs use."""

    def __init__(self, *projects, current=None):
        self.user = FakeUser()
        self._projects = list(projects)
        self.current_project = current
        self.saved = 0

    @property
    def projects(self):
        return iter(self._projects + [p for p in self.user.projects.values() if p not in self._projects])

    def get_project(self, name):
        return next((p for p in self.projects if p.name == name), None)

    def save(self):
        self.saved += 1


def project(tmp_path, name='Film', **kwargs):
    return ProjectConfig(name=name, rootdir=str(tmp_path / name.replace(' ', '_')), **kwargs)


def save_enabled(dialog):
    return dialog._btns.button(QtWidgets.QDialogButtonBox.Save).isEnabled()


@pytest.fixture
def warnings(monkeypatch):
    seen = []
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', staticmethod(
        lambda parent, title, text, *a, **k: seen.append((title, text))))
    return seen


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(ps.Path, 'home', classmethod(lambda cls: tmp_path / 'home'))


class TestUniquify:
    def test_unused_names_are_kept(self):
        assert ps._uniquify_proj_name('Film', ['Other']) == 'Film'

    def test_a_taken_name_gets_a_number(self):
        assert ps._uniquify_proj_name('Film', ['Film']) == 'Film (1)'

    def test_numbers_keep_counting_until_the_name_is_free(self):
        assert ps._uniquify_proj_name('Film', ['Film', 'Film (1)', 'Film (2)']) == 'Film (3)'


class TestStartProjectDialog:
    def test_defaults_to_an_untitled_project_under_the_home_directory(self, qapp, tmp_path):
        dialog = ps.StartProjectDialog(FakeConfig())
        assert dialog._name_editor.text() == 'Untitled Project' and dialog._token_editor.text() == 'Untitled_Project'
        assert dialog._rootdir_editor.text() == str(tmp_path / 'home' / 'dedaverse')
        assert save_enabled(dialog)

    def test_the_default_name_avoids_existing_projects(self, qapp, tmp_path):
        existing = ProjectConfig(name='Untitled Project', rootdir=str(tmp_path / 'x'))
        dialog = ps.StartProjectDialog(FakeConfig(existing))
        assert dialog._name_editor.text() == 'Untitled Project (1)'

    def test_typing_a_name_updates_the_token(self, qapp):
        dialog = ps.StartProjectDialog(FakeConfig())
        dialog._name_editor.setText('My Film 2')
        assert dialog._project.name == 'My Film 2' and dialog._token_editor.text() == 'My_Film_2'

    @pytest.mark.parametrize('token, valid', [('Good_Token', True), ('9bad', False), ('has space', False), ('', False)])
    def test_token_validation_toggles_save_and_the_highlight(self, qapp, token, valid):
        dialog = ps.StartProjectDialog(FakeConfig())
        dialog._token_editor.setText(token)
        dialog._validate_token()
        assert save_enabled(dialog) is valid
        assert bool(dialog._token_editor.styleSheet()) is (bool(token) and not valid)

    def test_save_is_disabled_for_a_blank_name(self, qapp):
        dialog = ps.StartProjectDialog(FakeConfig())
        dialog._name_editor.setText('  ')
        dialog._token_editor.setText('Tok')
        dialog._validate_token()
        assert not save_enabled(dialog)

    def test_a_project_that_already_exists_cannot_be_saved_again(self, qapp, tmp_path):
        existing = project(tmp_path, 'Film')
        dialog = ps.StartProjectDialog(FakeConfig(existing))
        dialog._name_editor.setText('Film')
        dialog._rootdir_editor.setText(existing.rootdir)
        dialog._validate_proj_root()
        assert not save_enabled(dialog)

    def test_a_folder_holding_a_differently_named_project_cannot_be_used(self, qapp, tmp_path):
        other = project(tmp_path, 'Original')
        other.save()
        dialog = ps.StartProjectDialog(FakeConfig())
        dialog._name_editor.setText('Renamed')
        dialog._rootdir_editor.setText(other.rootdir)
        dialog._validate_proj_root()
        assert not save_enabled(dialog)
        dialog._name_editor.setText('Original')
        dialog._validate_proj_root()
        assert save_enabled(dialog)

    def test_read_only_projects_lock_the_name_and_folder(self, qapp, monkeypatch):
        dialog = ps.StartProjectDialog(FakeConfig())
        monkeypatch.setattr(ProjectConfig, 'is_writable', property(lambda self: False))
        dialog._check_proj_writable()
        assert dialog._name_editor.isReadOnly() and dialog._rootdir_editor.isReadOnly()

    def test_picking_a_new_folder(self, qapp, monkeypatch, tmp_path):
        chosen = tmp_path / 'new_project'
        chosen.mkdir()
        dialog = ps.StartProjectDialog(FakeConfig())
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(chosen)))
        dialog._pick_rootdir()
        assert dialog._rootdir_editor.text() == str(chosen) and dialog._project.rootdir == chosen.resolve().as_posix()
        assert dialog._project.cfg_path.endswith('.dedaverse/project.cfg')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
        dialog._pick_rootdir()
        assert dialog._rootdir_editor.text() == str(chosen)

    def test_picking_a_folder_with_a_project_loads_it(self, qapp, monkeypatch, tmp_path):
        existing = project(tmp_path, 'Loaded', prim_name='Loaded_Tok')
        existing.save()
        dialog = ps.StartProjectDialog(FakeConfig())
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: existing.rootdir))
        dialog._pick_rootdir()
        assert dialog._name_editor.text() == 'Loaded' and dialog._token_editor.text() == 'Loaded_Tok'

    def test_saving_adds_the_project_and_makes_it_current(self, qapp, tmp_path):
        config = FakeConfig()
        dialog = ps.StartProjectDialog(config)
        dialog._project.rootdir = str(tmp_path / 'saved_project')
        dialog._token_editor.setText('Saved_Tok')
        changed = []
        dialog.project_changed.connect(lambda: changed.append(1))
        dialog.save_and_close()
        assert config.current_project is dialog._project and dialog._project.prim_name == 'Saved_Tok'
        assert 'Untitled Project' in config.user.projects and config.saved == 1 and changed == [1]
        assert (tmp_path / 'saved_project' / '.dedaverse' / 'project.cfg').is_file()

    def test_saving_with_an_invalid_token_warns(self, qapp, warnings):
        config = FakeConfig()
        dialog = ps.StartProjectDialog(config)
        dialog._token_editor.setText('1bad')
        dialog.save_and_close()
        assert warnings[0][0] == 'Invalid Token' and config.current_project is None


class TestProjectSettingsDialog:
    @pytest.fixture
    def config(self, tmp_path):
        film, game = project(tmp_path, 'Film', hdr_images_dir='H:/hdr', lights_root='lights', materials_root='mats'), \
            project(tmp_path, 'Game')
        return FakeConfig(film, game, current=film)

    @pytest.fixture
    def dialog(self, qapp, config):
        dlg = ps.ProjectSettingsDialog(config)
        dlg.show()
        yield dlg
        dlg.close()

    def test_fields_show_the_current_project(self, dialog, config):
        assert dialog._project_cb.currentText() == 'Film' and dialog._project_name_le.text() == 'Film'
        assert dialog._project_token_le.text() == 'Film'
        assert dialog._project_rootdir_le.text() == config.current_project.rootdir
        assert (dialog._hdr_images_dir_le.text(), dialog._lights_root_le.text(), dialog._materials_root_le.text()) == (
            'H:/hdr', 'lights', 'mats')

    def test_without_a_current_project_nothing_is_selected(self, qapp, tmp_path):
        dialog = ps.ProjectSettingsDialog(FakeConfig(project(tmp_path, 'Film')))
        assert dialog._project_cb.currentIndex() == -1 and dialog._project_name_le.text() == ''
        dialog.initialize()
        assert dialog._project_cb.currentIndex() == -1

    def test_showing_lists_the_projects_sorted(self, dialog):
        dialog.initialize()
        assert [dialog._project_cb.itemText(i) for i in range(dialog._project_cb.count())] == ['Film', 'Game']

    def test_choosing_another_project_fills_the_form(self, dialog, config):
        dialog._project_cb.setCurrentText('Game')
        assert dialog._project_name_le.text() == 'Game' and save_enabled(dialog)
        assert dialog._hdr_images_dir_le.text() == '' and dialog._project_rootdir_le.text() == config._projects[1].rootdir

    def test_clearing_the_selection_clears_the_form(self, dialog):
        dialog._project_cb.setCurrentIndex(-1)
        assert dialog._project_name_le.text() == '' and dialog._lights_root_le.text() == ''

    def test_typing_an_unknown_name_deselects_the_project(self, dialog):
        dialog._project_name_le.setText('Brand New')
        assert dialog._project_cb.currentIndex() == -1 and save_enabled(dialog)
        dialog._project_name_le.setText('Game')
        assert dialog._project_cb.currentText() == 'Game'

    @pytest.mark.parametrize('picker, field, title', [
        ('_pick_project_rootdir', '_project_rootdir_le', 'Choose Project Root Directory'),
        ('_pick_hdr_images_dir', '_hdr_images_dir_le', 'Choose HDR / Environment Textures Directory'),
    ])
    def test_directory_pickers(self, dialog, monkeypatch, picker, field, title):
        asked = []
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory',
                            staticmethod(lambda parent, caption, start: asked.append(caption) or 'D:/picked'))
        getattr(dialog, picker)()
        assert getattr(dialog, field).text() == 'D:/picked' and asked == [title] and save_enabled(dialog)
        dialog._btns.button(QtWidgets.QDialogButtonBox.Save).setEnabled(False)
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
        getattr(dialog, picker)()
        assert getattr(dialog, field).text() == 'D:/picked' and not save_enabled(dialog)

    @pytest.mark.parametrize('picker, field', [('_pick_lights_root', '_lights_root_le'),
                                                ('_pick_materials_root', '_materials_root_le')])
    def test_lights_and_materials_are_stored_relative_to_the_project(self, dialog, monkeypatch, tmp_path, picker, field):
        root = tmp_path / 'proj'
        (root / 'assets' / 'lights').mkdir(parents=True)
        dialog._project_rootdir_le.setText(str(root))
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory',
                            staticmethod(lambda *a, **k: str(root / 'assets' / 'lights')))
        getattr(dialog, picker)()
        assert getattr(dialog, field).text() == 'assets/lights'
        outside = tmp_path / 'elsewhere'
        outside.mkdir()
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(outside)))
        getattr(dialog, picker)()
        assert getattr(dialog, field).text() == str(outside)

    @pytest.mark.parametrize('picker, field', [('_pick_lights_root', '_lights_root_le'),
                                                ('_pick_materials_root', '_materials_root_le')])
    def test_without_a_project_root_the_path_stays_absolute(self, dialog, monkeypatch, picker, field):
        dialog._project_rootdir_le.setText('')
        getattr(dialog, field).setText('')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: 'D:/abs'))
        getattr(dialog, picker)()
        assert getattr(dialog, field).text() == 'D:/abs'
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
        getattr(dialog, picker)()

    def test_an_unresolvable_project_root_falls_back_to_the_absolute_path(self, dialog, monkeypatch):
        dialog._project_rootdir_le.setText('\0bad')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: 'D:/abs'))
        dialog._pick_lights_root()
        dialog._pick_materials_root()
        assert dialog._lights_root_le.text() == 'D:/abs' and dialog._materials_root_le.text() == 'D:/abs'

    def test_the_add_button_opens_the_start_dialog(self, dialog, monkeypatch):
        opened = []
        monkeypatch.setattr(ps.StartProjectDialog, 'exec_', lambda self: opened.append(self) or 0, raising=False)
        changed = []
        dialog.project_changed.connect(changed.append)
        dialog._add_project()
        assert len(opened) == 1 and changed == [dialog._config.current_project]

    def test_saving_requires_a_name_and_a_root(self, dialog, config, caplog):
        dialog._project_name_le.setText('')
        with caplog.at_level('WARNING'):
            dialog.save_and_close()
        assert 'required' in caplog.text and config.saved == 0

    def test_saving_with_an_invalid_token_warns(self, dialog, warnings, config):
        dialog._project_token_le.setText('9nope')
        dialog.save_and_close()
        assert warnings[0][0] == 'Invalid Token' and config.saved == 0

    def test_renaming_a_project_keeps_it_found_by_its_root_and_updates_it_in_place(self, dialog, config):
        film = config._projects[0]
        config.user.projects['Film'] = film
        dialog._project_name_le.setText('Film Renamed')            # deselects the combo box; the root still matches
        dialog._project_token_le.setText('Film_Tok')
        dialog._hdr_images_dir_le.setText('')
        dialog._lights_root_le.setText(' ')
        changed = []
        dialog.project_changed.connect(changed.append)
        dialog.save_and_close()
        assert film.name == 'Film Renamed' and film.prim_name == 'Film_Tok' and film.hdr_images_dir is None
        assert film.lights_root is None and film.cfg_path.endswith('.dedaverse/project.cfg')
        assert 'Film' not in config.user.projects and 'Film Renamed' in config.user.projects
        assert config.current_project is film and config.saved == 1 and changed == [film]

    def test_moving_a_selected_project_updates_its_root(self, dialog, config, tmp_path):
        film = config._projects[0]
        dialog._project_rootdir_le.setText(str(tmp_path / 'moved'))
        dialog._project_token_le.setText('Film')
        dialog.save_and_close()
        assert film.rootdir == str(tmp_path / 'moved') and film.cfg_path.endswith('moved/.dedaverse/project.cfg')
        assert (tmp_path / 'moved' / '.dedaverse' / 'project.cfg').is_file()

    def test_a_project_is_found_by_its_root_when_the_name_is_new(self, dialog, config):
        dialog._project_cb.setCurrentIndex(-1)
        game = config._projects[1]
        dialog._project_name_le.setText('Game Reborn')
        dialog._project_token_le.setText('Game_Tok')
        dialog._project_rootdir_le.setText(game.rootdir)
        dialog.save_and_close()
        assert game.name == 'Game Reborn' and config.current_project is game

    def test_a_project_is_found_by_name(self, dialog, config, tmp_path):
        dialog._project_cb.setCurrentIndex(-1)
        dialog._project_name_le.setText('Game')
        elsewhere = str(tmp_path / 'elsewhere')
        dialog._project_rootdir_le.setText(elsewhere)
        dialog.save_and_close()
        assert config.current_project is config._projects[1] and config._projects[1].rootdir == elsewhere

    def test_creating_a_new_project_asks_first(self, dialog, config, monkeypatch, tmp_path):
        dialog._project_cb.setCurrentIndex(-1)
        dialog._project_name_le.setText('Fresh')
        dialog._project_token_le.setText('Fresh_Tok')
        dialog._project_rootdir_le.setText(str(tmp_path / 'fresh'))
        monkeypatch.setattr(QtWidgets.QMessageBox, 'question', staticmethod(lambda *a, **k: QtWidgets.QMessageBox.No))
        dialog.save_and_close()
        assert config.current_project.name == 'Film' and config.saved == 0
        monkeypatch.setattr(QtWidgets.QMessageBox, 'question', staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes))
        dialog.save_and_close()
        assert config.current_project.name == 'Fresh' and config.current_project.prim_name == 'Fresh_Tok'
        assert (tmp_path / 'fresh' / '.dedaverse' / 'project.cfg').is_file() and config.saved == 1

    def test_creating_a_project_over_an_existing_config_reuses_it(self, dialog, config, monkeypatch, tmp_path):
        existing = ProjectConfig(name='OnDisk', rootdir=str(tmp_path / 'ondisk'), key='OD')
        existing.save()
        dialog._project_cb.setCurrentIndex(-1)
        dialog._project_name_le.setText('Adopted')
        dialog._project_token_le.setText('Adopted_Tok')
        dialog._project_rootdir_le.setText(existing.rootdir)
        monkeypatch.setattr(QtWidgets.QMessageBox, 'question', staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes))
        dialog.save_and_close()
        assert config.current_project.name == 'Adopted' and config.current_project.key == 'OD'

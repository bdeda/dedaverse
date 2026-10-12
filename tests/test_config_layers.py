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
"""Tests for config loading, saving and layering, isolated to a temporary home directory."""
import json
from pathlib import Path

import pytest

from deda.core import _config
from deda.core._config import (
    AppConfig, LayeredConfig, PluginConfig, ProjectConfig, ServiceConfig, SiteConfig, UserConfig,
)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Home and site config point into tmp_path; the LayeredConfig singleton is reset around each test."""
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.delenv('DEDAVERSE_SITE_CONFIG', raising=False)
    monkeypatch.delattr(LayeredConfig, '_instance', raising=False)
    yield home
    if hasattr(LayeredConfig, '_instance'):
        del LayeredConfig._instance


def app(name, command='run'):
    return AppConfig(name=name, version='1', command=command, icon_path='', install_url='', help_url='', enabled=True)


def service(name, url='http://x'):
    return ServiceConfig(name=name, enabled=True, url=url)


class TestSanitizePrimName:
    @pytest.mark.parametrize('raw, expected', [
        ('', 'Project'), ('   ', 'Project'), ('My Film!', 'My_Film'), ('9lives', '_9lives'),
        ('___', 'Project'), ('ok_name', 'ok_name'),
    ])
    def test_names(self, raw, expected):
        assert _config._sanitize_prim_name(raw) == expected


class TestEquality:
    def test_app_compares_and_hashes_by_name(self):
        assert app('a', 'x') == app('a', 'y') and hash(app('a')) == hash(app('a', 'z'))
        assert app('a') != app('b')
        assert app('a').__eq__(object()) is NotImplemented

    def test_plugin_compares_by_name_and_version(self):
        a = PluginConfig('p', '1', True, True, '')
        assert a == PluginConfig('p', '1', False, False, 'u') and hash(a) == hash(('p', '1'))
        assert a != PluginConfig('p', '2', True, True, '')

    def test_service_compares_by_name(self):
        assert service('s', 'a') == service('s', 'b') and hash(service('s')) == hash('s')

    def test_project_compares_with_names_and_hashes(self):
        project = ProjectConfig(name='Film', rootdir='r')
        assert project == 'Film' and str(project) == 'Film' and hash(project) == hash('Film')


class TestSiteConfig:
    def test_load_without_the_env_var_is_none(self):
        assert SiteConfig.load() is None

    def test_missing_file_gives_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv('DEDAVERSE_SITE_CONFIG', str(tmp_path / 'site' / 'site.cfg'))
        assert SiteConfig.load() == SiteConfig()

    def test_save_and_load_round_trip(self, tmp_path, monkeypatch):
        path = tmp_path / 'site' / 'site.cfg'
        monkeypatch.setenv('DEDAVERSE_SITE_CONFIG', str(path))
        SiteConfig(name='Studio', plugin_urls=['u'], apps=[app('Maya')]).save()
        loaded = SiteConfig.load()
        assert loaded.name == 'Studio' and loaded.plugin_urls == ['u'] and loaded.apps == [app('Maya')]

    def test_save_without_a_path_does_nothing(self):
        SiteConfig(name='x').save()

    def test_is_writable(self, tmp_path, monkeypatch):
        assert SiteConfig().is_writable is False
        monkeypatch.setenv('DEDAVERSE_SITE_CONFIG', str(tmp_path / 'nodir' / 'site.cfg'))
        assert SiteConfig().is_writable is False
        monkeypatch.setenv('DEDAVERSE_SITE_CONFIG', str(tmp_path / 'site.cfg'))
        assert SiteConfig().is_writable is True      # creatable in an existing directory
        (tmp_path / 'site.cfg').write_text('{}')
        assert SiteConfig().is_writable is True

    def test_hash_uses_the_name(self):
        assert hash(SiteConfig(name='a')) == hash('a')


class TestProjectConfig:
    def test_defaults_derive_prim_name_and_add_the_viewer_app(self):
        project = ProjectConfig(name='Killer Clowns', rootdir='r')
        assert project.prim_name == 'Killer_Clowns'
        assert [a.name for a in project.apps] == ['Dedaverse']
        assert ProjectConfig(name='n', rootdir='r', prim_name='  ').prim_name == 'n'

    def test_save_and_load_by_directory_and_by_file(self, tmp_path):
        project = ProjectConfig(name='Film', rootdir=str(tmp_path / 'film'), key='FLM')
        project.save()
        cfg = tmp_path / 'film' / '.dedaverse' / 'project.cfg'
        assert cfg.is_file() and project.cfg_path == cfg.as_posix()
        by_dir = ProjectConfig.load(tmp_path / 'film')
        by_file = ProjectConfig.load(cfg)
        assert by_dir.key == by_file.key == 'FLM' and by_dir.cfg_path == cfg.as_posix()

    def test_load_failures_return_none(self, tmp_path, caplog):
        assert ProjectConfig.load('') is None
        assert ProjectConfig.load(tmp_path / 'nothing') is None

    def test_load_repairs_a_blank_prim_name(self, tmp_path):
        cfg = tmp_path / 'p' / '.dedaverse' / 'project.cfg'
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({'name': 'Odd Name', 'rootdir': 'r', 'prim_name': ' '}))
        assert ProjectConfig.load(cfg).prim_name == 'Odd_Name'

    def test_save_needs_a_destination(self, caplog):
        project = ProjectConfig(name='n', rootdir='')
        project.save()
        assert project.cfg_path is None and 'neither rootdir or cfg_path' in caplog.text

    def test_is_writable(self, tmp_path):
        project = ProjectConfig(name='n', rootdir='r')
        assert project.is_writable
        project.cfg_path = str(tmp_path / 'missing.cfg')
        assert project.is_writable
        existing = tmp_path / 'there.cfg'
        existing.write_text('{}')
        project.cfg_path = str(existing)
        assert project.is_writable

    def test_save_skips_read_only_files(self, tmp_path, monkeypatch):
        project = ProjectConfig(name='n', rootdir=str(tmp_path), cfg_path=str(tmp_path / 'x.cfg'))
        monkeypatch.setattr(ProjectConfig, 'is_writable', property(lambda self: False))
        project.save()
        assert not (tmp_path / 'x.cfg').exists()

    def test_save_raises_when_the_directory_cannot_be_made(self, tmp_path):
        blocker = tmp_path / 'blocker'
        blocker.write_text('a file where a directory should be')
        project = ProjectConfig(name='n', rootdir=str(tmp_path), cfg_path=str(blocker / 'sub' / 'p.cfg'))
        with pytest.raises(OSError):
            project.save()


class TestUserConfig:
    def test_load_without_a_file_is_empty(self):
        assert UserConfig.load() == UserConfig()

    def test_save_load_round_trip_stores_project_rootdirs(self, isolated, tmp_path):
        user = UserConfig(current_project='Film', roles=['rigger'], assets_panel_path={'Film': ['Assets']})
        loaded_project = ProjectConfig(name='Film', rootdir=str(tmp_path / 'film'))
        user.add_project(loaded_project)
        user.projects['Plain'] = 'D:/plain'
        user.projects['Dict'] = {'rootdir': 'D:/dict'}
        user.save()
        data = json.loads((isolated / '.dedaverse' / 'user.cfg').read_text())
        assert data['projects'] == {'Film': str(tmp_path / 'film'), 'Plain': 'D:/plain', 'Dict': 'D:/dict'}
        again = UserConfig.load()
        assert again.current_project == 'Film' and again.roles == ['rigger']
        assert again.assets_panel_path == {'Film': ['Assets']}

    def test_is_writable(self, isolated):
        assert UserConfig().is_writable is False          # ~/.dedaverse does not exist yet
        (isolated / '.dedaverse').mkdir()
        assert UserConfig().is_writable is True
        (isolated / '.dedaverse' / 'user.cfg').write_text('{}')
        assert UserConfig().is_writable is True

    def test_add_project_validates_its_type(self):
        with pytest.raises(TypeError):
            UserConfig().add_project('nope')

    def test_load_project_reads_the_config_from_disk(self, tmp_path):
        ProjectConfig(name='Film', rootdir=str(tmp_path / 'film')).save()
        user = UserConfig(projects={'Film': str(tmp_path / 'film')})
        user.load_project('Film')
        assert isinstance(user.projects['Film'], ProjectConfig)
        user.load_project('Film')                          # already loaded: no-op
        with pytest.raises(ValueError):
            user.load_project('Unknown')

    def test_load_project_follows_a_rename(self, tmp_path):
        ProjectConfig(name='NewName', rootdir=str(tmp_path / 'film')).save()
        user = UserConfig(projects={'OldName': str(tmp_path / 'film')})
        user.load_project('OldName')
        assert 'NewName' in user.projects and 'OldName' not in user.projects

    @pytest.mark.xfail(strict=True, raises=KeyError,
                       reason='load_project reads self.projects[old name] after deleting it, and assigns '
                              'current_proj (typo for current_project)')
    def test_load_project_follows_a_rename_of_the_current_project(self, tmp_path):
        ProjectConfig(name='NewName', rootdir=str(tmp_path / 'film')).save()
        user = UserConfig(projects={'OldName': str(tmp_path / 'film')}, current_project='OldName')
        user.load_project('OldName')
        assert user.current_project == 'NewName'


class TestLayeredConfig:
    @pytest.mark.xfail(strict=True, raises=AttributeError,
                       reason='LayeredConfig.instance() creates the singleton without running __init__')
    def test_instance_on_a_fresh_singleton_is_initialised(self):
        assert LayeredConfig.instance().user is not None

    def test_defaults_include_the_viewer_app(self):
        config = LayeredConfig()
        assert [a.name for a in config.site.apps] == ['Dedaverse']
        assert LayeredConfig() is config

    def test_site_config_with_no_apps_gets_the_default(self, tmp_path, monkeypatch):
        path = tmp_path / 'site.cfg'
        monkeypatch.setenv('DEDAVERSE_SITE_CONFIG', str(path))
        SiteConfig(name='Studio').save()
        config = LayeredConfig()
        assert config.site.name == 'Studio' and [a.name for a in config.site.apps] == ['Dedaverse']

    def test_apps_merge_later_layers_over_earlier(self, tmp_path):
        config = LayeredConfig()
        config.site.apps = [app('Maya', 'site-maya'), app('Houdini')]
        config.user.apps = [app('Maya', 'user-maya')]
        project = ProjectConfig(name='Film', rootdir=str(tmp_path), apps=[app('Blender')])
        config.current_project = project
        merged = {a.name: a.command for a in config.get_merged_apps()}
        assert merged == {'Maya': 'user-maya', 'Houdini': 'run', 'Blender': 'run'}

    def test_services_merge_the_same_way(self, tmp_path):
        config = LayeredConfig()
        config.site.services = [service('jira', 'site')]
        config.user.services = [service('jira', 'user'), service('p4')]
        merged = {s.name: s.url for s in config.get_merged_services()}
        assert merged == {'jira': 'user', 'p4': 'http://x'}

    def test_layer_info_for_apps_and_services(self, tmp_path):
        config = LayeredConfig()
        config.site.apps = [app('SiteApp')]
        config.user.apps = [app('UserApp')]
        config.site.services = [service('site-svc')]
        config.user.services = [service('user-svc')]
        config.current_project = ProjectConfig(
            name='Film', rootdir=str(tmp_path), apps=[app('ProjApp')], services=[service('proj-svc')])
        assert config.get_app_layer_info('ProjApp')[0] == 'project'
        assert config.get_app_layer_info('UserApp')[0] == 'user'
        assert config.get_app_layer_info('SiteApp') == ('site', False)
        assert config.get_app_layer_info('Nope') == ('project', True)
        assert config.get_service_layer_info('proj-svc')[0] == 'project'
        assert config.get_service_layer_info('user-svc')[0] == 'user'
        assert config.get_service_layer_info('site-svc') == ('site', False)
        assert config.get_service_layer_info('nope') == ('project', True)

    def test_current_project_none_until_set_and_validates_type(self, tmp_path):
        config = LayeredConfig()
        assert config.current_project is None
        with pytest.raises(TypeError):
            config.current_project = 'Film'
        project = ProjectConfig(name='Film', rootdir=str(tmp_path))
        config.current_project = project
        assert config.current_project is project and config.user.current_project == 'Film'

    def test_current_project_loads_from_a_rootdir_string(self, tmp_path):
        ProjectConfig(name='Film', rootdir=str(tmp_path / 'film'), key='FLM').save()
        config = LayeredConfig()
        config.user.projects = {'Film': str(tmp_path / 'film')}
        config.user.current_project = 'Film'
        assert config.current_project.key == 'FLM'

    def test_current_project_without_a_cfg_file_is_synthesised(self, tmp_path):
        config = LayeredConfig()
        config.user.projects = {'Film': str(tmp_path / 'empty')}
        config.user.current_project = 'Film'
        assert config.current_project.rootdir == str(tmp_path / 'empty')

    def test_projects_iterator_and_lookup(self, tmp_path):
        ProjectConfig(name='Film', rootdir=str(tmp_path / 'film')).save()
        config = LayeredConfig()
        config.user.projects = {'Film': str(tmp_path / 'film'), 'Ghost': str(tmp_path / 'ghost')}
        assert sorted(p.name for p in config.projects) == ['Film', 'Ghost']
        assert config.get_project('Film').name == 'Film'
        assert config.get_project('Nope') is None

    def test_save_persists_user_and_site(self, isolated, tmp_path, monkeypatch):
        site = tmp_path / 'site.cfg'
        monkeypatch.setenv('DEDAVERSE_SITE_CONFIG', str(site))
        config = LayeredConfig()
        config.user.roles = ['animator']
        config.save()
        assert (isolated / '.dedaverse' / 'user.cfg').is_file() and site.is_file()

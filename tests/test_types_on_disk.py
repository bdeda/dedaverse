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
"""Behavioural tests for Entity/Collection/Project backed by a real project on disk."""
from pathlib import Path

import pytest
from pxr import Kind, Usd

from deda.core.types._asset import Asset
from deda.core.types._collection import Collection
from deda.core.types._element import Element
from deda.core.types._entity import Entity, _layer_is_anonymous
from deda.core.types._project import Project


@pytest.fixture
def project(tmp_path):
    return Project.create(name='Proj', rootdir=tmp_path / 'proj')


@pytest.fixture
def backed(tmp_path):
    """An Entity whose prim lives on a file-backed layer, as for a real asset."""
    stage = Usd.Stage.CreateNew(str(tmp_path / 'backed.usda'))
    prim = stage.DefinePrim('/Hero', 'Scope')
    stage.SetDefaultPrim(prim)
    entity = Entity('Hero', None)
    entity.prim = prim
    entity._stage = stage   # keep the stage alive for the prim
    return entity


@pytest.fixture
def tree(project):
    """A project with an Assets collection containing a Hero asset."""
    assets = project.add_collection('Assets')
    hero = assets.add_asset('Hero')
    return project, assets, hero


class TestEntityBasics:
    def test_prim_path_for_root_and_children(self):
        root = Entity('Root', None)
        child = Entity('Child', root)
        grandchild = Entity('Grand', child)
        assert root.prim_path == '/Root'
        assert child.prim_path == '/Child'
        assert grandchild.prim_path == '/Child/Grand'

    def test_metadata_is_empty_without_a_prim(self):
        entity = Entity('E', None)
        assert entity.metadata == {}
        assert entity.get_metadata('title', 'dflt') == 'dflt'
        assert entity.metadata_path is None

    def test_path_of_a_non_project_entity_is_empty(self):
        assert Entity('E', None).path == Path()

    def test_project_path_is_the_rootdir(self, project):
        assert project.path == project.rootdir

    def test_project_walks_up_the_parents(self, tree):
        project, assets, hero = tree
        assert hero.project is project and assets.project is project


class TestMetadata:
    def test_set_and_get_metadata_round_trip(self, backed):
        backed.set_metadata('title', 'The Hero')
        assert backed.get_metadata('title') == 'The Hero'
        assert backed.metadata['title'] == 'The Hero'
        assert backed.get_metadata('missing', 7) == 7

    def test_set_metadata_persists_to_disk(self, backed, tmp_path):
        backed.set_metadata('description', 'on disk')
        assert 'on disk' in (tmp_path / 'backed.usda').read_text()

    def test_get_edit_target_is_a_persistent_layer(self, backed):
        layer = backed.get_edit_target()
        assert layer is not None and not layer.anonymous

    @pytest.mark.xfail(strict=True, reason='Entity.prim_path omits the project prim, so Asset.prim is never valid '
                                           'on a project created with Project.create (stage holds /Proj/Assets/Hero)')
    def test_asset_prim_resolves_on_a_real_project(self, tree):
        _, _, hero = tree
        assert hero.prim.IsValid()

    def test_invalid_prim_reads_as_empty_and_cannot_be_written(self, tree):
        _, assets, _ = tree
        ghost = Asset('Ghost', assets)
        assert ghost.get_edit_target() is None
        assert ghost.get_metadata('k', 'd') == 'd'
        assert ghost.metadata == {}
        with pytest.raises(RuntimeError):
            ghost.set_metadata('k', 'v')

    def test_set_metadata_raises_when_there_is_no_edit_target(self, backed, monkeypatch):
        monkeypatch.setattr(Entity, 'get_edit_target', lambda self: None)
        with pytest.raises(RuntimeError, match='edit target'):
            backed.set_metadata('k', 'v')

    def test_edit_target_of_the_pseudo_root_is_the_root_layer(self):
        stage = Usd.Stage.CreateInMemory()
        holder = Entity('h', None)
        holder.prim = stage.GetPseudoRoot()
        assert holder.get_edit_target() == stage.GetRootLayer()

    def test_edit_target_is_none_for_anonymous_layers(self):
        stage = Usd.Stage.CreateInMemory()
        holder = Entity('A', None)
        holder.prim = stage.DefinePrim('/A')
        assert holder.get_edit_target() is None

    def test_layer_is_anonymous_fallbacks(self):
        class Old:
            identifier = 'anon:0x1'

        class Named:
            identifier = '/some/file.usda'

        class Nameless:
            pass

        assert _layer_is_anonymous(Old())
        assert not _layer_is_anonymous(Named())
        assert _layer_is_anonymous(Nameless())


class TestFromPrim:
    def test_group_kind_makes_a_collection_else_an_asset(self, project):
        stage = Usd.Stage.CreateInMemory()
        group = stage.DefinePrim('/G', 'Scope')
        Usd.ModelAPI(group).SetKind(Kind.Tokens.group)
        model = stage.DefinePrim('/M', 'Scope')
        assert isinstance(Entity.from_prim(group, project), Collection)
        assert isinstance(Entity.from_prim(model, project), Asset)

    def test_requires_parent_and_a_valid_prim(self, project):
        stage = Usd.Stage.CreateInMemory()
        prim = stage.DefinePrim('/X')
        with pytest.raises(ValueError, match='parent'):
            Entity.from_prim(prim, None)
        with pytest.raises(ValueError, match='invalid'):
            Entity.from_prim(stage.GetPrimAtPath('/nope'), project)
        with pytest.raises(ValueError, match='invalid'):
            Entity.from_prim(None, project)


class TestFromPath:
    def test_missing_path_is_none(self, tmp_path):
        assert Entity.from_path(str(tmp_path / 'nope')) is None

    def test_project_root_dir(self, project):
        found = Entity.from_path(str(project.rootdir))
        assert isinstance(found, Project) and found.rootdir == project.rootdir

    def test_a_dir_without_dedaverse_is_none(self, tmp_path):
        assert Entity.from_path(str(tmp_path)) is None

    def test_unrelated_file_types_are_none(self, tmp_path):
        f = tmp_path / 'notes.txt'
        f.write_text('x')
        assert Entity.from_path(str(f)) is None

    def test_metadata_usda_resolves_to_an_entity_with_the_same_name(self, tree):
        _, assets, hero = tree
        for entity in (assets, hero):
            found = Entity.from_path(str(entity.metadata_path))
            assert found is not None and found.name == entity.name

    def test_content_file_resolves_to_an_element(self, tree):
        project, _, _ = tree
        folder = project.rootdir / 'Assets' / 'Hero'
        folder.mkdir(parents=True, exist_ok=True)
        content = folder / 'hero_model.usda'
        content.write_text('#usda 1.0\n')
        found = Entity.from_path(str(content))
        assert isinstance(found, Element) and found.name == 'hero_model'

    def test_usda_outside_any_project_is_none(self, tmp_path):
        stray = tmp_path / 'stray.usda'
        stray.write_text('#usda 1.0\n')
        assert Entity.from_path(str(stray)) is None


class TestProject:
    def test_paths_and_names(self, project):
        assert project.metadata_dir == project.rootdir / '.dedaverse'
        assert project.metadata_path.is_file()
        assert project.user_settings_path.name == 'user_settings.usda'
        assert project.prim_path == f'/{project.prim_name}'
        assert project.asset_directory_for_prim_path('/Assets/Monsters') == project.rootdir / 'Assets' / 'Monsters'

    def test_stage_is_cached(self, project):
        stage = project.stage
        assert project.stage is stage

    def test_stage_is_created_for_a_project_without_metadata(self, tmp_path):
        root = tmp_path / 'bare'
        root.mkdir()
        bare = Project(name='Bare', rootdir=root)
        assert bare.stage.GetDefaultPrim().IsValid()
        assert bare.metadata_path.is_file()

    def test_sort_order_round_trip(self, tree):
        project, assets, _ = tree
        assert project.get_collection_sort_order(assets.prim_path) is None
        project.set_collection_sort_order(assets.prim_path, ['b', 'a'])
        assert project.get_collection_sort_order(assets.prim_path) == ['b', 'a']
        assert project.get_collection_sort_order('/nothing') is None
        assert project.user_settings_path.is_file()

    def test_sort_order_with_an_unusable_stored_value(self, tree):
        project, assets, _ = tree
        prim = project.stage.OverridePrim(assets.prim_path)
        prim.SetCustomDataByKey('sort_order', 5)
        assert project.get_collection_sort_order(assets.prim_path) is None

    def test_save_session_layer_without_a_stage_is_a_noop(self, tmp_path):
        Project(name='n', rootdir=tmp_path).save_session_layer()

    def test_find_or_create_finds_and_creates(self, tmp_path):
        made = Project.find_or_create(name='P', rootdir=tmp_path / 'p')
        found = Project.find_or_create(name='P', rootdir=tmp_path / 'p')
        assert made.metadata_path == found.metadata_path


class TestCollection:
    def test_add_and_remove_child_references(self, tree):
        _, assets, _ = tree
        assets.add_asset('Villain')
        assert (assets.children_metadata_dir / 'Villain.usda').is_file()
        assert 'Villain' in assets.metadata_path.read_text()
        assert assets.remove_child('Villain') is True
        assert assets.remove_child('Villain') is False
        assert 'Villain' not in assets.metadata_path.read_text()

    def test_add_asset_rejects_invalid_names(self, tree):
        _, assets, _ = tree
        with pytest.raises(ValueError):
            assets.add_asset('not valid')

    def test_children_of_a_collection_missing_from_the_stage_are_empty(self, tree):
        _, assets, _ = tree
        assert Collection('Ghost', assets).get_immediate_children() == []

    def test_project_children_come_from_the_default_prim(self, tree):
        project, _, _ = tree
        names = [c['name'] for c in project.get_immediate_children()]
        assert names == ['Assets']
        assert project.get_immediate_children()[0]['type'] in ('Collection', 'Asset')

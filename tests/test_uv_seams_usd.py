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
"""Tests for deda.core.ai.uv_seams._usd: reading meshes and UV layouts from real USD stages."""
import logging
import pickle

import numpy as np
import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, Vt

from deda.core.ai.uv_seams import _usd as usd

QUAD_POINTS = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
QUAD_UV = [(0, 0), (1, 0), (1, 1), (0, 1)]


def new_stage(path, up_axis=UsdGeom.Tokens.y):
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, up_axis)
    return stage


def add_mesh(stage, prim_path, points=QUAD_POINTS, counts=(4,), corners=(0, 1, 2, 3), uv=QUAD_UV, indices=None,
             interpolation='faceVarying', uv_set='st', left_handed=False):
    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(list(counts)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(list(corners)))
    if left_handed:
        mesh.CreateOrientationAttr(UsdGeom.Tokens.leftHanded)
    if uv is not None:
        primvar = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(uv_set, Sdf.ValueTypeNames.TexCoord2fArray, interpolation)
        primvar.Set(Vt.Vec2fArray([Gf.Vec2f(*t) for t in uv]))
        if indices is not None:
            primvar.SetIndices(Vt.IntArray(list(indices)))
    return mesh


def cube_stage(path):
    """A cube whose six faces each have their own UV square, so it has six UV islands."""
    stage = new_stage(path)
    points = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    uv = [(u + 2 * n, v) for n in range(6) for u, v in QUAD_UV]
    add_mesh(stage, '/Cube', points, [4] * 6, [i for quad in quads for i in quad], uv)
    stage.Save()
    return path


class TestListUsdMeshes:
    def test_finds_meshes_that_have_the_uv_set(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        UsdGeom.Scope.Define(stage, '/World')
        add_mesh(stage, '/World/Body')
        add_mesh(stage, '/World/NoUv', uv=None)
        add_mesh(stage, '/World/Other', uv_set='st1')
        stage.Save()
        refs = usd.list_usd_meshes(tmp_path / 'a.usda')
        assert refs == [usd.UsdMeshRef(tmp_path / 'a.usda', '/World/Body')]
        other = usd.list_usd_meshes(str(tmp_path / 'a.usda'), uv_set='st1')
        assert [ref.prim_path for ref in other] == ['/World/Other']

    def test_unsupported_interpolation_is_skipped_quietly(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        add_mesh(stage, '/Flat', uv=[(0, 0)], interpolation='constant')
        stage.Save()
        assert usd.list_usd_meshes(tmp_path / 'a.usda') == []

    def test_inconsistent_mesh_is_skipped_with_a_warning(self, tmp_path, caplog):
        stage = new_stage(tmp_path / 'a.usda')
        add_mesh(stage, '/Good')
        add_mesh(stage, '/Bad', uv=QUAD_UV[:3])
        stage.Save()
        with caplog.at_level(logging.WARNING):
            refs = usd.list_usd_meshes(tmp_path / 'a.usda')
        assert [ref.prim_path for ref in refs] == ['/Good']
        assert '/Bad' in caplog.text

    def test_mesh_without_faces_is_skipped_with_a_warning(self, tmp_path, caplog):
        stage = new_stage(tmp_path / 'a.usda')
        mesh = UsdGeom.Mesh.Define(stage, '/Empty')
        UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'vertex').Set(
            Vt.Vec2fArray([Gf.Vec2f(0, 0)]))
        stage.Save()
        with caplog.at_level(logging.WARNING):
            assert usd.list_usd_meshes(tmp_path / 'a.usda') == []
        assert '/Empty' in caplog.text

    def test_unreadable_file_gives_an_empty_list_and_a_warning(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING):
            assert usd.list_usd_meshes(tmp_path / 'missing.usd') == []
        assert 'cannot open' in caplog.text


class TestLoadUsdMesh:
    def test_cube_loads_as_triangles_with_six_islands(self, tmp_path):
        path = cube_stage(tmp_path / 'cube.usda')
        (ref,) = usd.list_usd_meshes(path)
        vertices, faces, island = usd.load_usd_mesh(ref)
        assert vertices.shape == (8, 3) and vertices.dtype == np.float64
        assert faces.shape == (12, 3) and faces.dtype == np.int64
        assert island.shape == (12,) and island.max() + 1 == 6

    def test_indexed_primvar_is_followed(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        points = QUAD_POINTS + [(2, 0, 0), (2, 1, 0)]
        uv = QUAD_UV + [(2, 0), (2, 1)]
        # Two quads sharing an edge; shared corners reuse the same UV values through the indices.
        add_mesh(stage, '/Strip', points, [4, 4], [0, 1, 2, 3, 1, 4, 5, 2], uv, indices=[0, 1, 2, 3, 1, 4, 5, 2])
        stage.Save()
        _, faces, island = usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Strip'))
        assert len(faces) == 4
        assert island.max() == 0

    def test_vertex_interpolated_primvar(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        add_mesh(stage, '/Quad', interpolation='vertex')
        stage.Save()
        _, faces, island = usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Quad'))
        assert faces.tolist() == [[0, 1, 2], [0, 2, 3]]
        assert island.tolist() == [0, 0]

    def test_z_up_stage_is_rotated_to_y_up(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda', up_axis=UsdGeom.Tokens.z)
        add_mesh(stage, '/Quad', points=[(0, 0, 0), (1, 0, 0), (1, 0, 2), (0, 0, 2)])
        stage.Save()
        vertices, _, _ = usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Quad'))
        assert vertices[2].tolist() == pytest.approx([1.0, 2.0, 0.0])

    def test_left_handed_mesh_has_its_winding_reversed(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        add_mesh(stage, '/Quad', left_handed=True)
        stage.Save()
        _, faces, _ = usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Quad'))
        assert faces.tolist() == [[0, 2, 1], [0, 3, 2]]

    def test_local_space_ignores_parent_transforms_and_world_space_applies_them(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        root = UsdGeom.Xform.Define(stage, '/Root')
        UsdGeom.Xformable(root).AddTranslateOp().Set(Gf.Vec3d(10, 0, 0))
        add_mesh(stage, '/Root/Quad')
        stage.Save()
        ref = usd.UsdMeshRef(tmp_path / 'a.usda', '/Root/Quad')
        local, _, _ = usd.load_usd_mesh(ref)
        world, _, _ = usd.load_usd_mesh(ref, world_space=True)
        assert local[1].tolist() == [1.0, 0.0, 0.0]
        assert world[1].tolist() == pytest.approx([11.0, 0.0, 0.0])

    @pytest.mark.parametrize('left_handed, expected', [(False, [[0, 2, 1], [0, 3, 2]]), (True, [[0, 1, 2], [0, 2, 3]])])
    def test_mirrored_world_transform_flips_winding(self, tmp_path, left_handed, expected):
        stage = new_stage(tmp_path / 'a.usda')
        root = UsdGeom.Xform.Define(stage, '/Root')
        UsdGeom.Xformable(root).AddScaleOp().Set(Gf.Vec3f(-1, 1, 1))
        add_mesh(stage, '/Root/Quad', left_handed=left_handed)
        stage.Save()
        world, faces, _ = usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Root/Quad'), world_space=True)
        assert world[1].tolist() == pytest.approx([-1.0, 0.0, 0.0])
        assert faces.tolist() == expected

    def test_other_uv_set_can_be_chosen(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        add_mesh(stage, '/Quad', uv_set='st1')
        stage.Save()
        ref = usd.UsdMeshRef(tmp_path / 'a.usda', '/Quad')
        _, _, island = usd.load_usd_mesh(ref, uv_set='st1')
        assert island.tolist() == [0, 0]
        with pytest.raises(ValueError, match="no 'st' UV"):
            usd.load_usd_mesh(ref)

    def test_prim_that_is_not_a_mesh_raises(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        UsdGeom.Scope.Define(stage, '/World')
        stage.Save()
        with pytest.raises(ValueError, match='not a mesh'):
            usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/World'))
        with pytest.raises(ValueError, match='not a mesh'):
            usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Nowhere'))

    def test_unopenable_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match='cannot open'):
            usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'missing.usd', '/Quad'))

    def test_mesh_without_points_raises(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        UsdGeom.Mesh.Define(stage, '/Empty')
        stage.Save()
        with pytest.raises(ValueError, match='no points or faces'):
            usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Empty'))

    def test_inconsistent_uvs_raise_with_the_location(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        add_mesh(stage, '/Bad', uv=QUAD_UV[:3])
        stage.Save()
        with pytest.raises(ValueError, match='/Bad'):
            usd.load_usd_mesh(usd.UsdMeshRef(tmp_path / 'a.usda', '/Bad'))


class TestUsdSource:
    def test_serves_one_item_per_mesh(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        add_mesh(stage, '/One')
        add_mesh(stage, '/Two')
        stage.Save()
        source = usd.UsdSource(usd.list_usd_meshes(tmp_path / 'a.usda'))
        assert len(source) == 2
        vertices, faces, island = source.get(1, np.random.default_rng(0))
        assert vertices.shape == (4, 3) and faces.shape == (2, 3) and island.shape == (2,)

    def test_options_reach_the_loader(self, tmp_path):
        stage = new_stage(tmp_path / 'a.usda')
        root = UsdGeom.Xform.Define(stage, '/Root')
        UsdGeom.Xformable(root).AddTranslateOp().Set(Gf.Vec3d(5, 0, 0))
        add_mesh(stage, '/Root/Quad', uv_set='uv0')
        stage.Save()
        refs = usd.list_usd_meshes(tmp_path / 'a.usda', 'uv0')
        vertices, _, _ = usd.UsdSource(refs, 'uv0', world_space=True).get(0, np.random.default_rng(0))
        assert vertices[0].tolist() == pytest.approx([5.0, 0.0, 0.0])

    def test_source_can_be_pickled_for_worker_processes(self, tmp_path):
        path = cube_stage(tmp_path / 'cube.usda')
        source = pickle.loads(pickle.dumps(usd.UsdSource(usd.list_usd_meshes(path), 'st', True)))
        assert len(source) == 1 and source.world_space is True


class TestSplitUsdSources:
    @pytest.fixture
    def files(self, tmp_path):
        paths = []
        for name in ('a', 'b', 'c', 'd'):
            stage = new_stage(tmp_path / f'{name}.usda')
            add_mesh(stage, '/Body')
            add_mesh(stage, '/Head')
            stage.Save()
            paths.append(tmp_path / f'{name}.usda')
        return paths

    def test_meshes_are_split_by_file(self, files):
        train, val = usd.split_usd_sources(files, val_frac=0.25, seed=0)
        assert len(train) == 6 and len(val) == 2
        assert {ref.path for ref in train.refs}.isdisjoint({ref.path for ref in val.refs})

    def test_group_key_keeps_related_files_together(self, files):
        train, val = usd.split_usd_sources(files, 0.5, 0, group_key=lambda p: 'ab' if p.stem in 'ab' else 'cd')
        assert {ref.path for ref in train.refs}.isdisjoint({ref.path for ref in val.refs})
        assert {ref.path.stem for ref in val.refs} in ({'a', 'b'}, {'c', 'd'})

    def test_files_without_usable_meshes_are_skipped(self, files, tmp_path, caplog):
        stage = new_stage(tmp_path / 'empty.usda')
        UsdGeom.Scope.Define(stage, '/World')
        stage.Save()
        with caplog.at_level(logging.WARNING):
            train, val = usd.split_usd_sources([*files, tmp_path / 'empty.usda', tmp_path / 'gone.usd'], 0.25, 0)
        assert len(train) + len(val) == 8
        assert 'empty.usda' in caplog.text

    def test_options_are_stored_on_both_sources(self, files):
        train, val = usd.split_usd_sources(files, 0.25, 0, uv_set='st', world_space=True)
        assert train.world_space and val.world_space and train.uv_set == val.uv_set == 'st'

    def test_no_usable_mesh_raises(self, tmp_path):
        with pytest.raises(ValueError, match='no usable meshes'):
            usd.split_usd_sources([tmp_path / 'gone.usd'], 0.5, 0)

    def test_single_file_cannot_be_split(self, files):
        with pytest.raises(ValueError, match='two groups'):
            usd.split_usd_sources(files[:1], 0.5, 0)

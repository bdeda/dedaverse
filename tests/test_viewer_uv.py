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
"""Tests for deda.core.viewer._uv: reading UV sets from USD meshes and analysing the layout."""
import numpy as np
import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, Vt

from deda.core.viewer import _uv

# Two quads sharing an edge (a 2x1 strip), as separate UV shells or one connected shell.
_COUNTS = [4, 4]
_INDICES = [0, 1, 4, 3, 1, 2, 5, 4]
_POINTS = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0)]


def _make_mesh(stage, path='/m'):
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in _POINTS]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(_COUNTS))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(_INDICES))
    return mesh


def _add_uvs(mesh, values, interpolation, indices=None, name='st', type_name=Sdf.ValueTypeNames.TexCoord2fArray):
    primvar = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(name, type_name, interpolation)
    primvar.Set(Vt.Vec2fArray([Gf.Vec2f(*v) for v in values]))
    if indices is not None:
        primvar.SetIndices(Vt.IntArray(indices))
    return primvar


def _connected_strip():
    """Face-varying UVs for the strip laid out as one connected shell in the 0-1 tile."""
    # Corner order follows _INDICES; shared vertices 1 and 4 carry the same UV in both faces.
    uv_for_vertex = {0: (0, 0), 1: (.5, 0), 2: (1, 0), 3: (0, 1), 4: (.5, 1), 5: (1, 1)}
    values = [uv_for_vertex[v] for v in range(6)]
    return values, list(_INDICES)


@pytest.fixture
def stage():
    return Usd.Stage.CreateInMemory()


class TestUdimTile:
    def test_first_tile(self):
        assert _uv.udim_tile(0.5, 0.5) == 1001

    def test_next_tile_in_u(self):
        assert _uv.udim_tile(1.2, 0.1) == 1002

    def test_next_tile_in_v(self):
        assert _uv.udim_tile(0.2, 1.9) == 1011

    def test_negative_uv(self):
        assert _uv.udim_tile(-0.1, 0.5) == 1000


class TestReadUvLayouts:
    def test_reads_face_varying_set(self, stage):
        mesh = _make_mesh(stage)
        values, indices = _connected_strip()
        _add_uvs(mesh, values, 'faceVarying', indices)
        (layout,) = _uv.read_uv_layouts(mesh.GetPrim())
        assert layout.uv_set.name == 'st'
        assert layout.uv_set.interpolation == 'faceVarying'
        assert layout.face_count == 2
        assert layout.uvs.shape == (8, 2)
        np.testing.assert_allclose(layout.uvs[0], (0, 0))

    def test_reads_multiple_sets_and_float2(self, stage):
        mesh = _make_mesh(stage)
        values, indices = _connected_strip()
        _add_uvs(mesh, values, 'faceVarying', indices, name='st')
        _add_uvs(mesh, values, 'faceVarying', indices, name='lightmap', type_name=Sdf.ValueTypeNames.Float2Array)
        names = [layout.uv_set.name for layout in _uv.read_uv_layouts(mesh.GetPrim())]
        assert sorted(names) == ['lightmap', 'st']

    def test_vertex_interpolation_uses_point_indices(self, stage):
        mesh = _make_mesh(stage)
        values = [(0, 0), (.5, 0), (1, 0), (0, 1), (.5, 1), (1, 1)]
        _add_uvs(mesh, values, 'vertex')
        (layout,) = _uv.read_uv_layouts(mesh.GetPrim())
        np.testing.assert_allclose(layout.uvs[2], values[4])

    def test_unindexed_face_varying(self, stage):
        mesh = _make_mesh(stage)
        _add_uvs(mesh, [(i, i) for i in range(8)], 'faceVarying')
        (layout,) = _uv.read_uv_layouts(mesh.GetPrim())
        np.testing.assert_allclose(layout.uvs[5], (5, 5))

    def test_skips_set_that_does_not_fit(self, stage):
        mesh = _make_mesh(stage)
        _add_uvs(mesh, [(0, 0), (1, 1)], 'faceVarying')
        assert _uv.read_uv_layouts(mesh.GetPrim()) == []

    def test_ignores_non_uv_primvars(self, stage):
        mesh = _make_mesh(stage)
        primvar = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('weights', Sdf.ValueTypeNames.FloatArray, 'vertex')
        primvar.Set(Vt.FloatArray([0.0] * 6))
        assert _uv.read_uv_layouts(mesh.GetPrim()) == []

    def test_set_without_values_is_skipped(self, stage):
        mesh = _make_mesh(stage)
        UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'faceVarying')
        assert _uv.read_uv_layouts(mesh.GetPrim()) == []

    def test_not_a_mesh_gives_nothing(self, stage):
        cube = UsdGeom.Cube.Define(stage, '/c')
        assert _uv.read_uv_layouts(cube.GetPrim()) == []

    def test_mesh_without_topology_gives_nothing(self, stage):
        mesh = UsdGeom.Mesh.Define(stage, '/empty')
        assert _uv.read_uv_layouts(mesh.GetPrim()) == []

    def test_time_sampled_uvs_fall_back_to_earliest(self, stage):
        mesh = _make_mesh(stage)
        primvar = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'faceVarying')
        primvar.Set(Vt.Vec2fArray([Gf.Vec2f(i, 0) for i in range(8)]), Usd.TimeCode(5))
        (layout,) = _uv.read_uv_layouts(mesh.GetPrim())
        np.testing.assert_allclose(layout.uvs[3], (3, 0))


class TestListMeshes:
    def test_finds_only_meshes(self, stage):
        _make_mesh(stage, '/a')
        _make_mesh(stage, '/group/b')
        UsdGeom.Cube.Define(stage, '/cube')
        assert [str(p.GetPath()) for p in _uv.list_meshes(stage)] == ['/a', '/group/b']

    def test_no_stage(self):
        assert _uv.list_meshes(None) == []


class TestFromMesh:
    def _set(self, interpolation, values, indices=None):
        return _uv.UvSet('st', interpolation, np.array(values, dtype=float), indices)

    def test_uniform_gives_one_uv_per_face(self):
        layout = _uv.UvLayout.from_mesh(self._set('uniform', [(0, 0), (1, 1)]), _COUNTS, _INDICES)
        np.testing.assert_allclose(layout.uvs[:4], [(0, 0)] * 4)
        np.testing.assert_allclose(layout.uvs[4:], [(1, 1)] * 4)

    def test_uniform_wrong_length(self):
        assert _uv.UvLayout.from_mesh(self._set('uniform', [(0, 0)]), _COUNTS, _INDICES) is None

    def test_constant(self):
        layout = _uv.UvLayout.from_mesh(self._set('constant', [(.25, .5)]), _COUNTS, _INDICES)
        assert layout.uvs.shape == (8, 2)
        np.testing.assert_allclose(layout.uvs[7], (.25, .5))

    def test_constant_wrong_length(self):
        assert _uv.UvLayout.from_mesh(self._set('constant', [(0, 0), (1, 1)]), _COUNTS, _INDICES) is None

    def test_unknown_interpolation(self):
        assert _uv.UvLayout.from_mesh(self._set('bogus', [(0, 0)] * 8), _COUNTS, _INDICES) is None

    def test_indices_out_of_range(self):
        uv_set = self._set('faceVarying', [(0, 0), (1, 1)], np.array([0, 1, 2, 0, 1, 0, 1, 0]))
        assert _uv.UvLayout.from_mesh(uv_set, _COUNTS, _INDICES) is None

    def test_topology_mismatch(self):
        assert _uv.UvLayout.from_mesh(self._set('faceVarying', [(0, 0)] * 8), [4, 4], [0, 1, 2]) is None

    def test_vertex_set_too_short_for_the_mesh(self):
        assert _uv.UvLayout.from_mesh(self._set('vertex', [(0, 0)] * 3), _COUNTS, _INDICES) is None


def _layout(values, interpolation='faceVarying', indices=None, counts=_COUNTS, verts=_INDICES):
    uv_set = _uv.UvSet('st', interpolation, np.array(values, dtype=float),
                       None if indices is None else np.array(indices))
    layout = _uv.UvLayout.from_mesh(uv_set, counts, verts)
    assert layout is not None
    return layout


def _strip_layout():
    values, indices = _connected_strip()
    return _layout(values, indices=indices)


class TestLayout:
    def test_next_corner_wraps_within_each_face(self):
        layout = _strip_layout()
        assert list(layout.next_corner) == [1, 2, 3, 0, 5, 6, 7, 4]

    def test_bounds(self):
        assert _strip_layout().bounds() == (0.0, 0.0, 1.0, 1.0)

    def test_bounds_without_uvs(self):
        assert _layout([], counts=[], verts=[]).bounds() == (0.0, 0.0, 1.0, 1.0)

    def test_connected_strip_is_one_island(self):
        labels = _strip_layout().island_labels()
        assert list(labels) == [0, 0]

    def test_split_faces_are_two_islands(self):
        # Every corner has its own UV, so no edge is shared between the faces.
        values = [(0, 0), (.4, 0), (.4, 1), (0, 1), (.6, 0), (1, 0), (1, 1), (.6, 1)]
        labels = _layout(values).island_labels()
        assert sorted(set(labels)) == [0, 1]

    def test_faces_touching_at_a_corner_are_separate_islands(self):
        # Faces share only UV vertex 0 -- no common edge.
        values = [(0, 0), (.4, 0), (.4, .4), (0, .4), (-.4, -.4), (-.4, 0), (0, 0), (0, -.4)]
        indices = [0, 1, 2, 3, 4, 5, 0, 7]
        labels = _layout(values, indices=indices).island_labels()
        assert sorted(set(labels)) == [0, 1]

    def test_island_labels_chain_across_many_faces(self):
        # A strip of n quads, each sharing an edge with the next: one island however long.
        n = 40
        verts, counts = [], [4] * n
        for i in range(n):
            verts += [2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1]
        values = [(i // 2, i % 2) for i in range(2 * n + 2)]
        labels = _layout(values, 'vertex', counts=counts, verts=verts).island_labels()
        assert set(labels) == {0}

    def test_island_labels_without_faces(self):
        assert len(_layout([], counts=[], verts=[]).island_labels()) == 0

    def test_signed_areas(self):
        areas = _strip_layout().signed_areas()
        np.testing.assert_allclose(areas, [.5, .5])

    def test_flipped_face_is_found(self):
        values, indices = _connected_strip()
        # Reverse the second face's winding by reversing its corner order.
        indices = indices[:4] + indices[4:][::-1]
        layout = _layout(values, indices=indices)
        assert list(layout.flipped_faces()) == [False, True]

    def test_flips_follow_the_majority(self):
        values, indices = _connected_strip()
        clockwise = indices[:4][::-1] + indices[4:][::-1]
        assert not _layout(values, indices=clockwise).flipped_faces().any()

    def test_degenerate_faces_are_not_flipped(self):
        values = [(0, 0)] * 4 + [(0, 0), (1, 0), (1, 1), (0, 1)]
        layout = _layout(values)
        assert not layout.flipped_faces().any()
        assert layout.stats().degenerate_count == 1

    def test_all_degenerate(self):
        assert not _layout([(0, 0)] * 8).flipped_faces().any()

    def test_edge_segments_are_unique_and_borders_flagged(self):
        segments, is_border = _strip_layout().edge_segments()
        # 7 distinct edges for two quads sharing one; only the shared one is interior.
        assert len(segments) == 7
        assert is_border.sum() == 6
        assert segments.shape == (7, 4)

    def test_edge_segments_empty(self):
        segments, is_border = _layout([], counts=[], verts=[]).edge_segments()
        assert len(segments) == 0 and len(is_border) == 0

    def test_face_centroids(self):
        centroids = _strip_layout().face_centroids()
        np.testing.assert_allclose(centroids, [(.25, .5), (.75, .5)])


class TestStats:
    def test_connected_strip(self):
        stats = _strip_layout().stats()
        assert stats.face_count == 2
        assert stats.island_count == 1
        assert stats.flipped_count == 0
        assert stats.degenerate_count == 0
        assert stats.bounds == (0.0, 0.0, 1.0, 1.0)
        assert stats.tiles == (1001,)
        assert stats.coverage == pytest.approx(1.0)

    def test_faces_in_two_udim_tiles(self):
        values = [(0, 0), (.9, 0), (.9, 1), (0, 1), (1.1, 0), (2, 0), (2, 1), (1.1, 1)]
        stats = _layout(values).stats()
        assert stats.tiles == (1001, 1002)
        assert stats.island_count == 2

    def test_coverage_counts_only_the_first_tile(self):
        values = [(0, 0), (.5, 0), (.5, .5), (0, .5), (1.1, 0), (2, 0), (2, 1), (1.1, 1)]
        assert _layout(values).stats().coverage == pytest.approx(.25)

    def test_no_faces(self):
        stats = _layout([], counts=[], verts=[]).stats()
        assert stats.face_count == 0 and stats.island_count == 0 and stats.tiles == ()

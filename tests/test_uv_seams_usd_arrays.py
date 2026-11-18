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
"""Tests for deda.core.ai.uv_seams._usd_arrays: converting USD polygon data to training arrays (numpy only)."""
from pathlib import Path

import numpy as np
import pytest

from deda.core.ai.uv_seams import _usd_arrays as ua
from deda.core.ai.uv_seams import islands_from_uv

QUAD_POINTS = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float32)
QUAD_UV = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)


def cube():
    """Unit cube as 6 quads, each face with its own UV square at a different offset (6 UV islands)."""
    points = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=np.float32)
    quads = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    counts = [4] * 6
    corners = [i for quad in quads for i in quad]
    uv = np.concatenate([QUAD_UV + [2.0 * n, 0.0] for n in range(6)])
    return points, counts, corners, uv


class TestFindUsdFiles:
    def test_mixes_files_and_directories_from_several_places(self, tmp_path):
        (tmp_path / 'a' / 'deep').mkdir(parents=True)
        (tmp_path / 'b').mkdir()
        wanted = [tmp_path / 'a' / 'one.usd', tmp_path / 'a' / 'deep' / 'two.USDA', tmp_path / 'b' / 'three.usdc']
        for path in wanted + [tmp_path / 'a' / 'readme.txt', tmp_path / 'a' / 'tex.png']:
            path.write_bytes(b'')
        loose = tmp_path / 'loose.usdz'
        loose.write_bytes(b'')
        found = ua.find_usd_files([tmp_path / 'a', str(tmp_path / 'b'), loose])
        assert found == sorted(wanted + [loose])

    def test_duplicates_are_removed(self, tmp_path):
        usd = tmp_path / 'x.usd'
        usd.write_bytes(b'')
        assert ua.find_usd_files([usd, tmp_path, usd]) == [usd]

    def test_explicit_file_is_kept_whatever_its_suffix(self, tmp_path):
        odd = tmp_path / 'asset.bin'
        odd.write_bytes(b'')
        assert ua.find_usd_files([odd]) == [odd]

    def test_missing_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match='nope'):
            ua.find_usd_files([tmp_path / 'nope'])

    def test_empty_directory_gives_empty_list(self, tmp_path):
        assert ua.find_usd_files([tmp_path]) == []


class TestUsdMeshToArrays:
    def test_indexed_face_varying_quad_becomes_two_triangles(self):
        verts, faces, uv, faces_uv = ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [0, 1, 2, 3], QUAD_UV,
                                                           uv_indices=[0, 1, 2, 3])
        assert verts.dtype == np.float64 and verts.shape == (4, 3)
        assert faces.tolist() == [[0, 1, 2], [0, 2, 3]]
        assert faces_uv.tolist() == [[0, 1, 2], [0, 2, 3]]
        assert uv.dtype == np.float64 and faces.dtype == np.int64 and faces_uv.dtype == np.int64

    def test_uv_indices_are_followed_not_assumed(self):
        uv = np.array([[0.5, 0.5], [0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
        _, faces, _, faces_uv = ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [0, 1, 2, 3], uv, [1, 2, 3, 4])
        assert faces.tolist() == [[0, 1, 2], [0, 2, 3]]
        assert faces_uv.tolist() == [[1, 2, 3], [1, 3, 4]]

    def test_unindexed_face_varying_uses_one_value_per_corner(self):
        _, _, _, faces_uv = ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [0, 1, 2, 3], QUAD_UV)
        assert faces_uv.tolist() == [[0, 1, 2], [0, 2, 3]]

    def test_vertex_interpolation_uses_the_point_index(self):
        _, faces, _, faces_uv = ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [3, 2, 1, 0], QUAD_UV,
                                                      uv_interpolation='vertex')
        assert faces.tolist() == faces_uv.tolist() == [[3, 2, 1], [3, 1, 0]]

    def test_indexed_vertex_interpolation_maps_points_through_the_indices(self):
        uv = np.array([[0, 0], [1, 1]], dtype=np.float32)
        _, _, _, faces_uv = ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [0, 1, 2, 3], uv, [0, 1, 1, 0],
                                                  uv_interpolation='varying')
        assert faces_uv.tolist() == [[0, 1, 1], [0, 1, 0]]

    def test_mixed_polygons_are_fan_triangulated_in_order(self):
        points = np.zeros((6, 3), dtype=np.float32)
        counts, corners = [3, 5], [0, 1, 2, 2, 3, 4, 5, 0]
        uv = np.zeros((8, 2), dtype=np.float32)
        _, faces, _, faces_uv = ua.usd_mesh_to_arrays(points, counts, corners, uv)
        assert faces.tolist() == [[0, 1, 2], [2, 3, 4], [2, 4, 5], [2, 5, 0]]
        assert faces_uv.tolist() == [[0, 1, 2], [3, 4, 5], [3, 5, 6], [3, 6, 7]]

    def test_flip_winding_reverses_every_triangle_in_both_arrays(self):
        _, faces, _, faces_uv = ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [0, 1, 2, 3], QUAD_UV, flip_winding=True)
        assert faces.tolist() == faces_uv.tolist() == [[0, 2, 1], [0, 3, 2]]

    def test_cube_with_separate_uv_squares_has_six_islands(self):
        points, counts, corners, uv = cube()
        _, faces, uv_out, faces_uv = ua.usd_mesh_to_arrays(points, counts, corners, uv)
        assert len(faces) == 12
        island = islands_from_uv(uv_out, faces_uv)
        assert island.max() + 1 == 6
        assert island.reshape(6, 2)[:, 0].tolist() == island.reshape(6, 2)[:, 1].tolist()  # both triangles together

    def test_uv_shared_between_two_faces_joins_them_into_one_island(self):
        # Two coplanar quads sharing the edge between points 1 and 2; their UVs continue across it.
        points = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [2, 0, 0], [2, 1, 0]], dtype=np.float32)
        uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [2, 0], [2, 1]], dtype=np.float32)
        corners = [0, 1, 2, 3, 1, 4, 5, 2]
        _, _, uv_out, faces_uv = ua.usd_mesh_to_arrays(points, [4, 4], corners, uv[corners])
        assert islands_from_uv(uv_out, faces_uv).max() == 0

    @pytest.mark.parametrize('interpolation', ['uniform', 'constant', 'bogus'])
    def test_unsupported_interpolation_raises(self, interpolation):
        with pytest.raises(ValueError, match='interpolation'):
            ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [0, 1, 2, 3], QUAD_UV, uv_interpolation=interpolation)

    @pytest.mark.parametrize('counts, corners, match', [
        ([], [], 'at least one face'),
        ([2], [0, 1], '3 or more'),
        ([4], [0, 1, 2], 'sum to 4'),
        ([4], [0, 1, 2, 9], 'do not exist'),
        ([4], [0, 1, 2, -1], 'do not exist'),
    ])
    def test_bad_polygon_data_raises(self, counts, corners, match):
        with pytest.raises(ValueError, match=match):
            ua.usd_mesh_to_arrays(QUAD_POINTS, counts, corners, QUAD_UV)

    @pytest.mark.parametrize('uv, uv_indices, interpolation, match', [
        (QUAD_UV[:3], None, 'faceVarying', 'one value per corner'),
        (QUAD_UV, [0, 1, 2], 'faceVarying', 'one per corner'),
        (QUAD_UV, [0, 1, 2, 4], 'faceVarying', 'do not exist'),
        (QUAD_UV[:3], None, 'vertex', 'one value per point'),
        (QUAD_UV, [0, 1, 2], 'vertex', 'one per point'),
        (QUAD_UV, [0, 1, 2, -1], 'vertex', 'do not exist'),
    ])
    def test_bad_uv_data_raises(self, uv, uv_indices, interpolation, match):
        with pytest.raises(ValueError, match=match):
            ua.usd_mesh_to_arrays(QUAD_POINTS, [4], [0, 1, 2, 3], uv, uv_indices, interpolation)


class TestZUpToYUp:
    def test_axes_are_rotated_without_mirroring(self):
        out = ua.z_up_to_y_up(np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 1.0]]))
        assert out.tolist() == [[1.0, 3.0, -2.0], [0.0, 1.0, 0.0]]

    def test_handedness_is_preserved(self):
        basis = ua.z_up_to_y_up(np.eye(3))
        assert np.linalg.det(basis) == pytest.approx(1.0)

    def test_input_is_not_modified(self):
        points = np.array([[1.0, 2.0, 3.0]])
        ua.z_up_to_y_up(points)
        assert points.tolist() == [[1.0, 2.0, 3.0]]

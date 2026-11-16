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
"""Tests for the game asset optimizer's mesh and UV measurements."""
import numpy as np
import pytest

from deda.plugins.game_asset import _metrics

# A unit quad made of two triangles: verts 0-1-2-3 counter-clockwise, faces (0,1,2) and (0,2,3).
QUAD = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
LOOP_VERTS = np.array([0, 1, 2, 0, 2, 3])
FACE_STARTS = np.array([0, 3])
TRI_LOOPS = np.array([[0, 1, 2], [3, 4, 5]])


def quad_metrics(uvs, positions=QUAD, raster=64):
    return _metrics.uv_metrics(positions, LOOP_VERTS, np.asarray(uvs, dtype=float), FACE_STARTS, TRI_LOOPS,
                               raster=raster)


class TestUvMetrics:
    def test_connected_planar_layout(self):
        uvs = QUAD[LOOP_VERTS][:, :2] * 0.5          # same shape as 3D, quarter of the UV square
        m = quad_metrics(uvs)
        assert m['uv_islands'] == 1
        assert m['gpu_verts'] == 4
        assert m['uv_coverage'] == pytest.approx(0.25, abs=0.02)
        assert m['overlap'] == 0
        assert m['area_distortion'] == pytest.approx(0, abs=1e-9)
        assert m['angle_distortion_deg'] == pytest.approx(0, abs=1e-6)
        assert m['out_of_bounds'] is False

    def test_split_layout_has_two_islands_and_more_gpu_verts(self):
        uvs = QUAD[LOOP_VERTS][:, :2] * 0.4
        uvs[3:] += 0.5                               # move the second triangle away: its corners no longer match
        m = quad_metrics(uvs)
        assert m['uv_islands'] == 2
        assert m['gpu_verts'] == 6

    def test_overlap_distortion_and_bounds(self):
        uvs = np.array([[0, 0], [1, 0], [1, 1], [0, 0], [1, 0], [1.5, 1]])   # second tri lands on the first
        m = quad_metrics(uvs)
        assert m['overlap'] > 0.3
        assert m['angle_distortion_deg'] > 1
        assert m['out_of_bounds'] is True

    def test_uneven_texel_density(self):
        uvs = QUAD[LOOP_VERTS][:, :2] * 0.5
        uvs[3:] = uvs[3:] * 0.5                      # second triangle gets a quarter of the texels
        assert quad_metrics(uvs)['area_distortion'] > 0.5

    def test_degenerate_and_offscreen_triangles_are_skipped(self):
        uvs = np.array([[2, 2], [3, 2], [3, 3], [0, 0], [0, 0], [0, 0]])
        m = quad_metrics(uvs)
        assert m['uv_coverage'] == 0 and m['overlap'] == 0
        assert m['area_distortion'] == 0 and m['angle_distortion_deg'] == 0

    def test_collinear_triangles_cover_nothing(self):
        uvs = np.array([[0.1, 0.1], [0.5, 0.5], [0.9, 0.9], [0.1, 0.9], [0.5, 0.5], [0.9, 0.1]])
        m = quad_metrics(uvs)
        assert m['uv_coverage'] == 0 and m['overlap'] == 0
        assert m['area_distortion'] == 0 and m['angle_distortion_deg'] == 0

    def test_tiny_triangle_inside_one_texel(self):
        uvs = np.array([[0.5, 0.5], [0.5001, 0.5], [0.5, 0.5001]] * 2)
        assert quad_metrics(uvs, raster=8)['uv_coverage'] == 0

    def test_empty_mesh(self):
        m = _metrics.uv_metrics(np.zeros((0, 3)), np.zeros(0, int), np.zeros((0, 2)), np.zeros(0, int),
                                np.zeros((0, 3), int))
        assert m['uv_islands'] == 0 and m['gpu_verts'] == 0 and m['out_of_bounds'] is False


class TestBakeDistances:
    def test_scales_with_error(self):
        extrusion, ray = _metrics.bake_distances(0.02, 1.0)
        assert ray == pytest.approx(0.05) and extrusion == pytest.approx(0.05 / 3)

    def test_clamped_to_size(self):
        assert _metrics.bake_distances(0.0, 2.0)[1] == pytest.approx(0.02)
        assert _metrics.bake_distances(5.0, 2.0)[1] == pytest.approx(0.16)


class TestErrorStats:
    def test_percent_of_diagonal_ignoring_nan(self):
        stats = _metrics.error_stats(np.array([0.0, 0.01, 0.02, np.nan]), 2.0)
        assert stats['mean_pct'] == pytest.approx(0.5)
        assert stats['max_pct'] == pytest.approx(1.0)
        assert 0.5 < stats['p99_pct'] <= 1.0

    @pytest.mark.parametrize('distances, diagonal', [([], 1.0), ([np.nan], 1.0), ([0.1], 0.0)])
    def test_nothing_to_measure(self, distances, diagonal):
        assert _metrics.error_stats(np.array(distances), diagonal) == {'mean_pct': 0.0, 'p99_pct': 0.0,
                                                                        'max_pct': 0.0}


class TestFlipGreen:
    def test_inverts_only_green_and_copies(self):
        pixels = np.array([0.1, 0.2, 0.3, 1.0, 0.5, 0.9, 0.5, 1.0], dtype=np.float32)
        flipped = _metrics.flip_green(pixels)
        np.testing.assert_allclose(flipped, [0.1, 0.8, 0.3, 1.0, 0.5, 0.1, 0.5, 1.0], rtol=1e-6)
        assert pixels[1] == pytest.approx(0.2)

    def test_rgb_buffers(self):
        np.testing.assert_allclose(_metrics.flip_green(np.zeros((2, 2, 3)), channels=3)[..., 1], 1.0)

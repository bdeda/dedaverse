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
"""Tests for the game asset optimizer options and result types."""
import pytest

from deda.plugins.game_asset._options import OptimizeError, OptimizeOptions, OptimizeResult


class TestOptimizeOptions:
    def test_defaults_are_valid(self):
        options = OptimizeOptions()
        options.validate()
        assert options.margin_fraction == pytest.approx(8 / 2048)

    def test_dict_round_trip_ignores_unknown_keys(self):
        data = OptimizeOptions(target_tris=5000, normal_convention='directx').to_dict()
        data['from_the_future'] = 1
        options = OptimizeOptions.from_dict(data)
        assert options.target_tris == 5000 and options.normal_convention == 'directx'

    def test_from_dict_validates(self):
        with pytest.raises(OptimizeError, match='target_tris'):
            OptimizeOptions.from_dict({'target_tris': 3})

    @pytest.mark.parametrize('change, message', [
        ({'target_tris': 11}, 'target_tris'),
        ({'texture_size': 1000}, 'texture_size'),
        ({'normal_convention': 'vulkan'}, 'normal_convention'),
        ({'uv_method': 'cylinder'}, 'uv_method'),
        ({'margin_px': -1}, 'margin_px'),
        ({'margin_px': 300}, 'margin_px'),
        ({'seam_smooth_iterations': -1}, 'seam_smooth_iterations'),
        ({'seam_angle': 0.5}, 'seam_angle'),
        ({'seam_angle': 90}, 'seam_angle'),
        ({'merge_distance': -0.1}, 'merge_distance'),
        ({'bake_samples': 0}, 'bake_samples'),
        ({'export_fbx': False, 'export_glb': False}, 'export_fbx'),
    ])
    def test_invalid_values_are_named(self, change, message):
        with pytest.raises(OptimizeError, match=message):
            OptimizeOptions(**change).validate()


class TestOptimizeResult:
    def test_round_trip_and_summary(self):
        result = OptimizeResult(source='a.usdz', output_dir='out', meshes=['out/a.fbx'],
                                stats={'source': {'tris': 700000},
                                       'game': {'tris': 12000, 'gpu_verts': 7600, 'uv_islands': 200},
                                       'surface_error': {'mean_pct': 0.01}})
        data = result.to_dict()
        data['extra'] = True
        again = OptimizeResult.from_dict(data)
        assert again == result
        assert again.summary() == ('700000 -> 12000 tris, 7600 GPU verts, 200 UV islands, '
                                   'mean error 0.01% of size')

    def test_summary_without_stats(self):
        assert OptimizeResult(source='a', output_dir='b').summary().startswith('? -> ? tris')

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
"""Tests for the orchestration of the Blender-side pipeline, with every bpy step patched.

The bpy steps themselves are exercised in a real Blender by tests/test_game_asset_blender.py.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from deda.plugins.game_asset import _blender_job as job
from deda.plugins.game_asset._options import OptimizeError, OptimizeOptions

ARRAYS = {'positions': np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float),
          'loop_vertices': np.array([0, 1, 2]), 'loop_uvs': np.array([[0, 0], [1, 0], [0, 1]], dtype=float),
          'face_loop_starts': np.array([0]), 'tri_loops': np.array([[0, 1, 2]])}
UV_REPORT = {'requested': 'auto', 'method': 'symmetry', 'projected_pct': 71.2, 'mirror_error_pct': 0.4}
BPY_STEPS = ('_reset_scene', '_import_source', '_diagonal', '_mesh_stats', '_make_low', '_unwrap',
             '_surface_distances', '_mesh_arrays', '_configure_cycles', '_bake_maps', '_assign_game_material',
             '_save_textures', '_export_glb', '_flip_normal_map', '_export_fbx', '_save_blend')


@pytest.fixture
def steps(tmp_path):
    """Patch every bpy step; attach them to one parent mock so call order can be checked."""
    parent = MagicMock()
    patchers = [patch.object(job, name, getattr(parent, name)) for name in BPY_STEPS]
    for p in patchers:
        p.start()
    parent._diagonal.return_value = 2.0
    parent._unwrap.return_value = UV_REPORT
    parent._mesh_stats.side_effect = [{'tris': 50000, 'verts': 30000, 'materials': 1},
                                      {'tris': 1000, 'verts': 600, 'materials': 1}]
    parent._surface_distances.return_value = np.array([0.001, 0.004, np.nan])
    parent._mesh_arrays.return_value = ARRAYS
    parent._configure_cycles.return_value = 'OPTIX'
    parent._bake_maps.return_value = {'basecolor': 'bc', 'normal': 'n', 'orm': 'orm'}
    parent._save_textures.side_effect = lambda images, out, name: {k: str(out / f'{k}.png') for k in images}
    parent._export_glb.side_effect = lambda low, path: path
    parent._export_fbx.side_effect = lambda low, path: path
    parent._save_blend.side_effect = lambda path: path
    yield parent
    for p in patchers:
        p.stop()


def call_order(parent) -> list[str]:
    return [c[0] for c in parent.mock_calls if '.' not in c[0] and c[0].startswith('_')]


class TestRun:
    def test_full_pipeline(self, steps, tmp_path):
        out = tmp_path / 'out'
        result = job.run(tmp_path / 'axe.usdz', out, OptimizeOptions(target_tris=1000))
        assert result.meshes == [str(out / 'axe.glb'), str(out / 'axe.fbx')]
        assert result.textures == {k: str(out / f'{k}.png') for k in ('basecolor', 'normal', 'orm')}
        assert result.stats['source']['tris'] == 50000
        assert result.stats['game']['tris'] == 1000 and result.stats['game']['uv_islands'] == 1
        assert result.stats['surface_error']['max_pct'] == pytest.approx(0.2)
        assert result.stats['bake']['device'] == 'OPTIX'
        assert result.stats['uv'] == UV_REPORT
        assert result.stats['bake']['max_ray_distance'] == pytest.approx(0.02)   # clamped to 1% of size
        assert set(result.timings) == {'import', 'reduce', 'unwrap', 'measure', 'bake', 'export'}
        assert not result.warnings and not result.blend
        report = json.loads((out / 'axe_report.json').read_text(encoding='utf-8'))
        assert report['meshes'] == result.meshes and result.report == str(out / 'axe_report.json')
        steps._flip_normal_map.assert_not_called()
        steps._save_blend.assert_not_called()

    def test_directx_flips_after_glb_and_before_fbx(self, steps, tmp_path):
        job.run(tmp_path / 'axe.usdz', tmp_path, OptimizeOptions(normal_convention='directx', keep_blend=True))
        order = call_order(steps)
        assert order.index('_export_glb') < order.index('_flip_normal_map') < order.index('_export_fbx')
        steps._flip_normal_map.assert_called_once_with('n', Path(str(tmp_path / 'normal.png')))
        steps._save_blend.assert_called_once_with(tmp_path / 'axe.blend')

    def test_name_option_and_single_export(self, steps, tmp_path):
        result = job.run(tmp_path / 'axe.usdz', tmp_path, OptimizeOptions(name='SM_Axe', export_glb=False))
        assert result.meshes == [str(tmp_path / 'SM_Axe.fbx')]
        steps._make_low.assert_called_once()
        assert steps._make_low.call_args[0][1] == 'SM_Axe'

    def test_source_within_budget_warns(self, steps, tmp_path):
        steps._mesh_stats.side_effect = [{'tris': 800, 'verts': 500, 'materials': 1},
                                         {'tris': 800, 'verts': 500, 'materials': 1}]
        steps._surface_distances.return_value = np.zeros(0)
        result = job.run(tmp_path / 'small.obj', tmp_path, OptimizeOptions(target_tris=1000, export_fbx=False))
        assert 'already within' in result.warnings[0]
        assert result.meshes == [str(tmp_path / 'small.glb')]


class TestMain:
    def write_job(self, tmp_path, **options) -> Path:
        path = tmp_path / 'job.json'
        path.write_text(json.dumps({'source': str(tmp_path / 'a.usdz'), 'output_dir': str(tmp_path / 'out'),
                                    'options': options, 'result': str(tmp_path / 'result.json')}),
                        encoding='utf-8')
        return path

    def test_success_writes_result(self, steps, tmp_path):
        path = self.write_job(tmp_path, target_tris=1000)
        assert job.main(['blender', '--background', '--', str(path)]) == 0
        result = json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))
        assert result['stats']['game']['tris'] == 1000

    def test_failure_writes_error_and_traceback(self, steps, tmp_path):
        steps._import_source.side_effect = OptimizeError('a.usdz contains no mesh')
        path = self.write_job(tmp_path)
        assert job.main(['blender', '--', str(path)]) == 1
        result = json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))
        assert result['error'] == 'OptimizeError: a.usdz contains no mesh'
        assert 'Traceback' in result['traceback']

    def test_invalid_options_are_reported(self, tmp_path):
        path = self.write_job(tmp_path, texture_size=7)
        assert job.main(['blender', '--', str(path)]) == 1
        assert 'texture_size' in json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))['error']

    def test_usage_without_job(self, capsys):
        with patch.object(job.sys, 'argv', ['blender', '--background']):
            assert job.main() == 2
        assert 'usage' in capsys.readouterr().err


class TestHelpers:
    def test_job_args(self):
        assert job._job_args(['blender', '-b', '--', 'job.json', 'x']) == ['job.json', 'x']
        assert job._job_args(['blender']) == []

    def test_texture_path(self, tmp_path):
        assert job._texture_path(tmp_path, 'Axe', 'orm') == tmp_path / 'T_Axe_ORM.png'

    def test_timed_records_even_on_error(self):
        timings = {}
        with pytest.raises(ValueError):
            with job._timed(timings, 'step'):
                raise ValueError('x')
        assert timings['step'] >= 0

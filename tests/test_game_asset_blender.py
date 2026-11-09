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
"""Run the game asset pipeline in a real Blender on a small generated mesh.

These tests exercise the bpy code in deda/plugins/game_asset/_blender_job.py that unit tests cannot reach.
They are skipped when Blender is not installed (e.g. in CI); set DEDAVERSE_BLENDER to pick a specific one.
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from deda.core.finder import find_blender
from deda.plugins.game_asset import OptimizeOptions, optimize

pytestmark = [pytest.mark.blender, pytest.mark.slow,
              pytest.mark.skipif(find_blender() is None, reason='Blender is not installed')]


def write_bumpy_sphere(directory: Path, rings: int = 24, segments: int = 48, flatten: float = 1.0) -> Path:
    """Write a textured, bumpy UV sphere (~2.2k triangles) as OBJ + MTL + PNG, like a small generated mesh.

    ``flatten`` scales Z, so a small value makes a flat disc (a stand-in for a blade or shield).
    """
    rng = np.random.default_rng(1)
    texture = (rng.random((64, 64, 3)) * 255).astype(np.uint8)
    texture[::8] = (200, 40, 40)
    Image.fromarray(texture).save(directory / 'albedo.png')
    (directory / 'sphere.mtl').write_text('newmtl skin\nKd 1 1 1\nNs 200\nmap_Kd albedo.png\n')

    lines = ['mtllib sphere.mtl', 'o Sphere']
    for r in range(rings + 1):
        theta = math.pi * r / rings
        for s in range(segments + 1):
            phi = 2 * math.pi * s / segments
            radius = 1.0 + 0.04 * math.sin(7 * phi) * math.sin(5 * theta)
            lines.append(f'v {radius * math.sin(theta) * math.cos(phi):.6f} {radius * math.cos(theta):.6f} '
                         f'{flatten * radius * math.sin(theta) * math.sin(phi):.6f}')
            lines.append(f'vt {s / segments:.6f} {1 - r / rings:.6f}')
    lines.append('usemtl skin')
    width = segments + 1
    for r in range(rings):
        for s in range(segments):
            a, b = r * width + s + 1, r * width + s + 2
            c, d = (r + 1) * width + s + 2, (r + 1) * width + s + 1
            lines.append(f'f {a}/{a} {d}/{d} {c}/{c}')
            lines.append(f'f {a}/{a} {c}/{c} {b}/{b}')
    path = directory / 'sphere.obj'
    path.write_text('\n'.join(lines) + '\n')
    return path


@pytest.fixture(scope='module')
def sphere(tmp_path_factory) -> Path:
    return write_bumpy_sphere(tmp_path_factory.mktemp('sphere'))


@pytest.fixture(scope='module')
def disc(tmp_path_factory) -> Path:
    return write_bumpy_sphere(tmp_path_factory.mktemp('disc'), flatten=0.15)


def test_reduces_unwraps_bakes_and_exports(sphere, tmp_path):
    options = OptimizeOptions(target_tris=400, texture_size=256, normal_convention='directx', use_gpu=False,
                              bake_samples=1, keep_blend=True)
    result = optimize(sphere, tmp_path / 'out', options)

    game = result.stats['game']
    assert result.stats['source']['tris'] == 24 * 48 * 2
    assert 300 <= game['tris'] <= 420
    assert game['uv_islands'] >= 1 and not game['out_of_bounds'] and game['overlap'] < 0.02
    assert result.stats['surface_error']['mean_pct'] < 1.0
    assert result.stats['bake']['device'] == 'CPU'
    assert result.stats['uv']['method'] == 'seams'   # a ball is not flat: auto keeps seams
    assert [Path(m).suffix for m in result.meshes] == ['.glb', '.fbx']
    assert Path(result.meshes[0]).read_bytes()[:4] == b'glTF'
    assert Path(result.blend).is_file()
    for key in ('basecolor', 'normal', 'orm'):
        with Image.open(result.textures[key]) as image:
            assert image.size == (256, 256)
    with Image.open(result.textures['basecolor']) as image:
        assert np.asarray(image.convert('RGB')).std() > 5  # the texture was baked, not left blank
    assert json.loads(Path(result.report).read_text(encoding='utf-8'))['meshes'] == result.meshes


def test_mesh_within_budget_is_kept(sphere, tmp_path):
    options = OptimizeOptions(target_tris=100000, texture_size=256, use_gpu=False, bake_samples=1,
                              export_fbx=False, name='kept')
    result = optimize(sphere, tmp_path, options)
    # Not decimated; only welding the OBJ's split pole vertices drops the 2 x 48 degenerate pole triangles.
    assert result.stats['game']['tris'] == result.stats['source']['tris'] - 2 * 48
    assert 'already within' in result.warnings[0]
    assert [Path(m).name for m in result.meshes] == ['kept.glb']


def test_flat_asset_gets_planar_projection_per_side(disc, tmp_path):
    options = OptimizeOptions(target_tris=600, texture_size=256, use_gpu=False, bake_samples=1, export_fbx=False)
    result = optimize(disc, tmp_path, options)
    uv, game = result.stats['uv'], result.stats['game']
    assert uv['method'] == 'symmetry' and uv['projected_pct'] > 55
    assert uv['faces']['front'] > 0 and uv['faces']['back'] > 0
    # The disc's bumps (sin 7phi) are not mirror-symmetric and 600 triangles sample them coarsely, so a few
    # percent is expected (2.0% measured); the AI-generated axe measured 0.43%.
    assert 0.0 <= uv['mirror_error_pct'] < 5.0
    # Front, back and a few rim strips; slivers merged away.
    assert game['uv_islands'] <= 12 and not game['out_of_bounds'] and game['overlap'] < 0.02

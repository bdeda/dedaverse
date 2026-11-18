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
"""Tests for the deda.core.ai.uv_seams package: public API and lazily loaded PyTorch and USD names."""
import types

import numpy as np
import pytest

import deda.core.ai.uv_seams as uv_seams


class TestPublicApi:
    def test_every_listed_name_exists(self):
        for name in uv_seams.__all__:
            assert hasattr(uv_seams, name), name

    def test_all_has_no_duplicates(self):
        assert len(uv_seams.__all__) == len(set(uv_seams.__all__))

    def test_end_to_end_without_torch(self):
        rng = np.random.default_rng(0)
        verts, faces, island = uv_seams.make_synthetic_box(3, rng)
        sample = uv_seams.prepare_sample(verts, faces, island)
        labels = uv_seams.decode_islands(sample.seam, sample.pairs, sample.num_faces)
        assert labels.max() + 1 == 6


class TestLazyNames:
    @pytest.mark.parametrize('name, module', [('SeamNet', '_model'), ('SeamPrediction', '_trainer'),
                                              ('evaluate', '_trainer'), ('predict', '_trainer'),
                                              ('train', '_trainer'), ('UsdSource', '_usd'),
                                              ('UsdMeshRef', '_usd'), ('list_usd_meshes', '_usd'),
                                              ('load_usd_mesh', '_usd'), ('split_usd_sources', '_usd')])
    def test_name_is_loaded_from_the_right_module(self, monkeypatch, name, module):
        requested = []
        sentinel = object()

        def fake_import(target, package=None):
            requested.append((target, package))
            return types.SimpleNamespace(**{name: sentinel})

        monkeypatch.setattr(uv_seams, 'importlib', types.SimpleNamespace(import_module=fake_import))
        assert getattr(uv_seams, name) is sentinel
        assert requested == [(f'.{module}', 'deda.core.ai.uv_seams')]

    def test_unknown_names_raise_attribute_error(self):
        with pytest.raises(AttributeError, match='no attribute'):
            uv_seams.not_a_real_name  # pylint: disable=pointless-statement

    def test_missing_torch_surfaces_as_import_error(self, monkeypatch):
        def no_torch(target, package=None):
            raise ModuleNotFoundError("No module named 'torch'", name='torch')

        monkeypatch.setattr(uv_seams, 'importlib', types.SimpleNamespace(import_module=no_torch))
        with pytest.raises(ModuleNotFoundError):
            uv_seams.train  # pylint: disable=pointless-statement

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
"""More Trellis API client tests: connection checks, gradio wrappers and the GLB to USD conversion."""
import sys
import types

import numpy as np
import pytest
import requests
from pxr import Usd

from deda.plugins.trellis import _api_client
from deda.plugins.trellis._api_client import TrellisApiClient


def client():
    return TrellisApiClient(client_factory=lambda url: object())


class TestConnection:
    @pytest.mark.parametrize('status, expected', [(200, True), (500, False)])
    def test_check_connection_by_status(self, monkeypatch, status, expected):
        monkeypatch.setattr(requests, 'get', lambda url, timeout: types.SimpleNamespace(status_code=status))
        assert client().check_connection() is expected

    def test_unreachable_server_is_false(self, monkeypatch):
        def refuse(url, timeout):
            raise requests.ConnectionError('refused')

        monkeypatch.setattr(requests, 'get', refuse)
        assert client().check_connection() is False

    def test_reset_session_drops_the_gradio_client(self):
        built = []
        api = TrellisApiClient(client_factory=lambda url: built.append(url) or object())
        first = api._session()
        assert api._session() is first
        api.reset_session()
        assert api._session() is not first and len(built) == 2


class TestGradioWrappers:
    @pytest.fixture
    def fake_gradio(self, monkeypatch):
        module = types.ModuleType('gradio_client')
        module.handle_file = lambda path: ('handled', path)
        module.Client = lambda url, verbose=False: ('client', url, verbose)
        monkeypatch.setitem(sys.modules, 'gradio_client', module)
        return module

    def test_handle_file_and_client_factory(self, fake_gradio):
        assert _api_client._handle_file('a.png') == ('handled', 'a.png')
        assert _api_client._gradio_client_factory('http://h') == ('client', 'http://h', False)

    def test_default_factory_is_used_when_gradio_is_installed(self, fake_gradio):
        assert TrellisApiClient()._session() == ('client', 'http://127.0.0.1:7860', False)

    def test_factory_reports_a_missing_gradio_client(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'gradio_client', None)
        with pytest.raises(ImportError, match='trellis'):
            _api_client._gradio_client_factory('http://h')

    def test_unmatched_endpoint_names_are_not_found(self):
        class Api:
            def view_api(self, return_format, print_info):
                return {'named_endpoints': {'/preprocess_image_x': {}, '/other': {}}}

        assert client()._find_endpoint(Api(), 'preprocess_image') is None


class TestExtractUsd:
    def test_extract_usd_converts_the_glb(self, tmp_path, monkeypatch):
        glb = tmp_path / 'm.glb'
        glb.write_bytes(b'glb')

        class Api:
            def predict(self, *args, api_name):
                return [str(glb)]

        api = TrellisApiClient(client_factory=lambda url: Api())
        api._session()
        monkeypatch.setattr(api, '_glb_to_usd', lambda data: b'usd:' + data)
        assert api.extract_usd({'seed': 1}) == b'usd:glb'

    def test_empty_glb_is_rejected(self, monkeypatch):
        api = client()
        monkeypatch.setattr(api, 'extract_glb', lambda *a: b'')
        with pytest.raises(ValueError):
            api.extract_usd({'seed': 1})

    def stage_from(self, data, tmp_path):
        path = tmp_path / 'out.usd'
        path.write_bytes(data)
        return Usd.Stage.Open(str(path))

    def test_without_trimesh_an_empty_model_prim_is_written(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, 'trimesh', None)
        stage = self.stage_from(client()._glb_to_usd(b'glb'), tmp_path)
        assert stage.GetDefaultPrim().GetPath() == '/Model'
        assert stage.GetDefaultPrim().GetMetadata('comment')

    @pytest.fixture
    def fake_trimesh(self, monkeypatch):
        module = types.ModuleType('trimesh')

        class Trimesh:
            def __init__(self, with_uv=True, with_material=True, normals_on_visual=True):
                self.vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
                self.faces = np.array([[0, 1, 2]])
                normals = np.array([[0, 0, 1]] * 3, dtype=float)
                self.visual = types.SimpleNamespace()
                if normals_on_visual:
                    self.visual.vertex_normals = normals
                else:
                    self.vertex_normals = normals
                if with_uv:
                    self.visual.uv = np.array([[0, 0], [1, 0], [0, 1]], dtype=float)
                if with_material:
                    self.visual.material = types.SimpleNamespace(main_color=[1.0, 0.5, 0.25, 1.0],
                                                                 baseColorTexture=object())

        class Scene:
            def __init__(self, geometry):
                self.geometry = geometry

        module.Trimesh, module.Scene = Trimesh, Scene
        module.state = types.SimpleNamespace(result=None)
        module.load = lambda path, file_type: module.state.result
        monkeypatch.setitem(sys.modules, 'trimesh', module)
        return module

    def test_scene_meshes_become_mesh_prims_with_uvs_normals_and_materials(self, fake_trimesh, tmp_path):
        fake_trimesh.state.result = fake_trimesh.Scene({'a': fake_trimesh.Trimesh(), 'junk': object()})
        stage = self.stage_from(client()._glb_to_usd(b'glb'), tmp_path)
        mesh = stage.GetPrimAtPath('/Model/Mesh_0')
        assert mesh.IsValid() and len(mesh.GetAttribute('points').Get()) == 3
        assert mesh.HasAttribute('primvars:st') and mesh.HasAttribute('primvars:normals')
        assert stage.GetPrimAtPath('/Model/Material_0/Shader').IsValid()
        assert mesh.GetRelationship('material:binding').GetTargets()

    def test_single_mesh_with_alternative_normals_and_no_extras(self, fake_trimesh, tmp_path):
        fake_trimesh.state.result = fake_trimesh.Trimesh(with_uv=False, with_material=False, normals_on_visual=False)
        stage = self.stage_from(client()._glb_to_usd(b'glb'), tmp_path)
        mesh = stage.GetPrimAtPath('/Model/Mesh_0')
        assert mesh.HasAttribute('primvars:normals') and not mesh.HasAttribute('primvars:st')

    def test_unknown_loader_result_gives_an_empty_model(self, fake_trimesh, tmp_path):
        fake_trimesh.state.result = object()
        stage = self.stage_from(client()._glb_to_usd(b'glb'), tmp_path)
        assert not stage.GetPrimAtPath('/Model/Mesh_0').IsValid()

    def test_conversion_failures_are_re_raised(self, fake_trimesh):
        def boom(path, file_type):
            raise RuntimeError('corrupt glb')

        fake_trimesh.load = boom
        with pytest.raises(RuntimeError, match='corrupt'):
            client()._glb_to_usd(b'glb')

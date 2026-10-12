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
"""Tests for the TRELLIS.2 client, using a fake Gradio client (no gradio or GPU needed)."""
import pytest

from deda.plugins.trellis import _api_client
from deda.plugins.trellis._api_client import TrellisApiClient


class FakeGradioClient:
    """Records predict() calls and answers like the TRELLIS.2 server does."""

    def __init__(self, glb_path=None, endpoints=('/preprocess_image_1', '/image_to_3d', '/extract_glb')):
        self.calls = []
        self._glb_path = glb_path
        self._endpoints = endpoints

    def view_api(self, return_format='dict', print_info=True):
        return {'named_endpoints': {name: {} for name in self._endpoints}}

    def predict(self, *args, api_name=None):
        self.calls.append((api_name, args))
        if api_name == '/image_to_3d':
            return '<div>preview</div>'  # the State output is not returned to API clients
        if api_name == '/extract_glb':
            return [str(self._glb_path), str(self._glb_path)]
        if api_name and api_name.startswith('/preprocess_image'):
            return 'processed.png'
        raise AssertionError(f'unexpected endpoint {api_name}')


@pytest.fixture
def image(tmp_path):
    path = tmp_path / 'in.png'
    path.write_bytes(b'png')
    return path


@pytest.fixture
def glb(tmp_path):
    path = tmp_path / 'out.glb'
    path.write_bytes(b'glTF-bytes')
    return path


@pytest.fixture(autouse=True)
def no_upload(monkeypatch):
    """Replace gradio_client.handle_file so the tests do not need gradio_client."""
    monkeypatch.setattr(_api_client, '_handle_file', lambda path: f'file:{path}')


def make_client(fake):
    return TrellisApiClient('http://127.0.0.1:7860/', client_factory=lambda url: fake)


def test_base_url_is_normalised():
    assert make_client(FakeGradioClient()).base_url == 'http://127.0.0.1:7860'


def test_generate_sends_server_argument_order(image):
    fake = FakeGradioClient()
    result = make_client(fake).generate_3d_from_image(
        image, seed=7, randomize_seed=False, resolution='512', ss_sampling_steps=5, tex_guidance_strength=2.0)
    api_name, args = fake.calls[-1]
    assert api_name == '/image_to_3d'
    # image, seed, resolution, ss(4), shape(4), tex(4): the order of TRELLIS.2's image_to_3d
    assert len(args) == 15
    assert args[0] == 'file:processed.png'
    assert args[1:3] == (7, '512')
    assert args[5] == 5          # ss_sampling_steps
    assert args[11] == 2.0       # tex_guidance_strength
    assert result['seed'] == 7
    assert result['state']
    assert result['preview_html'] == '<div>preview</div>'


def test_randomize_seed_ignores_given_seed(image):
    fake = FakeGradioClient()
    make_client(fake).generate_3d_from_image(image, seed=7, randomize_seed=True)
    assert 0 <= fake.calls[-1][1][1] <= _api_client.MAX_SEED


def test_preprocess_endpoint_name_is_looked_up(image):
    """Gradio suffixes duplicate function names, so ``/preprocess_image_1`` must be found."""
    fake = FakeGradioClient(endpoints=('/preprocess_image_2', '/image_to_3d'))
    make_client(fake).generate_3d_from_image(image)
    assert fake.calls[0][0] == '/preprocess_image_2'


def test_missing_preprocess_endpoint_still_generates(image):
    fake = FakeGradioClient(endpoints=('/image_to_3d',))
    make_client(fake).generate_3d_from_image(image)
    assert [name for name, _ in fake.calls] == ['/image_to_3d']
    assert fake.calls[0][1][0] == f'file:{image}'


def test_preprocess_can_be_skipped(image):
    fake = FakeGradioClient()
    make_client(fake).generate_3d_from_image(image, preprocess=False)
    assert [name for name, _ in fake.calls] == ['/image_to_3d']


def test_generate_validates_input(tmp_path, image):
    client = make_client(FakeGradioClient())
    with pytest.raises(FileNotFoundError):
        client.generate_3d_from_image(tmp_path / 'missing.png')
    with pytest.raises(ValueError):
        client.generate_3d_from_image(image, resolution='4096')


def test_extract_glb_returns_file_bytes(image, glb):
    fake = FakeGradioClient(glb_path=glb)
    client = make_client(fake)
    state = client.generate_3d_from_image(image)['state']
    assert client.extract_glb(state, decimation_target=200000, texture_size=1024) == b'glTF-bytes'
    assert fake.calls[-1] == ('/extract_glb', (200000, 1024))


def test_extract_glb_needs_a_generated_model_in_this_session(image, glb):
    client = make_client(FakeGradioClient(glb_path=glb))
    with pytest.raises(RuntimeError):
        client.extract_glb({'seed': 1})  # nothing generated yet
    state = client.generate_3d_from_image(image)['state']
    with pytest.raises(RuntimeError):
        client.extract_glb(None)
    client.reset_session()
    with pytest.raises(RuntimeError):
        client.extract_glb(state)  # the server dropped the model with the session


def test_all_calls_share_one_session(image, glb):
    """The model lives in the Gradio session, so one client must serve every call."""
    created = []

    def factory(url):
        created.append(url)
        return FakeGradioClient(glb_path=glb)

    client = TrellisApiClient(client_factory=factory)
    state = client.generate_3d_from_image(image)['state']
    client.extract_glb(state)
    assert len(created) == 1


def test_missing_gradio_client_is_reported(monkeypatch):
    monkeypatch.setitem(__import__('sys').modules, 'gradio_client', None)
    with pytest.raises(ImportError, match='trellis'):
        TrellisApiClient()

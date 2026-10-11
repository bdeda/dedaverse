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
"""End-to-end test of the Trellis client against a real Gradio server.

The server is a stand-in for TRELLIS.2's ``app.py`` (``tests/_fake_trellis2_app.py``) with
the same endpoint wiring and session-bound ``gr.State``, so this exercises the real
``gradio_client`` protocol without a GPU. Skipped unless ``gradio==6.0.1`` and
``gradio_client`` are installed.
"""
import importlib.util
import socket
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip('gradio')
pytest.importorskip('gradio_client')

from deda.plugins.trellis._api_client import TrellisApiClient  # noqa: E402

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture(scope='module')
def server_url():
    spec = importlib.util.spec_from_file_location('fake_trellis2_app', Path(__file__).parent / '_fake_trellis2_app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    port = _free_port()
    module.demo.launch(server_name='127.0.0.1', server_port=port, prevent_thread_lock=True, quiet=True)
    yield f'http://127.0.0.1:{port}'
    module.demo.close()


@pytest.fixture
def image(tmp_path):
    path = tmp_path / 'in.png'
    Image.new('RGB', (32, 32), (0, 128, 255)).save(path)
    return path


def test_generate_then_extract_glb(server_url, image):
    client = TrellisApiClient(server_url)
    assert client.check_connection()
    result = client.generate_3d_from_image(image, seed=42, randomize_seed=False, resolution='512')
    assert 'seed=42' in result['preview_html'] and 'resolution=512' in result['preview_html']
    glb = client.extract_glb(result['state'], decimation_target=200000, texture_size=1024)
    assert glb[:4] == b'glTF'


def test_model_belongs_to_the_session_that_made_it(server_url, image):
    first = TrellisApiClient(server_url)
    state = first.generate_3d_from_image(image)['state']
    second = TrellisApiClient(server_url)
    second._session()  # a new session with no model of its own
    with pytest.raises(Exception, match='no model|exception'):
        second._client.predict(200000, 1024, api_name='/extract_glb')
    assert first.extract_glb(state)[:4] == b'glTF'


def test_preprocess_endpoint_is_found(server_url):
    client = TrellisApiClient(server_url)
    assert client._find_endpoint(client._session(), 'preprocess_image') == '/preprocess_image_1'

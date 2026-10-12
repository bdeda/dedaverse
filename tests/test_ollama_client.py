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
"""Tests for the Ollama API client against a fake HTTP session."""
import base64

import pytest

from deda.plugins.ollama import _api_client as api
from deda.plugins.ollama._api_client import OllamaApiClient


class FakeResponse:
    def __init__(self, payload=None, status=200, text=''):
        self._payload = payload if payload is not None else {}
        self.status_code = status
        self.text = text
        self.headers = {'X': 'y'}

    def raise_for_status(self):
        if self.status_code >= 400:
            error = RuntimeError(f'HTTP {self.status_code}')
            error.response = self
            raise error

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []
        self.responses = []
        self.error = None

    def _handle(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        if self.error:
            raise self.error
        return self.responses.pop(0) if self.responses else FakeResponse()

    def get(self, url, **kwargs):
        return self._handle('GET', url, kwargs)

    def post(self, url, **kwargs):
        return self._handle('POST', url, kwargs)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api.requests, 'Session', FakeSession)
    return OllamaApiClient('http://box:11434/')


def b64(data):
    return base64.b64encode(data).decode()


def test_requires_requests(monkeypatch):
    monkeypatch.setattr(api, 'REQUESTS_AVAILABLE', False)
    with pytest.raises(ImportError):
        OllamaApiClient()


class TestListAndConnection:
    def test_list_models(self, client):
        client._session.responses = [FakeResponse({'models': [{'name': 'llama3'}]})]
        assert client.base_url == 'http://box:11434' and client.list_models() == [{'name': 'llama3'}]

    def test_list_models_failure_gives_an_empty_list(self, client):
        client._session.error = ConnectionError('down')
        assert client.list_models() == []

    def test_check_connection(self, client):
        assert client.check_connection() is True
        client._session.responses = [FakeResponse(status=500)]
        assert client.check_connection() is False
        client._session.error = ConnectionError('down')
        assert client.check_connection() is False


class TestText:
    def test_generate_text_builds_the_payload(self, client):
        client._session.responses = [FakeResponse({'response': 'hello'})]
        text = client.generate_text('llama3', 'hi', system='be brief', context=[1, 2], temperature=0.2)
        payload = client._session.calls[0][2]['json']
        assert text == 'hello' and payload == {'model': 'llama3', 'prompt': 'hi', 'stream': False,
                                               'system': 'be brief', 'context': [1, 2], 'temperature': 0.2}

    def test_generate_text_can_stream(self, client):
        response = FakeResponse()
        client._session.responses = [response]
        assert client.generate_text('m', 'p', stream=True) is response
        assert client._session.calls[0][2]['stream'] is True

    def test_generate_text_errors_are_raised(self, client):
        client._session.responses = [FakeResponse(status=500)]
        with pytest.raises(RuntimeError):
            client.generate_text('m', 'p')

    def test_chat(self, client):
        client._session.responses = [FakeResponse({'message': {'content': 'yo'}}), FakeResponse({}), FakeResponse()]
        assert client.chat('m', [{'role': 'user', 'content': 'hi'}], top_p=0.9) == 'yo'
        assert client._session.calls[0][2]['json']['top_p'] == 0.9
        assert client.chat('m', []) == ''
        streamed = client.chat('m', [], stream=True)
        assert isinstance(streamed, FakeResponse)

    def test_chat_errors_are_raised(self, client):
        client._session.error = TimeoutError('slow')
        with pytest.raises(TimeoutError):
            client.chat('m', [])


class TestImages:
    def test_process_image(self, client, tmp_path):
        image = tmp_path / 'a.png'
        image.write_bytes(b'pixels')
        client._session.responses = [FakeResponse({'response': 'a cat'})]
        assert client.process_image('llava', 'what?', image, system='sys', seed=1) == 'a cat'
        payload = client._session.calls[0][2]['json']
        assert payload['images'] == [b64(b'pixels')] and payload['system'] == 'sys' and payload['seed'] == 1

    def test_process_image_errors(self, client, tmp_path):
        with pytest.raises(FileNotFoundError):
            client.process_image('m', 'p', tmp_path / 'nope.png')
        image = tmp_path / 'a.png'
        image.write_bytes(b'x')
        client._session.error = ConnectionError('down')
        with pytest.raises(ConnectionError):
            client.process_image('m', 'p', image)

    @pytest.mark.parametrize('key', ['image', 'response'])
    def test_generate_image_from_either_key(self, client, tmp_path, key):
        client._session.responses = [FakeResponse({key: b64(b'img')})]
        target = tmp_path / 'sub' / 'out.png'
        assert client.generate_image('flux', 'a tree', output_path=target) == b'img'
        assert target.read_bytes() == b'img'

    def test_generate_image_without_saving_and_with_bad_data(self, client):
        client._session.responses = [FakeResponse({'image': b64(b'img')})]
        assert client.generate_image('flux', 'p') == b'img'
        client._session.responses = [FakeResponse({'nothing': 1})]
        with pytest.raises(ValueError, match='No image data'):
            client.generate_image('flux', 'p')


class TestThreeD:
    @pytest.mark.parametrize('key', ['model', 'response'])
    def test_generate_3d(self, client, tmp_path, key):
        image = tmp_path / 'in.png'
        image.write_bytes(b'px')
        client._session.responses = [FakeResponse({key: b64(b'mesh')})]
        target = tmp_path / 'out' / 'mesh.glb'
        assert client.generate_3d_from_image('trellis', image, prompt='a chair', output_path=target) == b'mesh'
        payload = client._session.calls[0][2]['json']
        assert payload['prompt'] == 'a chair' and payload['images'] == [b64(b'px')] and target.read_bytes() == b'mesh'

    def test_generate_3d_errors(self, client, tmp_path):
        with pytest.raises(FileNotFoundError):
            client.generate_3d_from_image('m', tmp_path / 'nope.png')
        image = tmp_path / 'in.png'
        image.write_bytes(b'px')
        client._session.responses = [FakeResponse({'nothing': 1})]
        with pytest.raises(ValueError, match='No 3D model data'):
            client.generate_3d_from_image('m', image)

    def test_generate_3d_without_a_prompt(self, client, tmp_path):
        image = tmp_path / 'in.png'
        image.write_bytes(b'px')
        client._session.responses = [FakeResponse({'model': b64(b'm')})]
        client.generate_3d_from_image('m', image)
        assert 'prompt' not in client._session.calls[0][2]['json']


class TestPull:
    def test_model_names_get_a_default_tag(self, client):
        response = FakeResponse()
        client._session.responses = [response, FakeResponse()]
        assert client.pull_model('llama3') is response
        assert client._session.calls[0][2]['json'] == {'model': 'llama3:latest', 'stream': True}
        client.pull_model('llama3:8b', stream=False)
        assert client._session.calls[1][2]['json'] == {'model': 'llama3:8b', 'stream': False}

    def test_http_errors_keep_the_response_text(self, client):
        client._session.responses = [FakeResponse(status=404, text='model not found')]
        with pytest.raises(RuntimeError) as info:
            client.pull_model('ghost')
        assert info.value.response_text == 'model not found'

    def test_errors_without_a_response_are_raised_as_is(self, client):
        client._session.error = ConnectionError('down')
        with pytest.raises(ConnectionError):
            client.pull_model('x')

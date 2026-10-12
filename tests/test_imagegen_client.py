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
"""Tests for the image generation clients (Gemini/Imagen, Ollama, generic REST) against fakes."""
import base64
import types

import pytest

from deda.plugins.imagegen import _api_client as api
from deda.plugins.imagegen._api_client import (
    GeminiImageGenClient, GenericWebServiceClient, ImageGenBackend, ImageGenClient, ImageGenRequest,
    OllamaImageGenClient,
)

PNG = b'\x89PNG fake image bytes'


def b64(data=PNG):
    return base64.b64encode(data).decode()


@pytest.fixture
def request_(tmp_path):
    return ImageGenRequest(prompt='  a hero  ', documentation='  Moody lighting  ', output_dir=tmp_path / 'out',
                           filename_prefix='hero')


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload if payload is not None else {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def json(self):
        return self._payload


@pytest.fixture
def http(monkeypatch):
    """Replace the module's requests with a recorder."""
    state = types.SimpleNamespace(posts=[], gets=[], response=FakeResponse(), error=None)

    def post(url, json=None, headers=None, timeout=None):
        state.posts.append({'url': url, 'json': json, 'headers': headers, 'timeout': timeout})
        if state.error:
            raise state.error
        return state.response

    def get(url, timeout=None):
        state.gets.append(url)
        if state.error:
            raise state.error
        return state.response

    monkeypatch.setattr(api, 'requests', types.SimpleNamespace(post=post, get=get), raising=False)
    monkeypatch.setattr(api, 'REQUESTS_AVAILABLE', True)
    return state


class TestHelpers:
    def test_prompt_combines_documentation_and_prompt(self, request_):
        assert api._build_full_prompt(request_) == 'Design context:\nMoody lighting\n\na hero'
        request_.documentation = '   '
        assert api._build_full_prompt(request_) == 'a hero'

    def test_image_is_read_as_base64_with_a_mime_type(self, tmp_path):
        png = tmp_path / 'ref.png'
        png.write_bytes(PNG)
        unknown = tmp_path / 'ref.zzz'
        unknown.write_bytes(b'x')
        assert api._read_image_b64(png) == ('image/png', b64())
        assert api._read_image_b64(unknown)[0] == 'image/jpeg'

    def test_save_image_creates_the_folder(self, tmp_path):
        path = api._save_image(PNG, tmp_path / 'a' / 'b', 'pre', 7, '.png')
        assert path.read_bytes() == PNG and path.name.startswith('pre_') and path.name.endswith('_007.png')

    @pytest.mark.parametrize('size, expected', [
        ((1920, 1080), '16:9'), ((1600, 1200), '4:3'), ((1080, 1920), '9:16'), ((900, 1200), '3:4'),
        ((1000, 1000), '1:1'),
    ])
    def test_aspect_ratio_names(self, size, expected):
        assert GeminiImageGenClient._aspect_ratio(*size) == expected

    def test_backend_enum_is_a_string(self):
        assert ImageGenBackend.GEMINI == 'gemini' and ImageGenBackend('ollama') is ImageGenBackend.OLLAMA


class TestGemini:
    @pytest.fixture
    def imagen(self, monkeypatch):
        calls = types.SimpleNamespace(client_args=None, generate=None, error=None)

        class Models:
            def generate_images(self, model, prompt, config):
                calls.generate = (model, prompt, config)
                if calls.error:
                    raise calls.error
                image = types.SimpleNamespace(image=types.SimpleNamespace(image_bytes=PNG))
                return types.SimpleNamespace(generated_images=[image, image])

        class Client:
            def __init__(self, api_key):
                calls.client_args = api_key
                self.models = Models()

        monkeypatch.setattr(api, 'new_genai', types.SimpleNamespace(Client=Client), raising=False)
        monkeypatch.setattr(api, 'genai_types', types.SimpleNamespace(
            GenerateImagesConfig=lambda **kw: kw), raising=False)
        monkeypatch.setattr(api, 'NEW_GENAI_AVAILABLE', True)
        return calls

    def test_defaults_and_setters(self):
        client = GeminiImageGenClient(api_key='k')
        assert client.model == GeminiImageGenClient.DEFAULT_MODEL
        client.model = 'gemini-x'
        client.set_api_key('new')
        assert client.model == 'gemini-x' and client._api_key == 'new'

    def test_imagen_saves_every_generated_image(self, imagen, request_):
        request_.width, request_.height, request_.num_images, request_.negative_prompt = 1920, 1080, 2, 'blurry'
        result = GeminiImageGenClient(api_key='secret').generate(request_)
        assert len(result.images) == 2 and all(p.read_bytes() == PNG for p in result.images)
        assert imagen.client_args == 'secret' and result.backend == 'gemini' and result.model == 'imagen-3.0-generate-002'
        config = imagen.generate[2]
        assert config['aspect_ratio'] == '16:9' and config['negative_prompt'] == 'blurry' and config['number_of_images'] == 2
        assert 'Moody lighting' in result.prompt_used

    def test_imagen_failure_is_re_raised(self, imagen, request_):
        imagen.error = RuntimeError('quota')
        with pytest.raises(RuntimeError, match='quota'):
            GeminiImageGenClient().generate(request_)

    @pytest.fixture
    def gemini(self, monkeypatch):
        state = types.SimpleNamespace(configured=None, error=None, models=[], contents=None)

        class GenerativeModel:
            def __init__(self, name):
                state.models.append(name)

            def generate_content(self, contents, generation_config):
                state.contents = contents
                if state.error:
                    raise state.error
                parts = [types.SimpleNamespace(inline_data=types.SimpleNamespace(data=b64(), mime_type='image/png')),
                         types.SimpleNamespace(inline_data=types.SimpleNamespace(data=b64(b'jpg'), mime_type='image/jpeg')),
                         types.SimpleNamespace(inline_data=None), types.SimpleNamespace()]
                return types.SimpleNamespace(candidates=[types.SimpleNamespace(content=types.SimpleNamespace(parts=parts))])

        fake = types.SimpleNamespace(configure=lambda api_key: setattr(state, 'configured', api_key),
                                     GenerativeModel=GenerativeModel, GenerationConfig=lambda **kw: kw)
        monkeypatch.setattr(api, 'genai', fake, raising=False)
        monkeypatch.setattr(api, 'GENAI_AVAILABLE', True)
        monkeypatch.setattr(api, 'NEW_GENAI_AVAILABLE', False)
        return state

    def test_gemini_models_save_png_and_jpeg_and_attach_references(self, gemini, request_, tmp_path):
        reference = tmp_path / 'ref.png'
        reference.write_bytes(PNG)
        request_.reference_images = [reference, tmp_path / 'missing.png']
        request_.model = 'gemini-2.0-flash'
        result = GeminiImageGenClient(api_key='k').generate(request_)
        assert [p.suffix for p in result.images] == ['.png', '.jpg'] and gemini.configured == 'k'
        assert gemini.models == ['gemini-2.0-flash'] and len(gemini.contents) == 2        # prompt + one reference
        assert gemini.contents[1]['inline_data']['mime_type'] == 'image/png'

    def test_gemini_failure_is_re_raised(self, gemini, request_):
        gemini.error = RuntimeError('blocked')
        with pytest.raises(RuntimeError, match='blocked'):
            GeminiImageGenClient().generate(request_)

    def test_a_missing_library_is_reported(self, monkeypatch, request_):
        monkeypatch.setattr(api, 'GENAI_AVAILABLE', False)
        monkeypatch.setattr(api, 'NEW_GENAI_AVAILABLE', False)
        with pytest.raises(ImportError, match='google-genai'):
            GeminiImageGenClient().generate(request_)


class TestOllama:
    def test_construction_needs_requests(self, monkeypatch):
        monkeypatch.setattr(api, 'REQUESTS_AVAILABLE', False)
        with pytest.raises(ImportError):
            OllamaImageGenClient()

    def test_properties_and_connection_check(self, http):
        client = OllamaImageGenClient('http://host:1234/', 'sdxl')
        assert client.base_url == 'http://host:1234' and client.model == 'sdxl'
        client.base_url = 'http://other/'
        client.model = 'm'
        assert client.base_url == 'http://other' and client.model == 'm'
        assert client.check_connection() is True and http.gets == ['http://other/api/tags']
        http.response = FakeResponse(status=500)
        assert client.check_connection() is False
        http.error = ConnectionError('down')
        assert client.check_connection() is False

    def test_generate_posts_and_saves_images(self, http, request_, tmp_path):
        reference = tmp_path / 'ref.png'
        reference.write_bytes(PNG)
        request_.reference_images = [reference, tmp_path / 'gone.png']
        request_.negative_prompt = 'ugly'
        request_.extra_params = {'seed': 4}
        http.response = FakeResponse({'images': [b64(), b64(b'two')]})
        result = OllamaImageGenClient().generate(request_)
        payload = http.posts[0]['json']
        assert payload['images'] == [b64()] and payload['negative_prompt'] == 'ugly' and payload['seed'] == 4
        assert payload['stream'] is False and http.posts[0]['url'].endswith('/api/generate')
        assert [p.read_bytes() for p in result.images] == [PNG, b'two'] and result.backend == 'ollama'

    def test_text_only_response_logs_a_warning(self, http, request_, caplog):
        http.response = FakeResponse({'response': 'I cannot draw'})
        with caplog.at_level('WARNING'):
            result = OllamaImageGenClient().generate(request_)
        assert result.images == [] and 'may not support image generation' in caplog.text

    def test_http_errors_are_re_raised(self, http, request_):
        http.response = FakeResponse(status=500)
        with pytest.raises(RuntimeError, match='500'):
            OllamaImageGenClient().generate(request_)


class TestGenericWebService:
    def test_requires_requests_and_an_endpoint(self, http, request_, monkeypatch):
        with pytest.raises(ValueError, match='not configured'):
            GenericWebServiceClient().generate(request_)
        monkeypatch.setattr(api, 'REQUESTS_AVAILABLE', False)
        with pytest.raises(ImportError):
            GenericWebServiceClient()

    def test_payload_template_is_expanded(self, http, request_):
        client = GenericWebServiceClient('http://x/txt2img')
        request_.width, request_.height, request_.num_images, request_.negative_prompt = 640, 480, 3, 'bad'
        request_.extra_params = {'steps': 20}
        payload = client._build_payload(request_, 'FULL')
        assert payload == {'prompt': 'FULL', 'negative_prompt': 'bad', 'width': 640, 'height': 480,
                           'n_iter': 3, 'steps': 20}

    def test_non_placeholder_values_and_unknown_placeholders_pass_through(self, http, request_):
        client = GenericWebServiceClient('http://x', payload_template={'a': 5, 'b': 'plain', 'c': '{unknown}'})
        assert client._build_payload(request_, 'p') == {'a': 5, 'b': 'plain', 'c': '{unknown}'}

    def test_generate_saves_images_and_sends_auth(self, http, request_):
        client = GenericWebServiceClient('http://x/api', image_json_path='output.images', auth_header='Bearer t',
                                         image_format='.webp')
        http.response = FakeResponse({'output': {'images': [b64(), [1, 2, 3]]}})
        result = client.generate(request_)
        assert http.posts[0]['headers'] == {'Content-Type': 'application/json', 'Authorization': 'Bearer t'}
        assert [p.suffix for p in result.images] == ['.webp', '.webp']
        assert result.images[1].read_bytes() == bytes([1, 2, 3]) and result.metadata == {'endpoint': 'http://x/api'}
        client.endpoint = 'http://y'
        assert client.endpoint == 'http://y'

    def test_errors_are_re_raised(self, http, request_):
        http.error = TimeoutError('slow')
        with pytest.raises(TimeoutError):
            GenericWebServiceClient('http://x').generate(request_)

    @pytest.mark.parametrize('data, expected', [
        ({'images': ['a', 'b']}, ['a', 'b']),
        ({'images': 'single'}, ['single']),
        ({'images': ''}, []),
        ({'other': 1}, []),
    ])
    def test_extracting_images(self, data, expected):
        assert GenericWebServiceClient('http://x')._extract_images(data) == expected

    def test_walking_through_a_non_dict_gives_nothing(self):
        client = GenericWebServiceClient('http://x', image_json_path='a.b.c')
        assert client._extract_images({'a': {'b': 'text'}}) == []


class TestFacade:
    def test_backend_switching_and_lazy_clients(self, http, request_):
        client = ImageGenClient(backend=ImageGenBackend.OLLAMA, ollama_url='http://h', ollama_model='m')
        assert client.backend == ImageGenBackend.OLLAMA
        first = client._get_active_client()
        assert isinstance(first, OllamaImageGenClient) and client._get_active_client() is first
        client.backend = ImageGenBackend.GENERIC
        client.configure_generic(endpoint='http://g', payload_template={'p': '{prompt}'}, image_json_path='imgs',
                                 auth_header='k', image_format='jpg')
        generic = client._get_active_client()
        assert isinstance(generic, GenericWebServiceClient) and generic.endpoint == 'http://g'
        client.backend = ImageGenBackend.GEMINI
        client.configure_gemini(api_key='key', model='imagen-x')
        gemini = client._get_active_client()
        assert isinstance(gemini, GeminiImageGenClient) and gemini.model == 'imagen-x'

    def test_reconfiguring_rebuilds_the_client(self, http):
        client = ImageGenClient(backend=ImageGenBackend.OLLAMA)
        first = client._get_active_client()
        client.configure_ollama(url='http://new')
        assert client._get_active_client() is not first and client._get_active_client().base_url == 'http://new'

    def test_generate_delegates_to_the_active_backend(self, http, request_):
        http.response = FakeResponse({'images': [b64()]})
        result = ImageGenClient(backend=ImageGenBackend.OLLAMA).generate(request_)
        assert len(result.images) == 1

    def test_unknown_backend(self):
        client = ImageGenClient()
        client._backend = 'carrier-pigeon'
        with pytest.raises(ValueError, match='Unknown backend'):
            client._get_active_client()

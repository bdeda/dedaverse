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
"""Tests for the fal.ai plugin: model registry, client, viewer notes, service and tool (no network)."""
import json
import sys
import types
from pathlib import Path

import pytest

import deda.plugins.fal as fal
from deda.plugins.fal import _client, _models, _notes


def png(path):
    path.write_bytes(b'\x89PNG fake')
    return path


class TestParam:
    def test_coerce_clamps_numbers_and_validates_choices(self):
        count = _models.Param('n', 'N', 'int', 1, 1, 4)
        assert count.coerce(9) == 4 and count.coerce('0') == 1 and count.coerce(2.7) == 2
        strength = _models.Param('s', 'S', 'float', 0.5, 0.0, 1.0)
        assert strength.coerce(5) == 1.0 and strength.coerce('0.25') == 0.25
        choice = _models.Param('c', 'C', 'choice', 'a', choices=('a', 'b'))
        assert choice.coerce('b') == 'b' and choice.coerce('zzz') == 'a'
        assert _models.Param('b', 'B', 'bool', False).coerce(1) is True
        assert _models.Param('x', 'X', 'float', None).coerce(3) == 3.0


class TestRegistry:
    def test_every_task_has_a_model_and_a_recommendation(self):
        for task in _models.TASKS:
            assert _models.models_for(task) and _models.recommend(task).task == task

    def test_defaults_and_param_lookup(self):
        model = _models.recommend(_models.TEXT_TO_IMAGE)
        assert model.endpoint == 'fal-ai/flux/dev' and model.defaults()['num_inference_steps'] == 28
        assert 'seed' not in model.defaults() and model.param('seed').kind == 'int' and model.param('nope') is None

    def test_recommendations(self):
        assert _models.recommend(_models.TEXT_TO_IMAGE, 'fast').endpoint == 'fal-ai/flux/schnell'
        assert _models.recommend(_models.TEXT_TO_IMAGE, 'quality').endpoint == 'fal-ai/flux-pro/v1.1'
        assert _models.recommend(_models.IMAGE_TO_IMAGE).endpoint == 'fal-ai/flux/dev/image-to-image'
        assert _models.recommend(_models.IMAGE_TO_IMAGE, has_reference=True).reference_arg == 'reference_image_url'
        assert _models.recommend(_models.IMAGE_EDIT).endpoint == 'fal-ai/flux-pro/kontext'
        assert _models.recommend(_models.IMAGE_TO_3D).endpoint == 'fal-ai/trellis'
        assert _models.recommend(_models.IMAGE_TO_3D, 'fast').endpoint == 'fal-ai/trellis'       # no match: the default
        assert _models.recommend(_models.TEXT_TO_IMAGE, has_reference=True).task == _models.TEXT_TO_IMAGE

    def test_no_model_for_a_task(self):
        with pytest.raises(ValueError, match='No fal model'):
            _models.recommend('make_coffee', models=[])

    def test_unmatched_default_falls_back_to_the_first_candidate(self):
        only = _models.FalModel('x/y', 'Only', _models.TEXT_TO_IMAGE, 'd')
        assert _models.recommend(_models.TEXT_TO_IMAGE, models=[only]) is only

    @pytest.mark.parametrize('args, expected', [
        ((True, False), _models.TEXT_TO_IMAGE), ((True, True), _models.IMAGE_TO_IMAGE),
        ((True, True, False, True), _models.IMAGE_EDIT), ((False, True, True), _models.IMAGE_TO_3D),
        ((True, True, True), _models.IMAGE_TO_3D)])
    def test_task_from_inputs(self, args, expected):
        assert _models.task_for(*args) == expected

    @pytest.mark.parametrize('args, message', [
        ((False, False), 'Enter a prompt'), ((False, True), 'Add a prompt'), ((True, False, True), 'source image')])
    def test_task_needs_usable_inputs(self, args, message):
        with pytest.raises(ValueError, match=message):
            _models.task_for(*args)


class TestAudioModels:
    def model(self, endpoint):
        return next(m for m in _models.BUILTIN_MODELS if m.endpoint == endpoint)

    def test_every_audio_task_has_models_and_a_default(self):
        picks = {task: _models.recommend(task).endpoint for task in (
            _models.TEXT_TO_MUSIC, _models.SOUND_EFFECT, _models.TEXT_TO_SPEECH, _models.VIDEO_TO_AUDIO)}
        assert picks == {'text_to_music': 'fal-ai/stable-audio-25/text-to-audio',
                         'sound_effect': 'fal-ai/elevenlabs/sound-effects/v2',
                         'text_to_speech': 'fal-ai/kokoro/american-english', 'video_to_audio': 'fal-ai/mmaudio-v2'}
        assert _models.recommend(_models.TEXT_TO_MUSIC, 'quality').endpoint == 'fal-ai/lyria2'
        assert _models.recommend(_models.SOUND_EFFECT, 'fast').endpoint == 'fal-ai/mmaudio-v2/text-to-audio'
        assert _models.recommend(_models.TEXT_TO_SPEECH, 'quality').endpoint == 'fal-ai/elevenlabs/tts/turbo-v2.5'

    def test_outputs_and_inputs(self):
        for endpoint in ('fal-ai/stable-audio-25/text-to-audio', 'fal-ai/lyria2', 'fal-ai/kokoro/american-english'):
            assert self.model(endpoint).output_kind == 'audio' and self.model(endpoint).output_field == 'audio'
        video = self.model('fal-ai/mmaudio-v2')
        assert video.video_arg == 'video_url' and video.output_kind == 'video' and video.output_field == 'video'

    def test_arguments_for_music_and_effects(self):
        music = _client.FalClient.build_arguments(_client.FalRequest(
            self.model('fal-ai/stable-audio-25/text-to-audio'), prompt='lofi beat', annotations='warm',
            params={'seconds_total': 999}))
        assert music['seconds_total'] == 190 and music['prompt'] == 'lofi beat\n\nArt direction: warm'
        effect = _client.FalClient.build_arguments(_client.FalRequest(
            self.model('fal-ai/elevenlabs/sound-effects/v2'), prompt='door creak', params={'duration_seconds': 99}))
        assert effect['text'] == 'door creak' and effect['duration_seconds'] == 22.0 and 'prompt' not in effect
        assert effect['output_format'] == 'mp3_44100_128'
        assert 'duration_seconds' not in _client.FalClient.build_arguments(
            _client.FalRequest(self.model('fal-ai/elevenlabs/sound-effects/v2'), prompt='x'))

    def test_speech_is_never_given_art_direction(self):
        request = _client.FalRequest(self.model('fal-ai/kokoro/american-english'), prompt=' Hello there. ',
                                     annotations='whisper it, sadly', params={'voice': 'am_adam', 'speed': 9})
        arguments = _client.FalClient.build_arguments(request)
        assert arguments['prompt'] == 'Hello there.' and arguments['voice'] == 'am_adam' and arguments['speed'] == 2.0
        eleven = _client.FalRequest(self.model('fal-ai/elevenlabs/tts/turbo-v2.5'), prompt='Bonjour',
                                    annotations='ignored', params={'voice': 'Aria', 'language_code': 'fr'})
        arguments = _client.FalClient.build_arguments(eleven)
        assert arguments['text'] == 'Bonjour' and arguments['voice'] == 'Aria' and arguments['language_code'] == 'fr'
        assert _models.Param('v', 'V', 'text', 'x').coerce(5) == '5'

    def test_speech_needs_text(self):
        request = _client.FalRequest(self.model('fal-ai/kokoro/american-english'), annotations='only direction')
        with pytest.raises(ValueError, match='needs a prompt'):
            _client.FalClient.build_arguments(request)

    def test_a_video_is_required_and_passed_on(self):
        model = self.model('fal-ai/mmaudio-v2')
        request = _client.FalRequest(model, prompt='rain on a roof')
        with pytest.raises(ValueError, match='needs a source video'):
            _client.FalClient.build_arguments(request)
        arguments = _client.FalClient.build_arguments(request, video_url='u://clip')
        assert arguments['video_url'] == 'u://clip' and arguments['prompt'] == 'rain on a roof'

    def test_user_models_can_declare_audio(self, tmp_path):
        file = tmp_path / 'm.json'
        file.write_text(json.dumps([{'endpoint': 'fal-ai/x', 'label': 'X', 'task': 'text_to_music',
                                     'output_kind': 'audio', 'direction_in_prompt': False, 'video_arg': 'v'}]))
        model = _models.load_user_models(file)[0]
        assert model.output_field == 'audio' and model.direction_in_prompt is False and model.video_arg == 'v'


class TestUserModels:
    def entry(self, **extra):
        return {'endpoint': 'fal-ai/custom', 'label': 'Custom', 'task': 'text_to_image', **extra}

    def test_absent_files_give_nothing(self, tmp_path):
        assert _models.load_user_models(tmp_path / 'none.json') == []

    def test_entries_are_loaded_and_override_builtins(self, tmp_path):
        file = tmp_path / 'models.json'
        file.write_text(json.dumps([
            self.entry(params=[{'name': 'steps', 'label': 'Steps', 'kind': 'int', 'default': 5, 'minimum': 1,
                                'maximum': 9, 'choices': [], 'help': 'h'}], speed='fast'),
            {'endpoint': 'fal-ai/trellis', 'label': 'My Trellis', 'task': 'image_to_3d', 'output_kind': 'mesh',
             'image_arg': 'image_url', 'prompt_arg': None}]))
        models = {m.endpoint: m for m in _models.all_models(file)}
        assert models['fal-ai/custom'].params[0].default == 5 and models['fal-ai/trellis'].label == 'My Trellis'
        assert models['fal-ai/trellis'].output_field == 'model_mesh'
        assert len([m for m in _models.all_models(file) if m.endpoint == 'fal-ai/trellis']) == 1

    def test_the_environment_variable_names_the_file(self, tmp_path, monkeypatch):
        file = tmp_path / 'm.json'
        file.write_text(json.dumps([self.entry()]))
        monkeypatch.setenv(_models.ENV_MODELS_FILE, str(file))
        assert [m.endpoint for m in _models.load_user_models()] == ['fal-ai/custom']

    def test_bad_files_and_entries_are_skipped(self, tmp_path, caplog):
        broken = tmp_path / 'broken.json'
        broken.write_text('{ nope')
        not_a_list = tmp_path / 'obj.json'
        not_a_list.write_text('{}')
        mixed = tmp_path / 'mixed.json'
        mixed.write_text(json.dumps([self.entry(), {'endpoint': 'x'}, self.entry(task='nonsense'),
                                     self.entry(output_kind='hologram'), 5]))
        with caplog.at_level('WARNING'):
            assert _models.load_user_models(broken) == [] and _models.load_user_models(not_a_list) == []
            assert len(_models.load_user_models(mixed)) == 1
        assert 'Could not read fal models' in caplog.text and 'Skipping invalid' in caplog.text


class FakeStatus:
    pass


Queued = type('Queued', (), {'position': 3})
InProgress = type('InProgress', (), {'logs': [{'message': 'step 2/12'}]})
Completed = type('Completed', (), {})


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.uploads = []
        self.calls = []

    def upload_file(self, path):
        self.uploads.append(Path(path).name)
        return f'https://fal.media/up/{Path(path).name}'

    def subscribe(self, endpoint, arguments, with_logs, on_queue_update):
        self.calls.append((endpoint, arguments))
        for status in (Queued(), InProgress(), Completed()):
            on_queue_update(status)
        return self.response


def make_client(response, tmp_path, key='k'):
    session = FakeSession(response)
    downloads = []

    def downloader(url, destination):
        downloads.append(url)
        destination.write_bytes(b'data')

    client = _client.FalClient(api_key=key, client_factory=lambda k: session, downloader=downloader)
    client.session, client.downloads = session, downloads
    return client


IMAGES = {'images': [{'url': 'https://fal.media/f/a.jpg', 'content_type': 'image/jpeg'},
                     {'url': 'https://fal.media/f/b.png'}], 'seed': 7, 'prompt': 'used'}


class TestBuildArguments:
    def model(self, endpoint):
        return next(m for m in _models.BUILTIN_MODELS if m.endpoint == endpoint)

    def test_defaults_overrides_and_prompt_composition(self):
        request = _client.FalRequest(self.model('fal-ai/flux/dev'), prompt=' a dragon ', annotations='moody',
                                     params={'num_images': 99, 'seed': None, 'output_format': 'jpeg', 'extra': 1})
        arguments = _client.FalClient.build_arguments(request)
        assert arguments['prompt'] == 'a dragon\n\nArt direction: moody' and arguments['num_images'] == 4
        assert arguments['output_format'] == 'jpeg' and arguments['extra'] == 1 and 'seed' not in arguments

    def test_images_references_and_negative_prompts(self):
        model = self.model('fal-ai/flux-general/image-to-image')
        request = _client.FalRequest(model, prompt='p', negative_prompt=' blurry ')
        arguments = _client.FalClient.build_arguments(request, 'u://img', 'u://ref')
        assert arguments['image_url'] == 'u://img' and arguments['reference_image_url'] == 'u://ref'
        assert arguments['negative_prompt'] == 'blurry'

    def test_a_reference_is_ignored_when_the_model_takes_none(self, caplog):
        request = _client.FalRequest(self.model('fal-ai/flux/dev/image-to-image'), prompt='p')
        with caplog.at_level('WARNING'):
            arguments = _client.FalClient.build_arguments(request, 'u://img', 'u://ref')
        assert 'ref' not in str(arguments) and 'takes no reference image' in caplog.text

    def test_required_inputs(self):
        with pytest.raises(ValueError, match='needs a prompt'):
            _client.FalClient.build_arguments(_client.FalRequest(self.model('fal-ai/flux/dev')))
        with pytest.raises(ValueError, match='needs a source image'):
            _client.FalClient.build_arguments(_client.FalRequest(self.model('fal-ai/trellis')))

    def test_meshes_take_no_prompt(self):
        arguments = _client.FalClient.build_arguments(_client.FalRequest(self.model('fal-ai/trellis')), 'u://img')
        assert arguments['image_url'] == 'u://img' and 'prompt' not in arguments and arguments['texture_size'] == 1024

    def test_compose_prompt(self):
        assert _client.compose_prompt('a', '') == 'a' and _client.compose_prompt('', ' b ') == 'b'
        assert _client.compose_prompt('', '') == ''


class TestRun:
    def request(self, tmp_path, endpoint='fal-ai/flux/dev', **kwargs):
        model = next(m for m in _models.BUILTIN_MODELS if m.endpoint == endpoint)
        return _client.FalRequest(model, output_dir=tmp_path / 'out', filename_prefix='my shot!', **kwargs)

    def test_text_to_image_downloads_every_image(self, tmp_path):
        client = make_client(IMAGES, tmp_path)
        statuses = []
        result = client.run(self.request(tmp_path, prompt='a dragon'), on_status=statuses.append)
        assert [p.name for p in result.paths] == ['my_shot_01.jpg', 'my_shot_02.png'] and result.seed == 7
        assert client.session.calls[0][0] == 'fal-ai/flux/dev' and client.session.uploads == []
        assert 'Queued (position 3)' in statuses and 'Running: step 2/12' in statuses and statuses[-1] == 'Done'

    def test_existing_files_are_never_overwritten(self, tmp_path):
        client = make_client({'images': [{'url': 'https://x/a.png'}]}, tmp_path)
        first = client.run(self.request(tmp_path, prompt='p')).paths[0]
        second = client.run(self.request(tmp_path, prompt='p')).paths[0]
        assert first != second and first.exists() and second.exists() and second.name.endswith('_2.png')

    def test_image_to_image_uploads_the_images(self, tmp_path):
        client = make_client(IMAGES, tmp_path)
        source, ref = png(tmp_path / 'src.png'), png(tmp_path / 'ref.png')
        request = self.request(tmp_path, 'fal-ai/flux-general/image-to-image', prompt='p', image=source,
                               reference_image=ref)
        client.run(request)
        endpoint, arguments = client.session.calls[0]
        assert client.session.uploads == ['src.png', 'ref.png']
        assert arguments['image_url'].endswith('src.png') and arguments['reference_image_url'].endswith('ref.png')

    def test_a_reference_is_not_uploaded_for_models_that_ignore_it(self, tmp_path):
        client = make_client(IMAGES, tmp_path)
        request = self.request(tmp_path, 'fal-ai/flux/dev/image-to-image', prompt='p',
                               image=png(tmp_path / 's.png'), reference_image=png(tmp_path / 'r.png'))
        client.run(request)
        assert client.session.uploads == ['s.png']

    def test_audio_is_downloaded_with_the_right_suffix(self, tmp_path):
        client = make_client({'audio': {'url': 'https://x/out', 'content_type': 'audio/mpeg'}, 'seed': 3}, tmp_path)
        request = self.request(tmp_path, 'fal-ai/stable-audio-25/text-to-audio', prompt='beat')
        result = client.run(request)
        assert result.paths[0].suffix == '.mp3' and result.files[0].kind == 'audio' and result.seed == 3

    @pytest.mark.parametrize('entry, kind, suffix', [
        ({'url': 'https://x/a'}, 'audio', '.wav'), ({'url': 'https://x/a', 'file_name': 'mix.flac'}, 'audio', '.flac'),
        ({'url': 'https://x/a'}, 'video', '.mp4')])
    def test_audio_and_video_suffix_fallbacks(self, entry, kind, suffix):
        assert _client.FalClient._suffix(_client.FalFile(kind=kind, **entry)) == suffix

    def test_a_video_is_uploaded_and_the_result_is_a_video(self, tmp_path):
        client = make_client({'video': {'url': 'https://x/v.mp4', 'content_type': 'video/mp4'}}, tmp_path)
        clip = tmp_path / 'clip.mp4'
        clip.write_bytes(b'video')
        request = self.request(tmp_path, 'fal-ai/mmaudio-v2', prompt='rain', video=clip)
        result = client.run(request)
        assert client.session.uploads == ['clip.mp4'] and client.session.calls[0][1]['video_url'].endswith('clip.mp4')
        assert result.paths[0].suffix == '.mp4' and result.files[0].kind == 'video'

    def test_a_video_model_needs_a_video(self, tmp_path):
        with pytest.raises(ValueError, match='needs a source video'):
            make_client({}, tmp_path).run(self.request(tmp_path, 'fal-ai/mmaudio-v2', prompt='rain'))

    def test_speech_runs_without_direction(self, tmp_path):
        client = make_client({'audio': {'url': 'https://x/s.wav'}}, tmp_path)
        request = self.request(tmp_path, 'fal-ai/kokoro/american-english', prompt='Hi', annotations='shout')
        client.run(request)
        assert client.session.calls[0][1]['prompt'] == 'Hi'
        with pytest.raises(ValueError, match='needs a prompt'):
            client.run(self.request(tmp_path, 'fal-ai/kokoro/american-english', annotations='only direction'))

    def test_a_mesh_result_is_saved_as_glb_even_with_an_image_content_type(self, tmp_path):
        client = make_client({'model_mesh': {'url': 'https://x/mesh', 'content_type': 'image/png',
                                             'file_name': 'weird.png'}}, tmp_path)
        request = self.request(tmp_path, 'fal-ai/trellis', image=png(tmp_path / 's.png'))
        result = client.run(request)
        assert result.paths[0].suffix == '.glb' and result.files[0].kind == 'mesh'

    @pytest.mark.parametrize('entry, suffix', [
        ({'url': 'https://x/a', 'content_type': 'image/webp'}, '.webp'), ({'url': 'https://x/a'}, '.png'),
        ({'url': 'https://x/a', 'file_name': 'q.jpeg'}, '.jpeg')])
    def test_suffix_rules_for_images(self, tmp_path, entry, suffix):
        result = make_client({'images': [entry]}, tmp_path).run(self.request(tmp_path, prompt='p'))
        assert result.paths[0].suffix == suffix

    def test_a_response_without_files_is_an_error(self, tmp_path):
        with pytest.raises(_client.FalError, match='returned no'):
            make_client({'images': []}, tmp_path).run(self.request(tmp_path, prompt='p'))
        with pytest.raises(_client.FalError):
            make_client(None, tmp_path).run(self.request(tmp_path, prompt='p'))

    def test_inputs_are_validated_before_anything_is_sent(self, tmp_path):
        client = make_client(IMAGES, tmp_path)
        with pytest.raises(ValueError, match='needs a prompt'):
            client.run(self.request(tmp_path))
        with pytest.raises(ValueError, match='needs a source image'):
            client.run(self.request(tmp_path, 'fal-ai/trellis'))
        with pytest.raises(FileNotFoundError):
            client.run(self.request(tmp_path, 'fal-ai/trellis', image=tmp_path / 'ghost.png'))
        assert client.session.calls == []

    def test_a_key_is_required(self, tmp_path, monkeypatch):
        monkeypatch.delenv(_client.ENV_API_KEY, raising=False)
        client = make_client(IMAGES, tmp_path, key='')
        assert not client.has_key
        with pytest.raises(_client.FalError, match=_client.ENV_API_KEY):
            client.run(self.request(tmp_path, prompt='p'))
        client.set_api_key(' typed ')
        assert client.api_key == 'typed' and client.has_key

    def test_the_key_can_come_from_the_environment(self, monkeypatch):
        monkeypatch.setenv(_client.ENV_API_KEY, 'from-env')
        assert _client.FalClient().api_key == 'from-env'

    def test_the_session_is_reused_until_the_key_changes(self, tmp_path):
        built = []
        client = _client.FalClient(api_key='a', client_factory=lambda key: built.append(key) or FakeSession({}))
        client._session()
        client._session()
        client.set_api_key('b')
        client._session()
        assert built == ['a', 'b']

    def test_describe_status(self):
        assert _client.describe_status(InProgress()) == 'Running: step 2/12'
        assert _client.describe_status(type('InProgress', (), {'logs': []})()) == 'Running'
        assert _client.describe_status(Completed()) == 'Completed' and _client.describe_status(FakeStatus()) == 'FakeStatus'


class TestRealIntegrationPoints:
    def test_the_default_factory_explains_a_missing_fal_client(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'fal_client', None)
        with pytest.raises(_client.FalError, match=r'\.\[fal\]'):
            _client._client_factory('key')

    def test_the_default_factory_builds_a_sync_client(self, monkeypatch):
        module = types.ModuleType('fal_client')
        module.SyncClient = lambda key: ('client', key)
        monkeypatch.setitem(sys.modules, 'fal_client', module)
        assert _client._client_factory('k') == ('client', 'k')

    def test_the_default_downloader_writes_the_response(self, tmp_path, monkeypatch):
        import requests
        response = types.SimpleNamespace(content=b'bytes', raise_for_status=lambda: None)
        monkeypatch.setattr(requests, 'get', lambda url, timeout: response)
        target = tmp_path / 'x.bin'
        _client._download('https://x', target)
        assert target.read_bytes() == b'bytes'

    def test_upload_checks_the_file(self, tmp_path):
        client = make_client({}, tmp_path)
        with pytest.raises(FileNotFoundError):
            client.upload(tmp_path / 'nope.png')


class TestNotes:
    def test_direction_from_the_note_and_the_text_annotations(self):
        payload = {'description': ' warmer light ', 'texts': [{'text': 'more rust'}, {'text': ' '}, None, {'text': 'low angle'}]}
        assert _notes.notes_to_direction(payload) == 'warmer light\nmore rust\nlow angle'
        assert _notes.notes_to_direction({}) == ''

    def test_loading_notes_finds_the_snapshot(self, tmp_path):
        notes = tmp_path / 'annotations_20250101_120000.json'
        notes.write_text(json.dumps({'description': 'moody', 'texts': []}))
        assert _notes.load_notes(notes) == ('moody', None)
        snapshot = png(tmp_path / 'snapshot_20250101_120000.png')
        assert _notes.load_notes(notes) == ('moody', snapshot)

    def test_bad_notes(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _notes.load_notes(tmp_path / 'missing.json')
        bad = tmp_path / 'bad.json'
        bad.write_text('{ nope')
        with pytest.raises(ValueError, match='not valid notes'):
            _notes.load_notes(bad)
        bad.write_text('[1]')
        with pytest.raises(ValueError, match='expected an object'):
            _notes.load_notes(bad)


class TestServiceAndTool:
    def test_the_service_lists_and_recommends_models(self):
        service = fal.FalService()
        assert service.name == 'fal' and service.models(fal.IMAGE_TO_3D)[0].endpoint == 'fal-ai/trellis'
        assert len(service.models()) >= 8 and service.recommend(fal.TEXT_TO_IMAGE, 'fast').speed == 'fast'
        assert service.client is service.client

    def test_loading_without_a_key_still_succeeds(self, monkeypatch, caplog):
        monkeypatch.delenv(_client.ENV_API_KEY, raising=False)
        service = fal.FalService()
        with caplog.at_level('INFO'):
            assert service.load() is True and service.loaded
        assert 'no FAL_KEY' in caplog.text

    def test_the_service_runs_requests_through_its_client(self, tmp_path):
        service = fal.FalService()
        service._client = make_client(IMAGES, tmp_path)
        request = fal.FalRequest(fal.recommend(fal.TEXT_TO_IMAGE), prompt='p', output_dir=tmp_path / 'o')
        assert len(service.run(request).paths) == 2

    def test_the_plugins_are_registered(self):
        registry = fal.PluginRegistry() if hasattr(fal, 'PluginRegistry') else None
        from deda.core import PluginRegistry
        assert isinstance(PluginRegistry().get('fal'), (fal.FalService, fal.FalTool))

    def test_the_tool_finds_the_service_and_builds_one_window(self, monkeypatch):
        from deda.core import PluginRegistry
        service = fal.FalService()
        PluginRegistry().register(service)
        try:
            tool = fal.FalTool()
            assert tool.load() is True and tool._service is service
        finally:
            PluginRegistry._registry_.pop('fal', None)
        built = []
        module = types.ModuleType('deda.plugins.fal._tool_window')
        module.FalToolWindow = lambda service, parent: built.append((service, parent)) or object()
        monkeypatch.setitem(sys.modules, 'deda.plugins.fal._tool_window', module)
        first = tool.initialize_window('parent')
        assert tool.initialize_window('parent') is first and built == [(service, 'parent')]

    def test_the_tool_without_a_service_warns(self, monkeypatch, caplog):
        monkeypatch.setattr(fal.PluginRegistry, 'get', lambda self, name: None)
        with caplog.at_level('WARNING'):
            assert fal.FalTool().load() is True
        assert 'service not found' in caplog.text

    def test_a_registration_failure_is_logged(self, monkeypatch, caplog):
        monkeypatch.setattr(fal, 'FalService', lambda: 1 / 0)
        with caplog.at_level('ERROR'):
            fal._register_plugins()
        assert 'Failed to register fal plugins' in caplog.text

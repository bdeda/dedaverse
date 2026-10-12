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
"""Tests for the fal.ai window (against a fake client; nothing is sent anywhere)."""
import json
import time
import types
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from deda.plugins.fal import _models, _tool_window as tw
from deda.plugins.fal._client import FalClient, FalFile, FalResult


class FakeClient(FalClient):
    def __init__(self):
        super().__init__(api_key='')
        self.has = True
        self.requests = []
        self.error = None
        self.result_files = []

    @property
    def has_key(self):
        return self.has or bool(self._api_key)

    def run(self, request, on_status=None):
        self.requests.append(request)
        if on_status:
            on_status('Working')
        if self.error:
            raise self.error
        files = [FalFile(url='u', kind=request.model.output_kind, path=p) for p in self.result_files]
        return FalResult(model=request.model, files=files, seed=11)


@pytest.fixture
def dialogs(monkeypatch):
    seen = []
    for kind in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QtWidgets.QMessageBox, kind, staticmethod(
            lambda parent, title, text, *a, _kind=kind, **k: seen.append((_kind, title, text))))
    return seen


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch, dialogs):
    real = QtCore.QSettings
    monkeypatch.setattr(tw.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'fal.ini'), real.IniFormat))
    monkeypatch.setattr(_models, 'USER_MODELS_FILE', tmp_path / 'no-models.json')
    created = []

    def build(client=None):
        service = types.SimpleNamespace(client=client or FakeClient())
        window = tw.FalToolWindow(service=service)
        window.fake = service.client
        created.append(window)
        return window

    yield build
    for window in created:
        if window._worker is not None:
            window._worker.wait(5000)
        window.close()


def png(path, size=16):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtCore.Qt.red)
    image.save(str(path))
    return path


def select_task(window, task):
    window._task_combo.setCurrentIndex(window._task_combo.findData(task))


def wait_for(condition, seconds=10):
    deadline = time.time() + seconds
    while time.time() < deadline and not condition():
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    assert condition()


class TestTaskAndModel:
    def test_the_recommended_model_is_selected_and_marked(self, make_window):
        window = make_window()
        assert window.model.endpoint == 'fal-ai/flux/dev' and '(recommended)' in window._model_combo.currentText()
        assert window._task_combo.count() == len(_models.TASKS)

    def test_the_preferred_speed_changes_the_choice(self, make_window):
        window = make_window()
        window._speed_combo.setCurrentIndex(window._speed_combo.findData('fast'))
        assert window.model.endpoint == 'fal-ai/flux/schnell'

    def test_inputs_follow_the_model(self, make_window):
        window = make_window()
        assert not window._prompt_edit.isHidden() and window._image_edit.isHidden() and window._reference_edit.isHidden()
        select_task(window, _models.IMAGE_TO_3D)
        assert window.model.endpoint == 'fal-ai/trellis'
        assert window._prompt_edit.isHidden() and not window._image_edit.isHidden()
        select_task(window, _models.IMAGE_TO_IMAGE)
        assert not window._image_edit.isHidden() and window._reference_edit.isHidden()
        window._reference_edit.setText('x.png')
        window._on_task_changed()
        assert window.model.reference_arg and not window._reference_edit.isHidden()
        assert not window._negative_edit.isHidden() and 'strength' in [n for n in window._params._editors]

    def test_the_description_and_notes_are_shown(self, make_window):
        window = make_window()
        assert 'concept art' in window._model_note.text() and 'non-commercial' in window._model_note.text()

    def test_a_task_without_models_clears_the_form(self, make_window, monkeypatch):
        window = make_window()
        monkeypatch.setattr(tw, 'models_for', lambda task: [])
        window._on_task_changed()
        assert window.model is None and window._model_note.text() == '' and window._params._editors == {}
        with pytest.raises(ValueError, match='No model'):
            window._build_request()


class TestParameters:
    def test_editors_match_the_parameter_kinds(self, make_window):
        window = make_window()
        select_task(window, _models.IMAGE_TO_3D)
        editors = {name: editor for name, (param, editor) in window._params._editors.items()}
        assert isinstance(editors['ss_sampling_steps'], QtWidgets.QSpinBox)
        assert isinstance(editors['mesh_simplify'], QtWidgets.QDoubleSpinBox)
        assert isinstance(editors['texture_size'], QtWidgets.QComboBox)
        assert window._params.values()['texture_size'] == 1024 and 'seed' not in window._params.values()

    def test_bool_choice_and_seed_values(self, make_window):
        window = make_window()
        window._model_combo.setCurrentIndex(window._model_combo.findText('Hunyuan3D 2.1 (image to 3D)')) \
            if False else None
        select_task(window, _models.IMAGE_TO_3D)
        window._model_combo.setCurrentIndex(1)
        assert window.model.endpoint == 'fal-ai/hunyuan3d-v21'
        editors = {n: e for n, (p, e) in window._params._editors.items()}
        editors['textured_mesh'].setChecked(True)
        editors['seed'].setValue(42)
        values = window._params.values()
        assert values['textured_mesh'] is True and values['seed'] == 42
        editors['seed'].setValue(-1)
        assert 'seed' not in window._params.values()

    def test_a_choice_without_a_default_can_be_left_unset(self, make_window):
        window = make_window()
        select_task(window, _models.IMAGE_EDIT)
        editors = {n: e for n, (p, e) in window._params._editors.items()}
        assert editors['aspect_ratio'].currentText() == '(default)' and 'aspect_ratio' not in window._params.values()
        editors['aspect_ratio'].setCurrentIndex(editors['aspect_ratio'].findData('16:9'))
        assert window._params.values()['aspect_ratio'] == '16:9'

    def test_editors_without_ranges_and_defaults_still_build(self, qapp):
        form = tw._ParamForm()
        model = _models.FalModel('x/y', 'X', _models.TEXT_TO_IMAGE, 'd', params=(
            _models.Param('a', 'A', 'int'), _models.Param('b', 'B', 'float'),
            _models.Param('c', 'C', 'float', 2.5, help='tip')))
        form.set_model(model)
        assert form.values() == {'c': 2.5}                       # the unset numbers read "Auto" and are left out
        editors = {n: e for n, (p, e) in form._editors.items()}
        editors['a'].setValue(3)
        editors['b'].setValue(1.5)
        assert form.values() == {'a': 3, 'b': 1.5, 'c': 2.5}
        form.set_model(None)
        assert form.values() == {}


class TestAudio:
    def test_every_audio_task_is_offered(self, make_window):
        window = make_window()
        for task in ('text_to_music', 'sound_effect', 'text_to_speech', 'video_to_audio'):
            assert window._task_combo.findData(task) >= 0

    def test_music_uses_the_prompt_and_direction(self, make_window):
        window = make_window()
        select_task(window, _models.TEXT_TO_MUSIC)
        assert window.model.endpoint == 'fal-ai/stable-audio-25/text-to-audio'
        assert not window._prompt_edit.isHidden() and not window._direction_edit.isHidden()
        assert window._image_edit.isHidden() and window._video_edit.isHidden()

    def test_speech_hides_the_direction_and_relabels_the_prompt(self, make_window):
        window = make_window()
        select_task(window, _models.TEXT_TO_SPEECH)
        assert window._direction_edit.isHidden() and window._direction_label.isHidden()
        assert window._prompt_label.text() == 'Text to speak:'
        select_task(window, _models.TEXT_TO_MUSIC)
        assert not window._direction_edit.isHidden() and window._prompt_label.text() == 'Prompt:'

    def test_text_parameters_are_edited_as_text(self, make_window):
        window = make_window()
        select_task(window, _models.TEXT_TO_SPEECH)
        window._speed_combo.setCurrentIndex(window._speed_combo.findData('quality'))
        assert window.model.endpoint == 'fal-ai/elevenlabs/tts/turbo-v2.5'
        editors = {n: e for n, (p, e) in window._params._editors.items()}
        assert isinstance(editors['voice'], QtWidgets.QLineEdit) and window._params.values()['voice'] == 'Rachel'
        editors['voice'].setText('Aria')
        editors['language_code'].setText(' fr ')
        assert window._params.values()['voice'] == 'Aria' and window._params.values()['language_code'] == 'fr'
        editors['language_code'].setText('')
        assert 'language_code' not in window._params.values()

    def test_optional_numbers_read_auto_until_set(self, make_window):
        window = make_window()
        select_task(window, _models.SOUND_EFFECT)
        editors = {n: e for n, (p, e) in window._params._editors.items()}
        assert editors['duration_seconds'].specialValueText() == 'Auto' and 'duration_seconds' not in window._params.values()
        editors['duration_seconds'].setValue(5.0)
        assert window._params.values()['duration_seconds'] == 5.0

    def test_the_video_row_follows_the_model(self, make_window, monkeypatch):
        window = make_window()
        select_task(window, _models.VIDEO_TO_AUDIO)
        assert not window._video_edit.isHidden() and window._image_edit.isHidden()
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('C:/clip.mp4', '')))
        window._on_browse_video()
        assert window._video_edit.text() == 'C:/clip.mp4' and window._build_request().video == Path('C:/clip.mp4')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('', '')))
        window._on_browse_video()
        assert window._video_edit.text() == 'C:/clip.mp4'

    def test_a_missing_video_is_reported(self, make_window, dialogs, tmp_path):
        window = make_window()
        select_task(window, _models.VIDEO_TO_AUDIO)
        window._prompt_edit.setPlainText('rain')
        window._on_run()
        assert 'source video' in dialogs[-1][2]
        window._video_edit.setText(str(tmp_path / 'ghost.mp4'))
        window._on_run()
        assert 'video that exists' in dialogs[-1][2] and window.fake.requests == []

    def test_audio_and_video_results_get_play_buttons(self, make_window, tmp_path):
        window = make_window()
        select_task(window, _models.TEXT_TO_MUSIC)
        window._prompt_edit.setPlainText('lofi')
        track = tmp_path / 'track.mp3'
        track.write_bytes(b'mp3')
        window.fake.result_files = [track]
        window._on_run()
        wait_for(lambda: window._results_layout.count() == 1 and window._run_btn.isEnabled())
        button = window._results_layout.itemAt(0).widget()
        assert 'track.mp3' in button.text() and button.text().endswith('Play')
        opened = []
        window._open = lambda path: opened.append(path)
        button.click()
        assert opened == [str(track)]

    def test_a_video_result_also_plays(self, make_window, tmp_path):
        window = make_window()
        select_task(window, _models.VIDEO_TO_AUDIO)
        clip = tmp_path / 'in.mp4'
        clip.write_bytes(b'v')
        window._video_edit.setText(str(clip))
        window._prompt_edit.setPlainText('rain')
        out = tmp_path / 'out.mp4'
        out.write_bytes(b'v')
        window.fake.result_files = [out]
        window._on_run()
        wait_for(lambda: window._results_layout.count() == 1 and window._run_btn.isEnabled())
        assert window._results_layout.itemAt(0).widget().text().endswith('Play')


class TestInputsAndRequests:
    def test_the_request_collects_the_form(self, make_window, tmp_path):
        window = make_window()
        window._prompt_edit.setPlainText('a dragon')
        window._direction_edit.setPlainText('moody')
        window._negative_edit.setText('blurry')
        window._out_dir_edit.setText(str(tmp_path / 'o'))
        window._prefix_edit.setText('drag')
        request = window._build_request()
        assert request.prompt == 'a dragon' and request.annotations == 'moody' and request.filename_prefix == 'drag'
        assert request.output_dir == tmp_path / 'o' and request.image is None and request.params['num_images'] == 1
        window._out_dir_edit.setText('')
        window._prefix_edit.setText('')
        again = window._build_request()
        assert again.output_dir == tw.DEFAULT_OUTPUT_DIR and again.filename_prefix == 'fal'

    def test_browsing(self, make_window, monkeypatch, tmp_path):
        window = make_window()
        select_task(window, _models.IMAGE_TO_IMAGE)
        picks = iter(['C:/src.png', 'C:/ref.png', '', ''])
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (next(picks), '')))
        window._on_browse_image()
        window._on_browse_reference()
        assert window._image_edit.text() == 'C:/src.png' and window._reference_edit.text() == 'C:/ref.png'
        assert window.model.reference_arg == 'reference_image_url'            # a reference picks a model that takes one
        window._on_browse_image()
        window._on_browse_reference()
        assert window._image_edit.text() == 'C:/src.png'
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(tmp_path)))
        window._on_browse_output()
        assert window._out_dir_edit.text() == str(tmp_path)
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
        window._on_browse_output()
        assert window._out_dir_edit.text() == str(tmp_path)

    def test_viewer_notes_fill_the_direction_and_reference(self, make_window, tmp_path, monkeypatch, dialogs):
        window = make_window()
        notes = tmp_path / 'annotations_1.json'
        notes.write_text(json.dumps({'description': 'cooler', 'texts': [{'text': 'rim light'}]}))
        png(tmp_path / 'snapshot_1.png')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (str(notes), '')))
        window._on_use_notes()
        assert window._direction_edit.toPlainText() == 'cooler\nrim light'
        assert window._reference_edit.text().endswith('snapshot_1.png') and 'Loaded notes' in window._status.text()
        (tmp_path / 'snapshot_1.png').unlink()
        window._reference_edit.setText('')
        window._on_use_notes()
        assert 'no snapshot' in window._status.text() and window._reference_edit.text() == ''
        notes.write_text('{ nope')
        window._on_use_notes()
        assert dialogs[-1][:2] == ('warning', 'Viewer notes')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('', '')))
        window._on_use_notes()


class TestRunning:
    def test_a_key_is_required(self, make_window, dialogs):
        window = make_window()
        window.fake.has = False
        window._on_run()
        assert dialogs[-1][:2] == ('warning', 'fal.ai API key') and window.fake.requests == []

    def test_a_typed_key_is_used(self, make_window):
        window = make_window()
        window.fake.has = False
        window._key_edit.setText(' typed ')
        window._prompt_edit.setPlainText('p')
        window._on_run()
        wait_for(lambda: window.fake.requests and window._run_btn.isEnabled())
        assert window.fake.api_key == 'typed'

    def test_inputs_are_validated_before_running(self, make_window, dialogs, tmp_path):
        window = make_window()
        window._on_run()
        assert dialogs[-1][:2] == ('warning', 'fal.ai') and 'needs a prompt' in dialogs[-1][2]
        select_task(window, _models.IMAGE_TO_3D)
        window._on_run()
        assert 'source image' in dialogs[-1][2]
        window._image_edit.setText(str(tmp_path / 'ghost.png'))
        window._on_run()
        assert 'exists' in dialogs[-1][2] and window.fake.requests == []

    def test_text_to_image_shows_thumbnails(self, make_window, tmp_path):
        window = make_window()
        window.fake.result_files = [png(tmp_path / 'a.png'), png(tmp_path / 'b.png'), png(tmp_path / 'c.png'),
                                    png(tmp_path / 'd.png')]
        window._prompt_edit.setPlainText('a dragon')
        window._on_run()
        assert not window._run_btn.isEnabled()
        wait_for(lambda: window._results_layout.count() == 4 and window._run_btn.isEnabled())
        assert 'Done: 4 file(s)' in window._status.text() and 'seed 11' in window._status.text()
        positions = {window._results_layout.getItemPosition(i)[:2] for i in range(4)}
        assert positions == {(0, 0), (0, 1), (0, 2), (1, 0)} and not window._progress.isVisible()
        window._on_clear()
        QtWidgets.QApplication.processEvents()
        assert window._results_layout.count() == 0

    def test_a_mesh_result_gets_an_open_button(self, make_window, tmp_path):
        window = make_window()
        select_task(window, _models.IMAGE_TO_3D)
        window._image_edit.setText(str(png(tmp_path / 'in.png')))
        mesh = tmp_path / 'chair.glb'
        mesh.write_bytes(b'glb')
        window.fake.result_files = [mesh]
        window._on_run()
        wait_for(lambda: window._results_layout.count() == 1 and window._run_btn.isEnabled())
        button = window._results_layout.itemAt(0).widget()
        assert isinstance(button, QtWidgets.QPushButton) and 'chair.glb' in button.text()
        opened = []
        window._open = lambda path: opened.append(path)
        button.click()
        assert opened == [str(mesh)]

    def test_failures_are_shown(self, make_window, dialogs):
        window = make_window()
        window.fake.error = RuntimeError('quota exceeded')
        window._prompt_edit.setPlainText('p')
        window._on_run()
        wait_for(lambda: any(kind == 'critical' for kind, *_ in dialogs) and window._run_btn.isEnabled())
        assert window._status.text() == 'Error: quota exceeded'

    def test_a_second_run_while_busy_is_ignored(self, make_window):
        window = make_window()
        window._worker = types.SimpleNamespace(isRunning=lambda: True)
        window._on_run()
        assert window.fake.requests == []
        window._worker = None

    def test_thumbnails_open_on_click_and_show_names_for_unreadable_files(self, qapp, tmp_path):
        opened = []
        thumb = tw._Thumbnail(str(png(tmp_path / 'a.png')), size=64)
        thumb.clicked.connect(opened.append)
        thumb.show()
        QtTest.QTest.mouseClick(thumb, QtCore.Qt.LeftButton)
        QtTest.QTest.mouseClick(thumb, QtCore.Qt.RightButton)
        assert opened == [str(tmp_path / 'a.png')] and not thumb.pixmap().isNull()
        bad = tmp_path / 'bad.png'
        bad.write_bytes(b'junk')
        assert tw._Thumbnail(str(bad)).text() == 'bad.png'
        thumb.close()

    def test_opening_a_result_uses_the_system_viewer(self, monkeypatch):
        calls = []
        monkeypatch.setattr('os.startfile', lambda path: calls.append(path), raising=False)
        monkeypatch.setattr('subprocess.Popen', lambda cmd: calls.append(cmd))
        tw.FalToolWindow._open('C:/x.png')
        assert calls
        monkeypatch.setattr(tw.sys, 'platform', 'linux')
        tw.FalToolWindow._open('/x.png')
        assert calls[-1] == ['xdg-open', '/x.png']


class TestSettings:
    def test_choices_are_remembered_but_not_the_key(self, make_window, tmp_path):
        window = make_window()
        select_task(window, _models.IMAGE_EDIT)
        window._speed_combo.setCurrentIndex(window._speed_combo.findData('quality'))
        window._out_dir_edit.setText(str(tmp_path / 'saved'))
        window._prefix_edit.setText('shot')
        window._key_edit.setText('secret')
        window.close()
        again = make_window()
        assert again._task_combo.currentData() == _models.IMAGE_EDIT and again._speed_combo.currentData() == 'quality'
        assert again._out_dir_edit.text() == str(tmp_path / 'saved') and again._prefix_edit.text() == 'shot'
        assert again._key_edit.text() == ''
        assert 'secret' not in (tmp_path / 'fal.ini').read_text()

    def test_a_window_without_a_service_makes_its_own_client(self, qapp, tmp_path, monkeypatch):
        real = QtCore.QSettings
        monkeypatch.setattr(tw.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'x.ini'), real.IniFormat))
        window = tw.FalToolWindow()
        assert isinstance(window._client, FalClient)
        window.close()

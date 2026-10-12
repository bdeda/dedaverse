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
"""Tests for the Ollama model browser dialog and its download worker."""
import json
import time

import pytest
from PySide6 import QtCore, QtWidgets

from deda.plugins.ollama import _model_browser as mb


class FakeResponse:
    def __init__(self, lines):
        self._lines = lines

    def iter_lines(self, decode_unicode=True):
        yield from self._lines


class FakeApi:
    def __init__(self, lines=(), installed=(), pull_error=None):
        self.lines = list(lines)
        self.installed = [{'name': n} for n in installed]
        self.pull_error = pull_error
        self.pulled = []
        self.list_error = None

    def pull_model(self, name, stream=True):
        self.pulled.append(name)
        if self.pull_error:
            raise self.pull_error
        return FakeResponse(self.lines)

    def list_models(self):
        if self.list_error:
            raise self.list_error
        return list(self.installed)


def j(**data):
    return json.dumps(data)


def run_worker(api, name='llama3.2'):
    worker = mb.ModelDownloadWorker(api, name)
    progress, finished = [], []
    worker.progress.connect(lambda s, d, t: progress.append((s, d, t)))
    worker.finished.connect(lambda ok, msg: finished.append((ok, msg)))
    worker.run()
    return worker, progress, finished


class TestWorker:
    def test_a_normal_download_reports_progress_and_success(self, qapp):
        lines = [j(status='pulling manifest'), '', '   ', 'not json', j(status='downloading', total=100, completed=40),
                 j(status='downloading', total=100, completed=100), j(status='success')]
        _, progress, finished = run_worker(FakeApi(lines))
        assert progress[0] == ('pulling manifest', 0, 0) and progress[-1] == ('success', 100, 100)
        assert finished == [(True, 'Model "llama3.2" downloaded successfully')]

    def test_a_completion_status_alone_counts(self, qapp):
        _, _, finished = run_worker(FakeApi([j(status='verifying sha256 digest'), j(status='successfully pulled')]))
        assert finished[0][0] is True and 'downloaded successfully' in finished[0][1]

    def test_a_silent_stream_is_still_reported_as_completed(self, qapp):
        _, _, finished = run_worker(FakeApi([j(status='pulling')]))
        assert finished == [(True, 'Model "llama3.2" download completed')]

    def test_cancelling_stops_the_download(self, qapp):
        api = FakeApi([j(status='a'), j(status='b')])
        worker = mb.ModelDownloadWorker(api, 'x')
        finished = []
        worker.finished.connect(lambda ok, msg: finished.append((ok, msg)))
        worker.cancel()
        worker.run()
        assert finished == [(False, 'Download cancelled by user')]

    @pytest.mark.parametrize('error, expected', [
        (RuntimeError('HTTP 404 not found'), 'not found in Ollama'),
        (RuntimeError('401 Unauthorized'), 'Unauthorized'),
        (RuntimeError('Read timeout'), 'timed out'),
        (RuntimeError('500 Internal Server Error'), 'Ollama server error'),
        (RuntimeError('something odd'), 'something odd'),
    ])
    def test_errors_are_explained(self, qapp, error, expected):
        _, _, finished = run_worker(FakeApi(pull_error=error))
        assert finished[0][0] is False and expected in finished[0][1]

    def test_the_server_error_body_is_used(self, qapp):
        class Response:
            text = json.dumps({'error': 'pull model manifest: file does not exist'})

        error = RuntimeError('HTTP 500')
        error.response = Response()
        _, _, finished = run_worker(FakeApi(pull_error=error))
        assert 'file does not exist' in finished[0][1]

    def test_message_bodies_and_plain_text_bodies(self, qapp):
        class Json:
            text = json.dumps({'message': 'disk is full'})

        class Plain:
            text = 'x' * 300

        for body, expected in ((Json, 'disk is full'), (Plain, 'x' * 200)):
            error = RuntimeError('bad')
            error.response = body()
            _, _, finished = run_worker(FakeApi(pull_error=error))
            assert expected in finished[0][1]

    def test_attached_response_text_is_used(self, qapp):
        error = RuntimeError('bad')
        error.response_text = json.dumps({'error': 'attached details'})
        _, _, finished = run_worker(FakeApi(pull_error=error))
        assert 'attached details' in finished[0][1]


@pytest.fixture
def dialogs(monkeypatch):
    seen = []
    for kind in ('warning', 'information', 'critical'):
        monkeypatch.setattr(QtWidgets.QMessageBox, kind, staticmethod(
            lambda parent, title, text, *a, _kind=kind, **k: seen.append((_kind, title, text))))
    monkeypatch.setattr(QtWidgets.QMessageBox, 'question', staticmethod(
        lambda *a, **k: seen.append(('question',)) or QtWidgets.QMessageBox.StandardButton.Yes))
    return seen


@pytest.fixture
def make_dialog(qapp, dialogs):
    created = []

    def build(api=None, category='text', parent=None):
        dialog = mb.ModelBrowserDialog(api or FakeApi(), category, parent=parent)
        created.append(dialog)
        return dialog

    yield build
    for dialog in created:
        dialog.close()


def wait_for(condition, seconds=10):
    deadline = time.time() + seconds
    while time.time() < deadline and not condition():
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    assert condition()


def texts(dialog):
    return [dialog._model_list.item(i).text() for i in range(dialog._model_list.count())]


class TestListing:
    def test_title_and_models_for_the_category(self, make_dialog):
        dialog = make_dialog(category='vision')
        assert dialog.windowTitle() == 'Download Models - Vision Models'
        assert texts(dialog) == ['LLaVA', 'BakLLaVA', 'LLaVA Phi-3', 'Moondream']
        assert dialog._model_list.currentRow() == 0

    def test_installed_models_are_marked(self, make_dialog):
        dialog = make_dialog(FakeApi(installed=['llava:latest', 'llama3.2:3b']), 'vision')
        assert texts(dialog)[0] == 'LLaVA ✓ (Installed)' and 'Moondream' in texts(dialog)

    def test_categories_without_models_are_empty(self, make_dialog):
        dialog = make_dialog(category='image_gen')
        assert texts(dialog) == [] and dialog._name_label.text() == '' and not dialog._download_btn.isEnabled()

    def test_a_failing_model_listing_is_survived(self, make_dialog):
        api = FakeApi()
        api.list_error = RuntimeError('refused')
        assert len(texts(make_dialog(api, 'vision'))) == 4

    def test_the_first_model_is_described_right_away(self, make_dialog):
        dialog = make_dialog(category='text')
        assert dialog._name_label.text() == 'Llama 3.2' and dialog._download_btn.isEnabled()

    def test_selection_shows_the_details(self, make_dialog):
        dialog = make_dialog(category='text')
        dialog._model_list.setCurrentRow(1)
        assert dialog._name_label.text() == 'Llama 3.1' and 'Capabilities' in dialog._capabilities_label.text()
        assert dialog._size_label.text().startswith('<b>Size:') and 'ollama.com/library/llama3.1' in dialog._url_label.text()
        assert dialog._download_btn.isEnabled() and dialog._download_btn.text() == 'Download Model'

    def test_installed_models_cannot_be_downloaded_again(self, make_dialog):
        dialog = make_dialog(FakeApi(installed=['llama3.2']), 'text')
        assert dialog._download_btn.text() == 'Already Installed' and not dialog._download_btn.isEnabled()

    def test_models_being_downloaded_show_that(self, make_dialog):
        dialog = make_dialog(category='text')
        dialog._downloading_models.add('llama3.2')
        dialog._on_selection_changed(dialog._model_list.currentItem(), None)
        assert dialog._download_btn.text() == 'Downloading...' and not dialog._download_btn.isEnabled()

    def test_missing_details_are_blank(self, make_dialog):
        dialog = make_dialog(category='text')
        item = QtWidgets.QListWidgetItem('Bare')
        item.setData(QtCore.Qt.ItemDataRole.UserRole, 'bare')
        item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, {'name': 'Bare'})
        item.setData(QtCore.Qt.ItemDataRole.UserRole + 2, False)
        dialog._on_selection_changed(item, None)
        assert dialog._capabilities_label.text() == dialog._size_label.text() == dialog._url_label.text() == ''
        dialog._on_selection_changed(None, None)
        assert dialog._name_label.text() == ''


class TestDownloading:
    def test_declining_the_confirmation_does_nothing(self, make_dialog, monkeypatch):
        dialog = make_dialog(category='text')
        monkeypatch.setattr(QtWidgets.QMessageBox, 'question', staticmethod(
            lambda *a, **k: QtWidgets.QMessageBox.StandardButton.No))
        dialog._on_download_clicked()
        assert dialog._downloading_models == set() and dialog._download_thread is None

    def test_nothing_to_download_when_nothing_is_selected_or_installed(self, make_dialog):
        make_dialog(category='image_gen')._on_download_clicked()
        installed = make_dialog(FakeApi(installed=['llama3.2']), 'text')
        installed._on_download_clicked()
        busy = make_dialog(category='text')
        busy._downloading_models.add('llama3.2')
        busy._on_download_clicked()
        assert busy._download_thread is None
        installed._on_model_double_clicked(installed._model_list.item(0))
        assert installed._download_thread is None

    def test_a_full_download_in_a_thread(self, make_dialog, dialogs):
        api = FakeApi([j(status='downloading', total=10, completed=5), j(status='success')], installed=[])
        dialog = make_dialog(api, 'text')
        dialog._on_download_clicked()
        assert not dialog._download_btn.isEnabled() and dialog._download_btn.text() == 'Downloading...'
        wait_for(lambda: any(kind == 'information' for kind, *_ in dialogs) and dialog._download_thread is None)
        assert api.pulled == ['llama3.2'] and dialog._downloading_models == set()
        assert not dialog._progress_bar.isVisible() and not dialog._cancel_btn.isVisible()
        assert dialogs[-1][:2] == ('information', 'Download Complete')

    def test_a_failed_download_is_reported_and_unlocks_the_button(self, make_dialog, dialogs):
        dialog = make_dialog(FakeApi(pull_error=RuntimeError('401 unauthorized')), 'text')
        dialog._on_download_clicked()
        wait_for(lambda: any(kind == 'critical' for kind, *_ in dialogs) and dialog._download_thread is None)
        assert dialog._download_btn.isEnabled() and dialog._download_btn.text() == 'Download Model'

    def test_a_cancelled_download_is_not_reported_as_an_error(self, make_dialog, dialogs):
        dialog = make_dialog(category='text')
        dialog._on_download_finished(False, 'Download cancelled by user')
        assert dialogs == []

    def test_cancelling_flags_the_worker(self, make_dialog):
        dialog = make_dialog(category='text')
        dialog._on_cancel_download()
        worker = mb.ModelDownloadWorker(FakeApi(), 'x')
        dialog._download_worker = worker
        dialog._on_cancel_download()
        assert worker._cancelled and dialog._cancel_btn.text() == 'Cancelling...' and not dialog._cancel_btn.isEnabled()

    def test_progress_display(self, make_dialog):
        dialog = make_dialog(category='text')
        dialog._on_download_progress('downloading', 50, 200)
        assert dialog._progress_bar.value() == 25 and dialog._progress_bar.format() == 'downloading... 25%'
        dialog._on_download_progress('', 100, 100)
        assert dialog._progress_bar.format() == '100%'
        dialog._on_download_progress('verifying', 0, 0)
        assert dialog._progress_bar.maximum() == 0 and dialog._progress_bar.format() == 'verifying...'
        dialog._on_download_progress('', 0, 0)
        assert dialog._progress_bar.format() == ''


class TestVerification:
    def test_a_confirmed_install_reloads_the_list_and_the_parent(self, make_dialog, monkeypatch):
        api = FakeApi(installed=['llama3.2:latest'])
        parent_calls = []

        class Parent(QtWidgets.QWidget):
            def _load_models(self):
                parent_calls.append(1)

        parent = Parent()
        scheduled = []
        monkeypatch.setattr(mb.QtCore.QTimer, 'singleShot', staticmethod(lambda ms, fn: scheduled.append((ms, fn))))
        dialog = make_dialog(api, 'text', parent=parent)
        assert dialog._verify_model_installed('llama3.2') is True
        scheduled[-1][1]()
        assert parent_calls == [1] and texts(dialog)[0].endswith('(Installed)')

    def test_missing_models_are_retried_with_a_growing_delay_and_then_given_up(self, make_dialog, monkeypatch):
        scheduled = []
        monkeypatch.setattr(mb.QtCore.QTimer, 'singleShot', staticmethod(lambda ms, fn: scheduled.append((ms, fn))))
        dialog = make_dialog(FakeApi(installed=[]), 'text')
        assert dialog._verify_model_installed('llama3.2') is False
        assert scheduled[-1][0] == 500
        assert dialog._verify_model_installed('llama3.2', retry_count=3) is False and scheduled[-1][0] == 2000
        before = len(scheduled)
        assert dialog._verify_model_installed('llama3.2', retry_count=5) is False
        assert len(scheduled) == before                                           # no further retries

    def test_giving_up_still_refreshes_a_parent_window(self, make_dialog, monkeypatch):
        parent_calls = []

        class Parent(QtWidgets.QWidget):
            def _load_models(self):
                parent_calls.append(1)

        scheduled = []
        monkeypatch.setattr(mb.QtCore.QTimer, 'singleShot', staticmethod(lambda ms, fn: scheduled.append(fn)))
        parent = Parent()
        dialog = make_dialog(FakeApi(), 'text', parent=parent)
        dialog._verify_model_installed('llama3.2', retry_count=5)
        scheduled[-1]()
        assert parent_calls == [1]

    def test_errors_while_verifying_are_retried(self, make_dialog, monkeypatch):
        scheduled = []
        monkeypatch.setattr(mb.QtCore.QTimer, 'singleShot', staticmethod(lambda ms, fn: scheduled.append(ms)))
        api = FakeApi()
        dialog = make_dialog(api, 'text')
        api.list_error = RuntimeError('refused')
        assert dialog._verify_model_installed('llama3.2') is False and scheduled == [500]
        assert dialog._verify_model_installed('llama3.2', retry_count=5) is False and scheduled == [500]

    def test_a_successful_finish_schedules_the_verification(self, make_dialog, monkeypatch, dialogs):
        scheduled = []
        monkeypatch.setattr(mb.QtCore.QTimer, 'singleShot', staticmethod(lambda ms, fn: scheduled.append(ms)))
        dialog = make_dialog(category='text')
        dialog._on_download_finished(True, 'Model "x" downloaded successfully')
        assert scheduled == [500] and dialogs[-1][1] == 'Download Complete'

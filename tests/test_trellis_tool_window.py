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
"""Tests for the Trellis tool window (against a fake API client and service)."""
import time
import types

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from deda.plugins.trellis import _tool_window as tw
from deda.plugins.trellis import _trellis2


class FakeApi:
    def __init__(self, base_url='http://127.0.0.1:7860'):
        self.base_url = base_url
        self.connected = True
        self.generated = []
        self.glb = b'glb-bytes'
        self.usd = b'usd-bytes'
        self.error = None

    def check_connection(self):
        return self.connected

    def generate_3d_from_image(self, image_path, **kwargs):
        if self.error:
            raise self.error
        self.generated.append((image_path, kwargs))
        return {'state': {'seed': 1}, 'seed': 1, 'preview_html': '<div/>'}

    def extract_glb(self, state, decimation_target, texture_size):
        if self.error:
            raise self.error
        self.extracted = (state, decimation_target, texture_size)
        return self.glb

    def extract_usd(self, state, decimation_target, texture_size):
        if self.error:
            raise self.error
        return self.usd


class FakeService:
    def __init__(self, can_start=True):
        self.can_start = can_start
        self.running = False
        self.started = 0
        self.start_error = None

    def get_base_url(self):
        return 'http://trellis.local:7000'

    def can_start_server(self):
        return self.can_start

    def server_running(self):
        return self.running

    def log_path(self):
        return 'C:/logs/server.log'

    def start_server(self):
        if self.start_error:
            raise self.start_error
        self.started += 1


@pytest.fixture
def dialogs(monkeypatch):
    seen = []
    for kind in ('warning', 'information', 'critical'):
        monkeypatch.setattr(QtWidgets.QMessageBox, kind, staticmethod(
            lambda parent, title, text, *a, _kind=kind, **k: seen.append((_kind, title, text))))
    return seen


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr(tw, 'TrellisApiClient', lambda base_url: fake)
    return fake


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch, dialogs, api):
    real = QtCore.QSettings
    monkeypatch.setattr(tw.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'trellis.ini'), real.IniFormat))
    created = []

    def build(service=None):
        window = tw.TrellisToolWindow(service=service)
        created.append(window)
        return window

    yield build
    for window in created:
        window._server_poll_timer.stop()
        window.close()


@pytest.fixture
def image(tmp_path):
    path = tmp_path / 'in.png'
    img = QtGui.QImage(32, 16, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtCore.Qt.blue)
    img.save(str(path))
    return path


def url_mime(*paths):
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(p)) for p in paths])
    return mime


def drag_enter(widget, mime):
    event = QtGui.QDragEnterEvent(QtCore.QPoint(2, 2), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    widget.dragEnterEvent(event)
    return event


def drop(widget, mime):
    event = QtGui.QDropEvent(QtCore.QPointF(2, 2), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    widget.dropEvent(event)
    return event


def wait_for(condition, seconds=10):
    deadline = time.time() + seconds
    while time.time() < deadline and not condition():
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    assert condition()


class TestImageDropLabel:
    def test_accepts_only_image_files(self, qapp, image, tmp_path):
        label = tw.ImageDropLabel()
        dropped = []
        label.image_dropped.connect(dropped.append)
        text = tmp_path / 'notes.txt'
        text.write_text('x')
        text_mime = url_mime(text)
        refused = drag_enter(label, text_mime)
        assert not refused.isAccepted() and not label._drag_over
        refused_move = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, text_mime, QtCore.Qt.LeftButton,
                                            QtCore.Qt.NoModifier)
        label.dragMoveEvent(refused_move)
        mime = url_mime(image)
        accepted = drag_enter(label, mime)
        assert accepted.isAccepted() and label._drag_over and 'green' in label.styleSheet()
        move = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        label.dragMoveEvent(move)
        assert move.isAccepted()
        event = drop(label, mime)
        assert event.isAccepted() and dropped == [str(image)] and not label._drag_over

    def test_leaving_resets_the_highlight_and_bad_drops_are_ignored(self, qapp, tmp_path):
        label = tw.ImageDropLabel()
        label._drag_over = True
        label.dragLeaveEvent(QtGui.QDragLeaveEvent())
        assert not label._drag_over and 'gray' in label.styleSheet()
        ghost = url_mime(tmp_path / 'missing.png')
        assert not drop(label, ghost).isAccepted()
        empty = QtCore.QMimeData()                              # events do not own their mime data: keep it alive
        assert not drop(label, empty).isAccepted()
        remote = QtCore.QMimeData()
        remote.setUrls([QtCore.QUrl('http://example.com/x.png')])
        assert not drop(label, remote).isAccepted()


class TestWindowSetup:
    def test_the_api_url_comes_from_the_service(self, make_window, api, monkeypatch):
        urls = []
        monkeypatch.setattr(tw, 'TrellisApiClient', lambda base_url: urls.append(base_url) or api)
        make_window(FakeService())
        make_window(None)
        assert urls == ['http://trellis.local:7000', 'http://127.0.0.1:7860']

    def test_defaults_match_the_small_gpu_advice(self, make_window):
        window = make_window()
        assert window._resolution_combo.currentText() == '512' and window._randomize_seed_check.isChecked()
        assert window.windowTitle().startswith('Trellis')

    def test_a_missing_client_is_explained(self, make_window, monkeypatch):
        def missing(base_url):
            raise ImportError('gradio_client is required')

        monkeypatch.setattr(tw, 'TrellisApiClient', missing)
        window = make_window()
        assert 'gradio_client is required' in window._status_bar.currentMessage() and window._api_client is None


class TestConnectionStatus:
    def test_connected(self, make_window):
        window = make_window(FakeService())
        assert window._status_bar.currentMessage() == 'Connected to Trellis' and window._start_server_btn.isHidden()

    def test_disconnected_offers_to_start_the_server_when_possible(self, make_window, api):
        api.connected = False
        window = make_window(FakeService(can_start=True))
        assert not window._start_server_btn.isHidden() and 'Use "Start TRELLIS.2 Server"' in window._status_bar.currentMessage()
        again = make_window(FakeService(can_start=False))
        assert again._start_server_btn.isHidden() and 'server is running' in again._status_bar.currentMessage()

    def test_while_the_server_loads_the_status_says_so(self, make_window, api):
        api.connected = False
        service = FakeService()
        window = make_window(service)
        service.running = True
        window._server_poll_timer.start()
        window._update_connection_status()
        assert 'Starting TRELLIS.2 server' in window._status_bar.currentMessage()
        assert window._server_poll_timer.isActive()

    def test_a_server_that_exited_points_to_the_log(self, make_window, api):
        api.connected = False
        service = FakeService()
        window = make_window(service)
        window._server_poll_timer.start()
        window._update_connection_status()
        assert 'server.log' in window._status_bar.currentMessage() and not window._server_poll_timer.isActive()
        assert not window._start_server_btn.isHidden()

    def test_a_connection_stops_the_polling(self, make_window, api):
        api.connected = False
        window = make_window(FakeService())
        window._server_poll_timer.start()
        api.connected = True
        window._update_connection_status()
        assert not window._server_poll_timer.isActive()


class TestStartServer:
    def test_a_ready_environment_starts_the_server_and_polls(self, make_window, api, monkeypatch):
        api.connected = False
        service = FakeService()
        window = make_window(service)
        monkeypatch.setattr(_trellis2, 'find_install', lambda path=None: 'C:/TRELLIS.2')
        monkeypatch.setattr(_trellis2, 'probe', lambda install: (True, 'GPU has 16 GB.'))
        service.running = True
        window._on_start_server_clicked()
        assert service.started == 1 and window._server_poll_timer.isActive()
        assert 'GPU has 16 GB.' in window._status_text.toPlainText()

    def test_an_environment_problem_is_shown(self, make_window, api, monkeypatch, dialogs):
        api.connected = False
        service = FakeService()
        window = make_window(service)
        monkeypatch.setattr(_trellis2, 'find_install', lambda path=None: 'C:/TRELLIS.2')
        monkeypatch.setattr(_trellis2, 'probe', lambda install: (False, 'torch is missing'))
        window._on_start_server_clicked()
        assert service.started == 0 and dialogs == [('warning', 'TRELLIS.2 is not ready', 'torch is missing')]

    def test_a_server_that_cannot_start_is_reported(self, make_window, api, monkeypatch, dialogs):
        api.connected = False
        service = FakeService()
        service.start_error = FileNotFoundError('no install')
        window = make_window(service)
        monkeypatch.setattr(_trellis2, 'find_install', lambda path=None: None)
        monkeypatch.setattr(_trellis2, 'probe', lambda install: (True, 'ok'))
        window._on_start_server_clicked()
        assert dialogs[-1][:2] == ('critical', 'Could not start the server') and not window._server_poll_timer.isActive()


class TestImagePreview:
    def test_browse_and_preview(self, make_window, image, monkeypatch):
        window = make_window()
        window.resize(900, 700)
        window.show()
        window._image_path_edit.setText(str(image))
        assert window._image_preview.pixmap() is not None and not window._image_preview.pixmap().isNull()
        assert window._image_preview.text() == ''
        window._image_path_edit.setText('')
        assert 'Drag and drop' in window._image_preview.text()
        window.resize(950, 720)
        QtWidgets.QApplication.processEvents()
        window.close()

    def test_an_unreadable_image_shows_the_placeholder(self, make_window, tmp_path):
        bad = tmp_path / 'bad.png'
        bad.write_bytes(b'junk')
        window = make_window()
        window._image_path_edit.setText(str(bad))
        assert 'Drag and drop' in window._image_preview.text()

    def test_dropping_on_the_preview_or_window_sets_the_path(self, make_window, image, tmp_path):
        window = make_window()
        window._image_preview.image_dropped.emit(str(image))
        assert window._image_path_edit.text() == str(image)
        window._image_path_edit.setText('')
        mime = url_mime(image)
        assert drag_enter(window, mime).isAccepted()
        move = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        window.dragMoveEvent(move)
        assert move.isAccepted() and drop(window, mime).isAccepted() and window._image_path_edit.text() == str(image)
        text = tmp_path / 'a.txt'
        text.write_text('x')
        bad = url_mime(text)
        assert not drag_enter(window, bad).isAccepted()
        refused = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, bad, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        window.dragMoveEvent(refused)
        assert not refused.isAccepted() and not drop(window, bad).isAccepted()
        empty = QtCore.QMimeData()
        assert not drop(window, empty).isAccepted()
        none = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, empty, QtCore.Qt.LeftButton,
                                    QtCore.Qt.NoModifier)
        window.dragMoveEvent(none)
        assert not none.isAccepted()


class TestGeneration:
    def test_it_validates_before_starting(self, make_window, api, image, dialogs, tmp_path):
        window = make_window(FakeService())
        window._on_generate_clicked()
        assert dialogs[-1][1] == 'Missing Image'
        window._image_path_edit.setText(str(image))
        api.connected = False
        window._on_generate_clicked()
        assert dialogs[-1][1] == 'Connection Failed' and 'http://127.0.0.1:7860' in dialogs[-1][2]
        window._api_client = None
        window._on_generate_clicked()
        assert dialogs[-1][1] == 'Not Connected'

    def test_generating_runs_in_a_thread_and_enables_extraction(self, make_window, api, image):
        window = make_window(FakeService())
        window._image_path_edit.setText(str(image))
        window._randomize_seed_check.setChecked(False)
        window._seed_spin.setValue(42)
        window._resolution_combo.setCurrentText('1024')
        window._on_generate_clicked()
        wait_for(lambda: window._generated_state is not None and window._generation_thread is None)
        path, kwargs = api.generated[0]
        assert path == str(image) and kwargs['seed'] == 42 and kwargs['resolution'] == '1024'
        assert kwargs['randomize_seed'] is False and kwargs['ss_sampling_steps'] == 12
        assert window._extract_glb_btn.isEnabled() and window._extract_usd_btn.isEnabled()
        assert not window._progress_bar.isVisible() and 'generated' in window._status_text.toPlainText()

    def test_random_seed_is_not_forwarded(self, make_window, api, image):
        window = make_window(FakeService())
        window._image_path_edit.setText(str(image))
        window._on_generate_clicked()
        wait_for(lambda: api.generated and window._generation_thread is None)
        assert api.generated[0][1]['seed'] is None and api.generated[0][1]['randomize_seed'] is True

    def test_failures_are_reported(self, make_window, api, image, dialogs):
        window = make_window(FakeService())
        window._image_path_edit.setText(str(image))
        api.error = RuntimeError('out of memory')
        window._on_generate_clicked()
        wait_for(lambda: dialogs and window._generation_thread is None)
        assert dialogs[-1][:2] == ('critical', 'Generation Failed') and 'Error: out of memory' in window._status_text.toPlainText()
        assert not window._extract_glb_btn.isEnabled()

    def test_a_result_without_state_warns(self, make_window):
        window = make_window(FakeService())
        window._on_generation_finished(True, 'done', {})
        assert 'No state data' in window._status_text.toPlainText() and not window._extract_glb_btn.isEnabled()

    def test_cleanup_without_a_thread_is_safe(self, make_window):
        window = make_window()
        window._cleanup_generation_thread()


class TestExtraction:
    @pytest.fixture
    def ready(self, make_window, api, tmp_path):
        window = make_window(FakeService())
        window._generated_state = {'seed': 1}
        window._output_path_edit.setText(str(tmp_path / 'out' / 'model.glb'))
        return window

    def test_glb_needs_a_model_and_a_path(self, make_window, dialogs):
        window = make_window()
        window._on_extract_glb_clicked()
        assert dialogs[-1][1] == 'No Model'
        window._generated_state = {'a': 1}
        window._on_extract_glb_clicked()
        assert dialogs[-1][1] == 'Missing Output Path'

    def test_glb_is_written_with_the_chosen_settings(self, ready, api, tmp_path, dialogs):
        ready._decimation_spin.setValue(200000)
        ready._texture_size_spin.setValue(1024)
        ready._on_extract_glb_clicked()
        assert (tmp_path / 'out' / 'model.glb').read_bytes() == b'glb-bytes'
        assert api.extracted == ({'seed': 1}, 200000, 1024) and dialogs[-1][:2] == ('information', 'Success')
        assert ready._extract_glb_btn.isEnabled()

    def test_empty_glb_data_warns_and_errors_are_reported(self, ready, api, dialogs):
        api.glb = b''
        ready._on_extract_glb_clicked()
        assert 'No GLB data' in ready._status_text.toPlainText()
        api.error = RuntimeError('server gone')
        ready._on_extract_glb_clicked()
        assert dialogs[-1][:2] == ('critical', 'Extraction Failed') and ready._extract_glb_btn.isEnabled()

    def test_usd_extraction(self, ready, api, tmp_path, dialogs, monkeypatch):
        target = tmp_path / 'usd' / 'model.usd'
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (str(target), '')))
        ready._on_extract_usd_clicked()
        assert target.read_bytes() == b'usd-bytes' and dialogs[-1][0] == 'information'
        api.usd = b''
        ready._on_extract_usd_clicked()
        assert 'No USD data' in ready._status_text.toPlainText()

    def test_usd_extraction_edge_cases(self, ready, api, tmp_path, dialogs, monkeypatch):
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: ('', '')))
        ready._on_extract_usd_clicked()
        assert dialogs == []
        ready._generated_state = None
        ready._on_extract_usd_clicked()
        assert dialogs[-1][1] == 'No Model'
        ready._generated_state = {'a': 1}
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName',
                            staticmethod(lambda *a, **k: (str(tmp_path / 'x.usd'), '')))
        api.error = ImportError('pxr')
        ready._on_extract_usd_clicked()
        assert dialogs[-1][1] == 'Missing Dependencies'
        api.error = RuntimeError('boom')
        ready._on_extract_usd_clicked()
        assert dialogs[-1][1] == 'Extraction Failed' and ready._extract_usd_btn.isEnabled()


class TestWindowState:
    def test_geometry_is_saved_and_restored(self, make_window, qapp, monkeypatch):
        window = make_window()
        window.resize(910, 720)
        window.show()
        QtWidgets.QApplication.processEvents()
        window._save_window_state()
        saved = window._settings.value('trellis_tool_window/geometry')
        assert saved and window._settings.value('trellis_tool_window/state') is not None
        restored = []
        monkeypatch.setattr(tw.TrellisToolWindow, 'restoreGeometry', lambda self, geometry: restored.append(geometry))
        make_window()._restore_window_state()
        assert restored == [saved]

    def test_closing_stops_a_running_generation(self, make_window):
        window = make_window()

        class Running:
            stopped = []

            def isRunning(self):
                return True

            def quit(self):
                self.stopped.append('quit')

            def wait(self, ms=None):
                self.stopped.append('wait')
                return len(self.stopped) > 4

            def terminate(self):
                self.stopped.append('terminate')

        thread = Running()
        window._generation_thread = thread
        window.close()
        assert 'quit' in thread.stopped and 'terminate' in thread.stopped
        window._generation_thread = None

    def test_state_errors_are_tolerated(self, make_window, monkeypatch):
        window = make_window()
        monkeypatch.setattr(window, 'saveGeometry', lambda: 1 / 0)
        window._save_window_state()
        monkeypatch.setattr(window, 'restoreGeometry', lambda g: 1 / 0)
        window._settings.setValue('trellis_tool_window/geometry', QtCore.QByteArray(b'x'))
        window._restore_window_geometry()
        monkeypatch.setattr(window, 'restoreState', lambda s: 1 / 0)
        window._settings.setValue('trellis_tool_window/state', QtCore.QByteArray(b'x'))
        window._restore_window_state()

    def test_showing_restores_the_cursor_once(self, make_window, monkeypatch):
        restored = []
        monkeypatch.setattr(QtWidgets.QApplication, 'restoreOverrideCursor', staticmethod(lambda: restored.append(1)))
        window = make_window()
        window.show()
        window.hide()
        window.show()
        QtCore.QCoreApplication.processEvents()
        time.sleep(0.1)
        QtCore.QCoreApplication.processEvents()
        assert restored and window._shown
        window.close()

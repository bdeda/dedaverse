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
"""Tests for the image generation tool window and its helper widgets."""
import time
import types
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from deda.plugins.imagegen import _tool_window as tw
from deda.plugins.imagegen._api_client import ImageGenBackend, ImageGenClient, ImageGenResult


def png(tmp_path, name='a.png'):
    path = tmp_path / name
    image = QtGui.QImage(30, 20, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtCore.Qt.green)
    image.save(str(path))
    return path


def wait_for(condition, seconds=10):
    deadline = time.time() + seconds
    while time.time() < deadline and not condition():
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    assert condition()


@pytest.fixture
def dialogs(monkeypatch):
    seen = []
    for kind in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QtWidgets.QMessageBox, kind, staticmethod(
            lambda parent, title, text, *a, _kind=kind, **k: seen.append((_kind, title, text))))
    return seen


class TestImageDropArea:
    def test_it_lists_unique_paths(self, qapp):
        area = tw._ImageDropArea()
        area.add_path('C:/a.png')
        area.add_path('C:/a.png')
        area.add_path('C:/b.png')
        assert area.all_paths() == ['C:/a.png', 'C:/b.png'] and area.item(0).text() == 'a.png'
        area.item(1).setSelected(True)
        assert area.selected_paths() == ['C:/b.png']

    def test_drops_add_only_image_files(self, qapp, tmp_path):
        area = tw._ImageDropArea()
        added = []
        area.images_added.connect(added.append)
        mime = QtCore.QMimeData()
        image, text = png(tmp_path), tmp_path / 'notes.txt'
        text.write_text('x')
        mime.setUrls([QtCore.QUrl.fromLocalFile(str(image)), QtCore.QUrl.fromLocalFile(str(text))])
        enter = QtGui.QDragEnterEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        area.dragEnterEvent(enter)
        move = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        area.dragMoveEvent(move)
        area.dropEvent(QtGui.QDropEvent(QtCore.QPointF(1, 1), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton,
                                        QtCore.Qt.NoModifier))
        assert enter.isAccepted() and move.isAccepted()
        assert [Path(x) for x in area.all_paths()] == [image] and [[Path(x) for x in batch] for batch in added] == [[image]]
        nothing = QtCore.QMimeData()
        refused = QtGui.QDragEnterEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, nothing, QtCore.Qt.LeftButton,
                                        QtCore.Qt.NoModifier)
        area.dragEnterEvent(refused)
        refused_move = QtGui.QDragMoveEvent(QtCore.QPoint(1, 1), QtCore.Qt.CopyAction, nothing, QtCore.Qt.LeftButton,
                                            QtCore.Qt.NoModifier)
        area.dragMoveEvent(refused_move)
        assert not refused.isAccepted() and not refused_move.isAccepted()
        area.dropEvent(QtGui.QDropEvent(QtCore.QPointF(1, 1), QtCore.Qt.CopyAction, nothing, QtCore.Qt.LeftButton,
                                        QtCore.Qt.NoModifier))
        assert len(added) == 1


class TestThumbnail:
    def test_shows_the_picture_and_reports_clicks(self, qapp, tmp_path):
        thumb = tw._ThumbnailWidget(str(png(tmp_path)), size=64)
        thumb.show()
        clicks = []
        thumb.clicked.connect(clicks.append)
        QtTest.QTest.mouseClick(thumb, QtCore.Qt.LeftButton)
        QtTest.QTest.mouseClick(thumb, QtCore.Qt.RightButton)
        assert thumb.pixmap() is not None and not thumb.pixmap().isNull() and clicks == [str(png(tmp_path))]
        thumb.close()

    def test_an_unreadable_file_has_a_placeholder(self, qapp, tmp_path):
        bad = tmp_path / 'bad.png'
        bad.write_bytes(b'junk')
        assert tw._ThumbnailWidget(str(bad)).text() == '(no preview)'


class TestGenerateWorker:
    def test_success_and_failure_are_reported_by_signal(self, qapp):
        class Client:
            def __init__(self, result=None, error=None):
                self.result, self.error = result, error

            def generate(self, request):
                if self.error:
                    raise self.error
                return self.result

        done, failed = [], []
        worker = tw._GenerateWorker(Client(result='result'), 'request')
        worker.finished.connect(done.append)
        worker.run()
        broken = tw._GenerateWorker(Client(error=RuntimeError('quota')), 'request')
        broken.error.connect(failed.append)
        broken.run()
        assert done == ['result'] and failed == ['quota']


class TestBackendSettings:
    def test_getters_and_defaults(self, qapp):
        widget = tw._BackendSettingsWidget()
        widget._gemini_key.setText(' key ')
        widget._ollama_url.setText(' http://o ')
        widget._generic_image_key.setText('  ')
        widget._generic_format.setText('')
        assert widget.gemini_key() == 'key' and widget.ollama_url() == 'http://o'
        assert widget.generic_image_key() == 'images' and widget.generic_format() == 'png'
        assert widget.gemini_model() == widget.ollama_model() == widget.generic_endpoint() == widget.generic_auth() == ''

    @pytest.mark.parametrize('backend, index', [(ImageGenBackend.GEMINI, 0), (ImageGenBackend.OLLAMA, 1),
                                                (ImageGenBackend.GENERIC, 2)])
    def test_panels_follow_the_backend(self, qapp, backend, index):
        widget = tw._BackendSettingsWidget()
        widget.show_backend(backend)
        assert widget._stack.currentIndex() == index
        widget.show_backend('unknown')
        assert widget._stack.currentIndex() == 0

    def test_settings_round_trip_without_the_api_key(self, qapp, tmp_path):
        settings = QtCore.QSettings(str(tmp_path / 's.ini'), QtCore.QSettings.IniFormat)
        widget = tw._BackendSettingsWidget()
        widget._gemini_key.setText('secret')
        widget._gemini_model.setText('imagen-x')
        widget._ollama_model.setText('sdxl')
        widget._generic_endpoint.setText('http://g')
        widget.save_settings(settings)
        assert 'secret' not in ' '.join(str(settings.value(k)) for k in settings.allKeys())
        other = tw._BackendSettingsWidget()
        other.restore_settings(settings)
        assert other.gemini_model() == 'imagen-x' and other.ollama_model() == 'sdxl'
        assert other.generic_endpoint() == 'http://g' and other.gemini_key() == ''


class FakeService:
    def __init__(self):
        self.client = ImageGenClient()
        self.client_calls = []


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch, dialogs):
    real = QtCore.QSettings
    monkeypatch.setattr(tw.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'imagegen.ini'), real.IniFormat))
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    created = []

    def build(service=None):
        window = tw.ImageGenToolWindow(service=service)
        created.append(window)
        return window

    yield build
    for window in created:
        if window._worker is not None:
            window._worker.wait(5000)
        window.close()


class TestWindow:
    def test_defaults(self, make_window):
        window = make_window()
        assert window.windowTitle() == 'Image Generation' and window._backend_combo.count() == 3
        assert window._width_spin.value() == window._height_spin.value() == 1024 and window._status_label.text() == 'Ready'
        assert window._prefix_edit.text() == 'imagegen'

    def test_the_backend_combo_switches_the_settings_panel(self, make_window):
        window = make_window()
        window._backend_combo.setCurrentIndex(2)
        assert window._backend_settings._stack.currentIndex() == 2

    def test_reference_images(self, make_window, tmp_path, monkeypatch):
        window = make_window()
        pictures = [str(png(tmp_path, 'a.png')), str(png(tmp_path, 'b.png'))]
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileNames', staticmethod(lambda *a, **k: (pictures, '')))
        window._on_add_reference()
        assert window._ref_list.all_paths() == pictures
        window._ref_list.item(0).setSelected(True)
        window._on_remove_reference()
        assert window._ref_list.all_paths() == [pictures[1]]

    def test_browsing_for_the_output_folder(self, make_window, monkeypatch, tmp_path):
        window = make_window()
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(tmp_path)))
        window._on_browse_output()
        assert window._out_dir_edit.text() == str(tmp_path)
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: ''))
        window._on_browse_output()
        assert window._out_dir_edit.text() == str(tmp_path)


class TestBuildingTheClient:
    def test_gemini_needs_a_key_from_the_field_or_the_environment(self, make_window, dialogs, monkeypatch):
        window = make_window()
        assert window._build_client() is None and dialogs[-1][1] == 'Missing API Key'
        monkeypatch.setenv('GEMINI_API_KEY', 'env-key')
        client = window._build_client()
        assert client._gemini_api_key == 'env-key'
        window._backend_settings._gemini_key.setText('typed-key')
        window._backend_settings._gemini_model.setText('imagen-x')
        client = window._build_client()
        assert client._gemini_api_key == 'typed-key' and client._gemini_model == 'imagen-x'

    def test_ollama_settings_are_applied(self, make_window):
        window = make_window()
        window._backend_combo.setCurrentIndex(1)
        window._backend_settings._ollama_url.setText('http://box:1')
        window._backend_settings._ollama_model.setText('sdxl')
        client = window._build_client()
        assert client.backend == ImageGenBackend.OLLAMA and client._ollama_url == 'http://box:1'

    def test_generic_needs_an_endpoint(self, make_window, dialogs):
        window = make_window()
        window._backend_combo.setCurrentIndex(2)
        assert window._build_client() is None and dialogs[-1][1] == 'Missing Endpoint'
        window._backend_settings._generic_endpoint.setText('http://g')
        window._backend_settings._generic_auth.setText('Bearer t')
        client = window._build_client()
        assert client._generic_endpoint == 'http://g' and client._generic_auth_header == 'Bearer t'

    def test_a_service_supplies_the_client(self, make_window):
        service = FakeService()
        window = make_window(service)
        window._backend_combo.setCurrentIndex(1)
        assert window._build_client() is service.client and service.client.backend == ImageGenBackend.OLLAMA


class TestGenerating:
    def test_a_prompt_is_required(self, make_window, dialogs):
        window = make_window()
        window._on_generate()
        assert dialogs[-1][1] == 'Missing Prompt'

    def test_a_missing_client_stops_generation(self, make_window, dialogs):
        window = make_window()
        window._prompt_edit.setPlainText('a hero')
        window._on_generate()
        assert dialogs[-1][1] == 'Missing API Key' and window._worker is None

    def test_generation_runs_in_a_thread_and_shows_thumbnails(self, make_window, tmp_path, monkeypatch):
        window = make_window()
        window._backend_combo.setCurrentIndex(1)
        window._prompt_edit.setPlainText(' a hero ')
        window._neg_prompt_edit.setText('blurry')
        window._doc_group.setChecked(True)
        window._doc_edit.setPlainText('design notes')
        window._ref_list.add_path(str(png(tmp_path, 'ref.png')))
        window._width_spin.setValue(512)
        window._count_spin.setValue(2)
        window._out_dir_edit.setText(str(tmp_path / 'out'))
        window._prefix_edit.setText('hero')
        requests = []
        images = [png(tmp_path, 'g1.png'), png(tmp_path, 'g2.png')]

        def fake_generate(self, request):
            requests.append(request)
            return ImageGenResult(images=images, prompt_used='p', backend='ollama', model='m')

        monkeypatch.setattr(ImageGenClient, 'generate', fake_generate)
        window._on_generate()
        assert not window._generate_btn.isEnabled()
        wait_for(lambda: window._results_layout.count() == 2 and window._generate_btn.isEnabled())
        request = requests[0]
        assert request.prompt == 'a hero' and request.negative_prompt == 'blurry' and request.documentation == 'design notes'
        assert request.width == 512 and request.num_images == 2 and request.filename_prefix == 'hero'
        assert request.output_dir == tmp_path / 'out' and [p.name for p in request.reference_images] == ['ref.png']
        assert window._status_label.text().startswith('Done') and not window._progress.isVisible()

    def test_documentation_is_left_out_when_the_group_is_unchecked(self, make_window, monkeypatch):
        window = make_window()
        window._backend_combo.setCurrentIndex(1)
        window._prompt_edit.setPlainText('x')
        window._doc_edit.setPlainText('ignored')
        window._doc_group.setChecked(False)
        window._out_dir_edit.setText('')
        window._prefix_edit.setText('')
        seen = []
        monkeypatch.setattr(ImageGenClient, 'generate', lambda self, request: seen.append(request) or
                            ImageGenResult(images=[], prompt_used='', backend='ollama', model='m'))
        window._on_generate()
        wait_for(lambda: seen and window._generate_btn.isEnabled())
        assert seen[0].documentation == '' and seen[0].filename_prefix == 'imagegen'
        assert seen[0].output_dir == Path.home() / 'dedaverse' / 'imagegen'

    def test_errors_are_shown(self, make_window, dialogs, monkeypatch):
        window = make_window()
        window._backend_combo.setCurrentIndex(1)
        window._prompt_edit.setPlainText('x')

        def boom(self, request):
            raise RuntimeError('server down')

        monkeypatch.setattr(ImageGenClient, 'generate', boom)
        window._on_generate()
        wait_for(lambda: any(kind == 'critical' for kind, *_ in dialogs))
        assert window._status_label.text() == 'Error: server down' and window._generate_btn.isEnabled()

    def test_a_second_request_while_running_is_ignored(self, make_window):
        window = make_window()
        window._worker = types.SimpleNamespace(isRunning=lambda: True)
        window._on_generate()
        assert window._status_label.text() == 'Ready'
        window._worker = None


class TestResultsAndFolders:
    def test_thumbnails_wrap_into_rows_and_can_be_cleared(self, make_window, tmp_path):
        window = make_window()
        window._add_thumbnails([png(tmp_path, f'{i}.png') for i in range(4)])
        positions = {window._results_layout.getItemPosition(i)[:2] for i in range(4)}
        assert positions == {(0, 0), (0, 1), (0, 2), (1, 0)}
        window._on_clear_results()
        QtWidgets.QApplication.processEvents()
        assert window._results_layout.count() == 0

    def test_opening_the_output_folder(self, make_window, tmp_path, monkeypatch):
        window = make_window()
        launched = []
        monkeypatch.setattr('subprocess.Popen', lambda cmd, **k: launched.append(cmd))
        window._out_dir_edit.setText('')
        window._on_open_output_folder()
        window._out_dir_edit.setText(str(tmp_path / 'absent'))
        window._on_open_output_folder()
        assert launched == []
        window._out_dir_edit.setText(str(tmp_path))
        window._on_open_output_folder()
        assert launched[0][0] in ('explorer', 'xdg-open') and launched[0][1] == str(tmp_path)

    def test_clicking_a_thumbnail_opens_it_in_the_default_viewer(self, make_window, tmp_path, monkeypatch):
        window = make_window()
        opened = []
        monkeypatch.setattr('os.startfile', lambda path: opened.append(path), raising=False)
        monkeypatch.setattr('subprocess.Popen', lambda cmd, **k: opened.append(cmd))
        window._on_thumbnail_clicked(str(tmp_path / 'x.png'))
        assert opened and str(tmp_path / 'x.png') in (opened[0] if isinstance(opened[0], str) else opened[0])


class TestSettings:
    def test_everything_is_saved_on_close_and_restored(self, make_window, tmp_path):
        window = make_window()
        window._backend_combo.setCurrentIndex(1)
        window._prompt_edit.setPlainText('a hero')
        window._neg_prompt_edit.setText('blurry')
        window._doc_group.setChecked(True)
        window._out_dir_edit.setText(str(tmp_path))
        window._prefix_edit.setText('hero')
        window._width_spin.setValue(768)
        window._height_spin.setValue(512)
        window._count_spin.setValue(3)
        window._backend_settings._ollama_model.setText('sdxl')
        window.show()
        window.close()
        again = make_window()
        assert again._backend_combo.currentIndex() == 1 and again._prompt_edit.toPlainText() == 'a hero'
        assert again._neg_prompt_edit.text() == 'blurry' and again._doc_group.isChecked()
        assert again._out_dir_edit.text() == str(tmp_path) and again._prefix_edit.text() == 'hero'
        assert (again._width_spin.value(), again._height_spin.value(), again._count_spin.value()) == (768, 512, 3)
        assert again._backend_settings.ollama_model() == 'sdxl'

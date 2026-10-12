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
"""Tests for the Ollama tool window (against a fake API client)."""
import sys
import types

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from deda.plugins.ollama import _tool_window as tw


class FakeApi:
    def __init__(self, base_url='http://localhost:11434'):
        self.base_url = base_url
        self.connected = True
        self.models = [{'name': 'llama3.2:latest'}, {'name': 'llava:7b'}, {'name': 'custom-thing'}, {'name': ''},
                       {'name': 'mistral:latest'}, {'name': 'mistral:latest'}]
        self.calls = []
        self.error = None
        self.reply = 'hello there'

    def check_connection(self):
        return self.connected

    def list_models(self):
        if self.error:
            raise self.error
        return list(self.models)

    def chat(self, model, messages):
        self.calls.append(('chat', model, messages))
        if self.error:
            raise self.error
        return self.reply

    def process_image(self, model, prompt, image_path):
        self.calls.append(('vision', model, prompt, image_path))
        if self.error:
            raise self.error
        return 'a picture of a cat'

    def generate_image(self, model, prompt, output_path):
        self.calls.append(('image', model, prompt, output_path))
        if self.error:
            raise self.error
        return self.image_bytes

    def generate_3d_from_image(self, model, image_path, prompt, output_path):
        self.calls.append(('3d', model, image_path, prompt, output_path))
        if self.error:
            raise self.error
        return b'mesh-bytes'


class FakeService:
    def __init__(self):
        self.url = None

    def get_base_url(self):
        return 'http://box:9999'

    def set_base_url(self, url):
        self.url = url


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
    image = QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtCore.Qt.red)
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    fake.image_bytes = bytes(buffer.data())
    monkeypatch.setattr(tw, 'OllamaApiClient', lambda base_url: fake)
    return fake


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch, dialogs, api):
    real = QtCore.QSettings
    monkeypatch.setattr(tw.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'ollama.ini'), real.IniFormat))
    created = []

    def build(service=None):
        window = tw.OllamaToolWindow(service=service)
        created.append(window)
        return window

    yield build
    for window in created:
        window.close()


def button(widget, text):
    return next(b for b in widget.findChildren(QtWidgets.QPushButton) if b.text().strip().endswith(text))


def line_edits(widget):
    """The widget's own line edits (editable combo boxes carry an inner one that is not of interest)."""
    return [e for e in widget.findChildren(QtWidgets.QLineEdit) if not isinstance(e.parent(), QtWidgets.QComboBox)]


def combo(window, name):
    return window.findChild(QtWidgets.QComboBox, name)


class TestSetup:
    def test_tabs_and_connection_status(self, make_window):
        window = make_window(FakeService())
        assert [window._tabs.tabText(i) for i in range(window._tabs.count())] == [
            'Text Processing', 'Image Processing', 'Settings']
        assert window._status_bar.currentMessage() == 'Connected to Ollama'

    def test_disconnected_and_missing_client(self, make_window, api, monkeypatch):
        api.connected = False
        assert 'Not connected' in make_window()._status_bar.currentMessage()
        def missing(base_url):
            raise ImportError('requests')

        monkeypatch.setattr(tw, 'OllamaApiClient', missing)
        window = make_window()
        assert window._status_bar.currentMessage() == 'Ollama API client not available'
        window._load_models()
        window._on_tab_changed(0)

    def test_the_service_supplies_the_url(self, make_window, monkeypatch, api):
        urls = []
        monkeypatch.setattr(tw, 'OllamaApiClient', lambda base_url: urls.append(base_url) or api)
        make_window(FakeService())
        assert urls == ['http://box:9999']


class TestModelLists:
    def test_models_are_filtered_per_category_with_recommended_first(self, make_window):
        window = make_window()
        window._load_models()
        text = [combo(window, 'model_text').itemText(i) for i in range(combo(window, 'model_text').count())]
        assert text[:2] == ['llama3.2:latest', 'mistral:latest'] and 'custom-thing' in text and '' not in text
        vision = [combo(window, 'model_vision').itemText(i) for i in range(combo(window, 'model_vision').count())]
        assert vision[0] == 'llava:7b'
        assert combo(window, 'model_text').currentText() == 'llama3.2:latest'

    def test_the_current_choice_survives_a_reload(self, make_window):
        window = make_window()
        window._load_models()
        combo(window, 'model_text').setCurrentText('mistral:latest')
        window._load_models()
        assert combo(window, 'model_text').currentText() == 'mistral:latest'

    def test_categories_without_matches_fall_back_to_every_model(self, make_window, api):
        api.models = [{'name': 'zzz'}]
        window = make_window()
        window._load_models()
        assert window._filter_models_for_category('text') == ['zzz']
        assert window._filter_models_for_category('3d') == ['zzz']
        window._all_models = []
        assert window._filter_models_for_category('text') == []
        window._update_model_combos()

    def test_keyword_matches_come_before_the_rest(self, make_window, api):
        api.models = [{'name': 'other'}, {'name': 'qwen2'}, {'name': 'llama3'}]
        window = make_window()
        window._load_models()
        assert window._filter_models_for_category('text') == ['llama3', 'qwen2', 'other']
        assert window._filter_models_for_category('unknown-category') == ['llama3', 'qwen2', 'other']

    def test_the_combo_falls_back_to_every_model_when_nothing_matches(self, make_window, api):
        window = make_window()
        window._all_models = [{'name': 'a'}, {'name': 'b'}]
        box = combo(window, 'model_text')
        box.addItem('b')
        box.setCurrentText('b')
        window._filter_models_for_category = lambda category: []
        window._update_combo_with_filter(box, 'text')
        assert [box.itemText(i) for i in range(box.count())] == ['a', 'b'] and box.currentText() == 'b'

    def test_the_first_item_is_used_without_a_recommendation(self, make_window, api):
        api.models = [{'name': 'zzz'}, {'name': 'yyy'}]
        window = make_window()
        window._load_models()
        assert combo(window, 'model_text').currentText() == 'zzz'

    def test_the_combo_is_widened_for_long_names(self, make_window):
        window = make_window()
        box = QtWidgets.QComboBox()
        window._adjust_combo_width(box, [])
        window._adjust_combo_width(box, ['a-very-long-model-name:with-a-tag-and-more'])
        assert 0 < box.minimumWidth() <= 400

    def test_load_failures_are_shown_in_the_status_bar(self, make_window, api):
        window = make_window()
        api.error = RuntimeError('refused')
        window._load_models()
        assert 'Failed to load models: refused' in window._status_bar.currentMessage()

    @pytest.mark.parametrize('title, category', [
        ('Text Processing', 'text'), ('Image Processing', 'vision'), ('Image Generation', 'image_gen'),
        ('3D from Image', '3d'), ('Settings', 'text')])
    def test_the_active_tab_picks_the_category(self, make_window, title, category):
        window = make_window()
        index = window._tabs.addTab(QtWidgets.QWidget(), title)
        window._on_tab_changed(index)
        assert window._current_category == category

    def test_the_selected_tab_is_remembered(self, make_window):
        window = make_window()
        window._tabs.setCurrentIndex(1)
        assert window._settings.value('ollama_tool_window/current_tab', type=int) == 1
        window._settings.setValue = lambda *a: 1 / 0
        window._on_tab_index_changed(2)


class TestModelBrowser:
    def test_needs_a_client(self, make_window, dialogs, monkeypatch):
        window = make_window()
        window._api_client = None
        window._show_model_browser('text')
        assert dialogs[-1][:2] == ('warning', 'Not Connected')

    def test_opens_the_browser_and_refreshes_the_list(self, make_window, monkeypatch):
        opened = []
        module = types.ModuleType('deda.plugins.ollama._model_browser')

        class Dialog:
            def __init__(self, api, category, parent=None):
                opened.append((api, category))

            def exec(self):
                return 1

        module.ModelBrowserDialog = Dialog
        monkeypatch.setitem(sys.modules, 'deda.plugins.ollama._model_browser', module)
        scheduled = []
        monkeypatch.setattr(tw.QtCore.QTimer, 'singleShot', staticmethod(lambda ms, fn: scheduled.append(ms)))
        window = make_window()
        window._show_model_browser('vision')
        assert opened[0][1] == 'vision' and scheduled[-3:] == [1000, 3000, 6000]

    def test_browser_failures_are_reported(self, make_window, monkeypatch, dialogs):
        module = types.ModuleType('deda.plugins.ollama._model_browser')

        def boom(*a, **k):
            raise RuntimeError('cannot open')

        module.ModelBrowserDialog = boom
        monkeypatch.setitem(sys.modules, 'deda.plugins.ollama._model_browser', module)
        make_window()._show_model_browser('text')
        assert dialogs[-1][:2] == ('critical', 'Error') and 'cannot open' in dialogs[-1][2]

    def test_download_buttons_open_the_browser_for_their_category(self, make_window, monkeypatch):
        window = make_window()
        asked = []
        monkeypatch.setattr(window, '_show_model_browser', lambda category: asked.append(category))
        image_tab, tab_3d = window._create_image_generation_tab(), window._create_3d_generation_tab()
        button(window._tabs.widget(0), 'Download Models...').click()
        button(window._tabs.widget(1), 'Download Models...').click()
        button(image_tab, 'Download Models...').click()
        button(tab_3d, 'Download Models...').click()
        assert asked == ['text', 'vision', 'image_gen', '3d']


class TestTextTab:
    @pytest.fixture
    def tab(self, make_window):
        window = make_window()
        window._load_models()
        return window, window._tabs.widget(0)

    def send(self, tab, message):
        edit = line_edits(tab)[0]
        edit.setText(message)
        button(tab, 'Send').click()
        return tab.findChild(QtWidgets.QTextEdit).toPlainText()

    def test_chatting(self, tab, api):
        window, widget = tab
        shown = self.send(widget, 'hi')
        assert 'You: hi' in shown and 'Assistant: hello there' in shown
        assert api.calls[0] == ('chat', 'llama3.2:latest', [{'role': 'user', 'content': 'hi'}])
        assert line_edits(widget)[0].text() == '' and button(widget, 'Send').isEnabled()

    def test_empty_input_or_model_does_nothing(self, tab, api):
        window, widget = tab
        assert self.send(widget, '') == ''
        combo(window, 'model_text').setCurrentText('')
        assert self.send(widget, 'hi') == '' and api.calls == []

    def test_errors_appear_in_the_chat(self, tab, api):
        window, widget = tab
        api.error = RuntimeError('model not found')
        assert 'Error: model not found' in self.send(widget, 'hi') and button(widget, 'Send').isEnabled()


class TestVisionTab:
    @pytest.fixture
    def tab(self, make_window, tmp_path, api):
        window = make_window()
        window._load_models()
        widget = window._tabs.widget(1)
        return window, widget, line_edits(widget)[0], tmp_path / 'cat.png'

    def test_it_needs_model_image_and_prompt(self, tab, dialogs):
        window, widget, path_edit, image = tab
        button(widget, 'Process Image').click()
        assert dialogs[-1][:2] == ('warning', 'Missing Information')

    def test_processing_an_image(self, tab, api):
        window, widget, path_edit, image = tab
        path_edit.setText(str(image))
        widget.findChildren(QtWidgets.QTextEdit)[0].setPlainText('what is this?')
        button(widget, 'Process Image').click()
        assert api.calls[0][:2] == ('vision', 'llava:7b') and widget.findChildren(QtWidgets.QTextEdit)[1].toPlainText() == 'a picture of a cat'
        assert button(widget, 'Process Image').isEnabled()

    def test_errors_are_shown(self, tab, api):
        window, widget, path_edit, image = tab
        path_edit.setText(str(image))
        widget.findChildren(QtWidgets.QTextEdit)[0].setPlainText('q')
        api.error = RuntimeError('vision failed')
        button(widget, 'Process Image').click()
        assert 'Error: vision failed' in widget.findChildren(QtWidgets.QTextEdit)[1].toPlainText()

    def test_browsing_for_an_image(self, tab, monkeypatch):
        window, widget, path_edit, image = tab
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('C:/x.png', '')))
        button(widget, 'Browse...').click()
        assert path_edit.text() == 'C:/x.png'
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('', '')))
        button(widget, 'Browse...').click()
        assert path_edit.text() == 'C:/x.png'


class TestHiddenTabs:
    """The image and 3D generation tabs are built but not yet shown; they still have to work."""

    @pytest.fixture
    def window(self, make_window, api):
        window = make_window()
        return window

    def test_image_generation(self, window, api, tmp_path, dialogs, monkeypatch):
        tab = window._create_image_generation_tab()
        box = tab.findChild(QtWidgets.QComboBox, 'model_image_gen')
        box.addItem('flux')
        box.setCurrentText('flux')
        button(tab, 'Generate Image').click()
        assert dialogs[-1][:2] == ('warning', 'Missing Information')
        tab.findChildren(QtWidgets.QTextEdit)[0].setPlainText('a tree')
        target = tmp_path / 'tree.png'
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (str(target), '')))
        browse = [b for b in tab.findChildren(QtWidgets.QPushButton) if b.text() == 'Browse...'][0]
        browse.click()
        assert line_edits(tab)[0].text() == str(target)
        button(tab, 'Generate Image').click()
        preview = [l for l in tab.findChildren(QtWidgets.QLabel) if l.minimumHeight() == 300][0]
        assert api.calls[-1] == ('image', 'flux', 'a tree', str(target)) and preview.pixmap() is not None
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: ('', '')))
        browse.click()
        api.image_bytes = b'not an image'
        button(tab, 'Generate Image').click()
        assert preview.text() == 'Failed to load generated image'
        api.error = RuntimeError('gpu busy')
        button(tab, 'Generate Image').click()
        assert preview.text() == 'Error: gpu busy' and button(tab, 'Generate Image').isEnabled()

    def test_3d_generation(self, window, api, tmp_path, dialogs, monkeypatch):
        tab = window._create_3d_generation_tab()
        box = tab.findChild(QtWidgets.QComboBox, 'model_3d')
        box.addItem('shap-e')
        box.setCurrentText('shap-e')
        button(tab, 'Generate 3D Model').click()
        assert dialogs[-1][:2] == ('warning', 'Missing Information')
        edits = line_edits(tab)
        edits[0].setText('C:/in.png')
        button(tab, 'Generate 3D Model').click()
        assert dialogs[-1][:2] == ('warning', 'Missing Output')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('C:/other.png', '')))
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (str(tmp_path / 'm.glb'), '')))
        browse_buttons = [b for b in tab.findChildren(QtWidgets.QPushButton) if b.text() == 'Browse...']
        browse_buttons[0].click()
        browse_buttons[1].click()
        assert edits[0].text() == 'C:/other.png' and edits[1].text() == str(tmp_path / 'm.glb')
        tab.findChildren(QtWidgets.QTextEdit)[0].setPlainText('chair')
        button(tab, 'Generate 3D Model').click()
        status = tab.findChildren(QtWidgets.QTextEdit)[1].toPlainText()
        assert api.calls[-1] == ('3d', 'shap-e', 'C:/other.png', 'chair', str(tmp_path / 'm.glb'))
        assert 'Success!' in status and 'Model size: 10 bytes' in status
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('', '')))
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: ('', '')))
        browse_buttons[0].click()
        browse_buttons[1].click()
        api.error = RuntimeError('no 3d here')
        button(tab, 'Generate 3D Model').click()
        assert 'Error: no 3d here' in tab.findChildren(QtWidgets.QTextEdit)[1].toPlainText()


class TestSettingsTab:
    def test_updating_the_url_reconnects(self, make_window, api, dialogs):
        service = FakeService()
        window = make_window(service)
        tab = window._tabs.widget(2)
        edit = tab.findChild(QtWidgets.QLineEdit)
        assert edit.text() == 'http://localhost:11434'
        edit.setText(' http://other:1111/ ')
        button(tab, 'Update').click()
        assert api.base_url == 'http://other:1111' and service.url == ' http://other:1111/ '.strip()
        assert dialogs[-1][:2] == ('information', 'Settings Updated')
        edit.setText('  ')
        dialogs.clear()
        button(tab, 'Update').click()
        assert dialogs == []

    def test_connection_test(self, make_window, api, dialogs):
        window = make_window()
        tab = window._tabs.widget(2)
        button(tab, 'Test Connection').click()
        assert dialogs[-1][:2] == ('information', 'Connection Test')
        api.connected = False
        button(tab, 'Test Connection').click()
        assert dialogs[-1][0] == 'warning' and 'Failed to connect' in dialogs[-1][2]
        window._api_client = None
        button(tab, 'Test Connection').click()
        assert 'not available' in dialogs[-1][2]


class TestWindowState:
    def test_state_round_trip(self, make_window):
        window = make_window()
        window.resize(910, 700)
        window.show()
        QtWidgets.QApplication.processEvents()
        window._tabs.setCurrentIndex(1)
        window._save_window_state()
        assert window._settings.value('ollama_tool_window/geometry') and window._settings.value(
            'ollama_tool_window/current_tab', type=int) == 1
        again = make_window()
        assert again._tabs.currentIndex() == 1

    def test_state_errors_are_tolerated(self, make_window, monkeypatch):
        window = make_window()
        monkeypatch.setattr(window, 'saveGeometry', lambda: 1 / 0)
        window._save_window_state()
        window._settings.setValue('ollama_tool_window/geometry', QtCore.QByteArray(b'x'))
        monkeypatch.setattr(window, 'restoreGeometry', lambda g: 1 / 0)
        window._restore_window_geometry()
        window._settings.setValue('ollama_tool_window/state', QtCore.QByteArray(b'x'))
        monkeypatch.setattr(window, 'restoreState', lambda s: 1 / 0)
        window._restore_window_state()

    def test_showing_restores_the_cursor_once(self, make_window, monkeypatch):
        restored = []
        monkeypatch.setattr(QtWidgets.QApplication, 'restoreOverrideCursor', staticmethod(lambda: restored.append(1)))
        window = make_window()
        window.show()
        window.hide()
        window.show()
        QtCore.QCoreApplication.processEvents()
        import time
        time.sleep(0.1)
        QtCore.QCoreApplication.processEvents()
        assert restored and window._shown
        window.close()

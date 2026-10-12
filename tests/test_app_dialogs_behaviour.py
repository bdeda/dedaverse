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
"""Behavioural tests for the add/configure/copy-move dialogs."""
import types

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from deda.app import _dialogs
from deda.core import PluginRegistry, Service, _types


@pytest.fixture(autouse=True)
def ini_settings(tmp_path, monkeypatch):
    """Keep the dialogs' QSettings out of the registry."""
    real = QtCore.QSettings
    monkeypatch.setattr(_dialogs.QtCore, 'QSettings', lambda *a: real(str(tmp_path / 'dialogs.ini'), real.IniFormat))


@pytest.fixture
def icon_file(tmp_path):
    path = tmp_path / 'custom.png'
    image = QtGui.QImage(16, 16, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtCore.Qt.red)
    image.save(str(path))
    return str(path)


def save_enabled(dialog):
    return dialog._btns.button(QtWidgets.QDialogButtonBox.Save).isEnabled()


class TestHelpers:
    @pytest.mark.parametrize('asset_type, filename', [
        ('Actor', 'icon_actor.png'), ('Character', 'icon_character.png'), ('Collection', 'icon_collection.png'),
        ('Kit', 'icon_kit.png'), ('Prop', 'icon_prop.png'), ('Sequence', 'icon_sequence.png'),
        ('Set', 'icon_set.png'), ('Shot', 'icon_shot.png'), ('Anything else', 'icon_asset.png'),
    ])
    def test_default_icons_by_asset_type(self, asset_type, filename):
        assert _dialogs._default_icon_path_for_asset_type(asset_type).name == filename

    def test_no_icons_folder(self, monkeypatch):
        monkeypatch.setattr(_dialogs.Path, 'is_dir', lambda self: False)
        assert _dialogs._default_icon_path_for_asset_type('Actor') is None

    def test_missing_icon_file(self, monkeypatch):
        monkeypatch.setattr(_dialogs.Path, 'is_file', lambda self: False)
        assert _dialogs._default_icon_path_for_asset_type('Actor') is None

    def test_clickable_label_emits_on_left_click(self, qapp):
        label = _dialogs.ClickableLabel('x')
        label.resize(40, 20)
        label.show()
        clicks = []
        label.clicked.connect(lambda: clicks.append(1))
        QtTest.QTest.mouseClick(label, QtCore.Qt.LeftButton)
        QtTest.QTest.mouseClick(label, QtCore.Qt.RightButton)
        assert clicks == [1]
        label.close()


class TestAddItemDialog:
    def test_save_needs_a_name(self, qapp):
        dialog = _dialogs.AddItemDialog('Asset')
        assert not save_enabled(dialog)
        dialog._name_le.textEdited.emit('Hero')
        assert save_enabled(dialog)
        dialog._name_le.textEdited.emit('   ')
        assert not save_enabled(dialog)

    def test_initial_name_and_type(self, qapp):
        dialog = _dialogs.AddItemDialog('Asset', initial_name='  Hero  ', initial_asset_type='Shot')
        assert dialog._name_le.text() == 'Hero' and dialog._types_cb.currentText() == 'Shot' and save_enabled(dialog)

    def test_asset_types_come_from_the_core_list(self, qapp):
        dialog = _dialogs.AddItemDialog('Asset')
        assert [dialog._types_cb.itemText(i) for i in range(dialog._types_cb.count())] == _types.all_default_asset_types()

    def test_changing_the_type_updates_the_icon_and_is_remembered(self, qapp):
        dialog = _dialogs.AddItemDialog('Asset')
        dialog._types_cb.setCurrentText('Shot')
        assert dialog._settings.value('AddItemDialog/Asset/lastType') == 'Shot'
        assert dialog._icon_lbl.pixmap() is not None and not dialog._icon_lbl.pixmap().isNull()
        again = _dialogs.AddItemDialog('Asset')
        assert again._types_cb.currentText() == 'Shot'

    @pytest.mark.parametrize('type_name, expected', [('Task', ['Work', 'Review', 'Notify']), ('App', ['Command', 'Python'])])
    def test_other_types(self, qapp, type_name, expected):
        dialog = _dialogs.AddItemDialog(type_name)
        assert [dialog._types_cb.itemText(i) for i in range(dialog._types_cb.count())] == expected

    def test_create_item_emits_name_and_type_and_closes(self, qapp):
        dialog = _dialogs.AddItemDialog('Asset')
        created = []
        dialog.item_created.connect(created.append)
        dialog._name_le.setText(' Hero ')
        dialog._create_item()
        assert created[0]['name'] == 'Hero' and created[0]['type'] == dialog._types_cb.currentText()
        assert 'icon' not in created[0]

    def test_app_dialog_includes_the_command(self, qapp):
        dialog = _dialogs.AddItemDialog('App')
        created = []
        dialog.item_created.connect(created.append)
        dialog._name_le.setText('Maya')
        dialog._command_le.setText('maya.exe -batch')
        dialog._create_item()
        assert created[0]['command'] == 'maya.exe -batch'

    def test_choosing_a_custom_icon(self, qapp, monkeypatch, icon_file):
        dialog = _dialogs.AddItemDialog('Asset')
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (icon_file, '')))
        dialog._open_icon_browser()
        created = []
        dialog.item_created.connect(created.append)
        dialog._name_le.setText('Hero')
        dialog._create_item()
        assert created[0]['icon'] == icon_file
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('', '')))
        dialog._open_icon_browser()                                   # cancelled: keeps the previous choice
        assert dialog._selected_icon_path == icon_file

    def test_an_unreadable_icon_choice_keeps_the_label(self, qapp, monkeypatch, tmp_path):
        bad = tmp_path / 'bad.png'
        bad.write_bytes(b'not an image')
        dialog = _dialogs.AddItemDialog('Task')
        before = dialog._icon_lbl.pixmap().cacheKey()
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (str(bad), '')))
        dialog._open_icon_browser()
        assert dialog._icon_lbl.pixmap().cacheKey() == before

    def test_missing_question_mark_icon(self, qapp, monkeypatch):
        dialog = _dialogs.AddItemDialog('Task')
        monkeypatch.setattr(_dialogs.Path, 'is_file', lambda self: False)
        dialog._update_dialog_icon()


class TestServiceDialog:
    @pytest.fixture
    def plugin_service(self):
        class Fake(Service):
            def load(self):
                return True

        service = Fake('zz-plugin', description='Does things')
        service.url = 'http://svc:9'
        PluginRegistry().register(service)
        yield service
        PluginRegistry._registry_.pop('zz-plugin', None)

    def test_plugin_services_are_offered_and_prefill_the_fields(self, qapp, plugin_service):
        dialog = _dialogs.AddItemDialog('Service')
        assert 'Plugin: Zz-Plugin' in [dialog._types_cb.itemText(i) for i in range(dialog._types_cb.count())]
        dialog._types_cb.setCurrentText('Plugin: Zz-Plugin')
        assert dialog._name_le.text() == 'zz-plugin' and dialog._url_le.text() == 'http://svc:9'
        assert not dialog._desc_label.isHidden()
        created = []
        dialog.item_created.connect(created.append)
        dialog._create_item()
        assert created[0]['plugin_service'] == 'zz-plugin' and created[0]['description'] == 'Does things'
        assert created[0]['url'] == 'http://svc:9' and created[0]['params'] == []

    def test_switching_back_to_rest_clears_a_plugin_url(self, qapp, plugin_service):
        dialog = _dialogs.AddItemDialog('Service')
        dialog._types_cb.setCurrentText('Plugin: Zz-Plugin')
        dialog._types_cb.setCurrentText('REST')
        assert dialog._url_le.text() == '' and dialog._desc_label.isHidden()

    def test_a_manually_typed_url_survives_switching_to_rest(self, qapp):
        dialog = _dialogs.AddItemDialog('Service')
        dialog._url_le.setText('http://mine')
        dialog._on_service_type_changed('REST')
        assert dialog._url_le.text() == 'http://mine'

    def test_plain_rest_service(self, qapp):
        dialog = _dialogs.AddItemDialog('Service')
        dialog._name_le.setText('Jira')
        dialog._url_le.setText(' http://jira ')
        created = []
        dialog.item_created.connect(created.append)
        dialog._create_item()
        assert created[0]['url'] == 'http://jira' and 'plugin_service' not in created[0]

    def test_plugin_without_a_description_or_url(self, qapp):
        class Bare(Service):
            def load(self):
                return True

            def get_base_url(self):
                return 'http://from-method'

        service = Bare('zz-bare')
        PluginRegistry().register(service)
        try:
            dialog = _dialogs.AddItemDialog('Service')
            dialog._types_cb.setCurrentText('Plugin: Zz-Bare')
            assert dialog._url_le.text() == 'http://from-method' and dialog._desc_label.isHidden()
        finally:
            PluginRegistry._registry_.pop('zz-bare', None)

    def test_the_service_hook_only_applies_to_services(self, qapp):
        dialog = _dialogs.AddItemDialog('Task')
        dialog._on_service_type_changed('anything')


class TestConfigureItemDialog:
    def test_app_fields_are_prefilled_and_saved(self, qapp):
        data = {'name': 'Maya', 'type': 'Command', 'title': 'Maya 2027', 'description': 'dcc', 'command': 'maya.exe'}
        dialog = _dialogs.ConfigureItemDialog('App', data, 3)
        updates = []
        dialog.item_updated.connect(lambda index, item: updates.append((index, item)))
        assert dialog._name_le.text() == 'Maya' and dialog._title_le.text() == 'Maya 2027'
        dialog._command_le.setText('maya.exe -v')
        dialog._save()
        assert updates == [(3, {'name': 'Maya', 'type': 'Command', 'title': 'Maya 2027', 'description': 'dcc',
                                'command': 'maya.exe -v'})]

    def test_blank_name_becomes_untitled_and_title_follows_the_name(self, qapp):
        dialog = _dialogs.ConfigureItemDialog('Task', {'type': 'Work'}, 0)
        updates = []
        dialog.item_updated.connect(lambda index, item: updates.append(item))
        dialog._name_le.setText('  ')
        dialog._title_le.setText('')
        dialog._save()
        assert updates[0]['name'] == 'Untitled' and updates[0]['title'] == 'Untitled'
        assert 'command' not in updates[0] and 'url' not in updates[0]

    def test_service_keeps_its_params(self, qapp):
        data = {'name': 'Jira', 'type': 'REST', 'url': 'http://j', 'params': ['a']}
        dialog = _dialogs.ConfigureItemDialog('Service', data, 1)
        updates = []
        dialog.item_updated.connect(lambda index, item: updates.append(item))
        dialog._url_le.setText(' http://new ')
        dialog._save()
        assert updates[0]['url'] == 'http://new' and updates[0]['params'] == ['a']

    def test_icons(self, qapp, monkeypatch, icon_file, tmp_path):
        dialog = _dialogs.ConfigureItemDialog('Task', {'name': 'x', 'icon': icon_file}, 0)
        assert dialog._selected_icon_path == icon_file
        missing = _dialogs.ConfigureItemDialog('Task', {'name': 'x', 'icon': str(tmp_path / 'gone.png')}, 0)
        assert missing._selected_icon_path is None
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (icon_file, '')))
        missing._open_icon_browser()
        updates = []
        missing.item_updated.connect(lambda index, item: updates.append(item))
        missing._save()
        assert updates[0]['icon'] == icon_file
        monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: ('', '')))
        missing._open_icon_browser()

    def test_an_unreadable_icon_file_falls_back_to_the_default_picture(self, qapp, tmp_path):
        bad = tmp_path / 'bad.png'
        bad.write_bytes(b'junk')
        dialog = _dialogs.ConfigureItemDialog('Task', {'name': 'x', 'icon': str(bad)}, 0)
        assert not dialog._icon_lbl.pixmap().isNull()


class FakeEntity:
    def __init__(self, fail=False, **metadata):
        self.metadata = dict(metadata)
        self.fail = fail

    def get_metadata(self, name, default=None):
        return self.metadata.get(name, default)

    def set_metadata(self, name, value):
        if self.fail:
            raise RuntimeError('layer is read-only')
        self.metadata[name] = value


class TestConfigureAssetDialog:
    def test_prefill_prefers_the_entity_metadata(self, qapp):
        entity = FakeEntity(title='From USD', description='usd desc', asset_type='Shot')
        dialog = _dialogs.ConfigureAssetDialog(entity, {'name': 'n', 'title': 'panel', 'description': 'panel desc'}, 0)
        assert dialog._title_le.text() == 'From USD' and dialog._desc_le.text() == 'usd desc'
        assert dialog._type_cb.currentText() == 'Shot'

    def test_prefill_falls_back_to_the_panel_item(self, qapp):
        dialog = _dialogs.ConfigureAssetDialog(FakeEntity(), {'name': 'Hero', 'type': 'Nonexistent'}, 0)
        assert dialog._title_le.text() == 'Hero' and dialog._type_cb.currentIndex() == 0

    def test_save_writes_metadata_and_emits(self, qapp):
        entity = FakeEntity()
        dialog = _dialogs.ConfigureAssetDialog(entity, {'name': 'Hero', 'is_collection': True}, 4)
        updates = []
        dialog.asset_metadata_updated.connect(lambda index, item: updates.append((index, item)))
        dialog._title_le.setText(' The Hero ')
        dialog._desc_le.setText('brave')
        dialog._type_cb.setCurrentText('Shot')
        dialog._save()
        assert entity.metadata == {'title': 'The Hero', 'description': 'brave', 'asset_type': 'Shot'}
        assert updates == [(4, {'name': 'Hero', 'type': 'Shot', 'title': 'The Hero', 'description': 'brave',
                                'is_collection': True})]
        assert dialog.result() == QtWidgets.QDialog.Accepted

    def test_a_failed_write_warns_and_does_not_emit(self, qapp, monkeypatch):
        warnings = []
        monkeypatch.setattr(QtWidgets.QMessageBox, 'warning', staticmethod(
            lambda parent, title, text, *a, **k: warnings.append(text)))
        dialog = _dialogs.ConfigureAssetDialog(FakeEntity(fail=True), {'name': 'Hero'}, 0)
        updates = []
        dialog.asset_metadata_updated.connect(lambda *a: updates.append(a))
        dialog._save()
        assert updates == [] and 'layer is read-only' in warnings[0]


class TestCopyMoveDialog:
    def test_lists_files_and_defaults_to_cancel(self, qapp):
        dialog = _dialogs.CopyMoveUsdFilesDialog([('C:/a/x.usd', 'x.usd'), ('C:/a/t/y.usd', 't/y.usd')])
        assert dialog._list.count() == 2 and 'x.usd' in dialog._list.item(0).text()
        assert dialog.result_action() == _dialogs.CopyMoveUsdFilesDialog.CancelAction

    @pytest.mark.parametrize('label, action', [('Copy', 1), ('Move', 2)])
    def test_copy_and_move_buttons(self, qapp, label, action):
        dialog = _dialogs.CopyMoveUsdFilesDialog([('C:/a/x.usd', 'x.usd')])
        button = next(b for b in dialog.findChildren(QtWidgets.QPushButton) if b.text() == label)
        button.click()
        assert dialog.result_action() == action and dialog.result() == QtWidgets.QDialog.Accepted

    def test_cancel(self, qapp):
        dialog = _dialogs.CopyMoveUsdFilesDialog([])
        dialog.reject()
        assert dialog.result_action() == _dialogs.CopyMoveUsdFilesDialog.CancelAction

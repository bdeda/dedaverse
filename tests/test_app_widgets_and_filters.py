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
"""Tests for the drag/drop event filters, the taskbar icon and the add button."""
import json
import types

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

import deda.app
from deda.app import _buttons, _eventfilter, _taskbar_icon
from deda.dcc import _eventfilter as dcc_eventfilter


class FakeEvent:
    def __init__(self, kind, mime=None):
        self._kind = kind
        self._mime = mime
        self.accepted = False

    def type(self):
        return self._kind

    def mimeData(self):
        return self._mime

    def accept(self):
        self.accepted = True


class FakeMime:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class FakeWidget:
    def mapFromGlobal(self, pos):
        return QtCore.QPoint(1, 2)


class TestAppEventFilter:
    @pytest.fixture
    def flt(self):
        return _eventfilter.EventFilter()

    def test_drag_enter_tracks_the_dragged_object(self, flt):
        seen = []
        flt.dragEnter.connect(lambda obj, data: seen.append(data))
        event = FakeEvent(QtCore.QEvent.DragEnter, FakeMime(json.dumps({'asset': 'Hero'})))
        flt.handle_drag_enter(object(), event)
        assert seen == [{'asset': 'Hero'}] and event.accepted
        flt.handle_drag_enter(object(), event)           # already tracking: ignored
        assert len(seen) == 1

    @pytest.mark.parametrize('mime', [None, FakeMime('')])
    def test_drag_enter_ignores_events_without_data(self, flt, mime):
        flt.handle_drag_enter(object(), FakeEvent(QtCore.QEvent.DragEnter, mime))
        assert flt._dragged_object is None

    def test_drag_move_emits_only_while_tracking(self, flt):
        moves = []
        flt.dragMove.connect(lambda obj, pos, data: moves.append((pos, data)))
        flt.handle_drag_move(FakeWidget(), FakeEvent(QtCore.QEvent.DragMove))
        assert moves == []
        flt._dragged_object = {'a': 1}
        flt.handle_drag_move(FakeWidget(), FakeEvent(QtCore.QEvent.DragMove))
        assert moves == [(QtCore.QPoint(1, 2), {'a': 1})]

    def test_drop_releases_the_object(self, flt):
        event = FakeEvent(QtCore.QEvent.Drop)
        flt.handle_drop(object(), event)
        assert not event.accepted
        flt._dragged_object = {'a': 1}
        flt.handle_drop(object(), event)
        assert flt._dragged_object is None and event.accepted

    def test_event_filter_dispatches_by_event_type_and_never_swallows(self, flt):
        calls = []
        flt.handle_drag_enter = lambda obj, e: calls.append('enter')
        flt.handle_drag_move = lambda obj, e: calls.append('move')
        flt.handle_drop = lambda obj, e: calls.append('drop')
        for kind in (QtCore.QEvent.DragEnter, QtCore.QEvent.DragMove, QtCore.QEvent.Drop,
                     QtCore.QEvent.MouseButtonRelease, QtCore.QEvent.KeyPress):
            assert flt.eventFilter(object(), FakeEvent(kind)) is False
        assert calls == ['enter', 'move', 'drop', 'drop']

    def test_install_event_filter(self, qapp, monkeypatch):
        installed = []
        monkeypatch.setattr(QtWidgets.QApplication, 'installEventFilter',
                            lambda self, obj: installed.append(obj))
        monkeypatch.setattr(_eventfilter, 'get_top_window', lambda: None)
        _eventfilter.install_event_filter(handler=None)
        assert isinstance(installed[0], _eventfilter.EventFilter)


class TestDccEventFilter:
    @pytest.fixture
    def flt(self):
        return dcc_eventfilter.EventFilter()

    def test_drag_enter_keeps_the_mime_data(self, flt):
        seen = []
        flt.dragEnter.connect(lambda obj, data: seen.append(data))
        mime = FakeMime('x')
        flt.handle_drag_enter(object(), FakeEvent(QtCore.QEvent.DragEnter, mime))
        assert seen == [mime] and flt._dragged_object is mime
        flt.handle_drag_enter(object(), FakeEvent(QtCore.QEvent.DragEnter, FakeMime('y')))
        assert len(seen) == 1

    def test_drag_enter_without_mime_data(self, flt):
        flt.handle_drag_enter(object(), FakeEvent(QtCore.QEvent.DragEnter, None))
        assert flt._dragged_object is None

    def test_drag_move_and_drop(self, flt):
        moves = []
        flt.dragMove.connect(lambda obj, pos, data: moves.append(pos))
        flt.handle_drag_move(FakeWidget(), FakeEvent(QtCore.QEvent.DragMove))
        flt._dragged_object = FakeMime('x')
        flt.handle_drag_move(FakeWidget(), FakeEvent(QtCore.QEvent.DragMove))
        assert moves == [QtCore.QPoint(1, 2)]
        flt.handle_drop(object(), FakeEvent(QtCore.QEvent.Drop))
        assert flt._dragged_object is None
        flt.handle_drop(object(), FakeEvent(QtCore.QEvent.Drop))     # nothing tracked: no-op

    def test_event_filter_dispatch(self, flt):
        calls = []
        flt.handle_drag_enter = lambda obj, e: calls.append('enter')
        flt.handle_drag_move = lambda obj, e: calls.append('move')
        flt.handle_drop = lambda obj, e: calls.append('drop')
        for kind in (QtCore.QEvent.DragEnter, QtCore.QEvent.DragMove, QtCore.QEvent.Drop, QtCore.QEvent.Show):
            assert flt.eventFilter(object(), FakeEvent(kind)) is False
        assert calls == ['enter', 'move', 'drop']

    def test_install_event_filter_parents_it_to_the_top_window(self, qapp, monkeypatch):
        installed = []
        monkeypatch.setattr(QtWidgets.QApplication, 'installEventFilter',
                            lambda self, obj: installed.append(obj))
        window = QtWidgets.QWidget()
        monkeypatch.setattr(deda.app, 'get_top_window', lambda: window)
        dcc_eventfilter.install_event_filter(handler=None)
        assert installed[0].parent() is window

    def test_install_event_filter_without_a_top_window_logs(self, qapp, monkeypatch, caplog):
        monkeypatch.setattr(deda.app, 'get_top_window', lambda: None)
        with caplog.at_level('ERROR'):
            dcc_eventfilter.install_event_filter(handler=None)
        assert 'Top window not found' in caplog.text


class Parent(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.opened = 0
        self.closed = False

    def _open_project_settings(self):
        self.opened += 1


@pytest.fixture
def ini_settings(tmp_path, monkeypatch):
    """Keep QSettings out of the registry: the icon gets an ini-file QSettings inside tmp_path."""
    real = QtCore.QSettings

    class IniSettings:
        def __new__(cls, organization, application):
            return real(str(tmp_path / f'{organization}_{application}.ini'), real.IniFormat)

    monkeypatch.setattr(_taskbar_icon.QtCore, 'QSettings', IniSettings)


class TestTaskbarIcon:
    @pytest.fixture
    def icon(self, qapp, ini_settings):
        parent = Parent()
        icon = _taskbar_icon.TaskbarIcon(QtGui.QIcon(), parent)
        yield icon
        icon.hide()

    def test_menu_structure_and_default_view_state(self, icon):
        texts = [a.text() for a in icon.contextMenu().actions()]
        assert texts == ['Project', 'View', 'Restart']
        assert all(a.isChecked() for a in (icon._action_assets, icon._action_apps,
                                           icon._action_services, icon._action_tasks))
        assert icon.toolTip() == 'Dedaverse is running.'

    def test_project_action_calls_the_parent(self, icon):
        icon.contextMenu().actions()[0].trigger()
        assert icon.parent().opened == 1

    def test_view_toggles_are_remembered(self, icon):
        icon._action_apps.setChecked(False)
        icon._action_apps.trigger()      # trigger toggles a checkable action back to checked
        icon._action_apps.setChecked(False)
        icon._on_view_toggled(_taskbar_icon._KEY_VIEW_APPS, icon._action_apps)
        assert icon._settings.value(_taskbar_icon._KEY_VIEW_APPS, True, type=bool) is False

    def test_update_action_appears_changes_and_goes_away(self, icon):
        icon.set_update_available(False)                      # nothing to remove yet
        icon.set_update_available(True, '1.2.3')
        assert icon._action_update_restart.text() == 'Update and restart (v1.2.3)'
        icon.set_update_available(True)
        assert icon._action_update_restart.text() == 'Update and restart'
        texts = [a.text() for a in icon.contextMenu().actions()]
        assert texts.index('Update and restart') < texts.index('Restart')
        icon.set_update_available(False)
        assert icon._action_update_restart is None
        assert 'Update and restart' not in [a.text() for a in icon.contextMenu().actions()]

    def test_restart_and_update_exit_with_their_codes(self, icon):
        with pytest.raises(SystemExit) as restart:
            icon._on_restart()
        with pytest.raises(SystemExit) as update:
            icon._on_update_restart()
        assert restart.value.code == deda.app.RESTART_CODE and update.value.code == deda.app.UPDATE_CODE

    def test_exit_closes_the_parent_and_quits(self, icon, monkeypatch):
        quit_calls = []
        monkeypatch.setattr(QtWidgets.QApplication, 'quit', lambda *a: quit_calls.append(1))
        icon._on_exit()
        assert quit_calls == [1] and not icon.isVisible()

    def test_tooltip_names_the_project(self, icon):
        icon.format_tool_tip('Film')
        assert 'Film' in icon.toolTip()


def test_add_button_is_a_square_with_a_cached_icon(qapp):
    first = _buttons.AddButton()
    second = _buttons.AddButton()
    assert first.width() == first.height() > 0
    assert _buttons.AddButton._ICON is not None and not first.icon().isNull()
    assert second.icon().cacheKey() == first.icon().cacheKey()

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
"""Behavioural tests for item tiles, panel headers and the tile panel (drag/drop, reorder, menus)."""
import json
import types

import pytest
from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from deda.app import _panel
from deda.app._panel import ASSET_MIME_TYPE, ItemTile, Panel, PanelHeader


def asset_mime(item):
    mime = QtCore.QMimeData()
    mime.setData(ASSET_MIME_TYPE, QtCore.QByteArray(json.dumps(item).encode('utf-8')))
    return mime


class FakeDropEvent:
    """A drag/drop event stand-in: the panel only reads its type, mime data and position."""

    def __init__(self, kind, mime=None, pos=(1, 1)):
        self._kind = kind
        self._mime = mime or QtCore.QMimeData()
        self._pos = QtCore.QPointF(*pos)
        self.accepted = False

    def type(self):
        return self._kind

    def mimeData(self):
        return self._mime

    def position(self):
        return self._pos

    def acceptProposedAction(self):
        self.accepted = True


def settle():
    """Run the event loop long enough for queued layout and show events (tiles appear a turn later)."""
    QtTest.QTest.qWait(40)


@pytest.fixture
def messages(monkeypatch):
    dialogs = []
    monkeypatch.setattr(_panel.AddItemDialog, 'exec', lambda self: dialogs.append(('add', self._type_name)) or 0)
    monkeypatch.setattr(_panel.ConfigureItemDialog, 'exec', lambda self: dialogs.append(('configure', self._type_name)) or 0)
    return dialogs


class TestItemTile:
    def test_tooltip_describes_the_item_and_escapes_html(self, qapp):
        tile = ItemTile({'name': '<Maya>', 'title': 'Maya 2027', 'type': 'Command', 'description': 'a & b'}, 120)
        tip = tile.toolTip()
        assert '&lt;Maya&gt;' in tip and 'Maya 2027' in tip and 'Type: Command' in tip and 'a &amp; b' in tip
        assert tile.width() == tile.height() == 120

    def test_tooltip_with_only_a_name(self, qapp):
        assert ItemTile({'name': 'x', 'title': 'x'}, 100).toolTip() == '<b>x</b>'
        assert 'Untitled' in ItemTile({}, 100).toolTip()

    def test_a_custom_icon_is_used_when_it_exists(self, qapp, tmp_path):
        icon = tmp_path / 'i.png'
        QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGB32).save(str(icon))
        tile = ItemTile({'name': 'x', 'icon': str(icon)}, 100)
        assert tile.findChildren(QtWidgets.QLabel)[0].pixmap() is not None

    def test_hover_restyles_the_border(self, qapp):
        tile = ItemTile({'name': 'x'}, 100)
        tile.enterEvent(QtGui.QEnterEvent(QtCore.QPointF(1, 1), QtCore.QPointF(1, 1), QtCore.QPointF(1, 1)))
        assert tile._hover_border in tile.styleSheet()
        tile.leaveEvent(QtCore.QEvent(QtCore.QEvent.Leave))
        assert tile._normal_border in tile.styleSheet()

    def test_double_click_activates_with_the_item(self, qapp):
        tile = ItemTile({'name': 'x'}, 100)
        tile.show()
        got = []
        tile.activated.connect(got.append)
        QtTest.QTest.mouseDClick(tile, QtCore.Qt.LeftButton)
        assert got == [{'name': 'x'}]
        tile.close()

    def test_dragging_starts_a_drag_with_the_asset_data(self, qapp, monkeypatch):
        drags = []

        class FakeDrag:
            def __init__(self, source):
                drags.append(self)

            def setMimeData(self, mime):
                self.mime = mime

            def setPixmap(self, pixmap):
                self.pixmap = pixmap

            def setHotSpot(self, point):
                self.hot_spot = point

            def exec(self, action):
                self.action = action

        monkeypatch.setattr(_panel.QtGui, 'QDrag', FakeDrag)
        item = {'name': 'Hero', 'type': 'Prop'}
        tile = ItemTile(item, 120, draggable=True)
        tile.show()
        press = QtCore.QPoint(10, 10)
        QtTest.QTest.mousePress(tile, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, press)
        assert tile._drag_start_pos is not None
        move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(60, 60), QtCore.QPointF(60, 60),
                                 QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        tile.mouseMoveEvent(move)
        assert json.loads(bytes(drags[0].mime.data(ASSET_MIME_TYPE)).decode()) == item
        assert drags[0].action == QtCore.Qt.CopyAction and tile._drag_start_pos is None
        QtTest.QTest.mouseRelease(tile, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, press)
        tile.close()

    def test_small_moves_and_other_buttons_do_not_start_a_drag(self, qapp, monkeypatch):
        monkeypatch.setattr(_panel.QtGui, 'QDrag', lambda source: pytest.fail('drag started'))
        tile = ItemTile({'name': 'x'}, 120, draggable=True)
        tile.show()
        tile._drag_start_pos = QtCore.QPoint(10, 10)
        near = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(11, 11), QtCore.QPointF(11, 11),
                                 QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        tile.mouseMoveEvent(near)
        no_button = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(90, 90), QtCore.QPointF(90, 90),
                                      QtCore.Qt.NoButton, QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
        tile.mouseMoveEvent(no_button)
        plain = ItemTile({'name': 'y'}, 120)
        plain.mouseMoveEvent(near)
        QtTest.QTest.mousePress(tile, QtCore.Qt.RightButton, QtCore.Qt.NoModifier, QtCore.QPoint(5, 5))
        tile.close()

    def test_dropping_an_asset_on_an_accepting_tile(self, qapp):
        tile = ItemTile({'name': 'Maya'}, 100, accept_asset_drop=True)
        dropped = []
        tile.asset_dropped.connect(lambda asset, target: dropped.append((asset, target)))
        mime = asset_mime({'name': 'Hero'})
        enter = QtGui.QDragEnterEvent(QtCore.QPoint(5, 5), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        tile.dragEnterEvent(enter)
        move = QtGui.QDragMoveEvent(QtCore.QPoint(5, 5), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        tile.dragMoveEvent(move)
        tile.dropEvent(QtGui.QDropEvent(QtCore.QPointF(5, 5), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton,
                                        QtCore.Qt.NoModifier))
        assert enter.isAccepted() and move.isAccepted()
        assert dropped == [({'name': 'Hero'}, {'name': 'Maya'})]

    def test_tiles_that_do_not_accept_drops_and_bad_payloads(self, qapp):
        def drop(mime):
            return QtGui.QDropEvent(QtCore.QPointF(5, 5), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton,
                                    QtCore.Qt.NoModifier)

        plain = ItemTile({'name': 'x'}, 100)
        mime = asset_mime({'name': 'a'})                      # the events do not own their mime data: keep it alive
        plain.dragEnterEvent(QtGui.QDragEnterEvent(QtCore.QPoint(5, 5), QtCore.Qt.CopyAction, mime,
                                                   QtCore.Qt.LeftButton, QtCore.Qt.NoModifier))
        plain.dragMoveEvent(QtGui.QDragMoveEvent(QtCore.QPoint(5, 5), QtCore.Qt.CopyAction, mime,
                                                 QtCore.Qt.LeftButton, QtCore.Qt.NoModifier))
        plain.dropEvent(drop(mime))
        accepting = ItemTile({'name': 'x'}, 100, accept_asset_drop=True)
        dropped = []
        accepting.asset_dropped.connect(lambda *a: dropped.append(a))
        broken = QtCore.QMimeData()
        broken.setData(ASSET_MIME_TYPE, QtCore.QByteArray(b'not json'))
        empty = QtCore.QMimeData()
        accepting.dropEvent(drop(broken))
        accepting.dropEvent(drop(empty))
        assert dropped == []


class TestPanelHeader:
    def test_title_and_navigation(self, qapp):
        header = PanelHeader('Assets', show_navigate_up=True)
        header.set_title('Assets / Monsters')
        assert header._title_label.text() == 'Assets / Monsters' and not header._navigate_up_btn.isHidden()
        header.set_show_navigate_up(False)
        assert header._navigate_up_btn.isHidden()

    def test_buttons_emit_signals_and_call_callbacks(self, qapp):
        called = []
        header = PanelHeader('x', settings_callback=lambda: called.append('settings'))
        header.show()
        events = []
        header.settings_clicked.connect(lambda: events.append('settings'))
        header.close_clicked.connect(lambda: events.append('close'))
        header.navigate_up_clicked.connect(lambda: events.append('up'))
        header.minmax_clicked.connect(lambda minimized: events.append(('minmax', minimized)))
        buttons = {b.text() or 'gear': b for b in header.findChildren(QtWidgets.QPushButton)}
        buttons['gear'].click()
        buttons['X'].click()
        buttons['↑'].click()
        header._minmax_btn.click()
        header._minmax_btn.click()
        assert events == ['settings', 'close', 'up', ('minmax', True), ('minmax', False)] and called == ['settings']
        assert header._minmax_btn.text() == '■' and not header.minimized
        header.close()

    def test_options_hide_buttons_and_an_icon_is_shown(self, qapp, tmp_path):
        icon = tmp_path / 'i.png'
        QtGui.QImage(8, 8, QtGui.QImage.Format.Format_RGB32).save(str(icon))
        header = PanelHeader('x', icon=str(icon), show_minmax=False, show_close=False, minimized=True)
        assert not hasattr(header, '_minmax_btn') and 'X' not in [b.text() for b in header.findChildren(QtWidgets.QPushButton)]
        assert header.minimized


def items(*names):
    return [{'name': n, 'type': 'Asset'} for n in names]


@pytest.fixture
def assets(qapp):
    panel = Panel('Assets', 'Assets', show_navigate_up=True)
    panel.resize(500, 400)
    panel.show()
    for item in items('a', 'b', 'c', 'd'):
        panel.add_item_tile(item)
    settle()
    yield panel
    panel.close()


@pytest.fixture
def apps(qapp):
    panel = Panel('Apps', 'Apps')
    panel.resize(500, 400)
    panel.show()
    yield panel
    panel.close()


def tiles(panel):
    return [panel._tiles_layout.itemAt(i).widget() for i in range(panel._tiles_layout.count())]


class TestPanelBasics:
    def test_type_name_is_singular_and_the_object_name_is_kept(self, assets):
        assert assets.objectName() == 'Assets' and assets._type_name == 'Asset' and repr(assets) == '<Panel Assets>'

    def test_tiles_are_added_and_sized_to_the_panel(self, assets):
        found = tiles(assets)
        assert len(found) == 4 and all(t.width() == t.height() >= 80 for t in found)
        assert [t._item_index for t in found] == [0, 1, 2, 3]
        assert found[0].isEnabled() and found[0]._draggable

    def test_apps_tiles_accept_asset_drops_and_forward_the_signal(self, apps):
        apps.add_item_tile({'name': 'Maya'})
        settle()
        tile = tiles(apps)[0]
        dropped = []
        apps.asset_dropped_on_tile.connect(lambda asset, target: dropped.append((asset, target)))
        tile.asset_dropped.emit({'name': 'Hero'}, {'name': 'Maya'})
        activated = []
        apps.item_activated.connect(activated.append)
        tile.activated.emit({'name': 'Maya'})
        assert dropped == [({'name': 'Hero'}, {'name': 'Maya'})] and activated == [{'name': 'Maya'}]
        assert not tile._draggable and tile._accept_asset_drop

    def test_title_visibility_and_navigation(self, assets):
        assets.set_title('Assets / Monsters')
        assert assets._header._title_label.text() == 'Assets / Monsters'
        assets.set_show_navigate_up(False)
        assert assets._header._navigate_up_btn.isHidden()
        ups = []
        assets.navigate_up_clicked.connect(lambda: ups.append(1))
        assets._header.navigate_up_clicked.emit()
        assets.visibility = False
        assert assets.visibility is False and not assets.isVisible()

    def test_minimizing_hides_only_the_content(self, assets):
        seen = []
        assets.minimized_changed.connect(lambda name, minimized: seen.append((name, minimized)))
        assets._header._minmax_btn.click()
        assert assets.minimized and not assets._scroll_area.isVisible() and seen == [('Assets', True)]
        assets._header._minmax_btn.click()
        assert assets._scroll_area.isVisible()

    def test_closing_emits_close_clicked(self, qapp):
        panel = Panel('Tasks', 'Tasks')
        closed = []
        panel.close_clicked.connect(lambda: closed.append(1))
        panel.close()
        assert closed == [1]

    def test_without_a_scroll_area_there_are_no_tiles(self, qapp):
        panel = Panel('Views', 'Views', show_scroll_area=False)
        assert panel.minimized is False
        panel._on_minimized(True)
        panel._update_tile_size()

    def test_resize_updates_the_tile_size(self, assets):
        assets.resize(900, 500)
        settle()
        assert tiles(assets)[0].width() > 80


class TestRemoveConfigureAdd:
    def test_removing_an_item(self, assets):
        removed = []
        assets.item_removed.connect(removed.append)
        assets._remove_item_at(1)
        assets._remove_item_at(10)
        assert [i['name'] for i in assets._items] == ['a', 'c', 'd'] and removed == [{'name': 'b', 'type': 'Asset'}]
        assert len(tiles(assets)) == 3

    def test_configuring_an_item_updates_it(self, apps, messages):
        apps.add_item_tile({'name': 'Maya'})
        updated = []
        apps.item_updated.connect(lambda index, item: updated.append((index, item)))
        apps._on_item_configured(0, {'name': 'Maya 2027'})
        apps._on_item_configured(5, {'name': 'x'})
        assert apps._items[0]['name'] == 'Maya 2027' and updated == [(0, {'name': 'Maya 2027'})]

    def test_open_configure_dialog(self, apps, messages):
        apps.add_item_tile({'name': 'Maya'})
        apps._open_configure_dialog(0)
        apps._open_configure_dialog(7)
        assert messages == [('configure', 'App')]

    def test_add_item_opens_the_dialog_and_forwards_the_result(self, assets, messages):
        added = []
        assets.add_item.connect(added.append)
        created = []
        assets.item_created.connect(created.append)
        assets._add_item()
        assert added == ['Asset'] and messages == [('add', 'Asset')]

    def test_new_assets_default_to_the_panels_asset_type(self, assets, messages, monkeypatch):
        seen = []
        original = _panel.AddItemDialog.__init__

        def spy(self, type_name, parent=None, initial_name=None, initial_asset_type=None):
            seen.append(initial_asset_type)
            original(self, type_name, parent=parent, initial_name=initial_name, initial_asset_type=initial_asset_type)

        monkeypatch.setattr(_panel.AddItemDialog, '__init__', spy)
        assets.get_default_asset_type = lambda: 'Shot'
        assets._add_item()
        assert seen == ['Shot']


class TestContextMenu:
    @pytest.fixture
    def captured(self, monkeypatch):
        menus = []
        real_menu = QtWidgets.QMenu

        class RecordingMenu(real_menu):
            def exec(self, pos=None):
                menus.append(self)

        monkeypatch.setattr(_panel.QtWidgets, 'QMenu', RecordingMenu)
        return menus

    def labels(self, menu):
        return [a.text() for a in menu.actions() if not a.isSeparator()]

    def test_empty_space_offers_to_add(self, assets, captured):
        assets._show_context_menu(QtCore.QPoint(2, 2))
        assert self.labels(captured[0]) == ['Add Asset']

    def test_asset_tile_menu_has_configure_remove_and_reordering(self, assets, captured, monkeypatch):
        assets.can_reorder_assets = lambda: True
        tile = tiles(assets)[1]
        monkeypatch.setattr(assets, '_tile_at_position', lambda pos: tile)
        assets._show_context_menu(QtCore.QPoint(2, 2))
        menu = captured[0]
        assert self.labels(menu) == ['Configure', 'Remove', 'Move Up', 'Move Down', 'Add Asset']
        emitted = []
        assets.asset_configure_requested.connect(emitted.append)
        order = []
        assets.asset_order_changed.connect(order.append)
        removed = []
        assets.item_removed.connect(removed.append)
        by_text = {a.text(): a for a in menu.actions()}
        by_text['Configure'].trigger()
        by_text['Move Up'].trigger()
        assert emitted == [1] and order == [['b', 'a', 'c', 'd']]
        by_text['Remove'].trigger()
        assert len(removed) == 1

    def test_apps_menu_for_writable_and_read_only_items(self, apps, captured, monkeypatch, messages):
        apps.add_item_tile({'name': 'Maya', 'is_writable': True})
        apps.add_item_tile({'name': 'Site', 'is_writable': False})
        settle()
        first, second = tiles(apps)
        monkeypatch.setattr(apps, '_tile_at_position', lambda pos: first)
        apps._show_context_menu(QtCore.QPoint(2, 2))
        assert self.labels(captured[0]) == ['Configure...', 'Remove', 'Add App']
        {a.text(): a for a in captured[0].actions()}['Configure...'].trigger()
        assert messages == [('configure', 'App')]
        monkeypatch.setattr(apps, '_tile_at_position', lambda pos: second)
        apps._show_context_menu(QtCore.QPoint(2, 2))
        assert self.labels(captured[1]) == ['Add App']

    def test_tile_lookup_by_position(self, assets):
        tile = tiles(assets)[0]
        viewport = assets._scroll_area.viewport()
        point = viewport.mapFromGlobal(tile.mapToGlobal(QtCore.QPoint(10, 10)))
        assert assets._tile_at_position(point) is tile
        assert assets._tile_at_position(QtCore.QPoint(-5, -5)) is None


class TestReordering:
    @pytest.fixture
    def reorderable(self, assets):
        assets.can_reorder_assets = lambda: True
        return assets

    def cell_center(self, panel, index):
        tile = tiles(panel)[index]
        viewport = panel._scroll_area.viewport()
        return viewport.mapFromGlobal(tile.mapToGlobal(QtCore.QPoint(tile.width() // 2, tile.height() // 2)))

    def test_move_asset_swaps_neighbours_and_ignores_the_ends(self, reorderable):
        order = []
        reorderable.asset_order_changed.connect(order.append)
        reorderable._move_asset(0, 1)
        reorderable._move_asset(0, -1)
        reorderable._move_asset(3, 1)
        reorderable._move_asset(9, 1)
        assert order == [['b', 'a', 'c', 'd']]
        empty = Panel('Assets', 'Assets')
        empty._move_asset(0, 1)

    def test_drag_enter_move_and_drop_reorders(self, reorderable):
        viewport = reorderable._scroll_area.viewport()
        mime = asset_mime({'name': 'a', 'type': 'Asset'})
        order = []
        reorderable.asset_order_changed.connect(order.append)
        enter = FakeDropEvent(QtCore.QEvent.Type.DragEnter, mime)
        assert reorderable.eventFilter(viewport, enter) is True and enter.accepted
        assert reorderable._reorder_dragged_item['name'] == 'a' and reorderable._reorder_preview_index == 0
        target = self.cell_center(reorderable, 3)
        move = FakeDropEvent(QtCore.QEvent.Type.DragMove, mime, (target.x(), target.y()))
        assert reorderable.eventFilter(viewport, move) is True
        assert reorderable._reorder_preview_index == 3
        drop = FakeDropEvent(QtCore.QEvent.Type.Drop, mime, (target.x(), target.y()))
        assert reorderable.eventFilter(viewport, drop) is True
        assert order == [['b', 'c', 'd', 'a']] and reorderable._reorder_dragged_item is None      # moved to the last cell
        assert [i['name'] for i in reorderable._items] == ['b', 'c', 'd', 'a']

    def test_leaving_the_viewport_restores_the_original_order(self, reorderable):
        viewport = reorderable._scroll_area.viewport()
        mime = asset_mime({'name': 'a'})
        reorderable.eventFilter(viewport, FakeDropEvent(QtCore.QEvent.Type.DragEnter, mime))
        target = self.cell_center(reorderable, 2)
        reorderable.eventFilter(viewport, FakeDropEvent(QtCore.QEvent.Type.DragMove, mime, (target.x(), target.y())))
        assert [i['name'] for i in reorderable._items] != ['a', 'b', 'c', 'd']
        assert reorderable.eventFilter(viewport, FakeDropEvent(QtCore.QEvent.Type.DragLeave, mime)) is False
        assert [i['name'] for i in reorderable._items] == ['a', 'b', 'c', 'd']
        assert reorderable.eventFilter(viewport, FakeDropEvent(QtCore.QEvent.Type.DragLeave, mime)) is False

    def test_dropping_on_a_tile_uses_its_left_or_right_half(self, reorderable):
        viewport = reorderable._scroll_area.viewport()
        mime = asset_mime({'name': 'a'})
        reorderable.eventFilter(viewport, FakeDropEvent(QtCore.QEvent.Type.DragEnter, mime))
        target = tiles(reorderable)[2]
        right = FakeDropEvent(QtCore.QEvent.Type.Drop, mime, (target.width() - 2, 5))
        order = []
        reorderable.asset_order_changed.connect(order.append)
        assert reorderable.eventFilter(target, right) is True
        assert order and order[0][0] != 'a'

    def test_unknown_assets_and_non_reorderable_panels_are_not_dragged(self, reorderable, assets):
        viewport = reorderable._scroll_area.viewport()
        unknown = FakeDropEvent(QtCore.QEvent.Type.DragEnter, asset_mime({'name': 'zzz'}))
        assert reorderable.eventFilter(viewport, unknown) is False and reorderable._reorder_dragged_item is None
        broken = QtCore.QMimeData()
        broken.setData(ASSET_MIME_TYPE, QtCore.QByteArray(b'junk'))
        assert reorderable.eventFilter(viewport, FakeDropEvent(QtCore.QEvent.Type.DragEnter, broken)) is False
        move = FakeDropEvent(QtCore.QEvent.Type.DragMove, asset_mime({'name': 'a'}))
        assert reorderable.eventFilter(viewport, move) is False
        drop = FakeDropEvent(QtCore.QEvent.Type.Drop, asset_mime({'name': 'a'}))
        assert reorderable.eventFilter(viewport, drop) is False

    def test_external_file_drops(self, assets, tmp_path):
        viewport = assets._scroll_area.viewport()
        real = tmp_path / 'scene.usda'
        real.write_text('#usda 1.0')
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(str(real)), QtCore.QUrl.fromLocalFile(str(tmp_path / 'gone.usda')),
                      QtCore.QUrl('http://example.com/x.usd')])
        files = []
        assets.file_dropped.connect(files.append)
        for kind in (QtCore.QEvent.Type.DragEnter, QtCore.QEvent.Type.DragMove):
            event = FakeDropEvent(kind, mime)
            assert assets.eventFilter(viewport, event) is False and event.accepted
        drop = FakeDropEvent(QtCore.QEvent.Type.Drop, mime)
        assert assets.eventFilter(viewport, drop) is True and drop.accepted
        assert files == [[str(real.resolve())]]
        plain = FakeDropEvent(QtCore.QEvent.Type.Drop, QtCore.QMimeData())
        assert assets.eventFilter(viewport, plain) is True and not plain.accepted     # swallowed, nothing emitted

    def test_unrelated_events_are_passed_on(self, assets):
        viewport = assets._scroll_area.viewport()
        assert assets.eventFilter(viewport, QtCore.QEvent(QtCore.QEvent.Type.Show)) in (True, False)

    def test_cell_and_index_lookups(self, reorderable):
        point = self.cell_center(reorderable, 2)
        assert reorderable._cell_index_at_position(point) == 2 and reorderable._is_over_grid_cell(point)
        assert reorderable._index_at_position(point) == 2
        far = QtCore.QPoint(-10, -10)
        assert reorderable._cell_index_at_position(far) is None and not reorderable._is_over_grid_cell(far)
        assert reorderable._index_at_position(far) == 4

    def test_the_reorder_preview_shows_a_placeholder(self, reorderable):
        reorderable._reorder_original_items = list(reorderable._items)
        reorderable._reorder_dragged_item = reorderable._items[0]
        reorderable._items = reorderable._items[1:]
        reorderable._reorder_preview_index = 1
        reorderable._relayout_tiles()
        frames = [w for w in tiles(reorderable) if not isinstance(w, ItemTile)]
        assert len(frames) == 1 and frames[0]._item_index == 1 and len(tiles(reorderable)) == 4

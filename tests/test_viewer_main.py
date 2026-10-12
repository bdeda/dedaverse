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
"""Tests for the viewer command line entry point (python -m deda.core.viewer)."""
import pytest

pytest.importorskip('pxr.Usdviewq', reason='the viewer needs a full USD build')

from click.testing import CliRunner  # noqa: E402
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from deda.core.viewer import __main__ as viewer_main  # noqa: E402


class FakeApp:
    def __init__(self):
        self.icon = None

    def setWindowIcon(self, icon):
        self.icon = icon

    def exec(self):
        return 5


class FakeWindow:
    instances = []

    def __init__(self):
        self.shown = False
        self.opened = []
        FakeWindow.instances.append(self)

    def show(self):
        self.shown = True

    def _open_path(self, path):
        self.opened.append(path)


class FakeSplash:
    def __init__(self, pixmap, flags):
        self.events = ['created']

    def show(self):
        self.events.append('show')

    def finish(self, window):
        self.events.append('finish')


@pytest.fixture
def patched(monkeypatch):
    FakeWindow.instances = []
    app = FakeApp()
    monkeypatch.setattr(viewer_main, 'Application', lambda: app)
    monkeypatch.setattr(viewer_main._window, 'MainWindow', FakeWindow)
    monkeypatch.setattr(viewer_main.QtWidgets, 'QSplashScreen', FakeSplash)
    monkeypatch.setattr(viewer_main.deda.log, 'initialize', lambda loglevel: None)
    scheduled = []
    monkeypatch.setattr(viewer_main.QtCore.QTimer, 'singleShot', staticmethod(lambda ms, fn: scheduled.append(fn)))
    return app, scheduled


def test_the_splash_image_is_drawn(qapp):
    pixmap = viewer_main._make_splash_pixmap()
    assert (pixmap.width(), pixmap.height()) == (viewer_main._SPLASH_WIDTH, viewer_main._SPLASH_HEIGHT)
    image = pixmap.toImage()
    assert len({image.pixelColor(x, y).name() for x in range(0, 420, 7) for y in range(0, 220, 7)}) > 1


def test_starting_without_a_file_shows_the_window_and_returns_the_event_loop_result(patched):
    app, scheduled = patched
    result = CliRunner().invoke(viewer_main.viewer, [], standalone_mode=False)
    assert result.return_value == 5 and FakeWindow.instances[0].shown and scheduled == []
    assert not app.icon.isNull()


def test_a_file_argument_is_opened_after_the_window_is_up(patched, tmp_path):
    _, scheduled = patched
    shot = tmp_path / 'shot.0001.exr'
    result = CliRunner().invoke(viewer_main.viewer, [str(shot)], standalone_mode=False)
    assert result.return_value == 5 and len(scheduled) == 1
    scheduled[0]()
    assert FakeWindow.instances[0].opened == [str(shot.resolve())]


def test_a_missing_icon_is_not_an_error(patched, monkeypatch):
    app, _ = patched
    monkeypatch.setattr(viewer_main.Path, 'is_file', lambda self: False)
    assert CliRunner().invoke(viewer_main.viewer, [], standalone_mode=False).return_value == 5 and app.icon is None

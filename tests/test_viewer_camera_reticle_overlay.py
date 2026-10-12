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
"""Tests for the camera reticle overlay and its usdview plugin."""
import types

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from deda.core.viewer import _camera_reticle as reticle


class Parent:
    def __init__(self):
        self.updates = 0

    def update(self):
        self.updates += 1


def draw_to_image(overlay, width=120, height=90):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.black)
    painter = QtGui.QPainter(image)
    overlay.draw(painter, QtCore.QRect(0, 0, width, height))
    painter.end()
    return image


def lit_pixels(image):
    return sum(1 for x in range(image.width()) for y in range(image.height())
               if image.pixelColor(x, y).red() > 0)


class TestOverlayProperties:
    def test_setters_update_the_parent(self):
        parent = Parent()
        overlay = reticle.CameraReticleOverlay(parent)
        overlay.enabled = False
        overlay.color = QtGui.QColor('red')
        overlay.size = 40
        overlay.style = 'grid'
        assert (overlay.enabled, overlay.color.name(), overlay.size, overlay.style) == (False, '#ff0000', 40, 'grid')
        assert parent.updates == 4

    def test_size_is_clamped_and_unknown_styles_ignored(self):
        overlay = reticle.CameraReticleOverlay(Parent())
        overlay.size = 1
        assert overlay.size == 5
        overlay.size = 1000
        assert overlay.size == 100
        overlay.style = 'bokeh'
        assert overlay.style == 'crosshair'

    def test_setters_work_without_a_parent(self):
        overlay = reticle.CameraReticleOverlay()
        overlay.enabled = True
        overlay.color = QtGui.QColor('blue')
        overlay.size = 10
        overlay.style = 'frame'
        assert overlay.style == 'frame'


class TestOverlayDrawing:
    @pytest.mark.parametrize('style', ['crosshair', 'frame', 'grid'])
    def test_every_style_draws_something(self, qapp, style):
        overlay = reticle.CameraReticleOverlay()
        overlay.style = style
        overlay.color = QtGui.QColor(255, 255, 255, 255)
        assert lit_pixels(draw_to_image(overlay)) > 0

    def test_grid_draws_more_than_a_crosshair(self, qapp):
        crosshair = reticle.CameraReticleOverlay()
        grid = reticle.CameraReticleOverlay()
        grid.style = 'grid'
        assert lit_pixels(draw_to_image(grid)) > lit_pixels(draw_to_image(crosshair))

    def test_disabled_overlay_draws_nothing(self, qapp):
        overlay = reticle.CameraReticleOverlay()
        overlay.enabled = False
        assert lit_pixels(draw_to_image(overlay)) == 0


class FakeRegistry:
    def __init__(self):
        self.commands = []

    def registerCommandPlugin(self, name, label, callback):
        self.commands.append((name, label, callback))


class FakeView:
    def __init__(self):
        self.painted = []
        self.updates = 0
        self.paintEvent = lambda event: self.painted.append(event)

    def update(self):
        self.updates += 1

    def rect(self):
        return QtCore.QRect(0, 0, 10, 10)


@pytest.fixture
def usd_available(monkeypatch):
    monkeypatch.setattr(reticle, 'USD_AVAILABLE', True)


class TestPlugin:
    def test_without_usd_nothing_is_registered(self, monkeypatch, caplog):
        monkeypatch.setattr(reticle, 'USD_AVAILABLE', False)
        registry = FakeRegistry()
        with caplog.at_level('WARNING'):
            assert reticle.registerPlugins(registry, None, None) is None
            reticle.CameraReticlePlugin().registerPlugins(registry, None, None)
        assert registry.commands == [] and 'not available' in caplog.text
        reticle.CameraReticlePlugin().configureView(FakeView())    # also a no-op without USD

    def test_register_adds_the_toggle_command(self, usd_available):
        registry = FakeRegistry()
        plugin = reticle.registerPlugins(registry, 'ctx', None)
        assert isinstance(plugin, reticle.CameraReticlePlugin)
        assert registry.commands[0][:2] == ('CameraReticlePlugin.toggle', 'Toggle Camera Reticle')
        assert plugin.overlay.enabled
        registry.commands[0][2]()
        assert plugin.overlay.enabled is False

    def test_toggle_updates_the_configured_view(self, usd_available):
        plugin = reticle.CameraReticlePlugin()
        plugin.registerPlugins(FakeRegistry(), None, None)
        view = FakeView()
        plugin.configureView(view)
        updates = view.updates
        plugin._toggle_reticle(None)
        assert plugin.overlay.enabled is False and view.updates > updates
        plugin._toggle_reticle(None)
        assert plugin.overlay.enabled is True

    def test_configure_wraps_the_paint_event(self, usd_available, qapp, monkeypatch):
        plugin = reticle.CameraReticlePlugin()
        plugin.registerPlugins(FakeRegistry(), None, None)
        view = FakeView()
        original_calls = view.painted
        plugin.configureView(view)
        assert plugin.overlay._parent is view

        painters = []

        class FakePainter:
            def __init__(self, target):
                painters.append(self)
                self.ended = False

            def end(self):
                self.ended = True

        drawn = []
        monkeypatch.setattr(reticle.QtGui, 'QPainter', FakePainter)
        monkeypatch.setattr(plugin.overlay, 'draw', lambda painter, rect: drawn.append(rect))
        view.paintEvent('event')                                  # calls the original, then draws
        assert original_calls == ['event'] and len(drawn) == 1 and painters[0].ended
        plugin.overlay.enabled = False
        view.paintEvent('again')
        assert len(drawn) == 1 and original_calls == ['event', 'again']

    def test_configure_without_a_paint_event(self, usd_available):
        plugin = reticle.CameraReticlePlugin()
        plugin.registerPlugins(FakeRegistry(), None, None)
        bare = types.SimpleNamespace(update=lambda: None)
        plugin.configureView(bare)
        assert plugin._original_paint_event is None

    def test_toggle_without_an_overlay_is_a_noop(self):
        plugin = reticle.CameraReticlePlugin()
        plugin._overlay = None
        plugin._toggle_reticle(None)
        assert plugin.overlay is None

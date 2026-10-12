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
"""Tests for the viewer slate text overlay."""
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from deda.core.viewer import _slate
from deda.core.viewer._slate import SlateTextGlOverlay

RECT = QtCore.QRect(0, 0, 400, 300)


def render(overlay, rect=RECT):
    image = QtGui.QImage(rect.width(), rect.height(), QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.black)
    painter = QtGui.QPainter(image)
    drew = overlay.draw(painter, rect)
    painter.end()
    return drew, image


def bright_bbox(image):
    xs, ys = [], []
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).red() > 128:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


class TestProperties:
    def test_defaults_and_constructor_values(self):
        overlay = SlateTextGlOverlay(font_family='Arial', lines=['a', 'b'], padding_px=3, frame_placement='center')
        assert overlay.enabled and overlay.font_family == 'Arial' and overlay.lines == ['a', 'b']
        assert overlay.padding_px == 3 and overlay.frame_placement == 'center'

    def test_values_are_clamped(self):
        overlay = SlateTextGlOverlay()
        overlay.padding_px = -5
        overlay.line_spacing_px = -1
        overlay.font_size = 0
        assert (overlay.padding_px, overlay.line_spacing_px, overlay.font_size) == (0.0, 0.0, 1.0)

    def test_unknown_placement_is_rejected(self, caplog):
        overlay = SlateTextGlOverlay()
        with caplog.at_level('WARNING'):
            overlay.frame_placement = 'middle-ish'
        assert overlay.frame_placement == 'top_left' and 'Unsupported slate placement' in caplog.text

    def test_colors_accept_floats_bytes_and_rgb(self):
        overlay = SlateTextGlOverlay()
        overlay.color = (255, 0, 0)
        assert overlay.color == (1.0, 0.0, 0.0, 1.0)
        overlay.color = (0.5, 0.5, 0.5, 0.5, 99)
        assert overlay.color == (0.5, 0.5, 0.5, 0.5)
        overlay.color = (300, -1, 0)
        assert overlay.color[0] == 1.0 and overlay.color[1] == 0.0

    @pytest.mark.parametrize('bad', [5, (1, 2), ('a', 'b', 'c'), None])
    def test_invalid_colors_are_ignored_with_a_warning(self, bad, caplog):
        overlay = SlateTextGlOverlay()
        before = overlay.color
        with caplog.at_level('WARNING'):
            overlay.color = bad
        assert overlay.color == before and 'Invalid slate color' in caplog.text

    def test_shadow_color_can_be_cleared(self):
        overlay = SlateTextGlOverlay()
        assert overlay.shadow_color is not None
        overlay.shadow_color = None
        assert overlay.shadow_color is None

    def test_shadow_offset_validation(self, caplog):
        overlay = SlateTextGlOverlay()
        overlay.shadow_offset_px = (2, 3)
        assert overlay.shadow_offset_px == (2.0, 3.0)
        with caplog.at_level('WARNING'):
            overlay.shadow_offset_px = 'x'
        assert overlay.shadow_offset_px == (2.0, 3.0) and 'Invalid shadow offset' in caplog.text

    def test_text_helpers(self):
        overlay = SlateTextGlOverlay()
        overlay.set_text('one\ntwo')
        assert overlay.lines == ['one', 'two']
        overlay.lines = [1, 2]
        assert overlay.lines == ['1', '2']
        overlay.set_text('')
        assert overlay.lines == []
        overlay.lines = ['x']
        overlay.clear()
        assert overlay.lines == []
        overlay.enabled = 0
        assert overlay.enabled is False


class TestDrawing:
    def test_nothing_is_drawn_without_text_or_when_disabled_or_degenerate(self, qapp):
        overlay = SlateTextGlOverlay()
        assert render(overlay)[0] is False                           # no lines
        overlay.set_text('hello')
        overlay.enabled = False
        assert render(overlay)[0] is False
        overlay.enabled = True
        assert render(overlay, QtCore.QRect(0, 0, 0, 0))[0] is False

    def test_text_is_drawn_near_the_top_left_by_default(self, qapp):
        overlay = SlateTextGlOverlay(font_size=16, shadow_color=None)
        overlay.set_text('SLATE')
        drew, image = render(overlay)
        box = bright_bbox(image)
        assert drew and box is not None and box[0] >= 10 and box[1] <= 40 and box[2] < 200

    @pytest.mark.parametrize('placement, check', [
        ('top_right', lambda b: b[0] > 200 and b[1] < 60),
        ('bottom_left', lambda b: b[0] < 100 and b[3] > 240),
        ('bottom_right', lambda b: b[0] > 200 and b[3] > 240),
        ('top_center', lambda b: 120 < b[0] and b[2] < 280 and b[1] < 60),
        ('bottom_center', lambda b: 120 < b[0] and b[2] < 280 and b[3] > 240),
        ('center', lambda b: 120 < b[0] and b[2] < 280 and 100 < b[1] and b[3] < 200),
    ])
    def test_placements(self, qapp, placement, check):
        overlay = SlateTextGlOverlay(font_size=14, frame_placement=placement, shadow_color=None)
        overlay.set_text('ABC')
        _, image = render(overlay)
        assert check(bright_bbox(image)), (placement, bright_bbox(image))

    def test_multiple_lines_and_shadow_and_family(self, qapp):
        overlay = SlateTextGlOverlay(font_family='Arial', font_size=14, lines=['one', 'two', 'three'])
        drew, image = render(overlay)
        single = SlateTextGlOverlay(font_family='Arial', font_size=14, lines=['one'])
        assert drew and bright_bbox(image)[3] > bright_bbox(render(single)[1])[3]

    def test_unknown_placement_falls_back_to_top_left_anchor(self):
        overlay = SlateTextGlOverlay(padding_px=7)
        overlay._frame_placement = 'bogus'
        assert overlay._resolve_anchor(RECT, 10, 10) == (7, 7)

    def test_draw_from_stage_view_paints_the_widget(self, qapp):
        overlay = SlateTextGlOverlay(font_size=14, lines=['hi'])
        widget = QtWidgets.QWidget()
        widget.resize(200, 100)
        # Painting a widget outside its paintEvent is only legal for the duration of a paint; use a
        # subclass that paints the overlay from paintEvent, as the viewer does.
        results = []

        class Canvas(QtWidgets.QWidget):
            def paintEvent(self, event):
                results.append(overlay.draw_from_stage_view(self))

        canvas = Canvas()
        canvas.resize(200, 100)
        canvas.grab()
        assert results and results[0] is True

    def test_draw_from_stage_view_without_pyside(self, monkeypatch):
        monkeypatch.setattr(_slate, 'PYSIDE6_AVAILABLE', False)
        assert SlateTextGlOverlay().draw_from_stage_view(object()) is False
        with pytest.raises(RuntimeError):
            SlateTextGlOverlay._to_qcolor((1, 1, 1, 1))

    def test_to_qcolor_of_none_is_transparent(self, qapp):
        assert SlateTextGlOverlay._to_qcolor(None).alpha() == 0

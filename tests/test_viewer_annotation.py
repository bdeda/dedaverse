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
"""Tests for annotation strokes and texts, their serialisation, and drawing them."""
import sys
import types

import pytest
from PySide6 import QtCore, QtGui

from deda.core.viewer import _annotation as ann
from deda.core.viewer._annotation import AnnotationGlOverlay, AnnotationStroke, AnnotationText


class FakeGL:
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA = 1, 2, 3, 4
    GL_LINE_STRIP, GL_PROJECTION, GL_MODELVIEW = 5, 6, 7

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith('gl'):
            return lambda *args: self.calls.append((name, args))
        raise AttributeError(name)

    def names(self):
        return [name for name, _ in self.calls]


class TestDataClasses:
    def test_stroke_round_trip(self):
        stroke = AnnotationStroke(points=[(0, 1), (2, 3)], color=(1.0, 0.0, 0.0, 1.0), line_width=4.0)
        again = AnnotationStroke.from_dict(stroke.to_dict())
        assert again.points == [(0.0, 1.0), (2.0, 3.0)] and again.color == (1.0, 0.0, 0.0, 1.0)
        assert again.line_width == 4.0

    def test_stroke_from_sparse_or_bad_data_uses_defaults(self):
        stroke = AnnotationStroke.from_dict({'color': 'nonsense'})
        assert stroke.points == [] and stroke.color == (1.0, 0.9, 0.2, 0.9) and stroke.line_width == 2.0

    def test_text_round_trip_with_and_without_shadow(self):
        text = AnnotationText(x=1, y=2, text='hi', font_size=20, font_family='Arial')
        again = AnnotationText.from_dict(text.to_dict())
        assert (again.x, again.y, again.text, again.font_size, again.font_family) == (1.0, 2.0, 'hi', 20.0, 'Arial')
        assert again.shadow_color == (0.0, 0.0, 0.0, 0.7) and again.shadow_offset_px == (2.0, 2.0)
        bare = AnnotationText(text='x', shadow_color=None).to_dict()
        assert 'shadow_color' not in bare
        loaded = AnnotationText.from_dict({'shadow_color': None, 'shadow_offset_px': 'bad', 'font_family': ''})
        assert loaded.shadow_color is None and loaded.shadow_offset_px == (2.0, 2.0) and loaded.font_family is None

    def test_text_from_empty_payload(self):
        text = AnnotationText.from_dict({})
        assert text.text == '' and text.color == (1.0, 1.0, 1.0, 0.9)


class TestColors:
    @pytest.mark.parametrize('value, expected', [
        ((255, 0, 0), (1.0, 0.0, 0.0, 1.0)), ((0.1, 0.2, 0.3, 0.4, 9), (0.1, 0.2, 0.3, 0.4)),
        ((2, 0, -1, 0.5), (2 / 255, 0.0, 0.0, 0.5)),
    ])
    def test_valid(self, value, expected):
        assert ann._normalize_color(value) == pytest.approx(expected)

    @pytest.mark.parametrize('value', [None, 5, (1, 2), ('a', 'b', 'c')])
    def test_invalid(self, value):
        assert ann._normalize_color(value) is None


class TestOverlayState:
    def test_defaults_and_setters(self):
        overlay = AnnotationGlOverlay(text_shadow_color=(0, 0, 0, 1), text_shadow_offset_px=(1, 1))
        assert overlay.enabled and not overlay.dirty
        overlay.enabled = 0
        overlay.default_color = (0.5, 0.5, 0.5)
        overlay.default_color = 'bad'
        overlay.default_text_color = (1, 0, 0)
        overlay.default_text_color = None
        overlay.default_text_font_size = 2
        assert overlay.enabled is False and overlay.default_color == (0.5, 0.5, 0.5, 1.0)
        assert overlay.default_text_color == (1.0, 0.0, 0.0, 1.0) and overlay.default_text_font_size == 8.0

    def test_bad_constructor_colors_fall_back(self):
        overlay = AnnotationGlOverlay(color='x', text_color='y', line_width=0, text_font_size=1)
        assert overlay.default_color == (1.0, 0.9, 0.2, 0.9)
        assert overlay.default_text_color == (1.0, 1.0, 1.0, 0.9)

    def test_strokes_and_texts_are_copied_out(self):
        overlay = AnnotationGlOverlay()
        stroke, text = AnnotationStroke(points=[(0, 0), (1, 1)]), AnnotationText(text='t')
        overlay.set_strokes([stroke])
        overlay.set_texts([text])
        overlay.strokes.clear()
        overlay.texts.clear()
        assert overlay.strokes == [stroke] and overlay.texts == [text]

    def test_clear_resets_everything(self):
        overlay = AnnotationGlOverlay()
        overlay.add_text(0, 0, 'a')
        overlay.select_text(0)
        overlay.begin_stroke()
        overlay.clear()
        assert overlay.texts == [] and overlay.strokes == [] and overlay.selected_text_indices == []


class TestStrokes:
    def test_drawing_a_stroke_marks_the_overlay_dirty(self):
        overlay = AnnotationGlOverlay()
        overlay.begin_stroke(color=(1, 0, 0), line_width=0.1)
        overlay.add_point(1, 2)
        overlay.add_point(3, 4)
        overlay.end_stroke()
        stroke = overlay.strokes[0]
        assert overlay.dirty and stroke.points == [(1.0, 2.0), (3.0, 4.0)]
        assert stroke.color == (1.0, 0.0, 0.0, 1.0) and stroke.line_width == 0.5
        overlay.clear_dirty()
        assert not overlay.dirty

    def test_add_point_starts_a_stroke_implicitly(self):
        overlay = AnnotationGlOverlay()
        overlay.add_point(1, 1)
        assert len(overlay.strokes) == 1

    def test_a_click_without_a_drag_leaves_no_stroke(self):
        overlay = AnnotationGlOverlay()
        overlay.begin_stroke()
        overlay.add_point(1, 1)
        overlay.end_stroke()
        assert overlay.strokes == []
        overlay.end_stroke()            # nothing active: a no-op

    def test_add_stroke_needs_two_points(self):
        overlay = AnnotationGlOverlay()
        overlay.add_stroke([])
        overlay.add_stroke([(0, 0)])
        overlay.add_stroke([(0, 0), (5, 5)], color=(0, 1, 0), line_width=3)
        overlay.add_stroke([(0, 0), (1, 1)], color='bad')
        assert len(overlay.strokes) == 2 and overlay.strokes[0].color == (0.0, 1.0, 0.0, 1.0)
        assert overlay.strokes[1].color == overlay.default_color


class TestTexts:
    def test_add_and_remove(self):
        overlay = AnnotationGlOverlay(text_shadow_color=(0, 0, 0, 0.5))
        first = overlay.add_text(1, 2, 'one', color=(1, 0, 0), font_size=10, font_family='Arial',
                                 shadow_color=(0, 1, 0), shadow_offset_px=(3, 3))
        second = overlay.add_text(5, 6, 'two')
        assert first.shadow_offset_px == (3, 3) and first.font_family == 'Arial'
        assert second.shadow_color == (0.0, 0.0, 0.0, 0.5) and second.font_size == 14.0
        assert overlay.remove_text(5) is False
        assert overlay.remove_text(0) is True and overlay.texts == [second]

    def test_remove_several_counts_what_was_removed(self):
        overlay = AnnotationGlOverlay()
        for i in range(4):
            overlay.add_text(i, 0, str(i))
        overlay.clear_dirty()
        assert overlay.remove_texts([0, 2, 2, 9]) == 2 and overlay.dirty
        assert [t.text for t in overlay.texts] == ['1', '3']
        overlay.clear_dirty()
        assert overlay.remove_texts([42]) == 0 and not overlay.dirty

    def test_selection_copy_cut_paste(self):
        overlay = AnnotationGlOverlay()
        for i in range(3):
            overlay.add_text(i * 10, 0, f't{i}')
        overlay.select_text(1)
        overlay.select_text(1)           # duplicates are ignored
        overlay.select_text(99)          # out of range is ignored
        overlay.select_text(2)
        assert overlay.selected_text_indices == [1, 2]
        overlay.deselect_text(2)
        overlay.deselect_text(7)
        assert [t.text for t in overlay.copy_selected_texts()] == ['t1']
        cut = overlay.cut_selected_texts()
        assert [t.text for t in cut] == ['t1'] and [t.text for t in overlay.texts] == ['t0', 't2']
        assert overlay.selected_text_indices == [] and overlay.cut_selected_texts() == []
        overlay.clear_dirty()
        overlay.paste_texts(cut, offset_x=1, offset_y=2)
        pasted = overlay.texts[-1]
        assert (pasted.x, pasted.y, pasted.text) == (11.0, 2.0, 't1') and overlay.dirty
        overlay.clear_dirty()
        overlay.paste_texts([])
        assert not overlay.dirty
        overlay.select_text(0)
        overlay.clear_selection()
        assert overlay.selected_text_indices == []

    def test_hit_testing(self, qapp):
        overlay = AnnotationGlOverlay()
        overlay.add_text(100, 100, 'Hello world', font_size=14)
        overlay.add_text(100, 100, 'On top', font_size=14, font_family='Arial')
        assert overlay.get_text_at_position(105, 100) == 1            # the most recent wins
        assert overlay.get_text_at_position(5, 5) is None
        assert AnnotationGlOverlay().get_text_at_position(0, 0) is None

    def test_hit_testing_an_empty_text_and_without_pyside(self, qapp, monkeypatch):
        overlay = AnnotationGlOverlay()
        overlay.add_text(10, 10, '')
        assert overlay.get_text_at_position(10, 10) == 0
        monkeypatch.setattr(ann, 'PYSIDE6_AVAILABLE', False)
        assert overlay.get_text_at_position(10, 10) is None


class TestPayload:
    def test_round_trip_clears_the_dirty_flag(self):
        overlay = AnnotationGlOverlay()
        overlay.add_stroke([(0, 0), (1, 1)])
        overlay.add_text(2, 3, 'note')
        payload = overlay.to_payload()
        other = AnnotationGlOverlay()
        other.add_point(0, 0)
        other.load_payload(payload)
        assert not other.dirty and len(other.strokes) == 1 and other.texts[0].text == 'note'
        other.load_payload({})
        assert other.strokes == [] and other.texts == []


class TestGlDrawing:
    def test_strokes_are_drawn_as_line_strips(self):
        gl = FakeGL()
        overlay = AnnotationGlOverlay()
        overlay.add_stroke([(0, 0), (5, 5), (9, 1)], line_width=3)
        overlay.set_strokes(overlay.strokes + [AnnotationStroke(points=[(1, 1)])])   # too short: skipped
        assert overlay.draw(100, 50, gl=gl) is True
        assert gl.names().count('glBegin') == 1 and gl.names().count('glVertex2f') == 3
        assert ('glLineWidth', (3.0,)) in gl.calls and gl.names().count('glPopMatrix') == 2

    @pytest.mark.parametrize('setup', ['disabled', 'empty_viewport', 'no_strokes'])
    def test_nothing_to_draw(self, setup):
        overlay = AnnotationGlOverlay()
        overlay.add_stroke([(0, 0), (1, 1)])
        width = 100
        if setup == 'disabled':
            overlay.enabled = False
        elif setup == 'empty_viewport':
            width = 0
        else:
            overlay.clear()
        assert overlay.draw(width, 50, gl=FakeGL()) is False

    def test_no_gl_and_no_immediate_mode(self, monkeypatch):
        overlay = AnnotationGlOverlay()
        overlay.add_stroke([(0, 0), (1, 1)])
        monkeypatch.setattr(ann, '_resolve_gl', lambda: None)
        assert overlay.draw(100, 50) is False

        class Core:
            GL_DEPTH_TEST = GL_BLEND = GL_SRC_ALPHA = GL_ONE_MINUS_SRC_ALPHA = 1

        assert overlay.draw(100, 50, gl=Core()) is False

    def test_gl_failures_are_swallowed(self):
        class Broken(FakeGL):
            def __getattr__(self, name):
                if name == 'glBegin':
                    return lambda *a: (_ for _ in ()).throw(RuntimeError('lost context'))
                return super().__getattr__(name)

        overlay = AnnotationGlOverlay()
        overlay.add_stroke([(0, 0), (1, 1)])
        assert overlay.draw(100, 50, gl=Broken()) is False

    def test_draw_from_stage_view(self):
        class View:
            def width(self):
                return 100

            height = 50

        overlay = AnnotationGlOverlay()
        overlay.add_stroke([(0, 0), (1, 1)])
        assert overlay.draw_from_stage_view(View(), gl=FakeGL()) is True

    def test_state_helpers_tolerate_failing_gl(self):
        class Failing:
            GL_DEPTH_TEST = GL_BLEND = GL_SRC_ALPHA = GL_ONE_MINUS_SRC_ALPHA = 1
            GL_PROJECTION = GL_MODELVIEW = 2

            def __getattr__(self, name):
                if name.startswith('gl'):
                    def boom(*args):
                        raise RuntimeError('gl error')
                    return boom
                raise AttributeError(name)

        ann._apply_gl_state(Failing())
        ann._apply_stroke_state(Failing(), AnnotationStroke())
        assert ann._push_ortho(Failing(), 1, 1) is False
        ann._pop_ortho(Failing(), True)
        assert ann._push_ortho(object(), 1, 1) is False
        ann._pop_ortho(object(), True)
        ann._pop_ortho(FakeGL(), False)
        ann._apply_gl_state(object())
        ann._apply_stroke_state(object(), AnnotationStroke())


class TestResolveGl:
    def test_pyopengl_first(self, monkeypatch):
        package, gl_module = types.ModuleType('OpenGL'), types.ModuleType('OpenGL.GL')
        package.GL = gl_module
        monkeypatch.setitem(sys.modules, 'OpenGL', package)
        monkeypatch.setitem(sys.modules, 'OpenGL.GL', gl_module)
        assert ann._resolve_gl() is gl_module

    def test_qt_context_fallbacks(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'OpenGL', None)
        funcs = types.SimpleNamespace()
        funcs.initializeOpenGLFunctions = lambda: setattr(funcs, 'ready', True)
        monkeypatch.setattr(ann.QtGui.QOpenGLContext, 'currentContext',
                            staticmethod(lambda: types.SimpleNamespace(functions=lambda: funcs)))
        assert ann._resolve_gl() is funcs and funcs.ready
        monkeypatch.setattr(ann.QtGui.QOpenGLContext, 'currentContext', staticmethod(lambda: None))
        assert ann._resolve_gl() is None

        def boom():
            raise RuntimeError('x')

        monkeypatch.setattr(ann.QtGui.QOpenGLContext, 'currentContext', staticmethod(boom))
        assert ann._resolve_gl() is None
        monkeypatch.setattr(ann, 'PYSIDE6_AVAILABLE', False)
        assert ann._resolve_gl() is None


class TestTextDrawing:
    def render(self, overlay, width=200, height=120):
        image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
        image.fill(QtCore.Qt.black)
        painter = QtGui.QPainter(image)
        drew = overlay.draw_texts(painter, QtCore.QRect(0, 0, width, height))
        painter.end()
        return drew, image

    def lit(self, image):
        return sum(1 for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x, y).red() > 0)

    def bright_rows(self, image):
        return [y for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x, y).red() > 128]

    def test_text_is_painted_from_a_bottom_origin(self, qapp):
        overlay = AnnotationGlOverlay()
        overlay.add_text(10, 15, 'low text', color=(1, 1, 1), font_size=14)           # 15px above the bottom
        drew, image = self.render(overlay)
        assert drew and min(self.bright_rows(image)) > 60
        high = AnnotationGlOverlay()
        high.add_text(10, 100, 'high text', color=(1, 1, 1), font_size=14)            # 100px above the bottom
        assert max(self.bright_rows(self.render(high)[1])) < 40

    def test_multi_line_text_and_selection_highlight(self, qapp):
        overlay = AnnotationGlOverlay()
        overlay.add_text(10, 90, 'a\nb', color=(1, 1, 1), font_size=14, font_family='Arial')
        plain = self.lit(self.render(overlay)[1])
        overlay.select_text(0)
        selected = self.lit(self.render(overlay)[1])
        assert selected > plain

    def test_nothing_to_paint(self, qapp):
        overlay = AnnotationGlOverlay()
        assert self.render(overlay)[0] is False                          # no texts
        overlay.add_text(0, 0, 'x')
        assert self.render(overlay, 0, 0)[0] is False                    # empty rect
        overlay.enabled = False
        assert self.render(overlay)[0] is False

    def test_painter_errors_are_swallowed(self, qapp, monkeypatch):
        overlay = AnnotationGlOverlay()
        overlay.add_text(0, 0, 'x')
        monkeypatch.setattr(AnnotationGlOverlay, '_to_qcolor', staticmethod(lambda c: 1 / 0))
        assert self.render(overlay)[0] is False

    def test_to_qcolor_requires_qt(self, monkeypatch):
        monkeypatch.setattr(ann, 'PYSIDE6_AVAILABLE', False)
        with pytest.raises(RuntimeError):
            AnnotationGlOverlay._to_qcolor((1, 1, 1, 1))

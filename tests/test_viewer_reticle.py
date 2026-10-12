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
"""Tests for the GL reticle overlay's geometry and its OpenGL drawing (against a recording fake)."""
import sys
import types

import pytest

from deda.core.viewer import _reticle
from deda.core.viewer._reticle import CameraReticleGlOverlay


class FakeGL:
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA = 1, 2, 3, 4
    GL_LINES, GL_PROJECTION, GL_MODELVIEW = 5, 6, 7

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith('gl'):
            return lambda *args: self.calls.append((name, args))
        raise AttributeError(name)

    def names(self):
        return [name for name, _ in self.calls]


class TestProperties:
    def test_defaults(self):
        overlay = CameraReticleGlOverlay()
        assert overlay.enabled and overlay.style == 'crosshair' and overlay.size_px == 20.0
        assert overlay.line_width == 1.0 and overlay.grid_spacing_px == 20.0
        assert overlay.color == (1.0, 1.0, 1.0, 0.7)

    def test_style_is_validated(self, caplog):
        overlay = CameraReticleGlOverlay()
        overlay.style = 'grid'
        with caplog.at_level('WARNING'):
            overlay.style = 'spiral'
        assert overlay.style == 'grid' and 'Unsupported reticle style' in caplog.text

    @pytest.mark.parametrize('attr, value, expected', [
        ('size_px', 1, 5.0), ('size_px', 1000, 200.0), ('size_px', '30', 30.0),
        ('line_width', 0, 0.5), ('line_width', 99, 10.0), ('line_width', 2, 2.0),
        ('grid_spacing_px', 1, 4.0), ('grid_spacing_px', 999, 200.0), ('grid_spacing_px', 50, 50.0),
    ])
    def test_numeric_values_are_clamped(self, attr, value, expected):
        overlay = CameraReticleGlOverlay()
        setattr(overlay, attr, value)
        assert getattr(overlay, attr) == expected

    @pytest.mark.parametrize('attr, message', [
        ('size_px', 'Invalid reticle size'), ('line_width', 'Invalid reticle line width'),
        ('grid_spacing_px', 'Invalid grid spacing'),
    ])
    def test_non_numeric_values_are_ignored(self, attr, message, caplog):
        overlay = CameraReticleGlOverlay()
        before = getattr(overlay, attr)
        with caplog.at_level('WARNING'):
            setattr(overlay, attr, 'wide')
        assert getattr(overlay, attr) == before and message in caplog.text

    def test_colors(self, caplog):
        overlay = CameraReticleGlOverlay()
        overlay.color = (255, 128, 0)
        assert overlay.color[:2] == (1.0, 128 / 255) and overlay.color[3] == 1.0
        overlay.color = (0.1, 0.2, 0.3, 0.4, 0.5)
        assert overlay.color == (0.1, 0.2, 0.3, 0.4)
        before = overlay.color
        with caplog.at_level('WARNING'):
            for bad in (3, (1, 2), ('x', 1, 1)):
                overlay.color = bad
        assert overlay.color == before and 'Invalid reticle color' in caplog.text

    def test_enabled_is_coerced(self):
        overlay = CameraReticleGlOverlay()
        overlay.enabled = 0
        assert overlay.enabled is False


class TestGeometry:
    def test_degenerate_viewports_have_no_segments(self):
        overlay = CameraReticleGlOverlay()
        assert overlay.build_segments(0, 100) == [] and overlay.build_segments(100, -1) == []
        assert overlay._safe_zone_segments(0, 0) == [] and overlay.build_ndc_segments(0, 0) == []

    def test_crosshair_is_two_lines_plus_safe_zones(self):
        segments = CameraReticleGlOverlay(size_px=20).build_segments(200, 100)
        assert segments[0] == ((90.0, 50.0), (110.0, 50.0)) and segments[1] == ((100.0, 40.0), (100.0, 60.0))
        assert len(segments) == 2 + 8

    def test_frame_style_draws_thirds(self):
        overlay = CameraReticleGlOverlay(style='frame')
        segments = overlay.build_segments(300, 150)
        assert ((100.0, 0.0), (100.0, 150.0)) in segments and ((0.0, 100.0), (300, 100.0)) in segments
        assert len(segments) == 6 + 8

    def test_grid_style_follows_the_spacing(self):
        overlay = CameraReticleGlOverlay(style='grid', grid_spacing_px=50)
        segments = overlay.build_segments(200, 100)
        verticals = [s for s in segments[:-10] if s[0][0] == s[1][0]]
        assert [s[0][0] for s in verticals] == [50.0, 100.0, 150.0]
        assert len(segments) == 3 + 1 + 2 + 8

    def test_safe_zones_are_inset_five_and_ten_percent(self):
        segments = CameraReticleGlOverlay()._safe_zone_segments(200, 100)
        assert segments[0] == ((10.0, 5.0), (190.0, 5.0))
        assert segments[4] == ((20.0, 10.0), (180.0, 10.0))

    def test_ndc_conversion_maps_corners_to_unit_range(self):
        overlay = CameraReticleGlOverlay()
        for (x1, y1), (x2, y2) in overlay.build_ndc_segments(400, 200):
            assert -1.0 <= x1 <= 1.0 and -1.0 <= y1 <= 1.0 and -1.0 <= x2 <= 1.0 and -1.0 <= y2 <= 1.0
        centre = overlay.build_ndc_segments(400, 200)[0]
        assert abs(centre[0][1]) < 1e-9          # the crosshair's horizontal line sits at vertical centre


class TestDrawing:
    def test_draw_uses_immediate_mode_with_an_ortho_projection(self):
        gl = FakeGL()
        overlay = CameraReticleGlOverlay()
        assert overlay.draw(200, 100, gl=gl) is True
        names = gl.names()
        assert names.count('glVertex2f') == 2 * len(overlay.build_segments(200, 100))
        assert names.index('glBegin') < names.index('glVertex2f') < names.index('glEnd')
        assert names.count('glPushMatrix') == 2 == names.count('glPopMatrix')
        assert ('glLineWidth', (1.0,)) in gl.calls and ('glColor4f', (1.0, 1.0, 1.0, 0.7)) in gl.calls

    def test_ndc_drawing_skips_the_projection_setup(self):
        gl = FakeGL()
        assert CameraReticleGlOverlay().draw(200, 100, gl=gl, use_ndc=True) is True
        assert 'glOrtho' not in gl.names() and 'glPushMatrix' not in gl.names()

    def test_disabled_or_empty_viewports_do_nothing(self):
        gl = FakeGL()
        overlay = CameraReticleGlOverlay(enabled=False)
        assert overlay.draw(200, 100, gl=gl) is False
        overlay.enabled = True
        assert overlay.draw(0, 100, gl=gl) is False and gl.calls == []

    def test_no_gl_available(self, monkeypatch):
        overlay = CameraReticleGlOverlay()
        monkeypatch.setattr(overlay, '_resolve_gl', lambda: None)
        assert overlay.draw(200, 100) is False

    def test_gl_without_immediate_mode_cannot_draw(self):
        class Core:
            GL_DEPTH_TEST = GL_BLEND = GL_SRC_ALPHA = GL_ONE_MINUS_SRC_ALPHA = 1

            def glEnable(self, flag):
                pass

        assert CameraReticleGlOverlay().draw(200, 100, gl=Core()) is False

    def test_gl_errors_are_swallowed(self):
        class Broken(FakeGL):
            def __getattr__(self, name):
                if name == 'glBegin':
                    return lambda *a: (_ for _ in ()).throw(RuntimeError('no context'))
                return super().__getattr__(name)

        assert CameraReticleGlOverlay().draw(200, 100, gl=Broken()) is False

    def test_state_setup_tolerates_failing_gl_calls(self):
        class Failing:
            GL_DEPTH_TEST = GL_BLEND = GL_SRC_ALPHA = GL_ONE_MINUS_SRC_ALPHA = 1
            GL_PROJECTION = GL_MODELVIEW = 2

            def __getattr__(self, name):
                if name.startswith('gl'):
                    def boom(*args):
                        raise RuntimeError('gl error')
                    return boom
                raise AttributeError(name)

        overlay = CameraReticleGlOverlay()
        overlay._apply_gl_state(Failing())
        assert overlay._push_ortho(Failing(), 10, 10) is False
        overlay._pop_ortho(Failing(), True)

    def test_ortho_needs_the_legacy_matrix_functions(self):
        overlay = CameraReticleGlOverlay()
        assert overlay._push_ortho(object(), 10, 10) is False
        overlay._pop_ortho(object(), True)          # missing functions: nothing to pop
        overlay._pop_ortho(FakeGL(), False)         # nothing was pushed

    def test_draw_from_stage_view_reads_width_and_height(self):
        gl = FakeGL()

        class View:
            def width(self):
                return 200

            height = 100

        assert CameraReticleGlOverlay().draw_from_stage_view(View(), gl=gl) is True


class TestResolveGl:
    def test_prefers_pyopengl(self, monkeypatch):
        package = types.ModuleType('OpenGL')
        gl_module = types.ModuleType('OpenGL.GL')
        package.GL = gl_module
        monkeypatch.setitem(sys.modules, 'OpenGL', package)
        monkeypatch.setitem(sys.modules, 'OpenGL.GL', gl_module)
        assert CameraReticleGlOverlay()._resolve_gl() is gl_module

    def test_falls_back_to_the_current_qt_context(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'OpenGL', None)
        funcs = types.SimpleNamespace(initialized=False)
        funcs.initializeOpenGLFunctions = lambda: setattr(funcs, 'initialized', True)
        context = types.SimpleNamespace(functions=lambda: funcs)
        monkeypatch.setattr(_reticle.QtGui.QOpenGLContext, 'currentContext', staticmethod(lambda: context))
        assert CameraReticleGlOverlay()._resolve_gl() is funcs and funcs.initialized

    def test_no_context_means_no_gl(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'OpenGL', None)
        monkeypatch.setattr(_reticle.QtGui.QOpenGLContext, 'currentContext', staticmethod(lambda: None))
        assert CameraReticleGlOverlay()._resolve_gl() is None

    def test_context_failures_mean_no_gl(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'OpenGL', None)

        def boom():
            raise RuntimeError('no gl')

        monkeypatch.setattr(_reticle.QtGui.QOpenGLContext, 'currentContext', staticmethod(boom))
        assert CameraReticleGlOverlay()._resolve_gl() is None

    def test_without_pyside_there_is_no_fallback(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'OpenGL', None)
        monkeypatch.setattr(_reticle, 'PYSIDE6_AVAILABLE', False)
        assert CameraReticleGlOverlay()._resolve_gl() is None

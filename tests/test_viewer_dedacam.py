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
"""Tests for hooking dedacam into the viewer's stage view (with a fake hook; no GPU)."""
import pytest

from deda.core.viewer import _dedacam


class FakeHook:
    def __init__(self):
        self.calls = []

    def set_view(self, stage_view, mode):
        self.calls.append(('view', mode))

    def set_quality(self, tier):
        self.calls.append(('quality', tier))


@pytest.fixture
def build_dir(tmp_path):
    (tmp_path / 'usdview' / 'dedacam_usdview').mkdir(parents=True)
    (tmp_path / 'python').mkdir()
    return tmp_path


def test_find_build_dir(build_dir, tmp_path_factory, monkeypatch):
    assert _dedacam.find_build_dir(build_dir) == build_dir
    assert _dedacam.find_build_dir(tmp_path_factory.mktemp('empty')) is None
    monkeypatch.delenv(_dedacam.ENV_BUILD_DIR, raising=False)
    assert _dedacam.find_build_dir() is None
    monkeypatch.setenv(_dedacam.ENV_BUILD_DIR, str(build_dir))
    assert _dedacam.find_build_dir() == build_dir
    assert _dedacam.DedacamController.is_available()


def test_load_hook_explains_a_missing_build(monkeypatch):
    monkeypatch.delenv(_dedacam.ENV_BUILD_DIR, raising=False)
    with pytest.raises(_dedacam.DedacamUnavailable, match=_dedacam.ENV_BUILD_DIR):
        _dedacam.load_hook()


def test_load_hook_reports_a_build_that_does_not_import(build_dir):
    with pytest.raises(_dedacam.DedacamUnavailable, match='same USD'):
        _dedacam.load_hook(build_dir)   # the folders are empty, so the import fails


def test_controller_hooks_and_unhooks():
    hook = FakeHook()
    controller = _dedacam.DedacamController(object(), loader=lambda: hook)
    assert controller.mode == 'off'
    controller.set_mode('off')
    assert hook.calls == []                      # nothing was loaded just to turn it off
    controller.set_mode('dof')
    assert controller.mode == 'dof'
    assert hook.calls == [('quality', 'cinematic'), ('view', 'dof')]
    controller.set_mode('off')
    assert controller.mode == 'off' and hook.calls[-1] == ('view', None)


def test_controller_loads_the_hook_once():
    loads = []

    def loader():
        loads.append(1)
        return FakeHook()

    controller = _dedacam.DedacamController(object(), loader=loader)
    controller.set_mode('zones')
    controller.set_mode('depth')
    assert len(loads) == 1


def test_quality_applies_to_the_hook():
    hook = FakeHook()
    controller = _dedacam.DedacamController(object(), loader=lambda: hook)
    controller.set_quality('low')               # before loading: remembered
    controller.set_mode('dof')
    assert ('quality', 'low') in hook.calls
    controller.set_quality('high')
    assert hook.calls[-1] == ('quality', 'high') and controller.quality == 'high'


def test_controller_validates_input():
    controller = _dedacam.DedacamController(object(), loader=FakeHook)
    with pytest.raises(ValueError):
        controller.set_mode('bokeh')
    with pytest.raises(ValueError):
        controller.set_quality('ultra')


def test_unavailable_dedacam_leaves_the_mode_off():
    def loader():
        raise _dedacam.DedacamUnavailable('nope')

    controller = _dedacam.DedacamController(object(), loader=loader)
    with pytest.raises(_dedacam.DedacamUnavailable):
        controller.set_mode('dof')
    assert controller.mode == 'off'


def test_last_error_comes_from_the_hooked_view():
    view = type('View', (), {})()
    controller = _dedacam.DedacamController(view, loader=FakeHook)
    assert controller.last_error is None
    view._dedacam = {'error': 'frame constants: boom'}
    assert controller.last_error == 'frame constants: boom'

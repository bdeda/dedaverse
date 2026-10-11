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
"""Tests for the environment the Maya launcher builds (no Maya needed)."""
import os

import pytest

import deda.plugins.maya as maya_plugin


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """Fake Autodesk MayaUSD, dedacam module, deda deps and a custom maya-usd install."""
    autodesk_usd = tmp_path / 'MayaUSD' / 'Maya2027' / '0.37.0' / 'mayausd' / 'USD'
    (autodesk_usd / 'lib' / 'python').mkdir(parents=True)
    dedacam = tmp_path / 'dedacam_build'
    (dedacam / 'maya').mkdir(parents=True)
    (dedacam / 'maya' / 'dedacam.mod').write_text('')
    deps = tmp_path / 'deps'
    deps.mkdir()
    custom = tmp_path / 'maya_usd_install'
    custom.mkdir()
    (custom / 'mayaUSD.mod').write_text('')
    monkeypatch.setattr(maya_plugin, '_USD_ROOT', tmp_path / 'MayaUSD' / 'Maya2027')
    monkeypatch.setattr(maya_plugin, '_DEDACAM_BUILD_DIR', dedacam)
    monkeypatch.setattr(maya_plugin, '_DEPS_DIR', deps)
    monkeypatch.delenv(maya_plugin.ENV_MAYAUSD_DIR, raising=False)
    return {'autodesk_usd': autodesk_usd, 'dedacam': dedacam / 'maya', 'custom': custom}


def build_env(**extra):
    return maya_plugin.Maya('Maya 2027').setup_env({'PATH': 'C:\\Windows', **extra})


def entries(env, name):
    return [e for e in env.get(name, '').split(os.pathsep) if e]


def test_default_uses_the_maya_usd_that_maya_ships(layout):
    env = build_env()
    assert entries(env, 'MAYA_MODULE_PATH') == [str(layout['dedacam'])]
    assert str(layout['autodesk_usd'] / 'lib' / 'python') in entries(env, 'PYTHONPATH')
    assert str(layout['autodesk_usd'] / 'lib') in entries(env, 'PATH')


def test_custom_maya_usd_goes_first_and_brings_its_own_usd(layout, monkeypatch):
    monkeypatch.setenv(maya_plugin.ENV_MAYAUSD_DIR, str(layout['custom']))
    env = build_env()
    assert entries(env, 'MAYA_MODULE_PATH') == [str(layout['custom']), str(layout['dedacam'])]
    # Autodesk's USD (25.x) must not be added next to the custom one.
    assert str(layout['autodesk_usd'] / 'lib' / 'python') not in entries(env, 'PYTHONPATH')
    assert str(layout['autodesk_usd'] / 'lib') not in entries(env, 'PATH')


def test_an_invalid_custom_dir_is_ignored(layout, monkeypatch, caplog):
    monkeypatch.setenv(maya_plugin.ENV_MAYAUSD_DIR, str(layout['custom'] / 'nope'))
    with caplog.at_level('WARNING'):
        env = build_env()
    assert entries(env, 'MAYA_MODULE_PATH') == [str(layout['dedacam'])]
    assert str(layout['autodesk_usd'] / 'lib' / 'python') in entries(env, 'PYTHONPATH')
    assert 'mayaUSD.mod' in caplog.text


def test_existing_module_path_is_kept_after_ours(layout, monkeypatch):
    monkeypatch.setenv(maya_plugin.ENV_MAYAUSD_DIR, str(layout['custom']))
    env = build_env(MAYA_MODULE_PATH='D:/studio/modules')
    assert entries(env, 'MAYA_MODULE_PATH')[-1] == 'D:/studio/modules'
    assert entries(env, 'MAYA_MODULE_PATH')[0] == str(layout['custom'])


def test_other_usd_builds_are_removed_from_the_environment(layout, tmp_path):
    foreign = tmp_path / 'other_usd' / 'lib'
    (foreign / 'pxr').mkdir(parents=True)
    env = build_env(PYTHONPATH=str(foreign), USD_ROOT='F:/other', PXR_PLUGINPATH_NAME='x')
    assert str(foreign) not in entries(env, 'PYTHONPATH')
    assert 'USD_ROOT' not in env and 'PXR_PLUGINPATH_NAME' not in env


def test_deda_and_the_startup_hook_are_importable_in_maya(layout):
    pythonpath = entries(build_env(), 'PYTHONPATH')
    assert any(e.endswith('startup') for e in pythonpath)
    assert any((os.path.isdir(os.path.join(e, 'deda'))) for e in pythonpath)

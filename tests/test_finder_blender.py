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
"""Tests for deda.core.finder._blender."""
from pathlib import Path
from unittest.mock import patch

import deda.core.finder as finder
from deda.core.finder import _blender


def make_exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'')
    return path


class TestIterBlenderInstalls:
    def test_windows_layout(self, tmp_path):
        exe = make_exe(tmp_path / 'Blender 5.2' / 'blender.exe')
        make_exe(tmp_path / 'Blender 4.5' / 'readme.txt')       # no executable: skipped
        make_exe(tmp_path / 'Other App' / 'blender.exe')        # not a Blender folder: skipped
        (tmp_path / 'blender-file.txt').write_text('')          # not a directory: skipped
        found = list(_blender.iter_blender_installs('Windows', [tmp_path, tmp_path / 'missing']))
        assert found == [('5.2', exe)]

    def test_macos_layout(self, tmp_path):
        exe = make_exe(tmp_path / 'Blender.app' / 'Contents' / 'MacOS' / 'Blender')
        assert list(_blender.iter_blender_installs('Darwin', [tmp_path])) == [('', exe)]

    def test_linux_layout(self, tmp_path):
        exe = make_exe(tmp_path / 'blender-4.5.1-linux-x64' / 'blender')
        assert list(_blender.iter_blender_installs('Linux', [tmp_path])) == [('4.5.1', exe)]

    def test_default_roots_per_platform(self, tmp_path):
        with patch.object(_blender, '_windows_roots', return_value=[tmp_path]):
            assert list(_blender.iter_blender_installs('Windows')) == []
        with patch.object(_blender.Path, 'home', return_value=tmp_path):
            # /Applications, /opt and /usr/local are real directories on some machines: only check the shape.
            for system in ('Darwin', 'Linux'):
                assert all(isinstance(exe, Path) for _, exe in _blender.iter_blender_installs(system))

    def test_windows_roots_use_program_files(self):
        with patch.dict(_blender.os.environ, {'ProgramFiles': r'D:\Apps'}, clear=True):
            roots = _blender._windows_roots()
        assert roots[0] == Path(r'D:\Apps') / 'Blender Foundation'
        assert roots[-1].name == 'common'


class TestFindBlender:
    def test_env_override_wins(self, tmp_path):
        exe = make_exe(tmp_path / 'my-blender.exe')
        assert finder.find_blender({finder.BLENDER_ENV_VAR: str(exe)}) == exe

    def test_missing_override_falls_through_to_newest_install(self, tmp_path):
        installs = [('4.5', Path('old')), ('5.2', Path('new')), ('', Path('unknown'))]
        with patch.object(_blender, 'iter_blender_installs', return_value=installs):
            assert finder.find_blender({finder.BLENDER_ENV_VAR: str(tmp_path / 'nope')}) == Path('new')

    def test_path_fallback(self):
        with patch.object(_blender, 'iter_blender_installs', return_value=[]), \
                patch.object(_blender.shutil, 'which', return_value='/usr/bin/blender'):
            assert finder.find_blender({}) == Path('/usr/bin/blender')

    def test_not_found(self):
        with patch.object(_blender, 'iter_blender_installs', return_value=[]), \
                patch.object(_blender.shutil, 'which', return_value=None):
            assert finder.find_blender({}) is None

    def test_defaults_to_os_environ(self):
        with patch.dict(_blender.os.environ, {finder.BLENDER_ENV_VAR: ''}), \
                patch.object(_blender, 'iter_blender_installs', return_value=[('5.2', Path('b'))]):
            assert finder.find_blender() == Path('b')

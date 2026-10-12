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
"""Tests for finding a TRELLIS.2 install and running its server (no WSL or GPU needed)."""
import subprocess
from pathlib import Path, PureWindowsPath

import pytest

from deda.plugins.trellis import _trellis2


@pytest.fixture
def install(tmp_path):
    (tmp_path / 'trellis2').mkdir()
    (tmp_path / 'app.py').write_text('')
    return tmp_path


def test_find_install_accepts_a_valid_checkout(install):
    assert _trellis2.find_install(install) == install


def test_find_install_rejects_incomplete_folders(tmp_path):
    assert _trellis2.find_install(tmp_path) is None
    (tmp_path / 'app.py').write_text('')
    assert _trellis2.find_install(tmp_path) is None  # no trellis2 package next to it


def test_find_install_uses_env_var(install, monkeypatch):
    monkeypatch.setenv(_trellis2.ENV_DIR, str(install))
    assert _trellis2.find_install() == install


@pytest.mark.parametrize('windows_path, expected', [
    (r'F:\git\bdeda\TRELLIS.2', '/mnt/f/git/bdeda/TRELLIS.2'),
    (r'c:\Users\Ben', '/mnt/c/Users/Ben'),
])
def test_to_wsl_path(windows_path, expected, monkeypatch):
    monkeypatch.setattr(_trellis2, 'Path', PureWindowsPath)
    assert _trellis2.to_wsl_path(windows_path) == expected


def test_windows_launch_goes_through_wsl():
    command = _trellis2.build_launch_command(r'F:\TRELLIS.2', port=7861, system='Windows', env={})
    assert command[:3] == ['wsl', '--', 'bash']
    assert command[-1] == "cd /mnt/f/TRELLIS.2 && GRADIO_SERVER_PORT=7861 exec python app.py"


def test_linux_launch_runs_bash_directly():
    command = _trellis2.build_launch_command('/opt/trellis', system='Linux', env={})
    assert command[:2] == ['bash', '-lc']
    assert command[-1].startswith('cd /opt/trellis && ')


def test_launch_honours_overrides():
    env = {
        _trellis2.ENV_WSL_DISTRO: 'Ubuntu',
        _trellis2.ENV_ACTIVATE: 'conda activate trellis2',
        _trellis2.ENV_COMMAND: 'python app.py --share',
    }
    command = _trellis2.build_launch_command(r'F:\T', system='Windows', env=env)
    assert command[:4] == ['wsl', '-d', 'Ubuntu', '--']
    assert command[-1] == 'cd /mnt/f/T && conda activate trellis2 && python app.py --share'


def test_launch_quotes_awkward_paths():
    command = _trellis2.build_launch_command('/opt/my trellis', system='Linux', env={})
    assert "cd '/opt/my trellis'" in command[-1]


def completed(returncode=0, stdout='', stderr=''):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def test_probe_reports_a_missing_environment(install, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: completed(1, stderr='bash: line 1: python: command not found\n'))
    ok, message = _trellis2.probe(install)
    assert not ok
    assert 'python: command not found' in message
    assert _trellis2.ENV_ACTIVATE in message


def test_probe_warns_about_small_gpus(install, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: completed(0, stdout='15\n'))
    ok, message = _trellis2.probe(install)
    assert ok
    assert '15 GB' in message and '512' in message


def test_probe_accepts_a_big_gpu(install, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: completed(0, stdout='80\n'))
    assert _trellis2.probe(install) == (True, 'GPU has 80 GB.')


def test_probe_handles_a_missing_shell_and_timeouts(install, monkeypatch):
    def no_wsl(*a, **k):
        raise FileNotFoundError('wsl')

    def slow(*a, **k):
        raise subprocess.TimeoutExpired('wsl', 1)

    monkeypatch.setattr(subprocess, 'run', no_wsl)
    assert not _trellis2.probe(install)[0]
    monkeypatch.setattr(subprocess, 'run', slow)
    assert 'did not finish' in _trellis2.probe(install, timeout=1)[1]


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


def test_server_lifecycle(install, tmp_path, monkeypatch):
    started = []
    process = FakeProcess()
    monkeypatch.setattr(subprocess, 'Popen', lambda command, **kw: started.append(command) or process)
    server = _trellis2.Trellis2Server(install, port=7899, log_path=tmp_path / 'logs' / 'server.log')

    assert not server.running
    server.start()
    server.start()  # already running: must not start a second one
    assert len(started) == 1 and server.running
    assert server.url == 'http://127.0.0.1:7899'
    assert (tmp_path / 'logs').is_dir()

    server.stop()
    assert process.terminated and not server.running


def test_wait_until_ready_gives_up_when_the_server_exits(install, tmp_path, monkeypatch):
    process = FakeProcess()
    process.returncode = 1  # exited straight away
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: process)
    server = _trellis2.Trellis2Server(install, log_path=tmp_path / 's.log')
    server.start()
    monkeypatch.setattr(server, 'is_ready', lambda: False)
    assert server.wait_until_ready(timeout=5, poll=0.01) is False


def test_tail_log(install, tmp_path):
    log_file = tmp_path / 's.log'
    log_file.write_text('\n'.join(f'line {i}' for i in range(50)))
    server = _trellis2.Trellis2Server(install, log_path=log_file)
    assert server.tail_log(3) == 'line 47\nline 48\nline 49'
    assert _trellis2.Trellis2Server(install, log_path=tmp_path / 'none.log').tail_log() == ''

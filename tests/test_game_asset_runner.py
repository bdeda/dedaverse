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
"""Tests for the host side of the game asset optimizer (finding and running Blender)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from deda.plugins.game_asset import _runner
from deda.plugins.game_asset._options import OptimizeError, OptimizeOptions


@pytest.fixture
def source(tmp_path) -> Path:
    path = tmp_path / 'axe.usdz'
    path.write_bytes(b'usdz')
    return path


def fake_blender(payload: dict | None, code: int = 0, lines: tuple[str, ...] = ('Blender 5.2',)):
    """Stand-in for _run_blender: reads the job file from the command and writes ``payload`` as the result."""
    def run(command, on_output):
        job = json.loads(Path(command[-1]).read_text(encoding='utf-8'))
        run.job = job
        for line in lines:
            if on_output:
                on_output(line)
        if payload is not None:
            Path(job['result']).write_text(json.dumps(payload), encoding='utf-8')
        return code, list(lines)
    return run


class TestOptimize:
    def test_success(self, source, tmp_path):
        payload = {'source': str(source), 'output_dir': str(tmp_path / 'out'), 'meshes': ['a.fbx'],
                   'stats': {'game': {'tris': 100}}}
        seen = []
        runner = fake_blender(payload)
        with patch.object(_runner, '_run_blender', side_effect=runner):
            result = _runner.optimize(source, tmp_path / 'out', OptimizeOptions(target_tris=500),
                                      blender=Path('blender'), on_output=seen.append)
        assert result.meshes == ['a.fbx'] and result.stats['game']['tris'] == 100
        assert seen == ['Blender 5.2']
        assert runner.job['options']['target_tris'] == 500
        assert Path(runner.job['output_dir']) == (tmp_path / 'out').resolve()

    def test_defaults_output_dir_and_blender(self, source):
        runner = fake_blender({'source': str(source), 'output_dir': 'x'})
        with patch.object(_runner, 'find_blender', return_value=Path('blender')), \
                patch.object(_runner, '_run_blender', side_effect=runner):
            _runner.optimize(source)
        assert Path(runner.job['output_dir']) == _runner.default_output_dir(source).resolve()
        assert runner.job['options'] == OptimizeOptions().to_dict()

    def test_job_error_is_raised(self, source):
        with patch.object(_runner, '_run_blender', side_effect=fake_blender({'error': 'OptimizeError: no mesh',
                                                                              'traceback': 'tb'})):
            with pytest.raises(OptimizeError, match='no mesh'):
                _runner.optimize(source, blender=Path('blender'))

    def test_missing_result_reports_exit_code_and_output(self, source):
        with patch.object(_runner, '_run_blender', side_effect=fake_blender(None, 3, ('boom',))):
            with pytest.raises(OptimizeError, match=r'code 3[\s\S]*boom'):
                _runner.optimize(source, blender=Path('blender'))

    def test_missing_source(self, tmp_path):
        with pytest.raises(OptimizeError, match='not found'):
            _runner.optimize(tmp_path / 'nope.usdz')

    def test_unsupported_source(self, tmp_path):
        bad = tmp_path / 'a.stl'
        bad.write_text('solid')
        with pytest.raises(OptimizeError, match='unsupported'):
            _runner.optimize(bad)

    def test_invalid_options(self, source):
        with pytest.raises(OptimizeError, match='texture_size'):
            _runner.optimize(source, options=OptimizeOptions(texture_size=3))

    def test_blender_not_found(self, source):
        with patch.object(_runner, 'find_blender', return_value=None):
            with pytest.raises(OptimizeError, match='DEDAVERSE_BLENDER'):
                _runner.optimize(source)


class TestCommand:
    def test_blender_command(self, tmp_path):
        command = _runner.blender_command(Path('blender'), tmp_path / 'job.json')
        assert command[:3] == ['blender', '--background', '--factory-startup']
        assert command[command.index('--python') + 1] == str(_runner.JOB_SCRIPT)
        assert command[-2:] == ['--', str(tmp_path / 'job.json')]
        assert _runner.JOB_SCRIPT.is_file()

    def test_default_output_dir(self):
        assert _runner.default_output_dir(Path('/x/axe.usdz')) == Path('/x/axe_game')

    def test_run_blender_streams_output_and_keeps_tail(self):
        seen = []
        code, tail = _runner._run_blender(
            [sys.executable, '-c', 'import sys\nfor i in range(30): print(i)\nsys.exit(4)'], seen.append)
        assert code == 4
        assert seen == [str(i) for i in range(30)]
        assert tail == [str(i) for i in range(5, 30)]

    def test_run_blender_without_callback(self):
        assert _runner._run_blender([sys.executable, '-c', 'print(1)'], None) == (0, ['1'])

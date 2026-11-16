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
"""Tests for the game asset optimizer command line, tool window and plugin (Blender is never started)."""
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6 import QtWidgets

import deda.plugins.game_asset as plugin
from deda.plugins.game_asset import __main__ as cli
from deda.plugins.game_asset import _tool_window
from deda.plugins.game_asset._options import OptimizeError, OptimizeOptions, OptimizeResult
from deda.plugins.game_asset._tool_window import GameAssetWindow, _OptimizeWorker


def fake_result(source: Path, output: Path) -> OptimizeResult:
    return OptimizeResult(source=str(source), output_dir=str(output), meshes=[str(output / 'a.fbx')],
                          textures={'basecolor': str(output / 'T_a_BaseColor.png')},
                          stats={'source': {'tris': 700000}, 'game': {'tris': 12000}}, warnings=['careful'])


def fake_optimize(source, output_dir=None, options=None, blender=None, on_output=None):
    if Path(source).name.startswith('bad'):
        raise OptimizeError('no mesh in it')
    if on_output:
        on_output('Blender 5.2')
    return fake_result(Path(source), Path(output_dir))


class TestCli:
    def test_single_input(self, tmp_path, capsys):
        with patch.object(cli, 'optimize', side_effect=fake_optimize) as run:
            assert cli.main([str(tmp_path / 'a.usdz'), '--tris', '8000', '--texture-size', '1024',
                             '--normals', 'directx', '--uv', 'seams', '--cpu', '--no-glb', '--keep-blend']) == 0
        source, output, options = run.call_args[0]
        assert output == tmp_path / 'a_game'
        assert options == OptimizeOptions(target_tris=8000, texture_size=1024, normal_convention='directx',
                                          uv_method='seams', use_gpu=False, export_glb=False, keep_blend=True)
        assert run.call_args[1]['on_output'] is None
        out = capsys.readouterr().out
        assert '700000 -> 12000 tris' in out and 'wrote' in out and 'warning: careful' in out

    def test_output_directories(self, tmp_path):
        with patch.object(cli, 'optimize', side_effect=fake_optimize) as run:
            assert cli.main([str(tmp_path / 'a.usdz'), '-o', str(tmp_path / 'out')]) == 0
            assert run.call_args[0][1] == tmp_path / 'out'
            assert cli.main([str(tmp_path / 'a.usdz'), str(tmp_path / 'b.glb'), '-o', str(tmp_path / 'out')]) == 0
            assert [c[0][1] for c in run.call_args_list[1:]] == [tmp_path / 'out' / 'a', tmp_path / 'out' / 'b']

    def test_failures_set_exit_code_but_continue(self, tmp_path, capsys):
        with patch.object(cli, 'optimize', side_effect=fake_optimize) as run:
            assert cli.main([str(tmp_path / 'bad.usdz'), str(tmp_path / 'good.usdz')]) == 1
        assert run.call_count == 2
        assert 'FAILED' in capsys.readouterr().err

    def test_verbose_prints_blender_output(self, tmp_path, capsys):
        with patch.object(cli, 'optimize', side_effect=fake_optimize):
            assert cli.main([str(tmp_path / 'a.usdz'), '-v', '--blender', 'b.exe']) == 0
        assert 'Blender 5.2' in capsys.readouterr().out

    def test_invalid_options(self, tmp_path, capsys):
        assert cli.main([str(tmp_path / 'a.usdz'), '--tris', '3']) == 2
        assert 'target_tris' in capsys.readouterr().err

    def test_no_inputs_opens_window(self):
        with patch.object(cli, '_run_window', return_value=0) as run_window:
            assert cli.main([]) == 0
        run_window.assert_called_once_with()


def wait_until_idle(qapp, window, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while window._thread is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert window._thread is None, 'job did not finish'


class TestWindow:
    def test_output_follows_source(self, qapp, tmp_path):
        window = GameAssetWindow()
        assert not window._run_button.isEnabled()
        window._source_edit.setText(str(tmp_path / 'axe.usdz'))
        assert window._output_edit.text() == str(tmp_path / 'axe_game')
        assert window._run_button.isEnabled()

    def test_user_output_is_kept(self, qapp, tmp_path):
        window = GameAssetWindow()
        window._output_edit.setText(str(tmp_path / 'mine'))
        window._output_edit.setModified(True)
        window._source_edit.setText(str(tmp_path / 'axe.usdz'))
        assert window._output_edit.text() == str(tmp_path / 'mine')

    def test_options_from_widgets(self, qapp):
        window = GameAssetWindow()
        assert window.options() == OptimizeOptions()
        window._tris_spin.setValue(5000)
        window._size_combo.setCurrentIndex(window._size_combo.findData(1024))
        window._normals_combo.setCurrentIndex(1)
        window._uv_combo.setCurrentIndex(window._uv_combo.findData('symmetry'))
        window._keep_blend_check.setChecked(True)
        assert window.options() == OptimizeOptions(target_tris=5000, texture_size=1024,
                                                   normal_convention='directx', uv_method='symmetry',
                                                   keep_blend=True)

    @pytest.mark.parametrize('name, expected', [('axe.usdz', 'Done: 700000 -> 12000 tris'),
                                                ('bad.usdz', 'FAILED: no mesh in it')])
    def test_run(self, qapp, tmp_path, name, expected):
        window = GameAssetWindow()
        window._source_edit.setText(str(tmp_path / name))
        with patch.object(_tool_window, 'optimize', side_effect=fake_optimize):
            window.run()
            window.run()  # a second click while running is ignored
            wait_until_idle(qapp, window)
        qapp.processEvents()
        text = window._log.toPlainText()
        assert expected in text
        assert window._run_button.isEnabled()

    def test_finished_logs_outputs_and_warnings(self, qapp, tmp_path):
        window = GameAssetWindow()
        window._on_finished(fake_result(tmp_path / 'a.usdz', tmp_path))
        text = window._log.toPlainText()
        assert 'wrote' in text and 'warning: careful' in text

    def test_close_waits_for_running_job(self, qapp, tmp_path):
        window = GameAssetWindow()
        window._source_edit.setText(str(tmp_path / 'axe.usdz'))
        with patch.object(_tool_window, 'optimize', side_effect=fake_optimize):
            window.run()
            window.close()
        qapp.processEvents()

    def test_worker_signals(self, qapp, tmp_path):
        results, failures, lines = [], [], []
        with patch.object(_tool_window, 'optimize', side_effect=fake_optimize):
            for name in ('a.usdz', 'bad.usdz'):
                worker = _OptimizeWorker(tmp_path / name, tmp_path, OptimizeOptions())
                worker.output.connect(lines.append)
                worker.finished.connect(results.append)
                worker.failed.connect(failures.append)
                worker.run()
        assert len(results) == 1 and failures == ['no mesh in it'] and lines == ['Blender 5.2']


class TestPlugin:
    def test_load_adds_menu_action(self, qapp):
        menu = QtWidgets.QMenu()
        tool = plugin.GameAssetOptimizer('GameAssetOptimizerTest', '0.0.1', 'Deda')
        with patch.object(plugin.deda.app, 'get_main_menu', return_value=menu):
            assert tool.load() is True
        assert [a.text() for a in menu.actions()] == ['Game Asset Optimizer']

    def test_initialize_window(self, qapp):
        window = plugin.GameAssetOptimizer('GameAssetOptimizerTest', '0.0.1', 'Deda').initialize_window(None)
        assert isinstance(window, GameAssetWindow)

    def test_plugin_is_registered(self):
        assert isinstance(plugin.deda.core.PluginRegistry().get('GameAssetOptimizer'), plugin.GameAssetOptimizer)

    def test_public_api(self):
        assert plugin.optimize is cli.optimize

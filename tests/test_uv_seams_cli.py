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
"""Tests for deda.core.ai.uv_seams.__main__: argument handling, error codes and prediction output.

PyTorch is replaced by a fake trainer, so these run without it.
"""
import types
from pathlib import Path

import numpy as np
import pytest

from deda.core.ai.uv_seams import __main__ as cli


class FakeTrainer:
    """Records what the CLI asks of the trainer."""

    def __init__(self):
        self.configs, self.predict_calls, self.error = [], [], None

    def train(self, config):
        if self.error:
            raise self.error
        self.configs.append(config)
        return config.out / 'best.pt'

    def predict(self, weights, mesh, threshold, min_faces):
        if self.error:
            raise self.error
        self.predict_calls.append((weights, mesh, threshold, min_faces))
        return types.SimpleNamespace(face_island=np.array([0, 0, 1]), seam_prob=np.array([0.1, 0.9]),
                                     pairs=np.array([[0, 1], [1, 2]]), threshold=0.4)


@pytest.fixture
def trainer(monkeypatch):
    fake = FakeTrainer()
    monkeypatch.setattr(cli, 'importlib', types.SimpleNamespace(import_module=lambda name, package=None: fake))
    return fake


class TestTrainCommand:
    def test_arguments_become_the_config(self, trainer, tmp_path, capsys):
        code = cli.main(['train', '--synthetic', '5', '--out', str(tmp_path), '--epochs', '2', '--lr', '0.001',
                         '--hidden', '32', '--layers', '3', '--rot-aug', 'full', '--amp', '--seed', '9',
                         '--group-regex', r'^(.*?)_lod\d+$', '--pos-weight', '4', '--num-workers', '0'])
        assert code == 0
        config = trainer.configs[0]
        assert (config.synthetic, config.epochs, config.lr, config.hidden, config.layers) == (5, 2, 0.001, 32, 3)
        assert (config.rot_aug, config.amp, config.seed, config.pos_weight) == ('full', True, 9, 4.0)
        assert config.group_regex == r'^(.*?)_lod\d+$' and config.out == tmp_path
        assert 'best checkpoint' in capsys.readouterr().out

    def test_defaults_match_the_config_defaults(self, trainer, tmp_path):
        cli.main(['train', '--data-dir', str(tmp_path), '--out', str(tmp_path / 'run')])
        config = trainer.configs[0]
        defaults = cli.TrainConfig(out=tmp_path / 'run', data_dir=tmp_path)
        assert config == defaults

    def test_resume_path_is_passed_on(self, trainer, tmp_path):
        cli.main(['train', '--synthetic', '3', '--out', str(tmp_path), '--resume', str(tmp_path / 'last.pt')])
        assert trainer.configs[0].resume == tmp_path / 'last.pt'

    def test_missing_data_is_a_usage_error(self, trainer, tmp_path, capsys):
        assert cli.main(['train', '--out', str(tmp_path)]) == 2
        assert 'data_dir is required' in capsys.readouterr().err
        assert trainer.configs == []

    def test_invalid_regex_is_a_usage_error(self, trainer, tmp_path, capsys):
        assert cli.main(['train', '--synthetic', '3', '--out', str(tmp_path), '--group-regex', '(']) == 2
        assert 'error:' in capsys.readouterr().err
        assert trainer.configs == []

    def test_trainer_failure_returns_one(self, trainer, tmp_path, capsys):
        trainer.error = ValueError('checkpoint mismatch')
        assert cli.main(['train', '--synthetic', '3', '--out', str(tmp_path)]) == 1
        assert 'checkpoint mismatch' in capsys.readouterr().err


class TestPredictCommand:
    def test_writes_next_to_the_mesh_by_default(self, trainer, tmp_path, capsys):
        mesh = tmp_path / 'axe.npz'
        assert cli.main(['predict', '--weights', 'best.pt', '--mesh', str(mesh)]) == 0
        assert trainer.predict_calls == [(Path('best.pt'), mesh, None, 8)]
        with np.load(tmp_path / 'axe_pred.npz') as result:
            assert result['face_island_pred'].tolist() == [0, 0, 1]
            assert result['seam_prob'].tolist() == [0.1, 0.9]
            assert result['dual_pairs'].tolist() == [[0, 1], [1, 2]]
            assert float(result['threshold']) == 0.4
        assert '3 faces -> 2 islands' in capsys.readouterr().out

    def test_output_threshold_and_min_faces_are_honoured(self, trainer, tmp_path):
        out = tmp_path / 'custom.npz'
        cli.main(['predict', '--weights', 'w.pt', '--mesh', str(tmp_path / 'm.npz'), '--output', str(out),
                  '--threshold', '0.7', '--min-faces', '3'])
        assert out.exists()
        assert trainer.predict_calls[0][2:] == (0.7, 3)

    def test_failure_returns_one(self, trainer, tmp_path, capsys):
        trainer.error = OSError('cannot read weights')
        assert cli.main(['predict', '--weights', 'w.pt', '--mesh', str(tmp_path / 'm.npz')]) == 1
        assert 'cannot read weights' in capsys.readouterr().err


class TestLoadTrainer:
    def test_missing_torch_is_reported_not_raised(self, monkeypatch, tmp_path, capsys):
        def no_torch(name, package=None):
            raise ModuleNotFoundError("No module named 'torch'", name='torch')

        monkeypatch.setattr(cli, 'importlib', types.SimpleNamespace(import_module=no_torch))
        assert cli.main(['train', '--synthetic', '3', '--out', str(tmp_path)]) == 2
        assert 'PyTorch is required' in capsys.readouterr().err

    def test_other_missing_modules_are_not_swallowed(self, monkeypatch, tmp_path):
        def broken(name, package=None):
            raise ModuleNotFoundError("No module named 'something_else'", name='something_else')

        monkeypatch.setattr(cli, 'importlib', types.SimpleNamespace(import_module=broken))
        with pytest.raises(ModuleNotFoundError):
            cli.main(['train', '--synthetic', '3', '--out', str(tmp_path)])


class TestParser:
    def test_a_command_is_required(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.main([])
        assert exc.value.code == 2
        assert 'command' in capsys.readouterr().err

    def test_rotation_mode_is_validated_by_argparse(self, tmp_path):
        with pytest.raises(SystemExit):
            cli.main(['train', '--synthetic', '3', '--out', str(tmp_path), '--rot-aug', 'tumble'])

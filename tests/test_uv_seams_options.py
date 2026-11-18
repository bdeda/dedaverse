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
"""Tests for deda.core.ai.uv_seams._options: the training configuration and learning-rate schedule."""
from pathlib import Path

import pytest

from deda.core.ai.uv_seams import _options as options


class TestTrainConfig:
    def test_defaults_are_valid_with_synthetic_data(self):
        options.TrainConfig(out=Path('runs/x'), synthetic=10).validate()

    def test_data_dir_is_required_without_synthetic(self):
        with pytest.raises(ValueError, match='data_dir is required'):
            options.TrainConfig(out=Path('runs/x')).validate()
        options.TrainConfig(out=Path('runs/x'), data_dir=Path('data')).validate()

    @pytest.mark.parametrize('field, value', [
        ('synthetic', -1), ('epochs', 0), ('batch_size', 0), ('hidden', 0), ('layers', 0), ('max_faces', 0),
        ('num_workers', -1), ('val_frac', 0.0), ('val_frac', 1.0), ('rot_aug', 'spin'), ('lr', 0.0),
    ])
    def test_bad_values_raise(self, field, value):
        config = options.TrainConfig(out=Path('runs/x'), synthetic=10)
        setattr(config, field, value)
        with pytest.raises(ValueError, match=field):
            config.validate()

    def test_to_dict_turns_paths_into_strings(self):
        out = options.TrainConfig(out=Path('runs/x'), data_dir=Path('data'), resume=Path('a.pt')).to_dict()
        assert out['out'] == str(Path('runs/x'))
        assert out['data_dir'] == 'data' and out['resume'] == 'a.pt'
        assert out['seed'] == 0 and out['group_regex'] is None

    def test_string_paths_are_converted(self):
        config = options.TrainConfig(out='runs/x', data_dir='data', resume='a.pt')
        assert config.out == Path('runs/x')
        assert config.data_dir == Path('data') and config.resume == Path('a.pt')


class TestLrScale:
    def test_warmup_rises_linearly_to_the_peak(self):
        scales = [options.lr_scale(step, warmup=4, total=100) for step in range(4)]
        assert scales == pytest.approx([0.25, 0.5, 0.75, 1.0])

    def test_decays_to_one_percent_by_the_end(self):
        assert options.lr_scale(100, warmup=10, total=100) == pytest.approx(0.01)
        assert options.lr_scale(500, warmup=10, total=100) == pytest.approx(0.01)   # past the end stays put

    def test_never_increases_after_warmup(self):
        scales = [options.lr_scale(step, warmup=10, total=200) for step in range(10, 200)]
        assert scales[0] == pytest.approx(1.0)
        assert all(a >= b for a, b in zip(scales, scales[1:]))

    def test_no_warmup_starts_at_the_peak(self):
        assert options.lr_scale(0, warmup=0, total=50) == pytest.approx(1.0)

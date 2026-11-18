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
"""Training configuration for the UV-seam model. Pure Python, so the CLI can validate it without PyTorch."""
import math
from dataclasses import dataclass, field
from pathlib import Path

from ._data import ROTATION_MODES

__all__ = ['TrainConfig', 'lr_scale']


@dataclass
class TrainConfig:
    """Everything a training run needs.

    Attributes:
        out: Output directory for checkpoints and ``metrics.jsonl``.
        data_dir: Folder of ``.npz`` assets (see :mod:`deda.core.ai.uv_seams._data`); unused with ``synthetic``.
        usd_paths: USD files and/or directories (searched recursively), from any locations. Each mesh with the UV
            set ``uv_set`` becomes one sample. Takes precedence over ``data_dir``.
        synthetic: When positive, train on this many random boxes instead of ``data_dir`` (smoke test).
        epochs: Number of passes over the training set.
        batch_size: Meshes per batch.
        lr: Peak learning rate (linear warm-up, then cosine decay).
        weight_decay: AdamW weight decay.
        hidden: Width of the network.
        layers: Number of message-passing layers.
        val_frac: Fraction of asset groups held out for validation.
        rot_aug: Rotation augmentation, one of ``none``, ``yaw`` (Y-up assets) or ``full``.
        max_faces: Skip meshes with more faces than this.
        min_faces: Smallest island kept when decoding.
        pos_weight: Loss weight on seam edges; zero or less estimates it from the data.
        num_workers: DataLoader worker processes.
        amp: Use bfloat16 autocast when the GPU supports it.
        resume: Checkpoint to continue from.
        seed: Random seed.
        group_regex: Regex over file stems that groups related assets for the train/val split.
        uv_set: Name of the USD UV primvar whose layout defines the islands.
        usd_world_space: Bake each USD mesh's local-to-world transform into its points.
    """

    out: Path
    data_dir: Path | None = None
    synthetic: int = 0
    epochs: int = 100
    batch_size: int = 4
    lr: float = 5e-4
    weight_decay: float = 1e-2
    hidden: int = 128
    layers: int = 8
    val_frac: float = 0.1
    rot_aug: str = 'yaw'
    max_faces: int = 30000
    min_faces: int = 8
    pos_weight: float = 0.0
    num_workers: int = 2
    amp: bool = False
    resume: Path | None = None
    seed: int = 0
    group_regex: str | None = None
    usd_paths: list[Path] = field(default_factory=list)
    uv_set: str = 'st'
    usd_world_space: bool = False

    def __post_init__(self) -> None:
        """Accept strings for the path settings."""
        self.out = Path(self.out)
        self.data_dir = Path(self.data_dir) if self.data_dir is not None else None
        self.resume = Path(self.resume) if self.resume is not None else None
        self.usd_paths = [Path(p) for p in self.usd_paths]

    def to_dict(self) -> dict:
        """Plain-Python copy (paths as strings) that can be stored in a checkpoint or JSON file."""
        out = {}
        for key, value in vars(self).items():
            if isinstance(value, Path):
                value = str(value)
            elif isinstance(value, list):
                value = [str(item) if isinstance(item, Path) else item for item in value]
            out[key] = value
        return out

    def validate(self) -> None:
        """Check the settings.

        Raises:
            ValueError: If a value is out of range, or none of ``data_dir``, ``usd_paths`` and ``synthetic`` is given.
        """
        if not self.synthetic and self.data_dir is None and not self.usd_paths:
            raise ValueError('data_dir is required unless usd_paths or a positive number of synthetic boxes is given')
        if not self.uv_set:
            raise ValueError('uv_set must not be empty')
        if self.synthetic < 0:
            raise ValueError(f'synthetic must be >= 0, got {self.synthetic}')
        for name in ('epochs', 'batch_size', 'hidden', 'layers', 'max_faces'):
            if getattr(self, name) < 1:
                raise ValueError(f'{name} must be >= 1, got {getattr(self, name)}')
        if self.num_workers < 0:
            raise ValueError(f'num_workers must be >= 0, got {self.num_workers}')
        if not 0.0 < self.val_frac < 1.0:
            raise ValueError(f'val_frac must be between 0 and 1, got {self.val_frac}')
        if self.rot_aug not in ROTATION_MODES:
            raise ValueError(f'rot_aug must be one of {ROTATION_MODES}, got {self.rot_aug!r}')
        if self.lr <= 0:
            raise ValueError(f'lr must be positive, got {self.lr}')


def lr_scale(step: int, warmup: int, total: int) -> float:
    """Learning-rate multiplier: linear warm-up, then cosine decay to 1% of the peak.

    Args:
        step: Zero-based optimizer step about to be taken.
        warmup: Number of warm-up steps.
        total: Total number of steps in the run.

    Returns:
        A factor in ``(0, 1]`` to multiply the peak learning rate by.
    """
    if step < warmup:
        return (step + 1) / max(warmup, 1)
    progress = min((step - warmup) / max(total - warmup, 1), 1.0)
    return 0.01 + 0.99 * 0.5 * (1.0 + math.cos(math.pi * progress))

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
"""Command line for the UV-seam model.

Run with:
    python -m deda.core.ai.uv_seams train --synthetic 200 --epochs 5 --out runs/smoke      # smoke test, no data
    python -m deda.core.ai.uv_seams train --data-dir data/npz --out runs/exp1 --epochs 100 --amp
    python -m deda.core.ai.uv_seams train --data-dir data/npz --out runs/exp1 --epochs 100 --resume runs/exp1/last.pt
    python -m deda.core.ai.uv_seams predict --weights runs/exp1/best.pt --mesh asset.npz   # writes asset_pred.npz

Argument handling needs only numpy; PyTorch is imported once a command actually runs.
"""
import argparse
import importlib
import logging
import re
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

from ._data import ROTATION_MODES, regex_group_key
from ._options import TrainConfig

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Run the ``train`` or ``predict`` command.

    Args:
        argv: Command line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code: 0 on success, 1 if the run failed, 2 on bad arguments or a missing PyTorch.
    """
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    config = None
    if args.command == 'train':
        try:
            config = _config_from_args(args)
            config.validate()
            if config.group_regex:
                regex_group_key(config.group_regex)
        except (ValueError, OSError, re.error) as err:
            print(f'error: {err}', file=sys.stderr)
            return 2
    trainer = _load_trainer()
    if trainer is None:
        return 2
    try:
        if config is not None:
            best = trainer.train(config)
            print(f'best checkpoint: {best}')
        else:
            _run_predict(args, trainer)
    except (ValueError, OSError, RuntimeError) as err:
        log.exception(err)
        print(f'error: {err}', file=sys.stderr)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    defaults = TrainConfig(out=Path('.'))
    parser = argparse.ArgumentParser(prog='python -m deda.core.ai.uv_seams',
                                     description='Train and run a model that predicts UV seams on game meshes.')
    parser.add_argument('-v', '--verbose', action='store_true', help='debug logging')
    commands = parser.add_subparsers(dest='command', required=True)

    train = commands.add_parser('train', help='train the seam network')
    train.add_argument('--data-dir', type=Path, help='folder of .npz assets (vertices, faces, face_island)')
    train.add_argument('--usd', type=Path, nargs='+', default=[], metavar='PATH',
                       help='USD files and/or directories (searched recursively), from any locations')
    train.add_argument('--usd-list', type=Path, metavar='FILE',
                       help='text file with one USD file or directory per line (blank lines and # comments ignored)')
    train.add_argument('--uv-set', default=defaults.uv_set, help='name of the USD UV primvar that defines the islands')
    train.add_argument('--usd-world-space', action='store_true',
                       help='bake each USD mesh\'s local-to-world transform into its points')
    train.add_argument('--synthetic', type=int, default=defaults.synthetic, metavar='N',
                       help='train on N random boxes instead (smoke test; no data needed)')
    train.add_argument('--out', type=Path, required=True, help='output folder for checkpoints and metrics')
    train.add_argument('--epochs', type=int, default=defaults.epochs)
    train.add_argument('--batch-size', type=int, default=defaults.batch_size)
    train.add_argument('--lr', type=float, default=defaults.lr)
    train.add_argument('--weight-decay', type=float, default=defaults.weight_decay)
    train.add_argument('--hidden', type=int, default=defaults.hidden)
    train.add_argument('--layers', type=int, default=defaults.layers)
    train.add_argument('--val-frac', type=float, default=defaults.val_frac)
    train.add_argument('--group-regex', help='regex on file stems that groups LODs/variants so they stay on '
                                             'one side of the train/val split, e.g. "^(.*?)(?:_lod\\d+)?$"')
    train.add_argument('--rot-aug', choices=ROTATION_MODES, default=defaults.rot_aug,
                       help='rotation augmentation; yaw assumes Y-up assets')
    train.add_argument('--max-faces', type=int, default=defaults.max_faces, help='skip meshes above this')
    train.add_argument('--min-faces', type=int, default=defaults.min_faces, help='smallest island kept')
    train.add_argument('--pos-weight', type=float, default=defaults.pos_weight,
                       help='loss weight on seam edges (0 or less: estimate from the data)')
    train.add_argument('--num-workers', type=int, default=defaults.num_workers)
    train.add_argument('--amp', action='store_true', help='bfloat16 autocast (needs a supporting GPU)')
    train.add_argument('--resume', type=Path, help='checkpoint to continue from (e.g. runs/exp1/last.pt)')
    train.add_argument('--seed', type=int, default=defaults.seed)

    predict = commands.add_parser('predict', help='predict islands for one .npz mesh')
    predict.add_argument('--weights', type=Path, required=True, help='checkpoint from training (best.pt)')
    predict.add_argument('--mesh', type=Path, required=True, help='.npz with vertices and faces')
    predict.add_argument('--output', type=Path, help='result file (default: <mesh>_pred.npz next to the mesh)')
    predict.add_argument('--threshold', type=float, help='seam probability cut-off (default: best from training)')
    predict.add_argument('--min-faces', type=int, default=defaults.min_faces, help='smallest island kept')
    return parser


def _config_from_args(args: argparse.Namespace) -> TrainConfig:
    usd_paths = list(args.usd)
    if args.usd_list is not None:
        usd_paths += _read_path_list(args.usd_list)
    return TrainConfig(out=args.out, data_dir=args.data_dir, synthetic=args.synthetic, epochs=args.epochs,
                       batch_size=args.batch_size, lr=args.lr, weight_decay=args.weight_decay, hidden=args.hidden,
                       layers=args.layers, val_frac=args.val_frac, rot_aug=args.rot_aug, max_faces=args.max_faces,
                       min_faces=args.min_faces, pos_weight=args.pos_weight, num_workers=args.num_workers,
                       amp=args.amp, resume=args.resume, seed=args.seed, group_regex=args.group_regex,
                       usd_paths=usd_paths, uv_set=args.uv_set, usd_world_space=args.usd_world_space)


def _read_path_list(path: Path) -> list[Path]:
    """Paths listed one per line in a text file; blank lines and ``#`` comments are ignored.

    Raises:
        OSError: If the file cannot be read.
    """
    lines = path.read_text(encoding='utf-8').splitlines()
    return [Path(line.strip()) for line in lines if line.strip() and not line.strip().startswith('#')]


def _load_trainer() -> ModuleType | None:
    """Import the PyTorch trainer, or print how to get PyTorch and return ``None``."""
    try:
        return importlib.import_module('._trainer', __package__)
    except ModuleNotFoundError as err:
        if err.name != 'torch':
            raise
        print('error: PyTorch is required to train or run the seam model '
              '(pip install torch, or install the "upscale" extra).', file=sys.stderr)
        return None


def _run_predict(args: argparse.Namespace, trainer: ModuleType) -> None:
    result = trainer.predict(args.weights, args.mesh, args.threshold, args.min_faces)
    output = args.output or args.mesh.with_name(args.mesh.stem + '_pred.npz')
    np.savez(output, face_island_pred=result.face_island, seam_prob=result.seam_prob, dual_pairs=result.pairs,
             threshold=result.threshold)
    print(f'{len(result.face_island)} faces -> {int(result.face_island.max()) + 1} islands '
          f'(threshold {result.threshold}); wrote {output}')


if __name__ == '__main__':
    sys.exit(main())

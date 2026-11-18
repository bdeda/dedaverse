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
"""Training, evaluation and inference for the seam network. Requires PyTorch.

A run writes to ``config.out``: ``best.pt`` (best validation seam F1), ``last.pt`` (latest epoch, for resuming)
and ``metrics.jsonl`` (one JSON line per epoch). Checkpoints hold only tensors and plain Python values, so they
load with ``torch.load(..., weights_only=True)``.
"""
import json
import logging
import math
import random
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch  # pylint: disable=import-error  # optional dependency; CI installs it after pylint
from torch.nn import functional  # pylint: disable=import-error
from torch.utils.data import DataLoader  # pylint: disable=import-error

from ._data import (Batch, MeshSeamDataset, NpzSource, SyntheticSource, collate_samples, estimate_pos_weight,
                    regex_group_key, split_paths)
from ._geometry import decode_islands, prepare_sample
from ._metrics import EdgeCounts, best_threshold, island_count_error
from ._model import SeamNet
from ._options import TrainConfig, lr_scale
from ._usd import split_usd_sources
from ._usd_arrays import find_usd_files

__all__ = ['THRESHOLDS', 'SeamPrediction', 'evaluate', 'predict', 'train']

log = logging.getLogger(__name__)

# Decision thresholds scored every epoch; the best one is stored in the checkpoint.
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)


@dataclass(eq=False)
class SeamPrediction:
    """The model's answer for one mesh.

    Attributes:
        face_island: ``(F,)`` island id per face, in the input face order.
        seam_prob: ``(E,)`` seam probability per dual edge.
        pairs: ``(E, 2)`` the dual edges ``seam_prob`` refers to.
        threshold: Probability at which an edge was cut.
    """

    face_island: np.ndarray
    seam_prob: np.ndarray
    pairs: np.ndarray
    threshold: float


def evaluate(model: SeamNet, loader: DataLoader, device: torch.device, pos_weight: float, min_faces: int = 8,
             amp_dtype: torch.dtype | None = None) -> dict[str, float]:
    """Score the model on a labelled loader.

    Args:
        model: The network (put in eval mode here; call ``model.train()`` afterwards to keep training).
        loader: Yields labelled :class:`~deda.core.ai.uv_seams.Batch` objects.
        device: Where the model lives.
        pos_weight: Seam weight used for the reported loss.
        min_faces: Smallest island kept when counting predicted islands.
        amp_dtype: Autocast dtype, or ``None`` for full precision.

    Returns:
        ``val_loss``, ``seam_f1``, ``seam_precision``, ``seam_recall`` and ``island_count_mae`` (all at the best
        threshold), and ``best_threshold`` itself.
    """
    model.eval()
    counts = {threshold: EdgeCounts() for threshold in THRESHOLDS}
    loss_sum, num_edges, num_meshes = 0.0, 0, 0
    count_errors = {threshold: 0 for threshold in THRESHOLDS}
    weight = torch.tensor(pos_weight, device=device)
    with torch.no_grad():
        for batch in loader:
            logits = _logits(model, batch, device, amp_dtype)
            target = torch.from_numpy(batch.seam).to(device)
            loss_sum += functional.binary_cross_entropy_with_logits(logits, target, pos_weight=weight,
                                                                    reduction='sum').item()
            num_edges += target.numel()
            prob = torch.sigmoid(logits).cpu().numpy()
            for threshold, count in counts.items():
                count.add(prob >= threshold, batch.seam > 0.5)
            for graph in range(batch.num_graphs):
                e_lo, e_hi = batch.edge_offsets[graph], batch.edge_offsets[graph + 1]
                f_lo, f_hi = batch.face_offsets[graph], batch.face_offsets[graph + 1]
                for threshold in THRESHOLDS:
                    count_errors[threshold] += island_count_error(prob[e_lo:e_hi], batch.seam[e_lo:e_hi],
                                                                  batch.pairs[e_lo:e_hi] - f_lo, int(f_hi - f_lo),
                                                                  min_faces, threshold)
                num_meshes += 1
    best = best_threshold(counts)
    return {'val_loss': loss_sum / max(num_edges, 1), 'seam_f1': counts[best].f1,
            'seam_precision': counts[best].precision, 'seam_recall': counts[best].recall, 'best_threshold': best,
            'island_count_mae': count_errors[best] / max(num_meshes, 1)}


def predict(weights: Path, mesh: Path, threshold: float | None = None, min_faces: int = 8) -> SeamPrediction:
    """Predict UV islands for one mesh stored as an ``.npz`` with ``vertices`` and ``faces``.

    Args:
        weights: Checkpoint written by :func:`train`.
        mesh: ``.npz`` file with ``vertices (V, 3)`` and ``faces (F, 3)``.
        threshold: Seam probability cut-off; defaults to the best one found during training.
        min_faces: Smallest island kept (smaller ones are merged into a neighbour).

    Returns:
        The :class:`SeamPrediction`.

    Raises:
        ValueError: If the file lacks ``vertices``/``faces`` or the mesh has no edge shared by two faces.
    """
    device = _device()
    checkpoint = torch.load(weights, map_location=device, weights_only=True)
    model = SeamNet(**checkpoint['model_cfg']).to(device)
    model.load_state_dict(checkpoint['model'])
    model.eval()
    with np.load(mesh) as data:
        if 'vertices' not in data or 'faces' not in data:
            raise ValueError(f'{mesh}: need vertices and faces arrays')
        sample = prepare_sample(data['vertices'], data['faces'])
    if sample.num_edges == 0:
        raise ValueError(f'{mesh}: no edge is shared by two faces, nothing to predict')
    with torch.no_grad():
        prob = torch.sigmoid(_logits(model, collate_samples([sample]), device, None)).cpu().numpy()
    cut = threshold if threshold is not None else float(checkpoint.get('best_threshold', 0.5))
    return SeamPrediction(decode_islands(prob, sample.pairs, sample.num_faces, cut, min_faces), prob, sample.pairs, cut)


def train(config: TrainConfig) -> Path:
    """Train the seam network.

    Args:
        config: The run settings (validated here).

    Returns:
        Path of ``best.pt`` in ``config.out``.

    Raises:
        ValueError: If the config is invalid, or ``config.resume`` was trained with a different network size.
        FileNotFoundError: If ``config.usd_paths`` or ``config.data_dir`` yields no input files.
    """
    config.validate()
    _seed_everything(config.seed)
    device = _device()
    config.out.mkdir(parents=True, exist_ok=True)
    train_set, val_set = _build_datasets(config)
    log.info(f'train={len(train_set)} val={len(val_set)} device={device}')
    model_cfg = {'hidden': config.hidden, 'layers': config.layers}
    model = SeamNet(**model_cfg).to(device)
    pos_weight = config.pos_weight if config.pos_weight > 0 else estimate_pos_weight(train_set)
    weight = torch.tensor(pos_weight, device=device)
    log.info(f'params={sum(p.numel() for p in model.parameters()) / 1e6:.2f}M pos_weight={pos_weight:.2f}')
    amp_dtype = _amp_dtype(config.amp, device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    total_steps = config.epochs * math.ceil(len(train_set) / config.batch_size)
    warmup = min(200, total_steps // 10)
    start_epoch, step, best_f1 = 0, 0, -1.0
    if config.resume:
        start_epoch, step, best_f1 = _resume(config.resume, model, optimizer, model_cfg, device)
        log.info(f'resumed from {config.resume} at epoch {start_epoch}')
        if not _carry_over_best(config.resume, config.out):
            log.warning('no best.pt next to the resume checkpoint; the first epoch here will write a new one')
            best_f1 = -1.0
    for epoch in range(start_epoch, config.epochs):
        train_set.set_epoch(epoch)
        model.train()
        started, running, batches = time.time(), 0.0, 0
        for batch in _loader(train_set, config, shuffle=True):
            for group in optimizer.param_groups:
                group['lr'] = config.lr * lr_scale(step, warmup, total_steps)
            logits = _logits(model, batch, device, amp_dtype)
            loss = functional.binary_cross_entropy_with_logits(logits, torch.from_numpy(batch.seam).to(device),
                                                               pos_weight=weight)
            step += 1
            if not torch.isfinite(loss):
                log.warning(f'epoch {epoch}: non-finite loss, skipping batch')
                continue
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running += loss.item()
            batches += 1
        metrics = evaluate(model, _loader(val_set, config, shuffle=False), device, pos_weight, config.min_faces,
                           amp_dtype)
        metrics.update(epoch=epoch, train_loss=running / max(batches, 1), seconds=round(time.time() - started, 1))
        log.info(json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()}))
        with open(config.out / 'metrics.jsonl', 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(metrics) + '\n')
        if metrics['seam_f1'] > best_f1:
            best_f1 = metrics['seam_f1']
            _save_checkpoint(config.out / 'best.pt', model, optimizer, epoch, step, best_f1, metrics, model_cfg,
                             config)
        _save_checkpoint(config.out / 'last.pt', model, optimizer, epoch, step, best_f1, metrics, model_cfg, config)
    log.info(f'done. best seam F1={best_f1:.4f} -> {config.out / "best.pt"}')
    return config.out / 'best.pt'


def _amp_dtype(enabled: bool, device: torch.device) -> torch.dtype | None:
    """bfloat16 when requested and supported, otherwise ``None`` (full precision)."""
    if not enabled:
        return None
    if device.type == 'cuda' and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    log.warning('amp needs a bfloat16-capable GPU; running in full precision')
    return None


def _build_datasets(config: TrainConfig) -> tuple[MeshSeamDataset, MeshSeamDataset]:
    """Training and validation datasets for ``config``.

    The input is synthetic boxes, else USD files from ``usd_paths``, else ``.npz`` files from ``data_dir``; real
    data is split by file (or ``group_regex`` group).
    """
    if config.synthetic:
        train_source = SyntheticSource(config.synthetic, config.seed)
        val_source = SyntheticSource(max(1, config.synthetic // 10), config.seed + 10_000)
    elif config.usd_paths:
        files = find_usd_files(config.usd_paths)
        if not files:
            raise FileNotFoundError(f'no USD files in {[str(p) for p in config.usd_paths]}')
        key = regex_group_key(config.group_regex) if config.group_regex else None
        train_source, val_source = split_usd_sources(files, config.val_frac, config.seed, key, config.uv_set,
                                                     config.usd_world_space)
    else:
        paths = sorted(Path(config.data_dir).glob('*.npz'))
        if not paths:
            raise FileNotFoundError(f'no .npz files in {config.data_dir}')
        key = regex_group_key(config.group_regex) if config.group_regex else None
        train_paths, val_paths = split_paths(paths, config.val_frac, config.seed, key)
        train_source, val_source = NpzSource(train_paths), NpzSource(val_paths)
    return (MeshSeamDataset(train_source, True, config.rot_aug, config.max_faces, config.seed),
            MeshSeamDataset(val_source, False, 'none', config.max_faces, config.seed))


def _carry_over_best(resume: Path, out: Path) -> bool:
    """Make sure ``out/best.pt`` exists after resuming, copying the earlier run's best checkpoint if needed.

    Resuming restores the earlier best score, so without this a run into a new directory that never beats it would
    finish without writing ``best.pt`` at all.

    Args:
        resume: The checkpoint being resumed from.
        out: This run's output directory.

    Returns:
        ``True`` if ``out/best.pt`` exists afterwards; ``False`` if there is no earlier best to carry over.
    """
    target = out / 'best.pt'
    if target.exists():
        return True
    previous = resume.parent / 'best.pt'
    if not previous.is_file():
        return False
    shutil.copy2(previous, target)
    return True


def _device() -> torch.device:
    """CUDA when available, else CPU."""
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def _loader(dataset: MeshSeamDataset, config: TrainConfig, shuffle: bool) -> DataLoader:
    return DataLoader(dataset, batch_size=config.batch_size, shuffle=shuffle, num_workers=config.num_workers,
                      collate_fn=collate_samples)


def _logits(model: SeamNet, batch: Batch, device: torch.device, amp_dtype: torch.dtype | None) -> torch.Tensor:
    """Run the model on a numpy :class:`Batch` and return float32 logits."""
    tensors = [torch.from_numpy(array).to(device) for array in
               (batch.node_feat, batch.edge_feat, batch.pairs, batch.graph_index, batch.face_counts)]
    with torch.autocast(device.type, dtype=amp_dtype, enabled=amp_dtype is not None):
        return model(*tensors).float()


def _resume(path: Path, model: SeamNet, optimizer: torch.optim.Optimizer, model_cfg: dict[str, int],
            device: torch.device) -> tuple[int, int, float]:
    """Load a checkpoint into ``model`` and ``optimizer``; returns ``(next_epoch, step, best_f1)``."""
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    if checkpoint['model_cfg'] != model_cfg:
        raise ValueError(f'{path} was trained with {checkpoint["model_cfg"]}, not {model_cfg}; '
                         'pass the same --hidden and --layers')
    model.load_state_dict(checkpoint['model'])
    optimizer.load_state_dict(checkpoint['optimizer'])
    return checkpoint['epoch'] + 1, checkpoint['step'], checkpoint['best_f1']


def _save_checkpoint(path: Path, model: SeamNet, optimizer: torch.optim.Optimizer, epoch: int, step: int,
                     best_f1: float, metrics: dict[str, float], model_cfg: dict[str, int],
                     config: TrainConfig) -> None:
    """Write a checkpoint atomically (temp file, then rename), so a crash never leaves a torn file."""
    payload = {'model': model.state_dict(), 'optimizer': optimizer.state_dict(), 'epoch': epoch, 'step': step,
               'best_f1': best_f1, 'best_threshold': metrics['best_threshold'], 'model_cfg': model_cfg,
               'config': config.to_dict()}
    temp = path.with_suffix('.tmp')
    torch.save(payload, temp)
    temp.replace(path)


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

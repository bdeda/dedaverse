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
"""Datasets and batching for UV-seam training. numpy only, so it works (and is tested) without PyTorch.

Data format, one ``.npz`` per asset:
    ``vertices (V, 3)`` float, ``faces (F, 3)`` int, and either
    ``face_island (F,)`` int (preferred), or ``faces_uv (F, 3)`` int plus ``uv (U, 2)`` float, in which case
    islands are derived from UV connectivity (``faces_uv`` must list faces in the same order as ``faces``).
"""
import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from ._geometry import SeamSample, islands_from_uv, make_synthetic_box, prepare_sample

__all__ = ['ROTATION_MODES', 'Batch', 'MeshSeamDataset', 'MeshSource', 'NpzSource', 'SyntheticSource',
           'collate_samples', 'estimate_pos_weight', 'random_rotation', 'regex_group_key', 'split_paths']

ROTATION_MODES = ('full', 'none', 'yaw')


@dataclass(eq=False)
class Batch:
    """Several :class:`SeamSample` merged into one disjoint graph.

    Attributes:
        node_feat: ``(sum F, NODE_DIM)`` float32.
        edge_feat: ``(sum E, EDGE_DIM)`` float32.
        pairs: ``(sum E, 2)`` int64, face indices offset into the merged graph.
        seam: ``(sum E,)`` float32 labels, or ``None`` when the samples carry none.
        graph_index: ``(sum F,)`` int64, which sample each face came from.
        face_counts: ``(B,)`` float32 faces per sample.
        face_offsets: ``(B + 1,)`` int64 cumulative face counts.
        edge_offsets: ``(B + 1,)`` int64 cumulative edge counts.
    """

    node_feat: np.ndarray
    edge_feat: np.ndarray
    pairs: np.ndarray
    seam: np.ndarray | None
    graph_index: np.ndarray
    face_counts: np.ndarray
    face_offsets: np.ndarray
    edge_offsets: np.ndarray

    @property
    def num_graphs(self) -> int:
        """Number of samples in the batch."""
        return int(self.face_counts.shape[0])


class MeshSource(Protocol):
    """Anything that can hand out raw meshes by index."""

    def __len__(self) -> int:
        raise NotImplementedError

    def get(self, index: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(vertices, faces, face_island)`` for item ``index``."""
        raise NotImplementedError


class MeshSeamDataset:
    """Map-style dataset (usable by ``torch.utils.data.DataLoader``) yielding :class:`SeamSample`.

    Meshes above ``max_faces`` or without any shared edge are skipped by moving on to the next item.
    Training items are rotated by a random rotation drawn from ``(seed, epoch, index)``, so runs are reproducible
    and every epoch sees fresh augmentation (call :meth:`set_epoch` before each epoch).
    """

    def __init__(self, source: MeshSource, train: bool = True, rot_aug: str = 'yaw', max_faces: int = 30000,
                 seed: int = 0) -> None:
        """Wrap a mesh source.

        Args:
            source: Where raw meshes come from.
            train: Apply rotation augmentation (validation data is never augmented).
            rot_aug: ``'none'``, ``'yaw'`` (about +Y, for Y-up assets) or ``'full'``.
            max_faces: Skip meshes with more faces than this.
            seed: Base seed for augmentation.

        Raises:
            ValueError: If ``rot_aug`` is not one of :data:`ROTATION_MODES`.
        """
        if rot_aug not in ROTATION_MODES:
            raise ValueError(f'rot_aug must be one of {ROTATION_MODES}, got {rot_aug!r}')
        self.source, self.train, self.rot_aug = source, train, rot_aug
        self.max_faces, self.seed, self.epoch = max_faces, seed, 0

    def __getitem__(self, index: int) -> SeamSample:
        """Prepare item ``index`` (or the next usable one).

        Raises:
            RuntimeError: If none of the next 10 meshes is usable.
        """
        size = len(self.source)
        for step in range(min(10, size)):
            item = (index + step) % size
            rng = np.random.default_rng([self.seed, self.epoch if self.train else 0, item])
            vertices, faces, island = self.source.get(item, rng)
            if len(faces) > self.max_faces:
                continue
            if self.train and self.rot_aug != 'none':
                vertices = vertices @ random_rotation(rng, self.rot_aug).T
            sample = prepare_sample(vertices, faces, island)
            if sample.num_edges:
                return sample
        raise RuntimeError(f'no usable mesh near index {index} (check max_faces={self.max_faces})')

    def __len__(self) -> int:
        return len(self.source)

    def set_epoch(self, epoch: int) -> None:
        """Change the augmentation stream; call before iterating a new epoch."""
        self.epoch = epoch


class NpzSource:
    """Meshes stored as ``.npz`` files (see the module docstring for the layout)."""

    def __init__(self, paths: Sequence[Path]) -> None:
        self.paths = [Path(p) for p in paths]

    def __len__(self) -> int:
        return len(self.paths)

    def get(self, index: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Load item ``index``.

        Raises:
            ValueError: If the file has neither ``face_island`` nor ``faces_uv`` + ``uv``.
        """
        del rng  # loading is deterministic
        path = self.paths[index]
        with np.load(path) as data:
            vertices = np.asarray(data['vertices'], dtype=np.float64)
            faces = np.asarray(data['faces'], dtype=np.int64)
            if 'face_island' in data:
                island = np.asarray(data['face_island'], dtype=np.int64)
            elif 'faces_uv' in data and 'uv' in data:
                island = islands_from_uv(data['uv'], data['faces_uv'])
            else:
                raise ValueError(f'{path}: need face_island, or faces_uv together with uv')
        return vertices, faces, island


class SyntheticSource:
    """Random boxes whose true seams are the 12 box edges. For smoke tests; needs no data."""

    def __init__(self, count: int, seed: int = 0) -> None:
        self.count, self.seed = count, seed

    def __len__(self) -> int:
        return self.count

    def get(self, index: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build box ``index``; the same index always gives the same box."""
        del rng  # the box is a pure function of (seed, index)
        own = np.random.default_rng([self.seed, index])
        return make_synthetic_box(int(own.integers(3, 9)), own)


def collate_samples(samples: Sequence[SeamSample]) -> Batch:
    """Merge samples into one batch graph (a ``DataLoader`` ``collate_fn``).

    Args:
        samples: One or more samples; all labelled or all unlabelled.

    Returns:
        The merged :class:`Batch`.

    Raises:
        ValueError: If ``samples`` is empty or only some samples carry labels.
    """
    if not samples:
        raise ValueError('cannot collate an empty batch')
    labelled = [s.seam is not None for s in samples]
    if any(labelled) and not all(labelled):
        raise ValueError('cannot mix labelled and unlabelled samples in one batch')
    face_counts = np.array([s.num_faces for s in samples], dtype=np.int64)
    edge_counts = np.array([s.num_edges for s in samples], dtype=np.int64)
    face_offsets = np.concatenate([[0], np.cumsum(face_counts)])
    edge_offsets = np.concatenate([[0], np.cumsum(edge_counts)])
    return Batch(node_feat=np.concatenate([s.node_feat for s in samples]),
                 edge_feat=np.concatenate([s.edge_feat for s in samples]),
                 pairs=np.concatenate([s.pairs + off for s, off in zip(samples, face_offsets[:-1])]),
                 seam=np.concatenate([s.seam for s in samples]) if all(labelled) else None,
                 graph_index=np.repeat(np.arange(len(samples), dtype=np.int64), face_counts),
                 face_counts=face_counts.astype(np.float32), face_offsets=face_offsets, edge_offsets=edge_offsets)


def estimate_pos_weight(dataset: MeshSeamDataset, limit: int = 64) -> float:
    """Loss weight that balances rare seam edges against the many non-seam edges.

    Args:
        dataset: Labelled dataset to sample.
        limit: Number of items to look at.

    Returns:
        ``non-seam edges / seam edges`` over the sampled items, clipped to ``[1, 30]``.

    Raises:
        ValueError: If the dataset yields samples without seam labels.
    """
    seams = non_seams = 0
    for index in range(min(limit, len(dataset))):
        seam = dataset[index].seam
        if seam is None:
            raise ValueError('estimate_pos_weight needs labelled samples')
        seams += int((seam > 0.5).sum())
        non_seams += int((seam <= 0.5).sum())
    return float(np.clip(non_seams / max(seams, 1), 1.0, 30.0))


def random_rotation(rng: np.random.Generator, mode: str) -> np.ndarray:
    """A random 3x3 rotation matrix.

    Args:
        rng: Random generator.
        mode: ``'none'`` (identity), ``'yaw'`` (about +Y) or ``'full'`` (uniform over all rotations).

    Returns:
        ``(3, 3)`` rotation matrix.

    Raises:
        ValueError: If ``mode`` is unknown.
    """
    if mode == 'none':
        return np.eye(3)
    if mode == 'yaw':
        angle = rng.uniform(0, 2 * np.pi)
        cos, sin = np.cos(angle), np.sin(angle)
        return np.array([[cos, 0, sin], [0, 1, 0], [-sin, 0, cos]])
    if mode == 'full':
        quat = rng.normal(size=4)
        w, x, y, z = quat / np.linalg.norm(quat)
        return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    raise ValueError(f'unknown rotation mode {mode!r}; expected one of {ROTATION_MODES}')


def regex_group_key(pattern: str) -> Callable[[Path], str]:
    """Build a grouping function for :func:`split_paths` from a regular expression.

    The key is the first capture group (or the whole match) found in the file stem, so
    ``r'^(.*?)(?:_lod\\d+)?$'`` keeps every LOD of an asset together. Files that do not match are their own group.

    Args:
        pattern: Regular expression searched in ``path.stem``.

    Returns:
        A function mapping a path to its group key.

    Raises:
        re.error: If ``pattern`` is not a valid regular expression.
    """
    compiled = re.compile(pattern)

    def key(path: Path) -> str:
        match = compiled.search(path.stem)
        if match is None:
            return path.stem
        return match.group(1) if compiled.groups else match.group(0)

    return key


def split_paths(paths: Sequence[Path], val_frac: float, seed: int,
                group_key: Callable[[Path], str] | None = None) -> tuple[list[Path], list[Path]]:
    """Split files into train and validation sets without separating groups.

    Group related assets (LODs, colour variants) with ``group_key`` so near-duplicates never straddle the split,
    which would make validation look better than it is. Without ``group_key`` every file is its own group.

    Args:
        paths: Files to split.
        val_frac: Fraction of groups used for validation (at least one group, never all).
        seed: Seed for the group shuffle.
        group_key: Maps a path to its group name.

    Returns:
        ``(train_paths, val_paths)``.

    Raises:
        ValueError: If there are fewer than two groups.
    """
    groups: dict[str, list[Path]] = {}
    for path in sorted(Path(p) for p in paths):
        groups.setdefault(group_key(path) if group_key else path.stem, []).append(path)
    if len(groups) < 2:
        raise ValueError(f'need at least two groups of files to split into train/val, found {len(groups)}')
    names = sorted(groups)
    random.Random(seed).shuffle(names)
    num_val = min(max(1, round(len(names) * val_frac)), len(names) - 1)
    val = [p for name in names[:num_val] for p in groups[name]]
    train = [p for name in names[num_val:] for p in groups[name]]
    return train, val

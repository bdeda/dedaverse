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
"""Seam-prediction metrics. numpy only."""
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from ._geometry import decode_islands

__all__ = ['EdgeCounts', 'best_threshold', 'island_count_error']


@dataclass
class EdgeCounts:
    """Running true/false positive and false negative counts for seam edges."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, predicted: np.ndarray, truth: np.ndarray) -> None:
        """Accumulate one batch.

        Args:
            predicted: Boolean array, True where an edge is predicted to be a seam.
            truth: Boolean array, True where an edge really is a seam.
        """
        predicted, truth = np.asarray(predicted, dtype=bool), np.asarray(truth, dtype=bool)
        self.tp += int((predicted & truth).sum())
        self.fp += int((predicted & ~truth).sum())
        self.fn += int((~predicted & truth).sum())

    @property
    def f1(self) -> float:
        """Harmonic mean of precision and recall (0 when both are 0)."""
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total > 0 else 0.0

    @property
    def precision(self) -> float:
        """Fraction of predicted seams that are real (0 when none were predicted)."""
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        """Fraction of real seams that were found (0 when there are none)."""
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0


def best_threshold(counts: Mapping[float, EdgeCounts]) -> float:
    """The threshold with the highest F1; ties go to the one closest to 0.5.

    Args:
        counts: Edge counts keyed by decision threshold.

    Returns:
        The best threshold.

    Raises:
        ValueError: If ``counts`` is empty.
    """
    if not counts:
        raise ValueError('counts is empty')
    return max(counts, key=lambda t: (counts[t].f1, -abs(t - 0.5)))


def island_count_error(seam_prob: np.ndarray, seam: np.ndarray, pairs: np.ndarray, num_faces: int,
                       min_faces: int = 1, threshold: float = 0.5) -> int:
    """Absolute difference between the predicted and true number of islands of one mesh.

    Args:
        seam_prob: ``(E,)`` predicted seam probabilities.
        seam: ``(E,)`` true seam labels (0/1).
        pairs: ``(E, 2)`` dual edges.
        num_faces: Number of faces.
        min_faces: Smallest island kept when decoding the prediction.
        threshold: Probability at which an edge counts as a seam.

    Returns:
        ``|predicted islands - true islands|``.
    """
    predicted = decode_islands(seam_prob, pairs, num_faces, threshold, min_faces)
    truth = decode_islands(np.asarray(seam, dtype=np.float32), pairs, num_faces, 0.5, 1)
    return abs(_count(predicted) - _count(truth))


def _count(labels: np.ndarray) -> int:
    """Number of distinct (contiguous) labels."""
    return int(labels.max()) + 1 if len(labels) else 0

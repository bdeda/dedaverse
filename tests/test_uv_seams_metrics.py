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
"""Tests for deda.core.ai.uv_seams._metrics: seam edge scores and island-count error."""
import numpy as np
import pytest

from deda.core.ai.uv_seams import _geometry as geo
from deda.core.ai.uv_seams import _metrics as metrics


class TestEdgeCounts:
    def test_counts_and_scores(self):
        counts = metrics.EdgeCounts()
        counts.add(np.array([1, 1, 0, 0, 1]), np.array([1, 0, 0, 1, 1]))
        assert (counts.tp, counts.fp, counts.fn) == (2, 1, 1)
        assert counts.precision == pytest.approx(2 / 3)
        assert counts.recall == pytest.approx(2 / 3)
        assert counts.f1 == pytest.approx(2 / 3)

    def test_accumulates_over_batches(self):
        counts = metrics.EdgeCounts()
        counts.add(np.array([True]), np.array([True]))
        counts.add(np.array([True]), np.array([False]))
        assert (counts.tp, counts.fp, counts.fn) == (1, 1, 0)

    def test_empty_counts_score_zero_instead_of_dividing_by_zero(self):
        counts = metrics.EdgeCounts()
        assert (counts.precision, counts.recall, counts.f1) == (0.0, 0.0, 0.0)


class TestBestThreshold:
    def test_picks_highest_f1(self):
        good, bad = metrics.EdgeCounts(tp=9, fp=1, fn=1), metrics.EdgeCounts(tp=5, fp=5, fn=5)
        assert metrics.best_threshold({0.3: bad, 0.6: good}) == 0.6

    def test_ties_go_to_the_threshold_closest_to_half(self):
        same = metrics.EdgeCounts(tp=1, fp=0, fn=0)
        assert metrics.best_threshold({0.3: same, 0.5: same, 0.7: same}) == 0.5

    def test_empty_mapping_raises(self):
        with pytest.raises(ValueError, match='empty'):
            metrics.best_threshold({})


class TestIslandCountError:
    @staticmethod
    def box():
        return geo.prepare_sample(*geo.make_synthetic_box(4, np.random.default_rng(0)))

    def test_perfect_prediction_has_no_error(self):
        sample = self.box()
        assert metrics.island_count_error(sample.seam, sample.seam, sample.pairs, sample.num_faces) == 0

    def test_missing_every_seam_is_off_by_five_islands(self):
        sample = self.box()
        assert metrics.island_count_error(np.zeros_like(sample.seam), sample.seam, sample.pairs,
                                          sample.num_faces) == 5

    def test_min_faces_removes_tiny_spurious_islands(self):
        sample = self.box()
        prob = sample.seam.copy()
        flat = np.nonzero(sample.seam == 0)[0]
        prob[flat[:40]] = 1.0                            # sprinkle spurious cuts inside the sides
        loose = metrics.island_count_error(prob, sample.seam, sample.pairs, sample.num_faces, min_faces=1)
        merged = metrics.island_count_error(prob, sample.seam, sample.pairs, sample.num_faces, min_faces=6)
        assert merged < loose

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
"""Tests for the artist-style (mid-plane + planar projection) UV layout decisions."""
import numpy as np
import pytest

from deda.plugins.game_asset import _symmetry as sym
from deda.plugins.game_asset._symmetry import BACK, FRONT, SIDE


def chain(count: int) -> np.ndarray:
    """edge_faces for faces 0..count-1 in a row (face i touches i+1), plus one border edge per end."""
    inner = [(i, i + 1) for i in range(count - 1)]
    return np.array([(0, -1)] + inner + [(count - 1, -1)], dtype=np.int64)


def chain_edge(i: int) -> int:
    """Index in ``chain`` of the edge between face i and i+1."""
    return i + 1


class TestChooseUvMethod:
    @pytest.mark.parametrize('requested, share, expected', [
        ('auto', 0.7, 'symmetry'), ('auto', sym.AUTO_MIN_SHARE, 'symmetry'), ('auto', 0.4, 'seams'),
        ('symmetry', 0.1, 'symmetry'), ('seams', 0.9, 'seams')])
    def test_resolves(self, requested, share, expected):
        assert sym.choose_uv_method(requested, share) == expected


class TestEdgeFacesFromLoops:
    def test_shared_border_and_non_manifold_edges(self):
        # Edge 0 is shared by faces 0 and 1, edge 1 is a border of face 0, edge 2 is used by three faces.
        loop_edges = np.array([0, 1, 2, 0, 2, 2])
        loop_faces = np.array([0, 0, 0, 1, 1, 2])
        edge_faces = sym.edge_faces_from_loops(loop_edges, loop_faces, edge_count=4)
        np.testing.assert_array_equal(edge_faces, [[0, 1], [0, -1], [0, 1], [-1, -1]])

    def test_empty_mesh(self):
        assert sym.edge_faces_from_loops(np.zeros(0), np.zeros(0), 2).tolist() == [[-1, -1], [-1, -1]]


class TestClassifyFaces:
    def test_thresholds_and_facing_check(self):
        smooth = np.array([0.9, -0.9, 0.1, 0.9])
        real = np.array([0.8, -0.7, 0.1, -0.2])   # the last face points away from the front it is smoothed into
        labels = sym.classify_faces(smooth, real, np.ones(4), np.zeros((0, 2), int), passes=0, min_piece=1)
        assert labels.tolist() == [FRONT, BACK, SIDE, SIDE]

    def test_majority_vote_fills_speckle(self):
        smooth = np.array([0.9, 0.9, 0.3, 0.9, 0.9])   # a noisy face in the middle of the front
        labels = sym.classify_faces(smooth, np.full(5, 0.5), np.ones(5), chain(5), min_piece=1)
        assert labels.tolist() == [FRONT] * 5

    def test_vote_never_projects_a_face_onto_the_wrong_side(self):
        smooth = np.array([0.9, 0.9, 0.3, 0.9, 0.9])
        real = np.array([0.5, 0.5, -0.5, 0.5, 0.5])
        labels = sym.classify_faces(smooth, real, np.ones(5), chain(5), min_piece=1)
        assert labels[2] == SIDE

    def test_small_pieces_become_side(self):
        smooth = np.array([0.9, 0.1, 0.1, 0.1, 0.1, 0.1])
        labels = sym.classify_faces(smooth, smooth, np.ones(6), chain(6), passes=0, min_piece=2)
        assert labels.tolist() == [SIDE] * 6


class TestFinalSeams:
    def test_label_borders_and_side_cuts_only(self):
        labels = np.array([FRONT, FRONT, SIDE, SIDE, BACK])
        side_seams = np.ones(6, dtype=bool)   # every cut proposed; only the one between two side faces stays
        seams = sym.final_seams(labels, side_seams, chain(5))
        assert seams.tolist() == [False, False, True, True, True, False]

    def test_no_side_cuts(self):
        assert not sym.final_seams(np.zeros(3, int), np.zeros(4, bool), chain(3)).any()


class TestInPlaneBasis:
    def test_long_axis_is_vertical(self):
        rng = np.random.default_rng(0)
        points = rng.normal(size=(200, 3)) * [3.0, 1.0, 0.1]   # long in X, flat in Z
        a, b = sym.in_plane_basis(points, np.array([0.0, 0.0, 1.0]))
        assert abs(b[0]) == pytest.approx(1.0, abs=0.02)
        np.testing.assert_allclose(a, np.cross([0, 0, 1], b), atol=1e-12)
        assert a @ b == pytest.approx(0.0, abs=1e-12) and np.linalg.norm(a) == pytest.approx(1.0)


class TestMergeSmallIslands:
    def test_cut_off_side_face_rejoins_its_strip(self):
        labels = np.zeros(10, int)
        seams = np.zeros(11, bool)
        seams[chain_edge(8)] = True   # face 9 is cut off on its own
        new_labels, new_seams = sym.merge_small_islands(labels, seams, chain(10), np.ones(11), min_faces=3)
        assert new_labels.tolist() == [SIDE] * 10 and not new_seams.any()

    def test_side_sliver_inside_a_projection_takes_its_label(self):
        labels = np.array([FRONT] * 4 + [SIDE] + [FRONT] * 4)
        new_labels, _ = sym.merge_small_islands(labels, np.zeros(10, bool), chain(9), np.ones(10), min_faces=2)
        assert new_labels.tolist() == [FRONT] * 9

    def test_joins_the_neighbour_with_the_longest_border(self):
        labels = np.array([FRONT] * 4 + [SIDE] + [BACK] * 4)
        lengths = np.ones(10)
        lengths[chain_edge(4)] = 3.0   # the sliver shares a longer edge with the back
        new_labels, _ = sym.merge_small_islands(labels, np.zeros(10, bool), chain(9), lengths, min_faces=2)
        assert new_labels[4] == BACK

    def test_small_projected_piece_joins_side_strip(self):
        labels = np.array([SIDE] * 5 + [FRONT])
        seams = np.ones(7, bool)   # proposed cuts on the strip itself
        seams[chain_edge(4)] = True
        new_labels, new_seams = sym.merge_small_islands(labels, seams, chain(6), np.ones(7), min_faces=2)
        assert new_labels[5] == SIDE and not new_seams[chain_edge(4)]

    def test_isolated_face_and_large_islands_are_kept(self):
        edge_faces = np.array([[0, -1], [1, 2]])
        labels, seams = sym.merge_small_islands(np.array([FRONT, SIDE, SIDE]), np.zeros(2, bool), edge_faces,
                                                np.ones(2), min_faces=2)
        assert labels.tolist() == [FRONT, SIDE, SIDE] and not seams.any()


class TestPlanarUvs:
    def test_front_back_mirrored_side_zero(self):
        positions = np.array([[2.0, 3.0, 0.5]] * 3)
        uv = sym.planar_uvs(positions, np.array([FRONT, BACK, SIDE]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
        assert uv.tolist() == [[2.0, 3.0], [-2.0, 3.0], [0.0, 0.0]]


class TestProjectedShare:
    def test_area_weighted(self):
        assert sym.projected_share(np.array([FRONT, BACK, SIDE]), np.array([1.0, 1.0, 2.0])) == 0.5

    def test_no_area(self):
        assert sym.projected_share(np.array([FRONT]), np.zeros(1)) == 0.0


def brute_nearest(points: np.ndarray):
    return lambda query: np.sqrt(((query[:, None, :] - points[None]) ** 2).sum(-1)).min(axis=1)


def tilted_plate(normal: np.ndarray, offset: np.ndarray, asymmetric: bool = False) -> np.ndarray:
    """A pebble-shaped plate (long in-plane, thin across), mirror-symmetric about its mid-plane."""
    rng = np.random.default_rng(3)
    u, v = rng.uniform(-1, 1, (2, 400))
    keep = u ** 2 + v ** 2 <= 1
    u, v = u[keep] * 2.0, v[keep]
    height = 0.15 * (1 - (u / 2) ** 2 - v ** 2)
    top = np.column_stack([u, v, height])
    bottom = np.column_stack([u, v, -height * (0.3 if asymmetric else 1.0)])
    local = np.vstack([top, bottom])
    z = normal / np.linalg.norm(normal)
    x = np.cross(z, [0.0, 1.0, 0.0]) if abs(z[1]) < 0.9 else np.cross(z, [1.0, 0.0, 0.0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return local @ np.vstack([x, y, z]) + offset


class TestSymmetryPlane:
    def test_finds_tilted_mid_plane(self):
        true_normal = np.array([0.1, 0.05, 1.0])
        true_normal /= np.linalg.norm(true_normal)
        points = tilted_plate(true_normal, np.array([0.3, -0.2, 0.5]))
        normal, origin, error = sym.symmetry_plane(points, brute_nearest(points), samples=150)
        angle = np.degrees(np.arccos(min(1.0, abs(normal @ true_normal))))
        assert angle < 2.0
        assert abs((origin - [0.3, -0.2, 0.5]) @ true_normal) < 0.01
        assert error < 0.01

    def test_search_corrects_a_tilted_principal_axis(self):
        # A one-sided lump at one end tilts the thinnest principal axis; the mirror search recovers the plate.
        normal = np.array([0.0, 0.0, 1.0])
        plate = tilted_plate(normal, np.zeros(3))
        rng = np.random.default_rng(5)
        lump = np.column_stack([rng.uniform(1.5, 2.0, 60), rng.uniform(-0.2, 0.2, 60), rng.uniform(0.2, 0.4, 60)])
        points = np.vstack([plate, lump])
        start = np.linalg.svd(points - points.mean(0), full_matrices=False)[2][2]
        found = sym.symmetry_plane(points, brute_nearest(points), samples=150)[0]
        tilt = lambda n: np.degrees(np.arccos(min(1.0, abs(n @ normal))))  # noqa: E731
        assert tilt(found) < tilt(start)
        assert tilt(found) < 2.0

    def test_asymmetric_shape_reports_larger_error(self):
        normal = np.array([0.0, 0.0, 1.0])
        sym_points = tilted_plate(normal, np.zeros(3))
        asym_points = tilted_plate(normal, np.zeros(3), asymmetric=True)
        symmetric = sym.symmetry_plane(sym_points, brute_nearest(sym_points), samples=100)[2]
        asymmetric = sym.symmetry_plane(asym_points, brute_nearest(asym_points), samples=100)[2]
        assert asymmetric > symmetric

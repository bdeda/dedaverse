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
"""Tests for deda.core.ai.uv_seams._geometry: welding, face graph, labels, features and island decoding."""
import numpy as np
import pytest

from deda.core.ai.uv_seams import _geometry as geo


def make_box(n=4, seed=0):
    return geo.make_synthetic_box(n, np.random.default_rng(seed))


def reference_components(pairs, num_nodes):
    """Plain union-find, numbered by each component's lowest node (the order label_components promises)."""
    parent = list(range(num_nodes))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    roots = [find(i) for i in range(num_nodes)]
    numbering = {root: k for k, root in enumerate(sorted(set(roots)))}
    return np.array([numbering[r] for r in roots])


class TestWeldVertices:
    def test_merges_coincident_points_and_keeps_face_order(self):
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0], [1, 1, 0]], dtype=float)
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        welded, new_faces = geo.weld_vertices(verts, faces)
        assert len(welded) == 4
        assert new_faces.shape == (2, 3)
        np.testing.assert_allclose(welded[new_faces], verts[faces])

    def test_welds_two_column_points(self):
        uv = np.array([[0, 0], [1, 1], [0, 0]], dtype=float)
        welded, faces = geo.weld_vertices(uv, np.array([[0, 1, 2]]), tol=1e-6)
        assert len(welded) == 2
        assert faces[0, 0] == faces[0, 2]

    @pytest.mark.parametrize('tol', [0.0, -1e-3])
    def test_rejects_non_positive_tolerance(self, tol):
        with pytest.raises(ValueError, match='tol must be positive'):
            geo.weld_vertices(np.zeros((3, 3)), np.array([[0, 1, 2]]), tol=tol)


class TestBuildDualGraph:
    def test_two_triangles_share_one_edge(self):
        pairs, edge_verts = geo.build_dual_graph(np.array([[0, 1, 2], [0, 2, 3]]))
        assert pairs.tolist() == [[0, 1]]
        assert edge_verts.tolist() == [[0, 2]]

    def test_isolated_triangle_has_no_edges(self):
        pairs, edge_verts = geo.build_dual_graph(np.array([[0, 1, 2]]))
        assert pairs.shape == (0, 2)
        assert edge_verts.shape == (0, 2)

    def test_non_manifold_edge_is_skipped(self):
        faces = np.array([[0, 1, 2], [0, 1, 3], [0, 1, 4]])   # three faces on edge (0, 1)
        pairs, _ = geo.build_dual_graph(faces)
        assert len(pairs) == 0

    def test_welded_closed_box_has_three_halves_edges_per_face(self):
        verts, faces, _ = make_box(3)
        welded, tris = geo.weld_vertices(geo.normalize_vertices(verts), faces)
        pairs, _ = geo.build_dual_graph(tris)
        assert len(pairs) == 3 * len(tris) // 2

    def test_unwelded_box_loses_the_edges_between_sides(self):
        verts, faces, _ = make_box(3)
        pairs, _ = geo.build_dual_graph(faces)
        assert len(pairs) == 3 * len(faces) // 2 - 12 * 3   # 12 box edges x n quads are open without welding


class TestLabelComponents:
    def test_matches_reference_on_random_graphs(self):
        rng = np.random.default_rng(3)
        for num_nodes, num_edges in [(50, 20), (200, 150), (300, 600), (10, 0)]:
            pairs = rng.integers(0, num_nodes, size=(num_edges, 2))
            np.testing.assert_array_equal(geo.label_components(pairs, num_nodes),
                                          reference_components(pairs, num_nodes))

    def test_no_edges_gives_one_component_per_node(self):
        np.testing.assert_array_equal(geo.label_components(np.zeros((0, 2), np.int64), 4), [0, 1, 2, 3])

    def test_no_nodes(self):
        assert geo.label_components(np.zeros((0, 2), np.int64), 0).shape == (0,)

    def test_long_chain_is_one_component(self):
        n = 3000
        pairs = np.stack([np.arange(n - 1), np.arange(1, n)], axis=1)
        assert geo.label_components(pairs, n).max() == 0


class TestPrepareSample:
    def test_box_seams_are_the_twelve_box_edges(self):
        for n in (2, 4):
            verts, faces, island = make_box(n)
            sample = geo.prepare_sample(verts, faces, island)
            assert sample.num_faces == len(faces)
            assert sample.num_edges == 3 * len(faces) // 2
            assert int(sample.seam.sum()) == 12 * n
            assert sample.node_feat.shape == (len(faces), geo.NODE_DIM)
            assert sample.edge_feat.shape == (sample.num_edges, geo.EDGE_DIM)
            assert sample.node_feat.dtype == np.float32

    def test_dihedral_cosine_separates_seams_from_flat_edges(self):
        verts, faces, island = make_box(4)
        sample = geo.prepare_sample(verts, faces, island)
        cosine = sample.edge_feat[:, 0]
        np.testing.assert_allclose(cosine[sample.seam == 0], 1.0, atol=1e-5)
        np.testing.assert_allclose(cosine[sample.seam == 1], 0.0, atol=1e-5)

    def test_without_islands_there_are_no_labels(self):
        verts, faces, _ = make_box(2)
        assert geo.prepare_sample(verts, faces).seam is None

    def test_edge_cosines_do_not_depend_on_rotation(self):
        verts, faces, island = make_box(3)
        rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        base = geo.prepare_sample(verts, faces, island)
        turned = geo.prepare_sample(verts @ rotation.T, faces, island)
        np.testing.assert_allclose(np.sort(base.edge_feat[:, 0]), np.sort(turned.edge_feat[:, 0]), atol=1e-5)

    @pytest.mark.parametrize('verts, faces, island, message', [
        (np.zeros((3, 2)), np.array([[0, 1, 2]]), None, 'vertices must have shape'),
        (np.zeros((0, 3)), np.array([[0, 1, 2]]), None, 'vertices must have shape'),
        (np.zeros((3, 3)), np.array([[0, 1]]), None, 'faces must have shape'),
        (np.zeros((3, 3)), np.zeros((0, 3), int), None, 'faces must have shape'),
        (np.zeros((3, 3)), np.array([[0, 1, 3]]), None, 'do not exist'),
        (np.zeros((3, 3)), np.array([[0, 1, -1]]), None, 'do not exist'),
        (np.zeros((3, 3)), np.array([[0, 1, 2]]), np.array([0, 1]), 'face_island must have shape'),
    ])
    def test_invalid_meshes_raise(self, verts, faces, island, message):
        with pytest.raises(ValueError, match=message):
            geo.prepare_sample(verts, faces, island)


class TestSeamLabels:
    def test_edges_between_different_islands_are_seams(self):
        labels = geo.seam_labels(np.array([0, 0, 1]), np.array([[0, 1], [1, 2]]))
        assert labels.tolist() == [0.0, 1.0]
        assert labels.dtype == np.float32


class TestEdgeFeatures:
    def test_no_edges_gives_empty_array(self):
        out = geo.edge_features(np.zeros((3, 3)), np.zeros((1, 3)), np.zeros((1, 3)),
                                np.zeros((0, 2), np.int64), np.zeros((0, 2), np.int64))
        assert out.shape == (0, geo.EDGE_DIM)


class TestDecodeIslands:
    def test_true_labels_decode_to_the_six_sides(self):
        verts, faces, island = make_box(4)
        sample = geo.prepare_sample(verts, faces, island)
        labels = geo.decode_islands(sample.seam, sample.pairs, sample.num_faces)
        assert labels.max() + 1 == 6
        assert len(set(zip(labels.tolist(), island.tolist()))) == 6

    def test_threshold_decides_which_edges_are_cut(self):
        pairs = np.array([[0, 1], [1, 2]])
        prob = np.array([0.4, 0.9])
        assert geo.decode_islands(prob, pairs, 3, threshold=0.5).max() + 1 == 2
        assert geo.decode_islands(prob, pairs, 3, threshold=0.95).max() + 1 == 1
        assert geo.decode_islands(prob, pairs, 3, threshold=0.3).max() + 1 == 3

    def test_small_islands_merge_into_their_neighbour(self):
        pairs = np.stack([np.arange(5), np.arange(1, 6)], axis=1)       # path 0-1-2-3-4-5
        prob = np.array([1, 0, 0, 0, 0], dtype=float)                   # cut after node 0
        assert geo.decode_islands(prob, pairs, 6, min_faces=1).max() + 1 == 2
        assert geo.decode_islands(prob, pairs, 6, min_faces=2).max() + 1 == 1

    def test_merge_prefers_the_neighbour_sharing_most_edges(self):
        # two 3-node blocks (A: 0,1,2  B: 3,4,5) and a lone node 6 joined to A by one edge and to B by two
        pairs = np.array([[0, 1], [1, 2], [3, 4], [4, 5], [2, 6], [3, 6], [4, 6]])
        prob = np.array([0, 0, 0, 0, 1, 1, 1], dtype=float)
        labels = geo.decode_islands(prob, pairs, 7, min_faces=2)
        assert labels[6] == labels[3] == labels[4]
        assert labels[6] != labels[0]

    def test_all_islands_small_are_left_alone(self):
        pairs = np.array([[0, 1], [1, 2], [2, 3]])
        labels = geo.decode_islands(np.array([0, 1, 0], dtype=float), pairs, 4, min_faces=5)
        assert labels.max() + 1 == 2

    def test_small_island_without_neighbours_is_left_alone(self):
        pairs = np.array([[0, 1], [1, 2]])                               # node 3 is not connected to anything
        labels = geo.decode_islands(np.zeros(2), pairs, 4, min_faces=2)
        assert labels.max() + 1 == 2

    def test_no_edges(self):
        labels = geo.decode_islands(np.zeros(0), np.zeros((0, 2), np.int64), 3, min_faces=4)
        assert labels.tolist() == [0, 1, 2]


class TestIslandsFromUv:
    @staticmethod
    def per_corner_uv(verts, faces, island):
        """UVs laid out per side (the two axes that are not the side's normal), one unit-square slot per side."""
        uv = np.zeros((len(faces) * 3, 2))
        for i in range(len(faces)):
            side = island[i]
            axes = [k for k in range(3) if k != side % 3]
            for k in range(3):
                uv[i * 3 + k] = verts[faces[i, k], axes] * 0.1 + side * 5.0
        return uv, np.arange(len(faces) * 3).reshape(-1, 3)

    def test_one_island_per_box_side(self):
        verts, faces, island = make_box(4)
        uv, faces_uv = self.per_corner_uv(verts, faces, island)
        labels = geo.islands_from_uv(uv, faces_uv)
        assert labels.max() + 1 == 6
        assert len(set(zip(labels.tolist(), island.tolist()))) == 6

    def test_cutting_a_side_in_uv_space_adds_an_island(self):
        verts, faces, island = make_box(4)
        uv, faces_uv = self.per_corner_uv(verts, faces, island)
        face_y = np.repeat(verts[faces].mean(axis=1)[:, 1], 3)
        uv[(np.repeat(island, 3) == 0) & (face_y > 0)] += 100.0
        assert geo.islands_from_uv(uv, faces_uv).max() + 1 == 7


class TestMakeSyntheticBox:
    def test_face_count_and_islands(self):
        verts, faces, island = make_box(3)
        assert len(faces) == 12 * 3 * 3
        assert sorted(set(island.tolist())) == [0, 1, 2, 3, 4, 5]
        assert len(verts) == 6 * 4 * 4

    def test_winding_is_outward(self):
        verts, faces, _ = make_box(3, seed=5)
        centroid, normal, _ = geo.face_geometry(verts, faces)
        assert ((centroid * normal).sum(axis=1) > 0).all()

    def test_same_seed_gives_the_same_box(self):
        np.testing.assert_array_equal(make_box(3, 7)[0], make_box(3, 7)[0])


class TestFaceGeometry:
    def test_unit_right_triangle(self):
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
        centroid, normal, area = geo.face_geometry(verts, np.array([[0, 1, 2]]))
        np.testing.assert_allclose(centroid, [[1 / 3, 1 / 3, 0]])
        np.testing.assert_allclose(normal, [[0, 0, 1]])
        np.testing.assert_allclose(area, [0.5])

    def test_degenerate_face_has_zero_normal_and_area(self):
        verts = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
        _, normal, area = geo.face_geometry(verts, np.array([[0, 1, 2]]))
        np.testing.assert_allclose(normal, 0)
        np.testing.assert_allclose(area, 0)


class TestNormalizeVertices:
    def test_fits_the_unit_box_and_centres(self):
        out = geo.normalize_vertices(np.array([[10, 0, 0], [14, 2, 1]], dtype=float))
        np.testing.assert_allclose(out.min(axis=0) + out.max(axis=0), 0, atol=1e-12)
        assert np.abs(out).max() == pytest.approx(1.0)

    def test_single_point_does_not_divide_by_zero(self):
        assert np.isfinite(geo.normalize_vertices(np.array([[3.0, 3.0, 3.0]]))).all()

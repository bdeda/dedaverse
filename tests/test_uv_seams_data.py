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
"""Tests for deda.core.ai.uv_seams._data: sources, dataset, batching, rotation and train/val splitting."""
from pathlib import Path

import numpy as np
import pytest

from deda.core.ai.uv_seams import _data as data
from deda.core.ai.uv_seams import _geometry as geo


class ListSource:
    """Fixed meshes, to steer the dataset's skipping logic."""

    def __init__(self, meshes):
        self.meshes = meshes

    def __len__(self):
        return len(self.meshes)

    def get(self, index, rng):
        return self.meshes[index]


def box_mesh(n=2, seed=0):
    return geo.make_synthetic_box(n, np.random.default_rng(seed))


def lone_triangle():
    return np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float), np.array([[0, 1, 2]]), np.array([0])


class TestRandomRotation:
    @pytest.mark.parametrize('mode', ['yaw', 'full'])
    def test_result_is_a_proper_rotation(self, mode):
        rng = np.random.default_rng(1)
        for _ in range(5):
            rot = data.random_rotation(rng, mode)
            np.testing.assert_allclose(rot @ rot.T, np.eye(3), atol=1e-12)
            assert np.linalg.det(rot) == pytest.approx(1.0)

    def test_none_is_identity(self):
        np.testing.assert_array_equal(data.random_rotation(np.random.default_rng(0), 'none'), np.eye(3))

    def test_yaw_keeps_the_up_axis(self):
        rot = data.random_rotation(np.random.default_rng(2), 'yaw')
        np.testing.assert_allclose(rot @ [0, 1, 0], [0, 1, 0], atol=1e-12)

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match='unknown rotation mode'):
            data.random_rotation(np.random.default_rng(0), 'tumble')


class TestSyntheticSource:
    def test_length_and_determinism(self):
        source = data.SyntheticSource(5, seed=3)
        assert len(source) == 5
        first = source.get(2, np.random.default_rng(0))
        again = data.SyntheticSource(5, seed=3).get(2, np.random.default_rng(99))
        np.testing.assert_array_equal(first[0], again[0])
        np.testing.assert_array_equal(first[1], again[1])

    def test_islands_are_the_six_sides(self):
        _, _, island = data.SyntheticSource(1).get(0, np.random.default_rng(0))
        assert sorted(set(island.tolist())) == [0, 1, 2, 3, 4, 5]


class TestNpzSource:
    def test_loads_face_island_files(self, tmp_path):
        verts, faces, island = box_mesh()
        path = tmp_path / 'a.npz'
        np.savez(path, vertices=verts, faces=faces, face_island=island)
        source = data.NpzSource([path])
        assert len(source) == 1
        out_verts, out_faces, out_island = source.get(0, np.random.default_rng(0))
        np.testing.assert_array_equal(out_verts, verts)
        np.testing.assert_array_equal(out_faces, faces)
        np.testing.assert_array_equal(out_island, island)

    def test_derives_islands_from_uv_connectivity(self, tmp_path):
        verts, faces, island = box_mesh(3)
        uv = np.zeros((len(faces) * 3, 2))
        for i in range(len(faces)):
            axes = [k for k in range(3) if k != island[i] % 3]
            for k in range(3):
                uv[i * 3 + k] = verts[faces[i, k], axes] * 0.1 + island[i] * 5.0
        path = tmp_path / 'uv.npz'
        np.savez(path, vertices=verts, faces=faces, uv=uv, faces_uv=np.arange(len(faces) * 3).reshape(-1, 3))
        _, _, derived = data.NpzSource([path]).get(0, np.random.default_rng(0))
        assert derived.max() + 1 == 6

    def test_file_without_labels_raises(self, tmp_path):
        verts, faces, _ = box_mesh()
        path = tmp_path / 'bare.npz'
        np.savez(path, vertices=verts, faces=faces)
        with pytest.raises(ValueError, match='need face_island'):
            data.NpzSource([path]).get(0, np.random.default_rng(0))


class TestMeshSeamDataset:
    def test_item_is_a_labelled_sample(self):
        ds = data.MeshSeamDataset(data.SyntheticSource(3), train=False)
        sample = ds[0]
        assert len(ds) == 3
        assert sample.num_edges > 0
        assert 0 < sample.seam.sum() < sample.num_edges

    def test_training_augmentation_is_reproducible_and_changes_each_epoch(self):
        ds = data.MeshSeamDataset(data.SyntheticSource(2), train=True, rot_aug='full', seed=4)
        first = ds[0].node_feat
        np.testing.assert_array_equal(first, ds[0].node_feat)
        ds.set_epoch(1)
        assert not np.allclose(first, ds[0].node_feat)

    def test_no_augmentation_when_rot_aug_is_none_or_not_training(self):
        base = data.MeshSeamDataset(data.SyntheticSource(1), train=False)[0].node_feat
        for ds in (data.MeshSeamDataset(data.SyntheticSource(1), train=True, rot_aug='none'),
                   data.MeshSeamDataset(data.SyntheticSource(1), train=False, rot_aug='full')):
            ds.set_epoch(5)
            np.testing.assert_array_equal(ds[0].node_feat, base)

    def test_oversized_meshes_are_skipped(self):
        big, small = box_mesh(6), box_mesh(2)
        ds = data.MeshSeamDataset(ListSource([big, small]), train=False, max_faces=len(small[1]))
        assert ds[0].num_faces == len(small[1])

    def test_meshes_without_shared_edges_are_skipped(self):
        ds = data.MeshSeamDataset(ListSource([lone_triangle(), box_mesh(2)]), train=False)
        assert ds[0].num_faces == len(box_mesh(2)[1])

    def test_usable_mesh_is_found_after_many_unusable_ones(self):
        big, small = box_mesh(4), box_mesh(2)
        ds = data.MeshSeamDataset(ListSource([big] * 12 + [small]), train=False, max_faces=len(small[1]))
        for index in (0, 5, 12):
            assert ds[index].num_faces == len(small[1])

    def test_raises_when_nothing_is_usable(self):
        ds = data.MeshSeamDataset(ListSource([box_mesh(2)]), train=False, max_faces=1)
        with pytest.raises(RuntimeError, match='no usable mesh'):
            ds[0]

    def test_index_wraps_around(self):
        ds = data.MeshSeamDataset(data.SyntheticSource(2), train=False)
        assert ds[1].num_faces == ds[3].num_faces

    def test_bad_rotation_mode_is_rejected(self):
        with pytest.raises(ValueError, match='rot_aug must be one of'):
            data.MeshSeamDataset(data.SyntheticSource(1), rot_aug='spin')


class TestCollateSamples:
    @staticmethod
    def samples(labelled=True):
        out = []
        for n in (2, 3):
            verts, faces, island = box_mesh(n)
            out.append(geo.prepare_sample(verts, faces, island if labelled else None))
        return out

    def test_merges_graphs_with_offsets(self):
        a, b = self.samples()
        batch = data.collate_samples([a, b])
        assert batch.num_graphs == 2
        assert batch.node_feat.shape[0] == a.num_faces + b.num_faces
        assert batch.face_offsets.tolist() == [0, a.num_faces, a.num_faces + b.num_faces]
        assert batch.edge_offsets.tolist() == [0, a.num_edges, a.num_edges + b.num_edges]
        np.testing.assert_array_equal(batch.pairs[a.num_edges:], b.pairs + a.num_faces)
        assert batch.graph_index.tolist() == [0] * a.num_faces + [1] * b.num_faces
        assert batch.face_counts.tolist() == [a.num_faces, b.num_faces]
        assert batch.face_counts.dtype == np.float32
        assert batch.seam.shape == (a.num_edges + b.num_edges,)

    def test_unlabelled_samples_give_no_labels(self):
        assert data.collate_samples(self.samples(labelled=False)).seam is None

    def test_mixed_labelled_and_unlabelled_raises(self):
        labelled, unlabelled = self.samples()[0], self.samples(labelled=False)[1]
        with pytest.raises(ValueError, match='mix labelled and unlabelled'):
            data.collate_samples([labelled, unlabelled])

    def test_empty_batch_raises(self):
        with pytest.raises(ValueError, match='empty batch'):
            data.collate_samples([])


class TestSplitPaths:
    PATHS = [Path(f'asset_{i:02d}.npz') for i in range(10)]

    def test_split_is_deterministic_and_disjoint(self):
        train, val = data.split_paths(self.PATHS, 0.2, seed=1)
        assert (train, val) == data.split_paths(list(reversed(self.PATHS)), 0.2, seed=1)
        assert len(val) == 2 and len(train) == 8
        assert not set(train) & set(val)

    def test_different_seeds_pick_different_validation_sets(self):
        vals = {tuple(data.split_paths(self.PATHS, 0.3, seed=s)[1]) for s in range(6)}
        assert len(vals) > 1

    def test_groups_are_never_split(self):
        paths = [Path(f'{name}_lod{lod}.npz') for name in ('axe', 'bow', 'cup', 'dog') for lod in range(3)]
        key = data.regex_group_key(r'^(.*?)(?:_lod\d+)?$')
        for seed in range(5):
            train, val = data.split_paths(paths, 0.25, seed, group_key=key)
            assert {key(p) for p in train}.isdisjoint({key(p) for p in val})
            assert len(val) == 3

    def test_always_keeps_one_group_on_each_side(self):
        train, val = data.split_paths(self.PATHS[:2], 0.99, seed=0)
        assert len(train) == 1 and len(val) == 1
        train, val = data.split_paths(self.PATHS[:3], 0.001, seed=0)
        assert len(val) == 1

    def test_too_few_groups_raises(self):
        with pytest.raises(ValueError, match='at least two groups'):
            data.split_paths([Path('a.npz')], 0.5, seed=0)
        with pytest.raises(ValueError, match='at least two groups'):
            data.split_paths([Path('a_lod0.npz'), Path('a_lod1.npz')], 0.5, seed=0,
                             group_key=data.regex_group_key(r'^(.*?)_lod\d+$'))


class TestRegexGroupKey:
    def test_uses_first_capture_group(self):
        assert data.regex_group_key(r'^(.*?)_v\d+$')(Path('sword_v2.npz')) == 'sword'

    def test_uses_whole_match_without_capture_groups(self):
        assert data.regex_group_key(r'[a-z]+')(Path('sword_v2.npz')) == 'sword'

    def test_unmatched_stem_is_its_own_group(self):
        assert data.regex_group_key(r'^zzz(.*)$')(Path('sword.npz')) == 'sword'


class TestEstimatePosWeight:
    def test_seams_are_rarer_than_other_edges(self):
        weight = data.estimate_pos_weight(data.MeshSeamDataset(data.SyntheticSource(6), train=False))
        assert 1.0 < weight <= 30.0

    def test_no_seams_hits_the_upper_clip(self):
        verts, faces, _ = box_mesh(3)
        one_island = (verts, faces, np.zeros(len(faces), dtype=int))
        assert data.estimate_pos_weight(data.MeshSeamDataset(ListSource([one_island]), train=False)) == 30.0

    def test_limit_caps_the_items_looked_at(self):
        calls = []

        class Counting(ListSource):
            def get(self, index, rng):
                calls.append(index)
                return super().get(index, rng)

        ds = data.MeshSeamDataset(Counting([box_mesh(2)] * 5), train=False)
        data.estimate_pos_weight(ds, limit=2)
        assert calls == [0, 1]

    def test_unlabelled_samples_are_rejected(self):
        class Unlabelled:
            def __len__(self):
                return 1

            def __getitem__(self, index):
                return geo.SeamSample(np.zeros((1, geo.NODE_DIM), np.float32), np.zeros((0, geo.EDGE_DIM), np.float32),
                                      np.zeros((0, 2), np.int64))

        with pytest.raises(ValueError, match='needs labelled samples'):
            data.estimate_pos_weight(Unlabelled())

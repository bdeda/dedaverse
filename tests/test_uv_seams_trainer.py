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
"""Tests for the PyTorch parts of deda.core.ai.uv_seams (model, training loop, evaluation, prediction).

PyTorch is an optional dependency. CI installs a CPU build for the test step; elsewhere this module is skipped
unless torch is installed: ``python -m pytest tests/test_uv_seams_trainer.py``.
"""
import json

import numpy as np
import pytest

torch = pytest.importorskip('torch')

from deda.core.ai.uv_seams import _data as data  # noqa: E402
from deda.core.ai.uv_seams import _geometry as geo  # noqa: E402
from deda.core.ai.uv_seams import _model as model_mod  # noqa: E402
from deda.core.ai.uv_seams import _options as options  # noqa: E402
from deda.core.ai.uv_seams import _trainer as trainer  # noqa: E402

CPU = torch.device('cpu')


def tiny_config(tmp_path, **overrides):
    settings = dict(out=tmp_path / 'run', synthetic=12, epochs=2, batch_size=4, hidden=16, layers=2, num_workers=0)
    settings.update(overrides)
    return options.TrainConfig(**settings)


def box_sample(n, seed=0):
    return geo.prepare_sample(*geo.make_synthetic_box(n, np.random.default_rng(seed)))


def tensors(batch):
    return [torch.from_numpy(a) for a in (batch.node_feat, batch.edge_feat, batch.pairs, batch.graph_index,
                                          batch.face_counts)]


class TestSeamNet:
    def test_one_finite_logit_per_edge(self):
        batch = data.collate_samples([box_sample(2), box_sample(3)])
        net = model_mod.SeamNet(hidden=16, layers=2).eval()
        logits = net(*tensors(batch))
        assert logits.shape == (batch.pairs.shape[0],)
        assert torch.isfinite(logits).all()

    def test_edge_direction_does_not_matter(self):
        batch = data.collate_samples([box_sample(3)])
        net = model_mod.SeamNet(hidden=16, layers=3).eval()
        node, edge, pairs, graph, counts = tensors(batch)
        np.testing.assert_allclose(net(node, edge, pairs, graph, counts).detach().numpy(),
                                   net(node, edge, pairs.flip(1), graph, counts).detach().numpy(), atol=1e-5)

    def test_meshes_in_a_batch_do_not_influence_each_other(self):
        first, other = box_sample(2), box_sample(4, seed=1)
        net = model_mod.SeamNet(hidden=16, layers=3).eval()
        alone = net(*tensors(data.collate_samples([first]))).detach().numpy()
        together = net(*tensors(data.collate_samples([first, other]))).detach().numpy()[:first.num_edges]
        np.testing.assert_allclose(alone, together, atol=1e-4)

    @pytest.mark.parametrize('hidden, layers', [(0, 2), (8, 0)])
    def test_empty_networks_are_rejected(self, hidden, layers):
        with pytest.raises(ValueError, match='must be >= 1'):
            model_mod.SeamNet(hidden=hidden, layers=layers)


class TestTrain:
    def test_writes_checkpoints_and_metrics(self, tmp_path):
        config = tiny_config(tmp_path)
        best = trainer.train(config)
        assert best == config.out / 'best.pt' and best.exists()
        assert (config.out / 'last.pt').exists()
        lines = (config.out / 'metrics.jsonl').read_text().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        for key in ('epoch', 'train_loss', 'val_loss', 'seam_f1', 'best_threshold', 'island_count_mae'):
            assert key in first
        assert np.isfinite(first['train_loss'])

    def test_checkpoint_loads_with_weights_only(self, tmp_path):
        config = tiny_config(tmp_path, epochs=1)
        checkpoint = torch.load(trainer.train(config), map_location='cpu', weights_only=True)
        assert checkpoint['model_cfg'] == {'hidden': 16, 'layers': 2}
        assert checkpoint['config']['synthetic'] == 12

    def test_resume_continues_from_the_next_epoch(self, tmp_path):
        trainer.train(tiny_config(tmp_path, epochs=1))
        config = tiny_config(tmp_path, epochs=2, resume=tmp_path / 'run' / 'last.pt')
        trainer.train(config)
        epochs = [json.loads(line)['epoch'] for line in (config.out / 'metrics.jsonl').read_text().splitlines()]
        assert epochs == [0, 1]

    def test_resume_into_a_new_directory_keeps_a_best_checkpoint(self, tmp_path):
        trainer.train(tiny_config(tmp_path, epochs=1))
        elsewhere = tmp_path / 'other'
        config = tiny_config(tmp_path, epochs=1, out=elsewhere, resume=tmp_path / 'run' / 'last.pt')
        # Nothing left to train (epoch 1 of 1 is done): the carried-over best must still be there.
        assert trainer.train(config) == elsewhere / 'best.pt'
        assert (elsewhere / 'best.pt').exists()

    def test_resume_without_an_earlier_best_starts_best_tracking_afresh(self, tmp_path):
        trainer.train(tiny_config(tmp_path, epochs=1))
        (tmp_path / 'run' / 'best.pt').unlink()
        config = tiny_config(tmp_path, epochs=2, out=tmp_path / 'other', resume=tmp_path / 'run' / 'last.pt')
        trainer.train(config)
        assert (config.out / 'best.pt').exists()

    def test_resume_with_a_different_network_size_is_refused(self, tmp_path):
        trainer.train(tiny_config(tmp_path, epochs=1))
        with pytest.raises(ValueError, match='pass the same --hidden and --layers'):
            trainer.train(tiny_config(tmp_path, hidden=32, resume=tmp_path / 'run' / 'last.pt'))

    def test_trains_from_npz_files(self, tmp_path):
        folder = tmp_path / 'assets'
        folder.mkdir()
        for i in range(6):
            verts, faces, island = geo.make_synthetic_box(3, np.random.default_rng(i))
            np.savez(folder / f'box_{i}.npz', vertices=verts, faces=faces, face_island=island)
        config = tiny_config(tmp_path, synthetic=0, data_dir=folder, epochs=1, val_frac=0.34)
        assert trainer.train(config).exists()

    def test_trains_from_usd_files_in_several_folders(self, tmp_path):
        from pxr import Gf, Sdf, Usd, UsdGeom, Vt  # pylint: disable=import-outside-toplevel

        for i in range(4):
            folder = tmp_path / f'dir{i % 2}'
            folder.mkdir(exist_ok=True)
            verts, faces, island = geo.make_synthetic_box(2, np.random.default_rng(i))
            stage = Usd.Stage.CreateNew(str(folder / f'box_{i}.usda'))
            mesh = UsdGeom.Mesh.Define(stage, '/Box')
            mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, p)) for p in verts]))
            mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(faces)))
            mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([int(v) for v in faces.ravel()]))
            # Each box side projected onto its own two axes, in its own UV slot: one island per side.
            uv = [tuple(float(x) for x in verts[faces[f, k]][[a for a in range(3) if a != island[f] % 3]] * 0.1
                        + island[f] * 5.0) for f in range(len(faces)) for k in range(3)]
            primvar = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'faceVarying')
            primvar.Set(Vt.Vec2fArray([Gf.Vec2f(*t) for t in uv]))
            stage.Save()
        config = tiny_config(tmp_path, synthetic=0, usd_paths=[tmp_path / 'dir0', tmp_path / 'dir1'], epochs=1,
                             val_frac=0.25)
        train_set, val_set = trainer._build_datasets(config)
        assert len(train_set) == 3 and len(val_set) == 1
        assert train_set[0].seam.sum() > 0
        assert trainer.train(config).exists()

    def test_usd_paths_without_usd_files_raise(self, tmp_path):
        (tmp_path / 'empty').mkdir()
        with pytest.raises(FileNotFoundError, match='no USD files'):
            trainer.train(tiny_config(tmp_path, synthetic=0, usd_paths=[tmp_path / 'empty']))

    def test_non_finite_loss_skips_the_batch(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(trainer.functional, 'binary_cross_entropy_with_logits',
                            lambda logits, target, **kw: (logits * 0).sum() + float('nan'))
        config = tiny_config(tmp_path, epochs=1)
        with caplog.at_level('WARNING'):
            trainer.train(config)
        assert 'non-finite loss' in caplog.text
        assert json.loads((config.out / 'metrics.jsonl').read_text().splitlines()[0])['train_loss'] == 0.0

    def test_empty_data_folder_raises(self, tmp_path):
        folder = tmp_path / 'empty'
        folder.mkdir()
        with pytest.raises(FileNotFoundError, match='no .npz files'):
            trainer.train(tiny_config(tmp_path, synthetic=0, data_dir=folder))

    def test_invalid_config_is_rejected_before_training(self, tmp_path):
        with pytest.raises(ValueError, match='epochs'):
            trainer.train(tiny_config(tmp_path, epochs=0))


class TestAmpDtype:
    def test_disabled_is_full_precision(self):
        assert trainer._amp_dtype(False, CPU) is None

    def test_cpu_falls_back_with_a_warning(self, caplog):
        with caplog.at_level('WARNING'):
            assert trainer._amp_dtype(True, CPU) is None
        assert 'bfloat16' in caplog.text

    def test_bf16_gpu_uses_bfloat16(self, monkeypatch):
        monkeypatch.setattr(trainer.torch.cuda, 'is_bf16_supported', lambda: True)
        assert trainer._amp_dtype(True, torch.device('cuda')) is torch.bfloat16


class TestEvaluate:
    def test_reports_every_metric(self, tmp_path):
        config = tiny_config(tmp_path)
        _, val_set = trainer._build_datasets(config)
        net = model_mod.SeamNet(hidden=16, layers=2)
        result = trainer.evaluate(net, trainer._loader(val_set, config, shuffle=False), CPU, pos_weight=3.0)
        assert set(result) == {'val_loss', 'seam_f1', 'seam_precision', 'seam_recall', 'best_threshold',
                               'island_count_mae'}
        assert 0.0 <= result['seam_f1'] <= 1.0
        assert result['best_threshold'] in trainer.THRESHOLDS

    def test_island_count_error_is_measured_at_the_selected_threshold(self, tmp_path, monkeypatch):
        config = tiny_config(tmp_path)
        _, val_set = trainer._build_datasets(config)
        seen = []

        def fake_error(prob, seam, pairs, num_faces, min_faces, threshold):
            seen.append(threshold)
            return 1 if threshold == 0.3 else 0

        monkeypatch.setattr(trainer, 'island_count_error', fake_error)
        monkeypatch.setattr(trainer, 'best_threshold', lambda counts: 0.3)
        net = model_mod.SeamNet(hidden=16, layers=2)
        result = trainer.evaluate(net, trainer._loader(val_set, config, shuffle=False), CPU, pos_weight=3.0)
        assert set(seen) == set(trainer.THRESHOLDS)
        assert result['island_count_mae'] == 1.0


class TestPredict:
    @pytest.fixture
    def weights(self, tmp_path):
        return trainer.train(tiny_config(tmp_path, epochs=1))

    @staticmethod
    def write_mesh(path, n=3):
        verts, faces, _ = geo.make_synthetic_box(n, np.random.default_rng(5))
        np.savez(path, vertices=verts, faces=faces)
        return len(faces)

    def test_returns_an_island_per_face_in_input_order(self, tmp_path, weights):
        mesh = tmp_path / 'box.npz'
        num_faces = self.write_mesh(mesh)
        result = trainer.predict(weights, mesh)
        assert result.face_island.shape == (num_faces,)
        assert result.seam_prob.shape == (result.pairs.shape[0],)
        assert sorted(set(result.face_island.tolist())) == list(range(result.face_island.max() + 1))
        assert result.threshold in trainer.THRESHOLDS

    def test_threshold_override(self, tmp_path, weights):
        mesh = tmp_path / 'box.npz'
        self.write_mesh(mesh)
        assert trainer.predict(weights, mesh, threshold=0.9).threshold == 0.9
        everything_cut = trainer.predict(weights, mesh, threshold=0.0, min_faces=1)
        assert everything_cut.face_island.max() + 1 == len(everything_cut.face_island)

    def test_file_without_faces_raises(self, tmp_path, weights):
        mesh = tmp_path / 'bad.npz'
        np.savez(mesh, vertices=np.zeros((3, 3)))
        with pytest.raises(ValueError, match='need vertices and faces'):
            trainer.predict(weights, mesh)

    def test_mesh_without_shared_edges_raises(self, tmp_path, weights):
        mesh = tmp_path / 'tri.npz'
        np.savez(mesh, vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float), faces=np.array([[0, 1, 2]]))
        with pytest.raises(ValueError, match='nothing to predict'):
            trainer.predict(weights, mesh)

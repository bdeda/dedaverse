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
"""train_uv_islands.py - train a face-graph network to predict UV seams on game meshes.

Task
  Input : triangle mesh (vertices, faces)
  Output: P(seam) for every mesh edge shared by two faces. Connected components
          of the non-seam edges are the predicted UV islands.
Labels
  Taken from your existing assets: edge is a seam iff its two faces are in
  different UV islands.

Data format (one .npz per asset, in --data-dir)
  vertices    (V,3) float
  faces       (F,3) int
  face_island (F,)  int            <- preferred; island id per face
  OR faces_uv (F,3) int + uv (U,2) <- island ids are derived from UV connectivity
  (face order of faces_uv must match faces)

Usage
  # 0) smoke test, no data needed
  python tools/uv_islands/train_uv_islands.py train --synthetic 200 --epochs 5 --out runs/smoke
  # 1) real training
  python tools/uv_islands/train_uv_islands.py train --data-dir data/npz --out runs/exp1 --epochs 100 --amp
  # 2) resume
  python tools/uv_islands/train_uv_islands.py train --data-dir data/npz --out runs/exp1 --epochs 100 --resume runs/exp1/last.pt
  # 3) inference on one asset (writes <name>_pred.npz)
  python tools/uv_islands/train_uv_islands.py predict --weights runs/exp1/best.pt --mesh asset.npz
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as Fn
from torch.utils.data import DataLoader, Dataset

from uv_geometry import (EDGE_DIM, NODE_DIM, decode_islands, islands_from_uv,
                         make_synthetic_cube, prepare_sample)


# ============================================================================
# data
# ============================================================================
def random_rotation(rng: np.random.Generator, mode: str) -> np.ndarray:
    if mode == "none":
        return np.eye(3)
    if mode == "yaw":  # about +Y (assumes Y-up assets; change if yours differ)
        t = rng.uniform(0, 2 * np.pi)
        c, s = np.cos(t), np.sin(t)
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


class NpzSource:
    def __init__(self, paths):
        self.paths = list(paths)

    def __len__(self):
        return len(self.paths)

    def get(self, idx, rng):
        d = np.load(self.paths[idx])
        v, f = d["vertices"].astype(np.float64), d["faces"].astype(np.int64)
        if "face_island" in d:
            isl = d["face_island"].astype(np.int64)
        elif "faces_uv" in d and "uv" in d:
            isl = islands_from_uv(d["uv"], d["faces_uv"])
        else:
            raise KeyError(f"{self.paths[idx]}: need face_island or (faces_uv + uv)")
        return v, f, isl


class SyntheticSource:
    """Boxes whose true seams are the 12 box edges. For smoke tests only."""

    def __init__(self, n, seed):
        self.n, self.seed = n, seed

    def __len__(self):
        return self.n

    def get(self, idx, rng):
        r = np.random.default_rng([self.seed, idx])
        return make_synthetic_cube(int(r.integers(3, 9)), r)


class MeshSeamDataset(Dataset):
    def __init__(self, source, train, rot_aug="yaw", max_faces=60000, seed=0):
        self.source, self.train, self.rot_aug = source, train, rot_aug
        self.max_faces, self.seed, self.epoch = max_faces, seed, 0

    def set_epoch(self, e):  # call before creating the DataLoader iterator
        self.epoch = e

    def __len__(self):
        return len(self.source)

    def __getitem__(self, idx):
        for k in range(10):  # skip oversized / edge-less meshes
            j = (idx + k) % len(self.source)
            rng = np.random.default_rng([self.seed, self.epoch if self.train else 0, j])
            v, f, isl = self.source.get(j, rng)
            if len(f) > self.max_faces:
                continue
            if self.train and self.rot_aug != "none":
                v = v @ random_rotation(rng, self.rot_aug).T
            x, ef, pairs, y = prepare_sample(v, f, isl)
            if len(pairs) == 0:
                continue
            return {"x": torch.from_numpy(x), "ef": torch.from_numpy(ef),
                    "pairs": torch.from_numpy(pairs), "y": torch.from_numpy(y)}
        raise RuntimeError("no usable mesh found near index %d (check --max-faces)" % idx)


def collate(batch):
    xs, efs, ps, ys, bs, fo, eo = [], [], [], [], [], [0], [0]
    for i, b in enumerate(batch):
        nf = b["x"].shape[0]
        xs.append(b["x"]); efs.append(b["ef"]); ys.append(b["y"])
        ps.append(b["pairs"] + fo[-1])
        bs.append(torch.full((nf,), i, dtype=torch.long))
        fo.append(fo[-1] + nf); eo.append(eo[-1] + b["pairs"].shape[0])
    return {"x": torch.cat(xs), "ef": torch.cat(efs), "pairs": torch.cat(ps),
            "y": torch.cat(ys), "batch": torch.cat(bs),
            "counts": torch.tensor(np.diff(fo), dtype=torch.float32),
            "fo": fo, "eo": eo}


def to_device(b, dev):
    return {k: (v.to(dev, non_blocking=True) if torch.is_tensor(v) else v) for k, v in b.items()}


# ============================================================================
# model: message passing on the face-adjacency graph + per-graph global context
# ============================================================================
def mlp(i, h, o):
    return nn.Sequential(nn.Linear(i, h), nn.SiLU(), nn.Linear(h, o))


class MPLayer(nn.Module):
    def __init__(self, h):
        super().__init__()
        self.msg, self.upd, self.norm = mlp(3 * h, h, h), mlp(3 * h, h, h), nn.LayerNorm(h)

    def forward(self, x, e, src, dst, batch, counts):
        m = self.msg(torch.cat([x[src], x[dst], e], -1)).to(x.dtype)
        agg = torch.zeros_like(x).index_add_(0, dst, m)
        deg = torch.zeros(x.shape[0], device=x.device, dtype=x.dtype).index_add_(
            0, dst, torch.ones(dst.shape[0], device=x.device, dtype=x.dtype))
        agg = agg / deg.clamp(min=1).unsqueeze(-1)
        # global context: mean over all faces of the same mesh. Lets the net
        # reason about the whole shape, not just a k-hop neighbourhood.
        g = torch.zeros(counts.shape[0], x.shape[1], device=x.device, dtype=torch.float32).index_add_(0, batch, x.float())
        g = (g / counts.unsqueeze(-1))[batch].to(x.dtype)  # fp32 accumulation: bf16 sums over 10k+ faces lose precision
        return self.norm(x + self.upd(torch.cat([x, agg, g], -1)).to(x.dtype))


class SeamNet(nn.Module):
    def __init__(self, hidden=128, layers=8):
        super().__init__()
        self.node_in, self.edge_in = mlp(NODE_DIM, hidden, hidden), mlp(EDGE_DIM, hidden, hidden)
        self.layers = nn.ModuleList(MPLayer(hidden) for _ in range(layers))
        self.head = mlp(3 * hidden, hidden, 1)

    def forward(self, b):
        x, pairs = self.node_in(b["x"]), b["pairs"]
        e = self.edge_in(b["ef"])
        src, dst = torch.cat([pairs[:, 0], pairs[:, 1]]), torch.cat([pairs[:, 1], pairs[:, 0]])
        e2 = torch.cat([e, e])
        for layer in self.layers:
            x = layer(x, e2, src, dst, b["batch"], b["counts"])
        xa, xb = x[pairs[:, 0]], x[pairs[:, 1]]
        # symmetric in (a, b): an undirected edge has one answer
        return self.head(torch.cat([xa + xb, (xa - xb).abs(), e], -1)).squeeze(-1)


# ============================================================================
# eval
# ============================================================================
@torch.no_grad()
def evaluate(model, loader, dev, pos_weight, amp_dtype, min_faces, thresholds=(0.3, 0.4, 0.5, 0.6, 0.7)):
    model.eval()
    tp, fp, fn = ({t: 0 for t in thresholds} for _ in range(3))
    loss_sum, n_edges, cnt_err, n_meshes = 0.0, 0, 0.0, 0
    for b in loader:
        b = to_device(b, dev)
        with torch.autocast(dev.type, dtype=amp_dtype, enabled=amp_dtype is not None):
            logits = model(b)
        logits = logits.float()
        loss_sum += Fn.binary_cross_entropy_with_logits(logits, b["y"], pos_weight=pos_weight,
                                                        reduction="sum").item()
        n_edges += b["y"].numel()
        prob, y = torch.sigmoid(logits).cpu().numpy(), b["y"].cpu().numpy() > 0.5
        for t in thresholds:
            p = prob >= t
            tp[t] += int((p & y).sum()); fp[t] += int((p & ~y).sum()); fn[t] += int((~p & y).sum())
        pairs = b["pairs"].cpu().numpy()
        for g in range(len(b["fo"]) - 1):  # island-count error at thr 0.5
            f0, f1, e0, e1 = b["fo"][g], b["fo"][g + 1], b["eo"][g], b["eo"][g + 1]
            pg = pairs[e0:e1] - f0
            n_pred = decode_islands(prob[e0:e1], pg, f1 - f0, 0.5, min_faces).max() + 1
            n_gt = decode_islands(y[e0:e1].astype(np.float32), pg, f1 - f0, 0.5, 1).max() + 1
            cnt_err += abs(int(n_pred) - int(n_gt)); n_meshes += 1

    def f1(t):
        p, r = tp[t] / max(tp[t] + fp[t], 1), tp[t] / max(tp[t] + fn[t], 1)
        return 2 * p * r / max(p + r, 1e-9), p, r

    best_t = max(thresholds, key=lambda t: f1(t)[0])
    f, p, r = f1(best_t)
    return {"val_loss": loss_sum / max(n_edges, 1), "seam_f1": f, "seam_precision": p, "seam_recall": r,
            "best_threshold": best_t, "island_count_mae": cnt_err / max(n_meshes, 1)}


# ============================================================================
# train
# ============================================================================
def save_ckpt(path: Path, payload):
    tmp = path.with_suffix(".tmp")
    torch.save(payload, tmp)
    os.replace(tmp, path)


def estimate_pos_weight(ds, n=64):
    pos = neg = 0
    for i in range(min(n, len(ds))):
        y = ds[i]["y"]
        pos += int((y > 0.5).sum()); neg += int((y <= 0.5).sum())
    return float(np.clip(neg / max(pos, 1), 1.0, 30.0))


def cmd_train(a):
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    if a.synthetic:
        n_val = max(1, a.synthetic // 10)
        tr_src, va_src = SyntheticSource(a.synthetic, a.seed), SyntheticSource(n_val, a.seed + 10_000)
    else:
        if not a.data_dir:
            raise SystemExit("--data-dir is required unless --synthetic N is given")
        paths = sorted(Path(a.data_dir).glob("*.npz"))
        if len(paths) < 2:
            raise SystemExit(f"need >=2 .npz files in {a.data_dir}, found {len(paths)}")
        random.Random(a.seed).shuffle(paths)
        n_val = max(1, int(len(paths) * a.val_frac))
        # NOTE: split by file. If your library has near-duplicate assets
        # (LODs, colour variants) split by asset family instead, or val is optimistic.
        va_src, tr_src = NpzSource(paths[:n_val]), NpzSource(paths[n_val:])
    tr = MeshSeamDataset(tr_src, True, a.rot_aug, a.max_faces, a.seed)
    va = MeshSeamDataset(va_src, False, "none", a.max_faces, a.seed)
    print(f"train={len(tr)} val={len(va)} device={dev}")

    mk = lambda ds, shuf: DataLoader(ds, batch_size=a.batch_size, shuffle=shuf, num_workers=a.num_workers,
                                     collate_fn=collate, drop_last=False, pin_memory=dev.type == "cuda")
    va_loader = mk(va, False)

    model_cfg = {"hidden": a.hidden, "layers": a.layers}
    model = SeamNet(**model_cfg).to(dev)
    print("params: %.2fM" % (sum(p.numel() for p in model.parameters()) / 1e6))
    pw = a.pos_weight if a.pos_weight > 0 else estimate_pos_weight(tr)
    print(f"pos_weight={pw:.2f}")
    pos_weight = torch.tensor(pw, device=dev)

    amp_dtype = None
    if a.amp:
        if dev.type == "cuda" and torch.cuda.is_bf16_supported():
            amp_dtype = torch.bfloat16
        else:
            print("WARNING: --amp needs a bf16-capable GPU; running fp32")

    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=a.wd)
    steps_per_epoch = math.ceil(len(tr) / a.batch_size)
    total, warm = a.epochs * steps_per_epoch, min(200, a.epochs * steps_per_epoch // 10)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / max(warm, 1) if s < warm else
                                              0.5 * (1 + math.cos(math.pi * (s - warm) / max(total - warm, 1))) * 0.99 + 0.01)

    start_epoch, best_f1 = 0, -1.0
    if a.resume:
        ck = torch.load(a.resume, map_location=dev)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); sched.load_state_dict(ck["sched"])
        start_epoch, best_f1 = ck["epoch"] + 1, ck["best_f1"]
        print(f"resumed from {a.resume} at epoch {start_epoch}")

    log = open(out / "metrics.jsonl", "a")
    for ep in range(start_epoch, a.epochs):
        tr.set_epoch(ep); model.train(); t0 = time.time(); run, nb = 0.0, 0
        for b in mk(tr, True):
            b = to_device(b, dev)
            with torch.autocast(dev.type, dtype=amp_dtype, enabled=amp_dtype is not None):
                logits = model(b)
            loss = Fn.binary_cross_entropy_with_logits(logits.float(), b["y"], pos_weight=pos_weight)
            if not torch.isfinite(loss):
                print("non-finite loss, skipping batch"); opt.zero_grad(set_to_none=True); continue
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step()
            run += loss.item(); nb += 1
        m = evaluate(model, va_loader, dev, pos_weight, amp_dtype, a.min_faces)
        m.update(epoch=ep, train_loss=run / max(nb, 1), lr=sched.get_last_lr()[0], sec=round(time.time() - t0, 1))
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()}))
        log.write(json.dumps(m) + "\n"); log.flush()
        payload = {"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(),
                   "epoch": ep, "best_f1": best_f1, "model_cfg": model_cfg,
                   "args": {k: v for k, v in vars(a).items() if k != "fn"},
                   "best_threshold": m["best_threshold"]}
        if m["seam_f1"] > best_f1:
            best_f1 = payload["best_f1"] = m["seam_f1"]
            save_ckpt(out / "best.pt", payload)
        save_ckpt(out / "last.pt", payload)
    print(f"done. best seam F1={best_f1:.4f}  ->  {out/'best.pt'}")


# ============================================================================
# predict
# ============================================================================
@torch.no_grad()
def cmd_predict(a):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(a.weights, map_location=dev)
    model = SeamNet(**ck["model_cfg"]).to(dev); model.load_state_dict(ck["model"]); model.eval()
    d = np.load(a.mesh)
    x, ef, pairs, _ = prepare_sample(d["vertices"], d["faces"], None)
    nf = x.shape[0]
    b = collate([{"x": torch.from_numpy(x), "ef": torch.from_numpy(ef), "pairs": torch.from_numpy(pairs),
                  "y": torch.zeros(len(pairs))}])
    prob = torch.sigmoid(model(to_device(b, dev)).float()).cpu().numpy()
    thr = a.threshold if a.threshold is not None else ck.get("best_threshold", 0.5)
    lab = decode_islands(prob, pairs, nf, thr, a.min_faces)
    dst = Path(a.mesh).with_name(Path(a.mesh).stem + "_pred.npz")
    np.savez(dst, face_island_pred=lab, seam_prob=prob, dual_pairs=pairs, threshold=thr)
    print(f"{nf} faces -> {lab.max() + 1} islands (thr={thr}); wrote {dst}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("train")
    t.add_argument("--data-dir"); t.add_argument("--synthetic", type=int, default=0, help="N synthetic boxes (smoke test)")
    t.add_argument("--out", required=True); t.add_argument("--epochs", type=int, default=100)
    t.add_argument("--batch-size", type=int, default=4); t.add_argument("--lr", type=float, default=5e-4)
    t.add_argument("--wd", type=float, default=1e-2); t.add_argument("--hidden", type=int, default=128)
    t.add_argument("--layers", type=int, default=8); t.add_argument("--val-frac", type=float, default=0.1)
    t.add_argument("--rot-aug", choices=["none", "yaw", "full"], default="yaw")
    t.add_argument("--max-faces", type=int, default=30000, help="skip meshes above this (decimate or raise if VRAM allows)"); t.add_argument("--min-faces", type=int, default=8)
    t.add_argument("--pos-weight", type=float, default=-1, help="<=0 means estimate from data")
    t.add_argument("--num-workers", type=int, default=2); t.add_argument("--amp", action="store_true")
    t.add_argument("--resume"); t.add_argument("--seed", type=int, default=0)
    t.set_defaults(fn=cmd_train)
    q = sp.add_parser("predict")
    q.add_argument("--weights", required=True); q.add_argument("--mesh", required=True)
    q.add_argument("--threshold", type=float); q.add_argument("--min-faces", type=int, default=8)
    q.set_defaults(fn=cmd_predict)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()

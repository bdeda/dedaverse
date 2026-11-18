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
"""uv_geometry.py - numpy/scipy-only mesh helpers for UV-island (seam) prediction.

Everything here is torch-free so it can be unit-tested and reused for
preprocessing, labelling and decoding.

Conventions
-----------
* A mesh is (vertices (V,3) float, faces (F,3) int). Triangles only.
* The "dual graph" has one node per face and one edge per mesh edge shared by
  exactly two faces. A dual edge is a *seam* if its two faces belong to
  different UV islands.
* Game assets usually duplicate vertices at UV seams / hard normals, so
  vertices MUST be welded by position before building adjacency; otherwise
  every UV seam looks like a mesh boundary and the label leaks into the input.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

WELD_TOL = 1e-5  # applied after normalisation to [-1, 1]


# --------------------------------------------------------------------------
# basic mesh ops
# --------------------------------------------------------------------------
def normalize_vertices(v: np.ndarray) -> np.ndarray:
    """Centre the bounding box at the origin, scale longest half-extent to 1."""
    lo, hi = v.min(0), v.max(0)
    center = (lo + hi) / 2.0
    scale = max(float((hi - lo).max()) / 2.0, 1e-12)
    return (v - center) / scale


def weld_vertices(vertices: np.ndarray, faces: np.ndarray, tol: float = WELD_TOL):
    """Merge vertices that coincide within `tol` (works for any column count,
    so it also welds UV coordinates). Face order is preserved.

    Quantisation-based: two points straddling a rounding boundary can fail to
    merge. Use a larger tol or pre-weld in your DCC tool if that matters.
    """
    q = np.round(vertices / tol).astype(np.int64)
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    return vertices[first], inv[faces]


def face_geometry(vertices: np.ndarray, faces: np.ndarray):
    """Per-face centroid (F,3), unit normal (F,3) (zeros if degenerate), area (F,)."""
    tri = vertices[faces]
    centroid = tri.mean(axis=1)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    a2 = np.linalg.norm(n, axis=1)
    n = n / np.maximum(a2[:, None], 1e-12)
    return centroid, n, 0.5 * a2


def _components(pairs: np.ndarray, n: int) -> np.ndarray:
    if len(pairs) == 0:
        return np.arange(n, dtype=np.int64)
    adj = coo_matrix((np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    _, lab = connected_components(adj, directed=False)
    return lab.astype(np.int64)


def build_dual_graph(faces: np.ndarray):
    """Face adjacency across manifold edges.

    Returns
      pairs (E,2): face index pairs sharing an edge used by exactly 2 faces
      ev    (E,2): the shared edge's vertex indices
    Non-manifold edges (>2 faces) are skipped.
    """
    F = len(faces)
    e = np.stack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=1).reshape(-1, 2)
    fid = np.repeat(np.arange(F), 3)
    es = np.sort(e, axis=1)
    order = np.lexsort((es[:, 1], es[:, 0]))
    es, fid = es[order], fid[order]
    same = (es[1:] == es[:-1]).all(axis=1)
    gid = np.cumsum(np.concatenate([[True], ~same])) - 1
    counts = np.bincount(gid)
    idx = np.nonzero(same & (counts[gid[:-1]] == 2))[0]
    fa, fb = fid[idx], fid[idx + 1]
    keep = fa != fb
    pairs = np.stack([fa, fb], axis=1)[keep]
    return pairs.astype(np.int64), es[idx][keep].astype(np.int64)


# --------------------------------------------------------------------------
# labels
# --------------------------------------------------------------------------
def islands_from_uv(uv: np.ndarray, faces_uv: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    """UV island id per face: faces are in the same island if they are
    connected through shared UV edges. UV points are welded by value first.
    `faces_uv` must be in the same face order as the 3D faces."""
    _, fuv = weld_vertices(uv.astype(np.float64), faces_uv.astype(np.int64), tol)
    pairs, _ = build_dual_graph(fuv)
    return _components(pairs, len(fuv))


def seam_labels(face_island: np.ndarray, pairs: np.ndarray) -> np.ndarray:
    return (face_island[pairs[:, 0]] != face_island[pairs[:, 1]]).astype(np.float32)


# --------------------------------------------------------------------------
# features
# --------------------------------------------------------------------------
def node_features(centroid, normal, area) -> np.ndarray:
    rel = area / max(float(area.mean()), 1e-12)
    return np.concatenate([normal, centroid, np.log(rel + 1e-3)[:, None]], axis=1).astype(np.float32)


def edge_features(v, centroid, normal, pairs, ev) -> np.ndarray:
    if len(pairs) == 0:
        return np.zeros((0, 4), np.float32)
    a, b = pairs[:, 0], pairs[:, 1]
    cos = (normal[a] * normal[b]).sum(1)
    length = np.linalg.norm(v[ev[:, 0]] - v[ev[:, 1]], axis=1)
    d = centroid[b] - centroid[a]
    dist = np.linalg.norm(d, axis=1)
    conv = ((normal[b] - normal[a]) * d).sum(1) / np.maximum(dist, 1e-12)  # sign ~ convex/concave
    rel_len = length / max(float(length.mean()), 1e-12)
    rel_dist = dist / max(float(dist.mean()), 1e-12)
    return np.stack([cos, np.log(rel_len + 1e-3), np.log(rel_dist + 1e-3), np.clip(conv, -2, 2)], 1).astype(np.float32)


NODE_DIM, EDGE_DIM = 7, 4


def prepare_sample(vertices, faces, face_island=None):
    """Raw mesh -> (x, ef, pairs, y). y is None when face_island is None.
    Face order is preserved, so per-face predictions map back to the input."""
    v = normalize_vertices(np.asarray(vertices, dtype=np.float64))
    v, f = weld_vertices(v, np.asarray(faces, dtype=np.int64), WELD_TOL)
    c, n, area = face_geometry(v, f)
    pairs, ev = build_dual_graph(f)
    ef = edge_features(v, c, n, pairs, ev)
    x = node_features(c, n, area)
    y = None if face_island is None else seam_labels(np.asarray(face_island), pairs)
    return x, ef, pairs, y


# --------------------------------------------------------------------------
# decoding
# --------------------------------------------------------------------------
def decode_islands(seam_prob, pairs, num_faces, thresh=0.5, min_faces=1, max_passes=10) -> np.ndarray:
    """Seam probabilities -> island id per face.

    1. Drop dual edges with prob >= thresh, take connected components.
    2. Optionally merge islands smaller than `min_faces` into the neighbour
       they share the most edges with (repeats up to `max_passes`).
    """
    lab = _components(pairs[np.asarray(seam_prob) < thresh], num_faces)
    if min_faces <= 1 or len(pairs) == 0:
        return lab
    for _ in range(max_passes):
        k = int(lab.max()) + 1
        small = np.bincount(lab, minlength=k) < min_faces
        if not small.any() or small.all():
            break
        la, lb = lab[pairs[:, 0]], lab[pairs[:, 1]]
        cross = la != lb
        la, lb = la[cross], lb[cross]
        src, dst = np.concatenate([la, lb]), np.concatenate([lb, la])
        m = small[src]
        src, dst = src[m], dst[m]
        if len(src) == 0:
            break
        uk, cnt = np.unique(src * k + dst, return_counts=True)
        s, d = uk // k, uk % k
        order = np.lexsort((-cnt, s))
        s, d = s[order], d[order]
        first = np.concatenate([[True], s[1:] != s[:-1]])
        comp = _components(np.stack([s[first], d[first]], 1), k)
        lab = comp[lab]
        _, lab = np.unique(lab, return_inverse=True)
        lab = np.asarray(lab).reshape(-1)
    return lab


# --------------------------------------------------------------------------
# synthetic data for smoke tests
# --------------------------------------------------------------------------
def make_synthetic_cube(n: int, rng: np.random.Generator):
    """Anisotropic box, each side an n x n grid of quads (2 tris each) with
    *duplicated* vertices per side (like a game asset). Island = side id, so
    the true seams are the 12 box edges."""
    g = np.linspace(-1, 1, n + 1)
    uu, vv = np.meshgrid(g, g, indexing="ij")
    scale = rng.uniform(0.5, 1.5, size=3)
    verts, faces, island, off = [], [], [], 0
    idx = np.arange((n + 1) * (n + 1)).reshape(n + 1, n + 1)
    for side in range(6):
        axis, sign = side % 3, (1.0 if side < 3 else -1.0)
        o = [i for i in range(3) if i != axis]
        p = np.zeros(((n + 1) ** 2, 3))
        p[:, o[0]], p[:, o[1]], p[:, axis] = uu.ravel(), vv.ravel(), sign
        a, b = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
        c, d = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
        tri = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)]) + off
        verts.append(p * scale)
        faces.append(tri)
        island.append(np.full(len(tri), side))
        off += len(p)
    v, f, isl = np.concatenate(verts), np.concatenate(faces), np.concatenate(island)
    t = v[f]
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    flip = (nrm * t.mean(1)).sum(1) < 0  # make winding outward
    f[flip] = f[flip][:, ::-1]
    return v, f, isl

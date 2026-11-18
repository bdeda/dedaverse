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
"""Mesh geometry for UV-seam prediction: face graph, labels, features and island decoding.

numpy only, so it is importable (and fully tested) without PyTorch.

Conventions:
    * A mesh is ``vertices (V, 3) float`` and ``faces (F, 3) int`` (triangles only).
    * The *dual graph* has one node per face and one edge per mesh edge shared by exactly two faces.
      A dual edge is a *seam* when its two faces belong to different UV islands.
    * Game assets duplicate vertices along UV seams and hard edges, so vertices must be welded by position
      before adjacency is built. Otherwise every seam looks like a mesh boundary and the label leaks into
      the input.
"""
from dataclasses import dataclass

import numpy as np

__all__ = ['EDGE_DIM', 'NODE_DIM', 'WELD_TOL', 'SeamSample', 'build_dual_graph', 'decode_islands', 'edge_features',
           'face_geometry', 'islands_from_uv', 'label_components', 'make_synthetic_box', 'node_features',
           'normalize_vertices', 'prepare_sample', 'seam_labels', 'weld_vertices']

# Per-face feature count: normal (3), centroid (3), log relative area (1).
NODE_DIM = 7

# Per-dual-edge feature count: dihedral cosine, log relative length, log relative distance, convexity.
EDGE_DIM = 4

# Vertex weld tolerance, applied after normalising the mesh to [-1, 1].
WELD_TOL = 1e-5


@dataclass(eq=False)
class SeamSample:
    """One mesh turned into model inputs (and, when island labels are known, targets).

    Attributes:
        node_feat: ``(F, NODE_DIM)`` float32 face features.
        edge_feat: ``(E, EDGE_DIM)`` float32 dual-edge features.
        pairs: ``(E, 2)`` int64 face indices joined by each dual edge.
        seam: ``(E,)`` float32, 1.0 where the edge is a seam; ``None`` when no labels were given.
    """

    node_feat: np.ndarray
    edge_feat: np.ndarray
    pairs: np.ndarray
    seam: np.ndarray | None = None

    @property
    def num_edges(self) -> int:
        """Number of dual edges."""
        return int(self.pairs.shape[0])

    @property
    def num_faces(self) -> int:
        """Number of faces."""
        return int(self.node_feat.shape[0])


def build_dual_graph(faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Find the face pairs that share a manifold edge.

    Edges used by more than two faces (non-manifold) are skipped.

    Args:
        faces: ``(F, 3)`` integer vertex indices.

    Returns:
        ``pairs`` ``(E, 2)``: indices of the two faces across each shared edge, and ``edge_verts`` ``(E, 2)``:
        the vertex indices of that edge.
    """
    faces = np.asarray(faces, dtype=np.int64)
    corner_edges = np.stack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=1).reshape(-1, 2)
    face_ids = np.repeat(np.arange(len(faces)), 3)
    corner_edges = np.sort(corner_edges, axis=1)
    order = np.lexsort((corner_edges[:, 1], corner_edges[:, 0]))
    corner_edges, face_ids = corner_edges[order], face_ids[order]
    same_as_next = (corner_edges[1:] == corner_edges[:-1]).all(axis=1)
    group = np.cumsum(np.concatenate([[True], ~same_as_next])) - 1
    group_size = np.bincount(group)
    first = np.nonzero(same_as_next & (group_size[group[:-1]] == 2))[0]
    face_a, face_b = face_ids[first], face_ids[first + 1]
    distinct = face_a != face_b
    pairs = np.stack([face_a, face_b], axis=1)[distinct]
    return pairs.astype(np.int64), corner_edges[first][distinct].astype(np.int64)


def decode_islands(seam_prob: np.ndarray, pairs: np.ndarray, num_faces: int, threshold: float = 0.5,
                   min_faces: int = 1, max_passes: int = 10) -> np.ndarray:
    """Turn per-edge seam probabilities into an island id per face.

    Edges with probability at or above ``threshold`` are cut, and the connected pieces are the islands. Islands
    smaller than ``min_faces`` are then merged into the neighbour they share the most edges with.

    Args:
        seam_prob: ``(E,)`` seam probability (or 0/1 label) per dual edge.
        pairs: ``(E, 2)`` dual edges.
        num_faces: Number of faces in the mesh.
        threshold: Probability at which an edge counts as a seam.
        min_faces: Smallest island kept; 1 disables merging.
        max_passes: Upper bound on merge rounds.

    Returns:
        ``(num_faces,)`` int64 island ids, contiguous from 0.
    """
    labels = label_components(pairs[np.asarray(seam_prob) < threshold], num_faces)
    if min_faces <= 1 or len(pairs) == 0:
        return labels
    for _ in range(max_passes):
        merged = _merge_small_islands(labels, pairs, min_faces)
        if merged is None:
            break
        labels = merged
    return labels


def edge_features(vertices: np.ndarray, centroid: np.ndarray, normal: np.ndarray, pairs: np.ndarray,
                  edge_verts: np.ndarray) -> np.ndarray:
    """Per dual edge: dihedral cosine, log relative edge length, log relative centroid distance, convexity.

    Lengths are relative to the mesh mean so the features do not depend on mesh size.

    Args:
        vertices: ``(V, 3)`` welded, normalised vertices.
        centroid: ``(F, 3)`` face centroids.
        normal: ``(F, 3)`` unit face normals.
        pairs: ``(E, 2)`` dual edges.
        edge_verts: ``(E, 2)`` vertex indices of each shared edge.

    Returns:
        ``(E, EDGE_DIM)`` float32 array (empty ``(0, EDGE_DIM)`` when there are no dual edges).
    """
    if len(pairs) == 0:
        return np.zeros((0, EDGE_DIM), np.float32)
    face_a, face_b = pairs[:, 0], pairs[:, 1]
    cosine = (normal[face_a] * normal[face_b]).sum(axis=1)
    length = np.linalg.norm(vertices[edge_verts[:, 0]] - vertices[edge_verts[:, 1]], axis=1)
    offset = centroid[face_b] - centroid[face_a]
    dist = np.linalg.norm(offset, axis=1)
    convexity = ((normal[face_b] - normal[face_a]) * offset).sum(axis=1) / np.maximum(dist, 1e-12)
    rel_length = length / max(float(length.mean()), 1e-12)
    rel_dist = dist / max(float(dist.mean()), 1e-12)
    return np.stack([cosine, np.log(rel_length + 1e-3), np.log(rel_dist + 1e-3), np.clip(convexity, -2, 2)],
                    axis=1).astype(np.float32)


def face_geometry(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centroid, unit normal and area of every triangle.

    Args:
        vertices: ``(V, 3)`` positions.
        faces: ``(F, 3)`` vertex indices.

    Returns:
        ``centroid`` ``(F, 3)``, ``normal`` ``(F, 3)`` (zero for degenerate faces) and ``area`` ``(F,)``.
    """
    tri = vertices[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    return tri.mean(axis=1), cross / np.maximum(double_area[:, None], 1e-12), 0.5 * double_area


def islands_from_uv(uv: np.ndarray, faces_uv: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    """UV island id per face from UV connectivity.

    Faces share an island when they are joined across a UV edge. UV points are welded by value first, so
    per-corner UV arrays work. ``faces_uv`` must list faces in the same order as the 3D faces.

    Args:
        uv: ``(U, 2)`` UV coordinates.
        faces_uv: ``(F, 3)`` indices into ``uv``.
        tol: Weld tolerance for coincident UV points.

    Returns:
        ``(F,)`` int64 island ids, contiguous from 0.
    """
    _, welded = weld_vertices(np.asarray(uv, dtype=np.float64), np.asarray(faces_uv, dtype=np.int64), tol)
    pairs, _ = build_dual_graph(welded)
    return label_components(pairs, len(welded))


def label_components(pairs: np.ndarray, num_nodes: int) -> np.ndarray:
    """Connected components of an undirected graph (numpy only; no scipy needed).

    Repeats minimum-label propagation along the edges with pointer jumping until nothing changes.

    Args:
        pairs: ``(E, 2)`` node index pairs.
        num_nodes: Number of nodes.

    Returns:
        ``(num_nodes,)`` int64 component ids, numbered from 0 in order of each component's lowest node.
    """
    label = np.arange(num_nodes, dtype=np.int64)
    if len(pairs) == 0:
        return label
    node_a, node_b = pairs[:, 0], pairs[:, 1]
    while True:
        lower = np.minimum(label[node_a], label[node_b])
        updated = label.copy()
        np.minimum.at(updated, node_a, lower)
        np.minimum.at(updated, node_b, lower)
        updated = updated[updated]
        if np.array_equal(updated, label):
            break
        label = updated
    _, dense = np.unique(label, return_inverse=True)
    return dense.reshape(-1).astype(np.int64)


def make_synthetic_box(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """An anisotropic box with ``n x n`` quads per side, for smoke tests.

    Each side has its own copy of the vertices (as in a game asset with split UVs) and is one island, so the
    true seams are the 12 box edges.

    Args:
        n: Quads per box side edge.
        rng: Random generator (sets the box proportions).

    Returns:
        ``vertices``, ``faces`` (outward winding) and ``face_island`` (side index, 0 to 5).
    """
    grid = np.linspace(-1, 1, n + 1)
    grid_u, grid_v = np.meshgrid(grid, grid, indexing='ij')
    scale = rng.uniform(0.5, 1.5, size=3)
    index = np.arange((n + 1) * (n + 1)).reshape(n + 1, n + 1)
    verts, faces, island, offset = [], [], [], 0
    for side in range(6):
        axis, sign = side % 3, (1.0 if side < 3 else -1.0)
        others = [i for i in range(3) if i != axis]
        points = np.zeros(((n + 1) ** 2, 3))
        points[:, others[0]], points[:, others[1]], points[:, axis] = grid_u.ravel(), grid_v.ravel(), sign
        c00, c01 = index[:-1, :-1].ravel(), index[:-1, 1:].ravel()
        c10, c11 = index[1:, :-1].ravel(), index[1:, 1:].ravel()
        tris = np.concatenate([np.stack([c00, c10, c01], 1), np.stack([c01, c10, c11], 1)]) + offset
        verts.append(points * scale)
        faces.append(tris)
        island.append(np.full(len(tris), side))
        offset += len(points)
    all_verts, all_faces, all_island = np.concatenate(verts), np.concatenate(faces), np.concatenate(island)
    tri = all_verts[all_faces]
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    inward = (normal * tri.mean(axis=1)).sum(axis=1) < 0
    all_faces[inward] = all_faces[inward][:, ::-1]
    return all_verts, all_faces, all_island


def node_features(centroid: np.ndarray, normal: np.ndarray, area: np.ndarray) -> np.ndarray:
    """Per face: normal, centroid and log area relative to the mesh mean.

    Args:
        centroid: ``(F, 3)`` face centroids.
        normal: ``(F, 3)`` unit face normals.
        area: ``(F,)`` face areas.

    Returns:
        ``(F, NODE_DIM)`` float32 array.
    """
    relative = area / max(float(area.mean()), 1e-12)
    return np.concatenate([normal, centroid, np.log(relative + 1e-3)[:, None]], axis=1).astype(np.float32)


def normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    """Centre the bounding box on the origin and scale its longest half-extent to 1.

    Args:
        vertices: ``(V, 3)`` positions (at least one vertex).

    Returns:
        ``(V, 3)`` positions in ``[-1, 1]``.
    """
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    half_extent = max(float((high - low).max()) / 2.0, 1e-12)
    return (vertices - (low + high) / 2.0) / half_extent


def prepare_sample(vertices: np.ndarray, faces: np.ndarray, face_island: np.ndarray | None = None) -> SeamSample:
    """Raw mesh to model inputs, plus seam labels when island ids are given.

    Face order is preserved, so per-face predictions map straight back onto the input mesh.

    Args:
        vertices: ``(V, 3)`` positions.
        faces: ``(F, 3)`` vertex indices.
        face_island: Optional ``(F,)`` UV island id per face.

    Returns:
        The prepared :class:`SeamSample`.

    Raises:
        ValueError: If the arrays have the wrong shape or a face index is out of range.
    """
    _validate_mesh(vertices, faces, face_island)
    welded, tris = weld_vertices(normalize_vertices(np.asarray(vertices, dtype=np.float64)),
                                 np.asarray(faces, dtype=np.int64), WELD_TOL)
    centroid, normal, area = face_geometry(welded, tris)
    pairs, edge_verts = build_dual_graph(tris)
    seam = None if face_island is None else seam_labels(np.asarray(face_island), pairs)
    return SeamSample(node_feat=node_features(centroid, normal, area),
                      edge_feat=edge_features(welded, centroid, normal, pairs, edge_verts), pairs=pairs, seam=seam)


def seam_labels(face_island: np.ndarray, pairs: np.ndarray) -> np.ndarray:
    """1.0 for dual edges whose faces are in different islands, else 0.0.

    Args:
        face_island: ``(F,)`` island id per face.
        pairs: ``(E, 2)`` dual edges.

    Returns:
        ``(E,)`` float32 labels.
    """
    return (face_island[pairs[:, 0]] != face_island[pairs[:, 1]]).astype(np.float32)


def weld_vertices(vertices: np.ndarray, faces: np.ndarray, tol: float = WELD_TOL) -> tuple[np.ndarray, np.ndarray]:
    """Merge vertices that coincide within ``tol``; face order is preserved.

    Works for any column count, so it also welds UV coordinates. The merge snaps points to a grid, so two points
    straddling a grid boundary can stay separate; pre-weld in your DCC tool if that matters.

    Args:
        vertices: ``(V, D)`` points.
        faces: ``(F, 3)`` indices into ``vertices``.
        tol: Grid size used to decide that points coincide.

    Returns:
        The merged ``(V', D)`` points and ``faces`` re-indexed into them.

    Raises:
        ValueError: If ``tol`` is not positive.
    """
    if tol <= 0:
        raise ValueError(f'tol must be positive, got {tol}')
    snapped = np.round(vertices / tol).astype(np.int64)
    _, first, inverse = np.unique(snapped, axis=0, return_index=True, return_inverse=True)
    return vertices[first], np.asarray(inverse).reshape(-1)[faces]


def _merge_small_islands(labels: np.ndarray, pairs: np.ndarray, min_faces: int) -> np.ndarray | None:
    """One merge round: join every island under ``min_faces`` to its most-shared neighbour.

    Returns the new labels, or ``None`` when there is nothing left to merge.
    """
    count = int(labels.max()) + 1
    small = np.bincount(labels, minlength=count) < min_faces
    if not small.any() or small.all():
        return None
    label_a, label_b = labels[pairs[:, 0]], labels[pairs[:, 1]]
    cross = label_a != label_b
    label_a, label_b = label_a[cross], label_b[cross]
    source, target = np.concatenate([label_a, label_b]), np.concatenate([label_b, label_a])
    from_small = small[source]
    source, target = source[from_small], target[from_small]
    if len(source) == 0:
        return None
    keys, shared = np.unique(source * count + target, return_counts=True)
    key_source, key_target = keys // count, keys % count
    order = np.lexsort((-shared, key_source))
    key_source, key_target = key_source[order], key_target[order]
    best = np.concatenate([[True], key_source[1:] != key_source[:-1]])
    merge_map = label_components(np.stack([key_source[best], key_target[best]], axis=1), count)
    _, dense = np.unique(merge_map[labels], return_inverse=True)
    return dense.reshape(-1).astype(np.int64)


def _validate_mesh(vertices: np.ndarray, faces: np.ndarray, face_island: np.ndarray | None) -> None:
    """Raise ``ValueError`` unless the mesh arrays are consistent."""
    vertices, faces = np.asarray(vertices), np.asarray(faces)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) == 0:
        raise ValueError(f'vertices must have shape (V, 3) with V > 0, got {vertices.shape}')
    if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0:
        raise ValueError(f'faces must have shape (F, 3) with F > 0, got {faces.shape}')
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError('faces reference vertices that do not exist')
    if face_island is not None and np.asarray(face_island).shape != (len(faces),):
        raise ValueError(f'face_island must have shape ({len(faces)},), got {np.asarray(face_island).shape}')

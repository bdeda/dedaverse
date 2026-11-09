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
"""Artist-style UV layout for flat assets: find the mid-plane, project each side, unwrap only the walls.

A flat prop (axe, sword, shield, plank) is unwrapped by an artist with one planar projection of the front,
one of the back (mirrored so it reads the right way round) and separate strips for the side walls. This
module makes every decision of that layout on plain arrays, so it is testable without Blender; the Blender
job supplies the arrays and applies the result.

Faces are labelled ``FRONT`` (1), ``BACK`` (-1) or ``SIDE`` (0). Edges are given as ``edge_faces``: an
``(E, 2)`` array of the two faces sharing each edge, ``-1`` for a border edge.

numpy only: this module is also imported by the job that runs inside Blender's Python.
"""
__all__ = ['AUTO_MIN_SHARE', 'BACK', 'FRONT', 'MIN_ISLAND_FACES', 'SIDE', 'choose_uv_method', 'classify_faces',
           'edge_faces_from_loops', 'final_seams', 'in_plane_basis', 'merge_small_islands', 'planar_uvs',
           'projected_share', 'symmetry_plane']

from collections.abc import Callable

import numpy as np

BACK, SIDE, FRONT = -1, 0, 1

#: Islands with fewer faces are merged into a neighbour (noise slivers).
MIN_ISLAND_FACES = 8

#: Share of the surface the front and back projections must cover for ``auto`` to pick ``symmetry``.
AUTO_MIN_SHARE = 0.55


def choose_uv_method(requested: str, share: float) -> str:
    """Resolve the ``uv_method`` option to the method that runs.

    Args:
        requested: ``'auto'``, ``'symmetry'`` or ``'seams'`` (validated by ``OptimizeOptions``).
        share: Fraction of the surface area the front/back projections would cover.

    Returns:
        ``'symmetry'`` or ``'seams'``. ``auto`` picks symmetry for flat assets (``share >= AUTO_MIN_SHARE``).
    """
    if requested == 'auto':
        return 'symmetry' if share >= AUTO_MIN_SHARE else 'seams'
    return requested


def classify_faces(smooth_facing: np.ndarray, real_facing: np.ndarray, areas: np.ndarray,
                   edge_faces: np.ndarray, facing: float = 0.6, passes: int = 6,
                   min_piece: int = 12) -> np.ndarray:
    """Label each face front, back or side.

    Facing is judged on the overall form (normals of a smoothed copy), as an artist would, so surface noise
    does not punch holes in the projections. Area-weighted majority votes then remove speckle, and front/back
    pieces too small to be worth their own island become side faces.

    Args:
        smooth_facing: Dot product of each face's smoothed normal with the plane normal.
        real_facing: The same for the real normal; a face is never projected onto a side it points away from.
        areas: Face areas.
        edge_faces: ``(E, 2)`` faces on each edge, ``-1`` for border edges.
        facing: Minimum ``|smooth_facing|`` for a face to be projected (0.6 is about 53 degrees).
        passes: Majority-vote passes.
        min_piece: Front/back pieces with fewer faces become side faces.

    Returns:
        ``(F,)`` int array of ``FRONT``, ``BACK`` and ``SIDE``.
    """
    smooth_facing = np.asarray(smooth_facing, dtype=np.float64)
    real_facing = np.asarray(real_facing, dtype=np.float64)
    areas = np.asarray(areas, dtype=np.float64)
    pairs = _interior(edge_faces)
    labels = np.where(smooth_facing > facing, FRONT, np.where(smooth_facing < -facing, BACK, SIDE))
    labels[labels * real_facing <= 0.05] = SIDE
    for _ in range(passes):
        votes = np.zeros((len(labels), 3))
        np.add.at(votes, (pairs[:, 0], labels[pairs[:, 1]] + 1), areas[pairs[:, 1]])
        np.add.at(votes, (pairs[:, 1], labels[pairs[:, 0]] + 1), areas[pairs[:, 0]])
        votes[np.arange(len(labels)), labels + 1] += areas * 1.2
        new = votes.argmax(axis=1) - 1
        new[new * real_facing <= 0.05] = SIDE
        if np.array_equal(new, labels):
            break
        labels = new
    comp = _components(len(labels), pairs, labels[pairs[:, 0]] == labels[pairs[:, 1]])
    sizes = np.bincount(comp)
    labels[(labels != SIDE) & (sizes[comp] < min_piece)] = SIDE
    return labels


def edge_faces_from_loops(loop_edges: np.ndarray, loop_faces: np.ndarray, edge_count: int) -> np.ndarray:
    """Build ``edge_faces`` from each face corner's edge and face.

    Args:
        loop_edges: ``(L,)`` edge index of each corner.
        loop_faces: ``(L,)`` face index of each corner.
        edge_count: Number of edges.

    Returns:
        ``(E, 2)`` the first two faces using each edge, ``-1`` where there are fewer (borders, loose edges).
    """
    edge_faces = np.full((edge_count, 2), -1, dtype=np.int64)
    loop_edges = np.asarray(loop_edges, dtype=np.int64)
    if loop_edges.size == 0:
        return edge_faces
    order = np.argsort(loop_edges, kind='stable')
    edges, faces = loop_edges[order], np.asarray(loop_faces, dtype=np.int64)[order]
    index = np.arange(len(edges))
    start = np.maximum.accumulate(np.where(np.r_[True, edges[1:] != edges[:-1]], index, 0))
    rank = index - start
    for column in (0, 1):
        edge_faces[edges[rank == column], column] = faces[rank == column]
    return edge_faces


def final_seams(labels: np.ndarray, side_seams: np.ndarray, edge_faces: np.ndarray) -> np.ndarray:
    """Seams for the layout: every border between labels, plus the cuts inside the side walls.

    Args:
        labels: Face labels.
        side_seams: ``(E,)`` cuts chosen for the side walls (ignored elsewhere).
        edge_faces: ``(E, 2)`` faces on each edge.

    Returns:
        ``(E,)`` bool seam flags.
    """
    edge_faces = np.asarray(edge_faces)
    interior = (edge_faces >= 0).all(axis=1)
    a = np.asarray(labels)[np.where(interior, edge_faces[:, 0], 0)]
    b = np.asarray(labels)[np.where(interior, edge_faces[:, 1], 0)]
    return interior & ((a != b) | (np.asarray(side_seams, dtype=bool) & (a == SIDE) & (b == SIDE)))


def in_plane_basis(points: np.ndarray, normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two unit axes spanning the plane: ``b`` along the longest in-plane extent, ``a = normal x b``.

    Args:
        points: ``(N, 3)`` positions.
        normal: Unit plane normal.

    Returns:
        ``(a, b)``; projecting onto them gives an upright, right-handed view from the front.
    """
    normal = np.asarray(normal, dtype=np.float64)
    centred = np.asarray(points, dtype=np.float64) - np.mean(points, axis=0)
    flat = centred - np.outer(centred @ normal, normal)
    b = np.linalg.svd(flat, full_matrices=False)[2][0]
    b = b - (b @ normal) * normal
    b /= np.linalg.norm(b)
    return np.cross(normal, b), b


def merge_small_islands(labels: np.ndarray, side_seams: np.ndarray, edge_faces: np.ndarray,
                        edge_lengths: np.ndarray, min_faces: int = MIN_ISLAND_FACES,
                        max_rounds: int = 6) -> tuple[np.ndarray, np.ndarray]:
    """Join islands with fewer than ``min_faces`` faces to the neighbour they share the longest border with.

    Noisy generated surfaces leave single triangles cut off by the seams; each costs a UV island, extra GPU
    vertices and packing space for no gain. A small piece joining a projected side takes that side's label
    (and its planar projection); one joining a side-wall island loses the seams between them.

    Args:
        labels: Face labels.
        side_seams: ``(E,)`` cuts inside the side walls.
        edge_faces: ``(E, 2)`` faces on each edge.
        edge_lengths: ``(E,)`` edge lengths.
        min_faces: Islands with fewer faces are merged.
        max_rounds: Merge passes (merged pieces can still be small and merge again).

    Returns:
        New ``(labels, side_seams)``.
    """
    labels = np.array(labels, copy=True)
    side_seams = np.array(side_seams, dtype=bool, copy=True)
    edge_faces = np.asarray(edge_faces)
    interior = (edge_faces >= 0).all(axis=1)
    pairs = edge_faces[interior]
    pair_edges = np.nonzero(interior)[0]
    lengths = np.asarray(edge_lengths, dtype=np.float64)[interior]
    for _ in range(max_rounds):
        cut = final_seams(labels, side_seams, edge_faces)[interior]
        comp = _components(len(labels), pairs, ~cut)
        sizes = np.bincount(comp)
        a, b = comp[pairs[:, 0]], comp[pairs[:, 1]]
        changed = False
        for small in np.nonzero(sizes < min_faces)[0]:
            faces = comp == small
            if faces.sum() >= min_faces:   # grew earlier this round by absorbing other pieces
                continue
            target = _longest_neighbour(small, a, b, cut, lengths)
            if target is None:
                continue
            target_label = labels[np.argmax(comp == target)]
            labels[faces] = target_label
            if target_label == SIDE:
                between = ((a == small) & (b == target)) | ((a == target) & (b == small))
                side_seams[pair_edges[between]] = False
            comp[faces] = target   # later merges this round see the grown island
            a, b = comp[pairs[:, 0]], comp[pairs[:, 1]]
            cut = final_seams(labels, side_seams, edge_faces)[interior]
            changed = True
        if not changed:
            break
    return labels, side_seams


def planar_uvs(positions: np.ndarray, labels: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Planar projection of face corners: the front as seen from the front, the back mirrored.

    Args:
        positions: ``(L, 3)`` position of each face corner.
        labels: ``(L,)`` label of each corner's face; side corners get ``(0, 0)``.
        a: In-plane horizontal axis.
        b: In-plane vertical axis.

    Returns:
        ``(L, 2)`` UVs in scene units (packing scales them into the 0-1 square).
    """
    positions = np.asarray(positions, dtype=np.float64)
    labels = np.asarray(labels)
    uv = np.column_stack([labels * (positions @ np.asarray(a)), positions @ np.asarray(b)])
    uv[labels == SIDE] = 0.0
    return uv


def projected_share(labels: np.ndarray, areas: np.ndarray) -> float:
    """Fraction of the surface area labelled front or back."""
    areas = np.asarray(areas, dtype=np.float64)
    total = areas.sum()
    return float(areas[np.asarray(labels) != SIDE].sum() / total) if total > 0 else 0.0


def symmetry_plane(points: np.ndarray, nearest: Callable[[np.ndarray], np.ndarray], samples: int = 1500,
                   seed: int = 0) -> tuple[np.ndarray, np.ndarray, float]:
    """Find the mirror plane between the front and back of a flat asset.

    Starts from the thinnest principal axis, then searches small tilts and offsets for the plane that
    best maps the surface onto itself when mirrored.

    Args:
        points: ``(N, 3)`` vertex positions.
        nearest: Returns the distance from each of an ``(M, 3)`` array of points to the nearest vertex.
        samples: Vertices used to score each candidate plane.
        seed: Random seed for the sample, so results are repeatable.

    Returns:
        ``(normal, origin, error)``: unit normal, a point on the plane, and the mean mirror error as a
        fraction of the bounding-box diagonal (0 for a perfectly symmetric shape).
    """
    points = np.asarray(points, dtype=np.float64)
    centre = points.mean(axis=0)
    axes = np.linalg.svd(points - centre, full_matrices=False)[2]
    normal0, side, along = axes[2], axes[1], axes[0]
    diagonal = float(np.linalg.norm(np.ptp(points, axis=0))) or 1.0
    thickness = float(np.ptp((points - centre) @ normal0))
    rng = np.random.default_rng(seed)
    sample = points[rng.choice(len(points), min(samples, len(points)), replace=False)]

    def score(normal: np.ndarray, offset: float) -> float:
        distance = (sample - centre) @ normal - offset
        return float(np.mean(nearest(sample - 2.0 * distance[:, None] * normal)))

    best = (score(normal0, 0.0), normal0, 0.0)
    for span, steps in ((np.radians(8.0), 9), (np.radians(1.5), 7)):
        base_normal, base_offset = best[1], best[2]
        tilts = np.tan(np.linspace(-span, span, steps))
        for ta in tilts:
            for tb in tilts:
                normal = base_normal + ta * side + tb * along
                normal /= np.linalg.norm(normal)
                for offset in base_offset + np.linspace(-0.15, 0.15, 7) * thickness:
                    error = score(normal, offset)
                    if error < best[0]:
                        best = (error, normal, offset)
    error, normal, offset = best
    return normal, centre + offset * normal, error / diagonal


# --- Internal -------------------------------------------------------------------------

def _components(count: int, pairs: np.ndarray, connect: np.ndarray) -> np.ndarray:
    """Connected-component id per face, joining the face pairs where ``connect`` is set."""
    parent = np.arange(count)

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for f, g in pairs[np.asarray(connect, dtype=bool)]:
        rf, rg = root(f), root(g)
        if rf != rg:
            parent[rf] = rg
    roots = np.array([root(i) for i in range(count)], dtype=np.int64)
    return np.unique(roots, return_inverse=True)[1].reshape(-1) if count else roots


def _interior(edge_faces: np.ndarray) -> np.ndarray:
    edge_faces = np.asarray(edge_faces, dtype=np.int64).reshape(-1, 2)
    return edge_faces[(edge_faces >= 0).all(axis=1)]


def _longest_neighbour(island: int, a: np.ndarray, b: np.ndarray, cut: np.ndarray,
                       lengths: np.ndarray) -> int | None:
    """The island sharing the longest cut border with ``island``, or None when it has no neighbour."""
    out = cut & (a == island) & (b != island)
    into = cut & (b == island) & (a != island)
    neighbours = np.concatenate([b[out], a[into]])
    if neighbours.size == 0:
        return None
    shared = np.concatenate([lengths[out], lengths[into]])
    ids, inverse = np.unique(neighbours, return_inverse=True)
    return int(ids[np.bincount(inverse, weights=shared).argmax()])

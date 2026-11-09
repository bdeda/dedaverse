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
"""Mesh and UV measurements used to score an optimized asset.

numpy only: this module is also imported by the job that runs inside Blender's Python, which ships numpy.
"""
__all__ = ['bake_distances', 'error_stats', 'flip_green', 'uv_metrics']

import numpy as np

_SAMPLE_X = 0.5 + 1.234e-4
_SAMPLE_Y = 0.5 + 3.217e-4


def bake_distances(max_error: float, diagonal: float) -> tuple[float, float]:
    """Pick the cage extrusion and max ray distance for a high-to-low bake.

    Rays must reach past the largest gap between the two surfaces, but not so far that they hit
    a neighbouring part. The distance is 2.5x the measured worst gap, clamped to 1-8% of the size.

    Args:
        max_error: Largest measured distance between the high- and low-poly surfaces.
        diagonal: Bounding-box diagonal of the asset.

    Returns:
        ``(cage_extrusion, max_ray_distance)`` in scene units.
    """
    ray = float(np.clip(2.5 * max_error, 0.01 * diagonal, 0.08 * diagonal))
    return ray / 3.0, ray


def error_stats(distances: np.ndarray, diagonal: float) -> dict[str, float]:
    """Summarise surface distances as percentages of the bounding-box diagonal.

    Args:
        distances: Distances between the two surfaces (NaN entries are ignored).
        diagonal: Bounding-box diagonal of the asset.

    Returns:
        ``mean_pct``, ``p99_pct`` and ``max_pct``.
    """
    d = np.asarray(distances, dtype=np.float64)
    d = d[~np.isnan(d)]
    if d.size == 0 or diagonal <= 0:
        return {'mean_pct': 0.0, 'p99_pct': 0.0, 'max_pct': 0.0}
    scale = 100.0 / diagonal
    return {'mean_pct': round(float(d.mean()) * scale, 4),
            'p99_pct': round(float(np.percentile(d, 99)) * scale, 4),
            'max_pct': round(float(d.max()) * scale, 4)}


def flip_green(pixels: np.ndarray, channels: int = 4) -> np.ndarray:
    """Convert a normal map between the OpenGL (Y+) and DirectX (Y-) conventions.

    Args:
        pixels: Flat or shaped float pixel buffer in 0-1, ``channels`` values per pixel.
        channels: Values per pixel (Blender images are RGBA).

    Returns:
        A new buffer of the same shape with the green channel inverted.
    """
    out = np.array(pixels, dtype=np.float32, copy=True)
    flat = out.reshape(-1, channels)
    flat[:, 1] = 1.0 - flat[:, 1]
    return out


def uv_metrics(positions: np.ndarray, loop_vertices: np.ndarray, loop_uvs: np.ndarray,
               face_loop_starts: np.ndarray, tri_loops: np.ndarray, raster: int = 512) -> dict:
    """Score a UV layout for a game mesh.

    Args:
        positions: ``(V, 3)`` vertex positions.
        loop_vertices: ``(L,)`` vertex index of each face corner.
        loop_uvs: ``(L, 2)`` UV of each face corner.
        face_loop_starts: ``(F,)`` first corner of each face (corners of a face are contiguous).
        tri_loops: ``(T, 3)`` corner indices of each triangle after triangulating the faces.
        raster: Resolution of the coverage/overlap raster.

    Returns:
        ``uv_islands``; ``gpu_verts`` (unique vertex+UV pairs, what the GPU actually stores);
        ``uv_coverage`` (fraction of the UV square used); ``overlap`` (fraction of used texels
        claimed twice); ``area_distortion`` (area-weighted mean |log2| of UV-to-3D area ratio,
        0 = even texel density); ``angle_distortion_deg``; ``out_of_bounds``.
    """
    positions = np.asarray(positions, dtype=np.float64)
    loop_vertices = np.asarray(loop_vertices, dtype=np.int64)
    loop_uvs = np.asarray(loop_uvs, dtype=np.float64)
    tri_loops = np.asarray(tri_loops, dtype=np.int64).reshape(-1, 3)

    keys = _corner_keys(loop_vertices, loop_uvs)
    p3 = positions[loop_vertices[tri_loops]]
    p2 = loop_uvs[tri_loops]
    area3 = 0.5 * np.linalg.norm(np.cross(p3[:, 1] - p3[:, 0], p3[:, 2] - p3[:, 0]), axis=1)
    e1, e2 = p2[:, 1] - p2[:, 0], p2[:, 2] - p2[:, 0]
    area2 = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    valid = (area3 > 1e-12) & (area2 > 1e-14)
    coverage, overlap = _raster_coverage(p2, raster)
    return {
        'uv_islands': _island_count(keys, np.asarray(face_loop_starts, dtype=np.int64), len(loop_vertices)),
        'gpu_verts': int(keys.max() + 1) if keys.size else 0,
        'uv_coverage': round(coverage, 4),
        'overlap': round(overlap, 4),
        'area_distortion': round(_area_distortion(area3[valid], area2[valid]), 4),
        'angle_distortion_deg': round(_angle_distortion(p3[valid], p2[valid], area3[valid]), 3),
        'out_of_bounds': bool(loop_uvs.size and ((loop_uvs < -1e-4).any() or (loop_uvs > 1 + 1e-4).any())),
    }


# --- Internal -------------------------------------------------------------------------

def _angle_distortion(p3: np.ndarray, p2: np.ndarray, weights: np.ndarray) -> float:
    if p3.size == 0 or weights.sum() <= 0:
        return 0.0
    diff = np.abs(_corner_angles(p3) - _corner_angles(p2)).mean(axis=1)
    return float(np.degrees(np.sum(diff * weights) / weights.sum()))


def _area_distortion(area3: np.ndarray, area2: np.ndarray) -> float:
    if area3.size == 0:
        return 0.0
    ratio = (area2 / area2.sum()) / (area3 / area3.sum())
    weights = area3 / area3.sum()
    return float(np.sum(weights * np.abs(np.log2(ratio))))


def _corner_angles(tris: np.ndarray) -> np.ndarray:
    out = []
    for i in range(3):
        a = tris[:, (i + 1) % 3] - tris[:, i]
        b = tris[:, (i + 2) % 3] - tris[:, i]
        cos = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-20)
        out.append(np.arccos(np.clip(cos, -1.0, 1.0)))
    return np.stack(out, axis=1)


def _corner_keys(loop_vertices: np.ndarray, loop_uvs: np.ndarray) -> np.ndarray:
    """Id per corner such that corners sharing a vertex and a UV share an id (a GPU vertex)."""
    if loop_vertices.size == 0:
        return np.zeros(0, dtype=np.int64)
    table = np.column_stack([loop_vertices.astype(np.float64), np.round(loop_uvs, 6)])
    _, inverse = np.unique(table, axis=0, return_inverse=True)
    return inverse.reshape(-1).astype(np.int64)


def _island_count(keys: np.ndarray, face_loop_starts: np.ndarray, loop_count: int) -> int:
    """Faces are in one island when they share a corner key; count the connected groups."""
    if face_loop_starts.size == 0:
        return 0
    loop_face = np.repeat(np.arange(len(face_loop_starts)), np.diff(np.append(face_loop_starts, loop_count)))
    parent = np.arange(len(face_loop_starts))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = np.argsort(keys, kind='stable')
    sorted_keys, sorted_faces = keys[order], loop_face[order]
    for j in np.nonzero(sorted_keys[1:] == sorted_keys[:-1])[0]:
        a, b = root(sorted_faces[j]), root(sorted_faces[j + 1])
        if a != b:
            parent[a] = b
    return len({root(i) for i in range(len(parent))})


def _raster_coverage(tris: np.ndarray, size: int) -> tuple[float, float]:
    """Rasterise UV triangles; return (fraction of texels covered, fraction of covered texels overlapped)."""
    counts = np.zeros((size, size), dtype=np.uint16)
    for tri in tris * size:
        x0, y0 = np.maximum(np.floor(tri.min(axis=0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(tri.max(axis=0)).astype(int), size)
        if x1 <= x0 or y1 <= y0:
            continue
        (ax, ay), (bx, by), (cx, cy) = tri
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        # Sample just off the texel centre so an edge shared by two triangles is not counted for both.
        xs, ys = np.meshgrid(np.arange(x0, x1) + _SAMPLE_X, np.arange(y0, y1) + _SAMPLE_Y)
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
        counts[y0:y1, x0:x1] += ((l1 >= 0) & (l2 >= 0) & (1 - l1 - l2 >= 0)).astype(np.uint16)
    covered = int(np.count_nonzero(counts))
    if not covered:
        return 0.0, 0.0
    return covered / counts.size, int(np.count_nonzero(counts > 1)) / covered

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
"""Convert USD mesh data (already read into numpy arrays) into the arrays the training code uses. numpy only.

USD stores a mesh as polygons: ``faceVertexCounts`` (corners per face), ``faceVertexIndices`` (corner -> point) and
UVs as a ``primvar`` that is either per corner (``faceVarying``) or per point (``vertex``), optionally indexed.
The seam model needs triangles plus, for labels, which UV island each triangle belongs to. This module does that
conversion without importing ``pxr``, so it is fast to test; :mod:`deda.core.ai.uv_seams._usd` reads the stage.
"""
from collections.abc import Iterable
from pathlib import Path

import numpy as np

__all__ = ['UV_INTERPOLATIONS', 'USD_SUFFIXES', 'find_usd_files', 'usd_mesh_to_arrays', 'z_up_to_y_up']

USD_SUFFIXES = ('.usd', '.usda', '.usdc', '.usdz')
UV_INTERPOLATIONS = ('faceVarying', 'varying', 'vertex')


def find_usd_files(paths: Iterable[Path | str]) -> list[Path]:
    """Expand a mix of USD files and directories into one sorted list of USD files.

    Directories are searched recursively. A path that is a file is kept as given, whatever its suffix, so an
    explicitly listed file is never silently dropped. Duplicates are removed.

    Args:
        paths: USD files and/or directories, possibly from several different locations.

    Returns:
        Sorted, de-duplicated list of files.

    Raises:
        FileNotFoundError: If an entry does not exist.
    """
    found: dict[Path, None] = {}
    for entry in paths:
        path = Path(entry)
        if path.is_dir():
            for child in path.rglob('*'):
                if child.is_file() and child.suffix.lower() in USD_SUFFIXES:
                    found[child] = None
        elif path.is_file():
            found[path] = None
        else:
            raise FileNotFoundError(f'USD path not found: {path}')
    return sorted(found)


def usd_mesh_to_arrays(points: np.ndarray, face_vertex_counts: np.ndarray, face_vertex_indices: np.ndarray,
                       uv_values: np.ndarray, uv_indices: np.ndarray | None = None,
                       uv_interpolation: str = 'faceVarying',
                       flip_winding: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Triangulate a USD polygon mesh together with its UVs.

    Convex polygons are split into fans from their first corner, and concave ones by ear clipping in the polygon's
    best-fit plane, so no triangle folds over. The same split is applied to the UV indices, so the ``i``-th triangle
    of ``faces`` and of ``faces_uv`` describe the same corners. Triangles keep the polygon's winding.

    Args:
        points: ``(V, 3)`` mesh points.
        face_vertex_counts: ``(F,)`` corners per polygon, each at least 3.
        face_vertex_indices: ``(sum counts,)`` point index of every corner.
        uv_values: ``(U, 2)`` UV primvar values.
        uv_indices: Primvar indices when the primvar is indexed, else ``None``.
        uv_interpolation: ``'faceVarying'`` (one UV per corner), or ``'vertex'`` / ``'varying'`` (one per point).
        flip_winding: Reverse every triangle, e.g. for a left-handed mesh, so winding is consistent across assets.

    Returns:
        ``(vertices (V, 3) float64, faces (T, 3) int64, uv (U, 2) float64, faces_uv (T, 3) int64)``.

    Raises:
        ValueError: On an unsupported interpolation (``uniform`` and ``constant`` carry no seam information),
            inconsistent array sizes, a polygon with fewer than 3 corners, an out-of-range index, or a concave
            polygon that cannot be triangulated (for example one that crosses itself).
    """
    if uv_interpolation not in UV_INTERPOLATIONS:
        raise ValueError(f'unsupported UV interpolation {uv_interpolation!r}; need one of {UV_INTERPOLATIONS}')
    vertices = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    counts = np.asarray(face_vertex_counts, dtype=np.int64).reshape(-1)
    corners = np.asarray(face_vertex_indices, dtype=np.int64).reshape(-1)
    uv = np.asarray(uv_values, dtype=np.float64).reshape(-1, 2)
    if len(counts) == 0 or counts.min() < 3:
        raise ValueError('mesh needs at least one face and every face needs 3 or more corners')
    if int(counts.sum()) != len(corners):
        raise ValueError(f'faceVertexCounts sum to {int(counts.sum())} but there are {len(corners)} corner indices')
    if corners.min() < 0 or corners.max() >= len(vertices):
        raise ValueError('faceVertexIndices refer to points that do not exist')
    corner_uv = _corner_uv_indices(corners, len(vertices), len(uv), uv_indices, uv_interpolation)

    tri_corners = _triangulate(vertices, counts, corners)
    faces, faces_uv = corners[tri_corners], corner_uv[tri_corners]
    if flip_winding:
        faces, faces_uv = faces[:, [0, 2, 1]], faces_uv[:, [0, 2, 1]]
    return vertices, faces, uv, faces_uv


def z_up_to_y_up(vertices: np.ndarray) -> np.ndarray:
    """Rotate Z-up points to Y-up (a proper rotation of -90 degrees about X: ``(x, y, z) -> (x, z, -y)``).

    Args:
        vertices: ``(V, 3)`` points.

    Returns:
        A new ``(V, 3)`` array.
    """
    points = np.asarray(vertices, dtype=np.float64)
    return np.stack([points[:, 0], points[:, 2], -points[:, 1]], axis=1)


def _corner_uv_indices(corners: np.ndarray, num_points: int, num_uv: int, uv_indices: np.ndarray | None,
                       interpolation: str) -> np.ndarray:
    """UV index of every polygon corner, for either interpolation, indexed or not."""
    explicit = None if uv_indices is None else np.asarray(uv_indices, dtype=np.int64).reshape(-1)
    if interpolation == 'faceVarying':
        if explicit is None:
            if num_uv != len(corners):
                raise ValueError(f'faceVarying UVs need one value per corner ({len(corners)}), got {num_uv}')
            result = np.arange(len(corners), dtype=np.int64)
        else:
            if len(explicit) != len(corners):
                raise ValueError(f'faceVarying UV indices need one per corner ({len(corners)}), got {len(explicit)}')
            result = explicit
    else:
        if explicit is None:
            if num_uv != num_points:
                raise ValueError(f'{interpolation} UVs need one value per point ({num_points}), got {num_uv}')
            result = corners
        else:
            if len(explicit) != num_points:
                raise ValueError(f'{interpolation} UV indices need one per point ({num_points}), got {len(explicit)}')
            result = explicit[corners]
    if result.min() < 0 or result.max() >= num_uv:
        raise ValueError('UV indices refer to UV values that do not exist')
    return result


def _ear_clip(points: np.ndarray) -> list[tuple[int, int, int]]:
    """Triangulate one simple polygon given counter-clockwise in 2D.

    Args:
        points: ``(n, 2)`` corners, counter-clockwise.

    Returns:
        ``n - 2`` triangles as local corner indices, all counter-clockwise.

    Raises:
        ValueError: If no ear can be found (the polygon crosses itself or is degenerate).
    """
    span = float(np.ptp(points, axis=0).max()) if len(points) else 0.0
    eps = 1e-12 * max(span * span, 1e-300)

    def turn(a: int, b: int, c: int) -> float:
        (ax, ay), (bx, by), (cx, cy) = points[a], points[b], points[c]
        return float((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))

    remaining = list(range(len(points)))
    triangles = []
    while len(remaining) > 3:
        size = len(remaining)
        for k in range(size):
            prev, ear, nxt = remaining[k - 1], remaining[k], remaining[(k + 1) % size]
            if turn(prev, ear, nxt) <= eps:
                continue  # reflex or flat corner: not an ear
            corners = points[[prev, ear, nxt]]
            blocked = False
            for other in remaining:
                if other in (prev, ear, nxt) or (np.abs(corners - points[other]).max(axis=1) <= 0.0).any():
                    continue
                if turn(prev, ear, other) >= -eps and turn(ear, nxt, other) >= -eps and turn(nxt, prev, other) >= -eps:
                    blocked = True
                    break
            if not blocked:
                triangles.append((prev, ear, nxt))
                del remaining[k]
                break
        else:
            raise ValueError('concave polygon cannot be triangulated (it may cross itself)')
    triangles.append((remaining[0], remaining[1], remaining[2]))
    return triangles


def _triangulate(points: np.ndarray, counts: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Split polygons into triangles: fans for convex polygons, ear clipping for concave ones.

    Args:
        points: ``(V, 3)`` mesh points.
        counts: ``(F,)`` corners per polygon (at least 3 each).
        corners: ``(sum counts,)`` point index of every corner.

    Returns:
        ``(sum(counts - 2), 3)`` int64 triangles as indices into the corner arrays, polygon by polygon.

    Raises:
        ValueError: If a concave polygon cannot be triangulated.
    """
    first = np.cumsum(counts) - counts
    tri_counts = counts - 2
    tri_first = np.cumsum(tri_counts) - tri_counts
    tri_face = np.repeat(np.arange(len(counts)), tri_counts)
    fan = np.arange(int(tri_counts.sum())) - tri_first[tri_face] + 1
    base = first[tri_face]
    triangles = np.stack([base, base + fan, base + fan + 1], axis=1)

    position = points[corners]
    polygon = np.repeat(np.arange(len(counts)), counts)
    index = np.arange(len(corners))
    local = index - first[polygon]
    following = np.where(local == counts[polygon] - 1, first[polygon], index + 1)
    preceding = np.where(local == 0, first[polygon] + counts[polygon] - 1, index - 1)
    normal = np.add.reduceat(np.cross(position, position[following]), first, axis=0)  # Newell normal (2x area)
    length = np.linalg.norm(normal, axis=1)
    edge_in, edge_out = position - position[preceding], position[following] - position
    perimeter = np.add.reduceat(np.linalg.norm(edge_out, axis=1), first)
    turn = np.einsum('ij,ij->i', np.cross(edge_in, edge_out), normal[polygon])
    scale = np.linalg.norm(edge_in, axis=1) * np.linalg.norm(edge_out, axis=1) * length[polygon]
    reflex = np.zeros(len(counts), dtype=bool)
    np.logical_or.at(reflex, polygon, turn < -1e-9 * scale)
    # Flat or zero-area polygons keep the fan: no plane to clip in, and no worse than before.
    concave = reflex & (counts > 3) & (length > 1e-9 * perimeter * perimeter)

    for face in np.nonzero(concave)[0]:
        unit = normal[face] / length[face]
        axis_u = np.cross(unit, np.eye(3)[int(np.argmin(np.abs(unit)))])
        axis_u /= np.linalg.norm(axis_u)
        axis_v = np.cross(unit, axis_u)
        own = position[first[face]:first[face] + counts[face]]
        flat = np.stack([own @ axis_u, own @ axis_v], axis=1)
        local_tris = np.asarray(_ear_clip(flat), dtype=np.int64)
        triangles[tri_first[face]:tri_first[face] + tri_counts[face]] = local_tris + first[face]
    return triangles

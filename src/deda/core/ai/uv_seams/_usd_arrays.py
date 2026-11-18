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

    Polygons are split into fans from their first corner; the same split is applied to the UV indices so the
    ``i``-th triangle of ``faces`` and of ``faces_uv`` describe the same corners.

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
            inconsistent array sizes, a polygon with fewer than 3 corners, or an out-of-range index.
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

    first = np.cumsum(counts) - counts
    tri_counts = counts - 2
    tri_face = np.repeat(np.arange(len(counts)), tri_counts)
    fan = np.arange(int(tri_counts.sum())) - np.repeat(np.cumsum(tri_counts) - tri_counts, tri_counts) + 1
    base = first[tri_face]
    tri_corners = np.stack([base, base + fan, base + fan + 1], axis=1)
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

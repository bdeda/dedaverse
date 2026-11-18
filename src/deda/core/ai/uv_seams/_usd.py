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
"""Read meshes and their UV layouts from USD files and hand them to the seam training code.

Each ``UsdGeomMesh`` that has the chosen UV primvar becomes one training sample: points and triangles come from the
mesh, and the UV layout the artist authored is passed on as the label source, so every UV discontinuity (including a
cut inside one island) becomes a seam label. Everything is converted in memory; no intermediate files are written.

Conventions: time is the earliest authored time code; a Z-up stage is rotated to Y-up so rotation augmentation and
the model see one up axis; left-handed meshes (and mirrored world transforms) have their winding reversed.
Meshes under instanceable prims are not visited. Subdivision surfaces are read as their control cage.
"""
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pxr import Tf, Usd, UsdGeom

from ._data import split_paths
from ._geometry import UvLayout
from ._usd_arrays import UV_INTERPOLATIONS, usd_mesh_to_arrays, z_up_to_y_up

__all__ = ['UsdMeshRef', 'UsdSource', 'list_usd_meshes', 'load_usd_mesh', 'split_usd_sources']

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsdMeshRef:
    """Where one mesh lives: a USD file and the path of the mesh prim inside it.

    Attributes:
        path: The USD file.
        prim_path: Prim path of the ``UsdGeomMesh``, e.g. ``/Asset/Geom/Body``.
    """

    path: Path
    prim_path: str


class UsdSource:
    """A :class:`~deda.core.ai.uv_seams.MeshSource` over USD meshes (one item per mesh prim).

    The stage is opened when an item is requested, so the source stays small and can be pickled for DataLoader
    workers.
    """

    def __init__(self, refs: Sequence[UsdMeshRef], uv_set: str = 'st', world_space: bool = False) -> None:
        """Wrap a list of mesh references.

        Args:
            refs: Meshes to serve, usually from :func:`list_usd_meshes`.
            uv_set: Name of the UV primvar (without the ``primvars:`` prefix).
            world_space: Bake each mesh's local-to-world transform into its points.
        """
        self.refs = list(refs)
        self.uv_set = uv_set
        self.world_space = world_space

    def __len__(self) -> int:
        return len(self.refs)

    def get(self, index: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, UvLayout]:
        """Load mesh ``index`` as ``(vertices, faces, uv_layout)``.

        Raises:
            ValueError: If the file or mesh cannot be read.
        """
        del rng  # loading is deterministic
        return load_usd_mesh(self.refs[index], self.uv_set, self.world_space)


def list_usd_meshes(path: Path | str, uv_set: str = 'st') -> list[UsdMeshRef]:
    """Find the meshes in a USD file that can be used for training.

    A mesh qualifies when it has the UV primvar ``uv_set`` and converts cleanly. Meshes without that UV set are
    skipped quietly; meshes whose data is inconsistent are skipped with a warning. An unreadable file gives an empty
    list and a warning, so one bad file does not stop a run over many files.

    Args:
        path: The USD file.
        uv_set: Name of the UV primvar.

    Returns:
        References to the usable meshes, in stage traversal order.
    """
    path = Path(path)
    try:
        stage = _open_stage(path)
    except ValueError as err:
        log.warning('%s', err)
        return []
    time = Usd.TimeCode.EarliestTime()
    refs = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        primvar = UsdGeom.PrimvarsAPI(prim).GetPrimvar(uv_set)
        if not primvar.IsDefined() or primvar.GetInterpolation() not in UV_INTERPOLATIONS:
            log.debug('%s: no usable %r UVs on %s', path, uv_set, prim.GetPath())
            continue
        try:
            _mesh_arrays(prim, uv_set, time, flip_winding=False)
        except ValueError as err:
            log.warning('%s: skipping %s: %s', path, prim.GetPath(), err)
            continue
        refs.append(UsdMeshRef(path, str(prim.GetPath())))
    return refs


def load_usd_mesh(ref: UsdMeshRef, uv_set: str = 'st',
                  world_space: bool = False) -> tuple[np.ndarray, np.ndarray, UvLayout]:
    """Read one mesh and convert it to the arrays the training code takes.

    Args:
        ref: Which mesh to read.
        uv_set: Name of the UV primvar whose layout defines the islands.
        world_space: Bake the mesh's local-to-world transform into its points (otherwise local space is used).

    Returns:
        ``(vertices (V, 3) float64, faces (T, 3) int64, uv_layout)``: the triangulated mesh, Y-up, and its
        :class:`~deda.core.ai.uv_seams.UvLayout` (same triangle order), from which seam labels are read.

    Raises:
        ValueError: If the file cannot be opened, the prim is not a mesh, or its data is missing or inconsistent.
    """
    stage = _open_stage(ref.path)
    prim = stage.GetPrimAtPath(ref.prim_path)
    if not prim.IsValid() or not prim.IsA(UsdGeom.Mesh):
        raise ValueError(f'{ref.path}: {ref.prim_path} is not a mesh')
    time = Usd.TimeCode.EarliestTime()
    matrix = _world_matrix(prim, time) if world_space else None
    mirrored = matrix is not None and bool(np.linalg.det(matrix[:3, :3]) < 0)
    left_handed = UsdGeom.Mesh(prim).GetOrientationAttr().Get(time) == UsdGeom.Tokens.leftHanded
    try:
        vertices, faces, uv, faces_uv = _mesh_arrays(prim, uv_set, time, flip_winding=left_handed != mirrored)
    except ValueError as err:
        raise ValueError(f'{ref.path}: {ref.prim_path}: {err}') from err
    if matrix is not None:
        vertices = vertices @ matrix[:3, :3] + matrix[3, :3]
    if UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z:
        vertices = z_up_to_y_up(vertices)
    return vertices, faces, UvLayout(uv, faces_uv)


def split_usd_sources(files: Sequence[Path], val_frac: float, seed: int,
                      group_key: Callable[[Path], str] | None = None, uv_set: str = 'st',
                      world_space: bool = False) -> tuple[UsdSource, UsdSource]:
    """Scan USD files and split their meshes into training and validation sources.

    The split is by file (or by ``group_key`` group), so meshes of one asset never straddle it. Files with no usable
    mesh are skipped with a warning before splitting, so neither side can end up empty.

    Args:
        files: USD files, from any directories.
        val_frac: Fraction of groups held out for validation.
        seed: Seed for the group shuffle.
        group_key: Maps a file to its group name (see :func:`~deda.core.ai.uv_seams.regex_group_key`).
        uv_set: Name of the UV primvar.
        world_space: Bake local-to-world transforms into the points.

    Returns:
        ``(train_source, val_source)``.

    Raises:
        ValueError: If no file has a usable mesh, or fewer than two groups remain to split.
    """
    by_file: dict[Path, list[UsdMeshRef]] = {}
    for path in files:
        refs = list_usd_meshes(path, uv_set)
        if refs:
            by_file[Path(path)] = refs
        else:
            log.warning('%s: no usable meshes with UV set %r; skipped', path, uv_set)
    if not by_file:
        raise ValueError(f'no usable meshes with UV set {uv_set!r} in {len(files)} USD file(s)')
    train_files, val_files = split_paths(list(by_file), val_frac, seed, group_key)
    train = [ref for path in train_files for ref in by_file[path]]
    val = [ref for path in val_files for ref in by_file[path]]
    return UsdSource(train, uv_set, world_space), UsdSource(val, uv_set, world_space)


def _mesh_arrays(prim: Usd.Prim, uv_set: str, time: Usd.TimeCode,
                 flip_winding: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Read a mesh prim's points, polygons and UV primvar and triangulate them.

    Raises:
        ValueError: If points, faces or the UV primvar are missing or inconsistent.
    """
    mesh = UsdGeom.Mesh(prim)
    points = mesh.GetPointsAttr().Get(time)
    counts = mesh.GetFaceVertexCountsAttr().Get(time)
    corners = mesh.GetFaceVertexIndicesAttr().Get(time)
    if points is None or counts is None or corners is None:
        raise ValueError('mesh has no points or faces')
    primvar = UsdGeom.PrimvarsAPI(prim).GetPrimvar(uv_set)
    values = primvar.Get(time) if primvar.IsDefined() else None
    if values is None:
        raise ValueError(f'mesh has no {uv_set!r} UV values')
    uv_indices = np.asarray(primvar.GetIndices(time), dtype=np.int64) if primvar.IsIndexed() else None
    return usd_mesh_to_arrays(np.asarray(points), np.asarray(counts), np.asarray(corners), np.asarray(values),
                              uv_indices, primvar.GetInterpolation(), flip_winding)


def _open_stage(path: Path) -> Usd.Stage:
    """Open a USD file.

    Raises:
        ValueError: If USD cannot open it.
    """
    try:
        return Usd.Stage.Open(str(path))
    except Tf.ErrorException as err:
        raise ValueError(f'cannot open USD file {path}: {err}') from err


def _world_matrix(prim: Usd.Prim, time: Usd.TimeCode) -> np.ndarray:
    """Local-to-world transform as a 4x4 numpy array in USD's row-vector convention (translation in row 3)."""
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(time)
    return np.array([list(row) for row in matrix], dtype=np.float64)

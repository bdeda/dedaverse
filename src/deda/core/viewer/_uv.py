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
"""UV data for the UV editor: reading UV sets off a USD mesh and analysing their layout.

Everything here is plain numpy over ``pxr`` types, with no Qt, so it is unit-testable and can be
reused by the mesh tools that will edit and optimise UVs later.

A UV set is a texture-coordinate primvar (``primvars:st`` and friends). USD stores its values with an
interpolation that says how they map onto the mesh; :meth:`UvLayout.from_mesh` resolves any of them
to one UV per face corner, which is the form every analysis below works on.
"""

__all__ = ['UvLayout', 'UvSet', 'UvStats', 'list_meshes', 'read_uv_layouts', 'udim_tile']

import logging
from dataclasses import dataclass, field

import numpy as np
from pxr import Sdf, Usd, UsdGeom

log = logging.getLogger(__name__)

# Faces whose UV area is smaller than this are reported as degenerate (collapsed) rather than flipped.
_DEGENERATE_AREA = 1e-12


@dataclass(frozen=True)
class UvSet:
    """One texture-coordinate primvar as authored on a mesh.

    Attributes:
        name: The primvar name without the ``primvars:`` prefix, e.g. ``st``.
        interpolation: The USD interpolation token (``faceVarying``, ``vertex``, ...).
        values: The authored UV values, shape ``(N, 2)``.
        indices: The authored index array, or None when the primvar is not indexed.
    """

    name: str
    interpolation: str
    values: np.ndarray
    indices: np.ndarray | None = None


@dataclass(frozen=True)
class UvStats:
    """Summary numbers for a :class:`UvLayout`.

    Attributes:
        face_count: Number of faces.
        island_count: Number of connected UV shells.
        flipped_count: Faces whose UV winding is opposite to the majority (mirrored or inside out).
        degenerate_count: Faces collapsed to (almost) zero UV area.
        bounds: ``(u_min, v_min, u_max, v_max)`` over every UV.
        tiles: The UDIM tile numbers the faces sit in, sorted.
        coverage: Fraction of the 0-1 tile covered by face area (overlaps count more than once).
    """

    face_count: int
    island_count: int
    flipped_count: int
    degenerate_count: int
    bounds: tuple[float, float, float, float]
    tiles: tuple[int, ...]
    coverage: float


@dataclass
class UvLayout:
    """A UV set resolved to one UV per face corner, with the mesh topology needed to analyse it.

    Corner arrays are laid out in the mesh's ``faceVertexIndices`` order, so corner ``i`` belongs to
    face ``face_of_corner[i]`` and its neighbour around the face is ``next_corner[i]``.

    Attributes:
        uv_set: The set this layout was resolved from.
        face_counts: Vertex count of every face.
        uvs: One UV per face corner, shape ``(C, 2)``.
        uv_ids: One id per corner; corners that share a UV vertex share an id.
    """

    uv_set: UvSet
    face_counts: np.ndarray
    uvs: np.ndarray
    uv_ids: np.ndarray
    face_of_corner: np.ndarray = field(init=False, repr=False)
    next_corner: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        counts = np.asarray(self.face_counts, dtype=np.int64)
        self.face_counts = counts
        self.face_of_corner = np.repeat(np.arange(len(counts)), counts)
        starts = np.cumsum(counts) - counts
        nxt = np.arange(int(counts.sum())) + 1
        nxt[(starts + counts - 1)[counts > 0]] = starts[counts > 0]
        self.next_corner = nxt

    def bounds(self) -> tuple[float, float, float, float]:
        """``(u_min, v_min, u_max, v_max)`` over every UV, or the 0-1 tile when there are none."""
        if not len(self.uvs):
            return 0.0, 0.0, 1.0, 1.0
        lo, hi = self.uvs.min(axis=0), self.uvs.max(axis=0)
        return float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])

    def edge_segments(self) -> tuple[np.ndarray, np.ndarray]:
        """The UV wireframe as unique segments.

        Returns:
            ``(segments, is_border)``: segments shaped ``(E, 4)`` as ``u0, v0, u1, v1``, and a bool
            per segment that is True where only one face uses the edge (a shell border).
        """
        a_ids, b_ids = self.uv_ids, self.uv_ids[self.next_corner]
        lo, hi = np.minimum(a_ids, b_ids), np.maximum(a_ids, b_ids)
        span = int(hi.max()) + 1 if len(hi) else 1
        keys = lo * span + hi
        _, first, counts = np.unique(keys, return_index=True, return_counts=True)
        starts = self.uvs[first]
        ends = self.uvs[self.next_corner[first]]
        return np.hstack([starts, ends]), counts == 1

    def face_centroids(self) -> np.ndarray:
        """The mean UV of every face, shape ``(F, 2)``."""
        counts = np.maximum(self.face_counts, 1)[:, None]
        sums = np.stack([np.bincount(self.face_of_corner, weights=self.uvs[:, k],
                                     minlength=self.face_count) for k in (0, 1)], axis=1)
        return sums / counts

    @property
    def face_count(self) -> int:
        """Number of faces."""
        return len(self.face_counts)

    def flipped_faces(self) -> np.ndarray:
        """Bool per face: True where the UV winding is opposite to the majority of the faces.

        Whether counter-clockwise or clockwise is the 'right' way round depends on how the UVs were
        authored, so the majority of the non-degenerate faces decides.
        """
        areas = self.signed_areas()
        live = np.abs(areas) > _DEGENERATE_AREA
        if not live.any():
            return np.zeros(self.face_count, dtype=bool)
        majority_positive = (areas[live] > 0).sum() * 2 >= live.sum()
        return live & ((areas < 0) if majority_positive else (areas > 0))

    @classmethod
    def from_mesh(cls, uv_set: UvSet, face_counts, face_indices) -> 'UvLayout | None':
        """Resolve `uv_set` against a mesh's topology.

        Args:
            uv_set: The UV set to resolve.
            face_counts: The mesh ``faceVertexCounts``.
            face_indices: The mesh ``faceVertexIndices``.

        Returns:
            The layout, or None when the UV data does not fit the mesh (wrong length, indices out
            of range, or an interpolation with no per-corner meaning).
        """
        counts = np.asarray(face_counts, dtype=np.int64)
        verts = np.asarray(face_indices, dtype=np.int64)
        corner_count = int(counts.sum())
        if corner_count != len(verts):
            return None
        values = np.asarray(uv_set.values, dtype=np.float64).reshape(-1, 2)
        lookup = (np.arange(len(values)) if uv_set.indices is None
                  else np.asarray(uv_set.indices, dtype=np.int64))
        if lookup.size and (lookup.min() < 0 or lookup.max() >= len(values)):
            return None

        interp = uv_set.interpolation
        if interp == 'faceVarying':
            slots = lookup
            ids = lookup
        elif interp in ('vertex', 'varying'):
            if verts.size and (verts.max() >= len(lookup)):
                return None
            slots = lookup[verts]
            ids = verts
        elif interp == 'uniform':
            if len(lookup) != len(counts):
                return None
            slots = np.repeat(lookup, counts)
            ids = np.repeat(np.arange(len(counts)), counts)
        elif interp == 'constant':
            if len(lookup) != 1:
                return None
            slots = np.zeros(corner_count, dtype=np.int64)
            ids = slots
        else:
            return None
        if len(slots) != corner_count:
            return None
        return cls(uv_set, counts, values[slots], ids.astype(np.int64))

    def island_labels(self) -> np.ndarray:
        """Label every face with its connected UV shell, numbered from 0.

        Faces are connected when they share a UV edge (both end points are the same UV vertices), so
        shells that merely touch at a corner stay separate, matching how DCC UV editors treat shells.
        """
        face_count = self.face_count
        labels = np.arange(face_count)
        if face_count == 0:
            return labels
        a_ids, b_ids = self.uv_ids, self.uv_ids[self.next_corner]
        lo, hi = np.minimum(a_ids, b_ids), np.maximum(a_ids, b_ids)
        span = int(hi.max()) + 1
        order = np.argsort(lo * span + hi, kind='stable')
        keys = (lo * span + hi)[order]
        faces = self.face_of_corner[order]
        same = keys[1:] == keys[:-1]
        left, right = faces[:-1][same], faces[1:][same]
        while True:
            smaller = np.minimum(labels[left], labels[right])
            before = labels.copy()
            np.minimum.at(labels, left, smaller)
            np.minimum.at(labels, right, smaller)
            labels = labels[labels]  # pointer jumping: follow each label to its root
            if np.array_equal(labels, before):
                break
        return np.unique(labels, return_inverse=True)[1]

    def signed_areas(self) -> np.ndarray:
        """The signed UV area of every face (shoelace); counter-clockwise is positive."""
        nxt = self.uvs[self.next_corner]
        cross = self.uvs[:, 0] * nxt[:, 1] - nxt[:, 0] * self.uvs[:, 1]
        return 0.5 * np.bincount(self.face_of_corner, weights=cross, minlength=self.face_count)

    def stats(self) -> UvStats:
        """Summarise the layout."""
        areas = self.signed_areas()
        degenerate = np.abs(areas) <= _DEGENERATE_AREA
        centroids = self.face_centroids()
        tiles = sorted({udim_tile(u, v) for u, v in centroids}) if self.face_count else []
        in_first = (centroids[:, 0] >= 0) & (centroids[:, 0] < 1) & (centroids[:, 1] >= 0) & (centroids[:, 1] < 1)
        labels = self.island_labels()
        return UvStats(
            face_count=self.face_count,
            island_count=int(labels.max()) + 1 if len(labels) else 0,
            flipped_count=int(self.flipped_faces().sum()),
            degenerate_count=int(degenerate.sum()),
            bounds=self.bounds(),
            tiles=tuple(tiles),
            coverage=float(np.abs(areas[in_first]).sum()),
        )


def list_meshes(stage: Usd.Stage | None) -> list[Usd.Prim]:
    """Every mesh prim on `stage`, instance proxies included, in traversal order."""
    if stage is None:
        return []
    return [prim for prim in Usd.PrimRange(stage.GetPseudoRoot(), Usd.TraverseInstanceProxies())
            if prim.IsA(UsdGeom.Mesh)]


def read_uv_layouts(prim: Usd.Prim, time: Usd.TimeCode = Usd.TimeCode.Default()) -> list[UvLayout]:
    """Read every UV set on a mesh prim and resolve each against the mesh topology.

    A float2 or texCoord2f array primvar counts as a UV set. Sets whose data does not fit the mesh
    are skipped with a warning rather than failing the rest.

    Args:
        prim: A prim holding a ``UsdGeom.Mesh``.
        time: When to sample; falls back to the earliest sample for time-sampled-only data.

    Returns:
        The layouts, in primvar order. Empty when `prim` is not a mesh.
    """
    if not prim or not prim.IsA(UsdGeom.Mesh):
        return []
    mesh = UsdGeom.Mesh(prim)
    counts = _get(mesh.GetFaceVertexCountsAttr(), time)
    indices = _get(mesh.GetFaceVertexIndicesAttr(), time)
    if counts is None or indices is None:
        return []
    layouts = []
    for primvar in UsdGeom.PrimvarsAPI(prim).GetPrimvars():
        if not _is_uv_type(primvar.GetTypeName()):
            continue
        values = _get(primvar.GetAttr(), time)
        if values is None:
            continue
        name = primvar.GetPrimvarName()
        index_attr = primvar.GetIndicesAttr()
        index_values = _get(index_attr, time) if index_attr and index_attr.HasValue() else None
        uv_set = UvSet(name=str(name), interpolation=str(primvar.GetInterpolation()),
                       values=np.array(values, dtype=np.float64).reshape(-1, 2),
                       indices=None if index_values is None else np.array(index_values, dtype=np.int64))
        layout = UvLayout.from_mesh(uv_set, np.array(counts), np.array(indices))
        if layout is None:
            log.warning(f'UV set {name!r} on {prim.GetPath()} does not match the mesh topology; skipped')
            continue
        layouts.append(layout)
    return layouts


def udim_tile(u: float, v: float) -> int:
    """The UDIM tile number containing (u, v): 1001 for the 0-1 tile, +1 per tile in U (up to 10 wide)
    and +10 per tile in V."""
    return 1001 + int(np.floor(u)) + 10 * int(np.floor(v))


def _get(attr: Usd.Attribute, time: Usd.TimeCode):
    """Value of `attr` at `time`, else at its earliest sample, else None."""
    value = attr.Get(time)
    return value if value is not None else attr.Get(Usd.TimeCode.EarliestTime())


def _is_uv_type(type_name) -> bool:
    """True for the primvar value types UV sets are authored with."""
    return type_name in (Sdf.ValueTypeNames.TexCoord2fArray, Sdf.ValueTypeNames.Float2Array)

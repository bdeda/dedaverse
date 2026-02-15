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
"""Collection type for the asset system."""

import os
from pathlib import Path

from pxr import Kind, Sdf, Tf, Usd

from ._asset import Asset

__all__ = ['Collection']


def _create_entity_usda(
    usda_path: Path,
    path_segments: list[str],
    kind_tokens: Kind.Tokens,
    *,
    asset_identifier: str | None = None,
) -> None:
    """Create a USDA file with a hierarchy of Scope prims and set the leaf's kind.

    path_segments is the full prim path segments (e.g. ["KCRC", "Assets", "Monsters", "Cletus"]).
    The leaf prim gets the given kind (e.g. group or model). If asset_identifier is set,
    the leaf gets assetInfo (SetAssetName, SetAssetIdentifier).

    Args:
        usda_path: Path to the USDA file to create.
        path_segments: Full prim path segment names from root to leaf.
        kind_tokens: Kind for the leaf prim (e.g. Kind.Tokens.group, Kind.Tokens.model).
        asset_identifier: If set, set assetInfo on the leaf (for assets).
    """
    usda_path = Path(usda_path)
    usda_path.parent.mkdir(parents=True, exist_ok=True)
    if usda_path.exists():
        stage = Usd.Stage.Open(str(usda_path))
        for prim in list(stage.GetPseudoRoot().GetChildren()):
            stage.RemovePrim(prim.GetPath())
    else:
        stage = Usd.Stage.CreateNew(str(usda_path))
    if not path_segments:
        stage.GetRootLayer().Save()
        return
    # Build hierarchy: /seg0/seg1/.../segN; set kind on each (ancestors = group, leaf = kind_tokens)
    path = Sdf.Path("/" + path_segments[0])
    prim = stage.DefinePrim(path, "Scope")
    is_leaf = len(path_segments) == 1
    Usd.ModelAPI(prim).SetKind(kind_tokens if is_leaf else Kind.Tokens.group)
    for i, seg in enumerate(path_segments[1:], start=1):
        path = path.AppendChild(seg)
        prim = stage.DefinePrim(path, "Scope")
        is_leaf = i == len(path_segments) - 1
        Usd.ModelAPI(prim).SetKind(kind_tokens if is_leaf else Kind.Tokens.group)
    stage.SetDefaultPrim(prim)
    if asset_identifier:
        model_api = Usd.ModelAPI(prim)
        model_api.SetAssetName(path_segments[-1])
        model_api.SetAssetIdentifier(Sdf.AssetPath(asset_identifier))
    stage.GetRootLayer().Save()


def _asset_id_string(parent: Asset, name: str) -> str:
    """Build asset identifier in form project_name:collection_name:...:name::."""
    parts: list[str] = []
    p = parent
    while p is not None:
        parts.append(p.name)
        p = p.parent
    parts.reverse()
    parts.append(name)
    return ":".join(parts) + "::"


class Collection(Asset):
    """Asset that groups other Assets, Sequences, or Shots.

    A Collection organizes assets hierarchically. Project and Sequence are
    specializations. Inherits the full Entity API.
    """

    def __init__(self, name, parent):
        super().__init__(name, parent)

    def add_asset(self, name: str) -> Asset:
        """Add a new asset as a child of this collection.

        Validates the name, creates the asset's USDA file with a prim for every
        level of the hierarchy (from root scope down to this child), sets Kind
        to Model and assetInfo.
        Adds the child's USDA as a sublayer on this collection's layer.

        Args:
            name: Prim name for the new asset (must be a valid USD identifier).

        Returns:
            The new Asset instance (parent is this collection).

        Raises:
            ValueError: If name is not a valid identifier (Tf.IsValidIdentifier).
        """
        if not Tf.IsValidIdentifier(name):
            raise ValueError(f"Invalid prim identifier: {name!r}")
        proj = self.project
        child_prim_path = f"{self.prim_path}/{name}"
        asset_dir = proj.asset_directory_for_prim_path(child_prim_path)
        asset_dir.mkdir(parents=True, exist_ok=True)
        child_path = self.children_metadata_dir / f"{name}.usda"
        if self.parent is None:
            path_segments = [name]
        else:
            path_segments = self.prim_path.strip("/").split("/") + [name]
        _create_entity_usda(
            child_path,
            path_segments,
            Kind.Tokens.model,
            asset_identifier=_asset_id_string(self, name),
        )
        _add_child_reference(self, name, child_path)
        return Asset(name, self)

    def add_collection(self, name: str) -> "Collection":
        """Add a new collection as a child of this collection.

        Validates the name, creates the collection's USDA file with a prim for
        every level of the hierarchy (from root scope down to this child), sets
        Kind to Group. Adds the
        child's USDA as a sublayer on this collection's layer.

        Args:
            name: Prim name for the new collection (must be a valid USD identifier).

        Returns:
            The new Collection instance (parent is this collection).

        Raises:
            ValueError: If name is not a valid identifier (Tf.IsValidIdentifier).
        """
        if not Tf.IsValidIdentifier(name):
            raise ValueError(f"Invalid prim identifier: {name!r}")
        proj = self.project
        child_prim_path = f"{self.prim_path}/{name}"
        asset_dir = proj.asset_directory_for_prim_path(child_prim_path)
        asset_dir.mkdir(parents=True, exist_ok=True)
        child_path = self.children_metadata_dir / f"{name}.usda"
        if self.parent is None:
            path_segments = [name]
        else:
            path_segments = self.prim_path.strip("/").split("/") + [name]
        _create_entity_usda(child_path, path_segments, Kind.Tokens.group)
        _add_child_reference(self, name, child_path)
        return Collection(name, self)

    def remove_child(self, name: str) -> bool:
        """Remove a child from this collection's USDA metadata by removing its prim.

        Does not delete the child's USDA file on disk.

        Args:
            name: Name of the child asset or collection to remove.

        Returns:
            True if the child prim was found and removed, False otherwise.
        """
        child_path = self.children_metadata_dir / f"{name}.usda"
        return _remove_child_reference(self, name, child_path)

    def get_immediate_children(self) -> list[dict]:
        """Return immediate child prims of this collection on the project stage.

        Only direct children (one level below this scope) are returned, not
        descendants. Each item is a dict with keys: name, type ('Collection' or
        'Asset'), is_collection (True for Collection, False for Asset). For the
        project, uses the default prim's children (child references).

        Returns:
            List of dicts suitable for use in the Assets panel grid.
        """
        stage = self.project.stage
        if stage is None:
            return []
        if self.parent is None:
            default_prim = stage.GetDefaultPrim()
            prim = default_prim if default_prim.IsValid() else stage.GetPseudoRoot()
        else:
            prim = stage.GetPrimAtPath(self.prim_path)
            if not prim.IsValid():
                return []
        scope_path = prim.GetPath()
        result = []
        for child in prim.GetChildren():
            if child.GetPath().GetParentPath() != scope_path:
                continue
            name = child.GetName()
            kind = Usd.ModelAPI(child).GetKind()
            typ = 'Collection' if kind == Kind.Tokens.group else 'Asset'
            custom = child.GetCustomData() if hasattr(child, 'GetCustomData') else {}
            if not custom:
                custom = {}
            result.append({
                'name': name,
                'type': custom.get('asset_type', typ),
                'is_collection': typ == 'Collection',
                'description': (custom.get('description') or '') if isinstance(custom.get('description'), str) else '',
                'title': (custom.get('title') or '') if isinstance(custom.get('title'), str) else '',
            })
        return result

    def iter_assets(self):
        for prim in self.project.stage.TraverseAll():
            yield Asset._from_prim(prim)


def _add_child_reference(parent: Collection, name: str, child_path: Path) -> None:
    """Add a child prim on the parent's layer that references the child's USDA file."""
    parent_path = parent.metadata_path.resolve()
    parent_dir = parent_path.parent
    rel = os.path.relpath(str(child_path.resolve()), str(parent_dir))
    rel = rel.replace("\\", "/")
    layer = Sdf.Layer.FindOrOpen(str(parent_path))
    if layer is None:
        raise RuntimeError(f"Parent layer not found: {parent_path}")
    stage = Usd.Stage.Open(layer)
    child_prim_path = parent.prim_path + "/" + name
    child_prim = stage.DefinePrim(Sdf.Path(child_prim_path), "Scope")
    child_prim.GetReferences().AddReference(rel)
    stage.GetRootLayer().Save()
    proj = parent.project
    if hasattr(proj, "_stage"):
        proj._stage = None


def _remove_child_reference(parent: Collection, name: str, child_path: Path) -> bool:
    """Remove the child prim from the parent's layer. Returns True if removed."""
    parent_path = parent.metadata_path.resolve()
    layer = Sdf.Layer.FindOrOpen(str(parent_path))
    if layer is None:
        return False
    stage = Usd.Stage.Open(layer)
    child_prim_path = parent.prim_path + "/" + name
    child_prim = stage.GetPrimAtPath(Sdf.Path(child_prim_path))
    if not child_prim.IsValid():
        return False
    stage.RemovePrim(child_prim_path)
    stage.GetRootLayer().Save()
    proj = parent.project
    if hasattr(proj, "_stage"):
        proj._stage = None
    return True

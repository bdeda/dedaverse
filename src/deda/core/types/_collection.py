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

        Validates the name, creates the asset's USDA file on disk under
        children_metadata_dir, defines a root prim with that name as default,
        sets Kind to Model and assetInfo. Adds a child prim with reference on
        this collection's get_edit_target layer.

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
        child_path = self.children_metadata_dir / f"{name}.usda"
        child_path.parent.mkdir(parents=True, exist_ok=True)
        stage = Usd.Stage.CreateNew(str(child_path))
        prim_path_on_stage = Sdf.Path("/" + name)
        prim = stage.DefinePrim(prim_path_on_stage, "Scope")
        stage.SetDefaultPrim(prim)
        model_api = Usd.ModelAPI(prim)
        model_api.SetKind(Kind.Tokens.model)
        identifier = _asset_id_string(self, name)
        model_api.SetAssetName(name)
        model_api.SetAssetIdentifier(Sdf.AssetPath(identifier))
        stage.GetRootLayer().Save()
        _add_child_prim_with_reference(self, name, child_path)
        return Asset(name, self)

    def add_collection(self, name: str) -> "Collection":
        """Add a new collection as a child of this collection.

        Validates the name, creates the collection's USDA file on disk under
        children_metadata_dir, defines a root prim with that name as default,
        sets Kind to Group. Adds a child prim with reference on this
        collection's get_edit_target layer.

        Args:
            name: Prim name for the new collection (must be a valid USD identifier).

        Returns:
            The new Collection instance (parent is this collection).

        Raises:
            ValueError: If name is not a valid identifier (Tf.IsValidIdentifier).
        """
        if not Tf.IsValidIdentifier(name):
            raise ValueError(f"Invalid prim identifier: {name!r}")
        child_path = self.children_metadata_dir / f"{name}.usda"
        child_path.parent.mkdir(parents=True, exist_ok=True)
        stage = Usd.Stage.CreateNew(str(child_path))
        prim_path_on_stage = Sdf.Path("/" + name)
        prim = stage.DefinePrim(prim_path_on_stage, "Scope")
        stage.SetDefaultPrim(prim)
        Usd.ModelAPI(prim).SetKind(Kind.Tokens.group)
        stage.GetRootLayer().Save()
        _add_child_prim_with_reference(self, name, child_path)
        return Collection(name, self)

    def iter_assets(self):
        for prim in self.project.stage.TraverseAll():
            yield Asset._from_prim(prim)


def _add_child_prim_with_reference(
    parent: Collection, name: str, child_path: Path
) -> None:
    """Add a child prim on parent's layer with reference to child_path.

    Path on the layer is /RootPrimName/name. Root prim name is parent.prim_name
    for Project (USD identifier), or parent.name for Collection/Asset.
    """
    parent_dir = parent.metadata_path.resolve().parent
    ref_path = os.path.relpath(str(child_path.resolve()), str(parent_dir))
    stage = Usd.Stage.Open(str(parent.metadata_path))
    stage.SetEditTarget(stage.GetRootLayer())
    root_prim_name = getattr(parent, "prim_name", None) or parent.name
    child_prim_path = Sdf.Path("/" + root_prim_name + "/" + name)
    prim = stage.DefinePrim(child_prim_path, "Scope")
    prim.GetReferences().AddReference(ref_path)
    stage.GetRootLayer().Save()

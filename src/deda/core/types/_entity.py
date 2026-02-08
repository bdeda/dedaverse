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
"""Entity types for the asset system.

Entity is the base class for all asset system types (Element, Asset, etc.).
Each entity is backed by a USD file where the default prim is the location
from which metadata is serialized.
"""

from pathlib import Path

from pxr import Sdf, Usd

from ._asset_id import AssetID

__all__ = ['Entity']


class Entity:
    """Base class for all asset system types (Element, Asset, etc.).

    Provides common attributes: name, parent, project, path, and metadata_path.
    Subclasses must override from_path() to implement type-specific path parsing.
    """

    def __init__(self, name: str, parent: 'Entity | None') -> None:
        """Initialize the entity.

        Args:
            name: Display name of the entity.
            parent: Parent entity, or None if this is a root entity.
        """
        self._name = name
        self._parent = parent
        
    
        
    @property 
    def metadata(self):
        return # TODO
    
    @property
    def metadata_path(self) -> Path | None:
        """The dedaverse metadata path relative to the project rootdir.

        Returns:
            Path to the metadata file, or None if not yet resolved.
        """
        return None

    @property
    def name(self) -> str:
        """Display name of the entity."""
        return self._name

    @property
    def parent(self) -> 'Entity | None':
        """Parent entity, or None if this is a root entity."""
        return self._parent

    @property
    def prim_path(self) -> str:
        """USD prim path for this entity in the project stage.

        Root (project) is /{name}; children are {parent.prim_path}/{name}.
        """
        if self._parent is None:
            return f'/{self._name}'
        return f'{self._parent.prim_path}/{self._name}'

    @property
    def path(self) -> Path:
        """File system path for this entity.

        For the project root, returns the project rootdir. For children,
        returns the path relative to the project (implementation pending).

        Returns:
            Path to the entity on disk.
        """
        proj = self.project
        if self is proj and hasattr(proj, 'rootdir'):
            rootdir = proj.rootdir
            return Path(rootdir) if isinstance(rootdir, str) else rootdir
        return Path()

    @property
    def project(self) -> 'Entity':
        """The root (project) entity, found by walking up the parent chain."""
        item: Entity | None = self
        while item is not None:
            if item.parent is None:
                return item
            item = item.parent
        return self

    def get_edit_target(self):
        """Return the best layer to edit for this entity's prim.

        For the stage's pseudo-root prim, returns the stage's root layer.
        Otherwise, walks the prim's spec stack and returns the first layer
        that has a defining opinion (Sdf.SpecifierDef) and a non-anonymous
        identifier, so edits go to a persistent, class-level layer.

        Returns:
            Sdf.Layer to use as the edit target, or None if no suitable
            layer is found (e.g. prim is defined only on anonymous layers).

        Note:
            Requires self.prim (e.g. on Asset and subclasses). Not defined
            on Entity when prim is not available.
        """
        stage = self.prim.GetStage()
        if self.prim.IsPseudoRoot():
            return stage.GetRootLayer()
        for spec in self.prim.GetPrimStack():
            if spec.specifier != Sdf.SpecifierDef:
                continue
            if spec.layer.IsAnonymous():
                continue
            return spec.layer
        return None

    def set_metadata(self, name: str, value) -> None:
        """Set custom metadata on this entity's prim and save the edit target layer.

        Uses Usd.Prim.SetCustomDataByKey to store the value. The value must be
        a type that USD accepts for custom data (e.g. str, int, float, bool,
        list, dict, or types convertible to VtValue). The stage's edit target
        is set to this entity's edit layer, then the layer is saved to disk.

        Args:
            name: Key for the custom metadata.
            value: Value to set; must be a type supported by SetCustomDataByKey.

        Raises:
            RuntimeError: If no edit target is available for this entity.
            Exception: If the value type is not supported by USD or save fails.

        Note:
            Requires self.prim (e.g. on Asset and subclasses).
        """
        layer = self.get_edit_target()
        if layer is None:
            raise RuntimeError("No edit target for this entity; cannot set metadata.")
        stage = self.prim.GetStage()
        stage.SetEditTarget(Usd.EditTarget(layer))
        self.prim.SetCustomDataByKey(name, value)
        layer.Save()

    @classmethod
    def from_path(cls, path: str) -> 'Entity | None':
        """Create an entity instance from a file path.

        If the path does not represent a valid entity of this type, returns None.
        Subclasses must override to implement type-specific path parsing.

        Args:
            path: File path string (e.g., USD file path).

        Returns:
            Instance of the entity subclass, or None if the path is invalid.

        Raises:
            NotImplementedError: When called on the base Entity class.
                Subclasses must override this method.
        """
        raise NotImplementedError
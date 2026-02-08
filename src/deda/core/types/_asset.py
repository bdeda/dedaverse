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
"""Asset type for the asset system.

Assets are backed by a usda file under the project root .dedaverse directory.
That directory follows the form:
    <project_rootdir>/.dedaverse/project.cfg  -- config data for the project
    <project_rootdir>/.dedaverse/{project_name}.usda -- project stage (metadata, assets)
"""

from pathlib import Path

from pxr import Sdf, Tf, Usd

from ._entity import Entity

__all__ = ['Asset']


class Asset(Entity):
    """Entity representing an asset that may contain Elements or Collections.

    An Asset groups related elements (e.g. character, prop) and can nest
    Collections. Inherits the full Entity API.
    """
    
    def __init__(self, name, parent):
        if parent is None:
            raise ValueError("Asset parent cannot be None.")
        super().__init__(name, parent)
    
    def children(self):
        # Only collections can have children assets.
        return None
    
    @property
    def prim(self):
        """Usd.Prim for this asset on the project stage.

        The prim may be created later. If the prim is not valid (e.g. stage
        reloaded), it is re-acquired from the project stage.

        Returns:
            Usd.Prim at this asset's prim_path; may be invalid if not yet created.
        """
        proj = self.project
        if not hasattr(proj, 'stage'):
            return Usd.Prim()
        stage = proj.stage
        if stage is None:
            return Usd.Prim()
        path = Sdf.Path(self.prim_path)
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            prim = stage.GetPrimAtPath(path)
        return prim

    @property
    def children_metadata_dir(self) -> Path:
        """Directory where child collection/asset USDA files are stored.

        For a collection under project: .dedaverse/collection_name.
        For an asset under collection: .dedaverse/collection_name/asset_name.
        """
        return self.parent.children_metadata_dir / self.name

    @property
    def metadata(self):
        return  # TODO

    @property
    def metadata_dir(self) -> Path:
        """Directory containing this asset's USDA file (parent's children dir)."""
        return self.parent.children_metadata_dir

    @property
    def metadata_path(self) -> Path:
        """Path to this asset's USDA file.

        Format: parent.children_metadata_dir / {name}.usda, e.g.
        .dedaverse/collection_name.usda for a collection under project,
        .dedaverse/collection_name/asset_name.usda for an asset under collection.
        """
        return self.parent.children_metadata_dir / f'{self.name}.usda'    
    
    @classmethod
    def validate_name(cls, name: str):
        """Validate the name string and return True or False if the name is valid.
        This method is meant to be used during asset creation.

        Args:
            name: (str) The string name to validate.

        Returns:
            (bool) True is valid, False otherwise.

        Raises:
            TypeError: Name is not a string type.

        """
        if not isinstance(name, str):
            raise TypeError(f'Name must be a string type! Got {type(name)}.')
        name = name.strip()
        if not name:
            return False
        return Tf.IsValidIdentifier(name) 
    
    def _from_prim(self, prim):
        """Instantiate the asset from the given prim in the metadata. 
        This is used internally from the Collection class."""
        if prim.GetTypeName() == 'AssetInfo':
            raise ValueError
        # if prim has children that are Asset types, return a Collection
   

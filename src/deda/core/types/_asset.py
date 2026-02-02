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
"""Asset type for the asset system."""

from pathlib import Path

from pxr import Tf

from ._entity import Entity

__all__ = ['Asset']


class Asset(Entity):
    """Entity representing an asset that may contain Elements or Collections.

    An Asset groups related elements (e.g. character, prop) and can nest
    Collections. Inherits the full Entity API.
    """
    
    def children(self):
        # Only collections can have children assets.
        return None
    
    @property 
    def metadata(self):
        return # TODO
    
    @property
    def metadata_dir(self) -> Path | None:
        """The dedaverse metadata dir relative to the project rootdir.

        Returns:
            Path to the metadata file, or None if not yet resolved.
        """
        # Project metadata comes from .dedaverse directory under the project rootdir
        return self.parent.metadata_dir / self.name
    
    @property
    def metadata_path(self) -> Path | None:
        """The dedaverse metadata path relative to the project rootdir.

        Returns:
            Path to the metadata file, or None if not yet resolved.
        """
        # Project metadata comes from .dedaverse directory under the project rootdir
        return self.metadata_dir / f'{self.name}.usda'    
    
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
        
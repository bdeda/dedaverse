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

from typing import Self

from ._asset_id import AssetID

__all__ = ['AssetID', 'Entity']


class Entity:
    """Base class for all asset system types (Element, Asset, etc.)."""

    def __init__(self, name: str, parent: Self | None) -> None:
        """Initialize the entity.

        Args:
            name: Display name of the entity.
            parent: Parent entity, or None if this is a root entity.
        """
        self._name = name
        self._parent = parent

    @classmethod
    def from_path(cls, path: str) -> Self | None:
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
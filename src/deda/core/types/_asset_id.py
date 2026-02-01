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
"""AssetID type for the asset system.

AssetID is a string identifier for an Entity, unique per project.
"""

import re
from functools import total_ordering

__all__ = ['AssetID']

# USD prim names: start with letter or underscore, then alphanumeric or underscore
_USD_PRIM_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


@total_ordering
class AssetID:
    """String identifier for an Entity, unique per project.

    Used for asset lookup and as a reference to an Entity from other systems.
    Format: ``asset_name:sub_asset_name::element_type/relative_path``,
            ``asset_name::``.
            ``asset_name:sub_asset_name::
            ``project_name:asset_name:sub_asset_name::
    Supports hashing (dict keys), ordering (sortable), and string conversion.
    """

    def __init__(self, asset_id: str) -> None:
        """Initialize the asset ID.

        Args:
            asset_id: String identifier in format
                ``asset_name:sub_asset_name::element_type/relative_path`` or
                ``asset_name::``. Must contain ``::``. The prefix (before ``::``)
                must consist of USD-valid prim name segments separated by single
                ``:`` delimiters.

        Raises:
            ValueError: If asset_id does not contain ``::``, or if the prefix
                contains invalid characters or segment structure.
        """
        self._asset_id = self._validate_asset_id(asset_id)

    @staticmethod
    def _validate_asset_id(asset_id: str) -> str:
        """Validate asset_id format and return the trimmed string.

        Args:
            asset_id: Raw string to validate.

        Returns:
            Trimmed asset_id string if valid.

        Raises:
            TypeError: If asset_id is not a string.
            ValueError: If asset_id lacks "::", has empty prefix, empty
                segment, or invalid USD prim name characters in prefix.
        """
        if not isinstance(asset_id, str):
            raise TypeError(f'asset_id must be str, got {type(asset_id).__name__}')
        asset_id = asset_id.strip()
        if '::' not in asset_id:
            raise ValueError(
                f'asset_id must contain "::" separator, got {asset_id!r}'
            )
        prefix, _ = asset_id.split('::', 1)
        if not prefix:
            raise ValueError(
                f'asset_id prefix (before "::") must be non-empty, got {asset_id!r}'
            )
        segments = prefix.split(':')
        for i, seg in enumerate(segments):
            if not seg:
                raise ValueError(
                    f'asset_id prefix segment {i} is empty (double colon or leading '
                    f'trailing ":"), got {asset_id!r}'
                )
            if not _USD_PRIM_NAME_RE.match(seg):
                raise ValueError(
                    f'asset_id prefix segment {i!r} contains invalid characters for '
                    f'USD prim name (use [A-Za-z_][A-Za-z0-9_]*), got {seg!r}'
                )
        return asset_id

    def __str__(self) -> str:
        """Return the string value of the asset ID.

        Returns:
            The underlying asset ID string.
        """
        return str(self._asset_id)

    def __repr__(self) -> str:
        """Return a repr showing the AssetID type and its string value.

        Returns:
            String of the form ``AssetID('value')``.
        """
        return f"AssetID({self._asset_id!r})"

    def __hash__(self) -> int:
        """Return hash for use as dict key or in sets.

        Returns:
            Hash of the asset ID string.
        """
        return hash(self._asset_id)

    def __eq__(self, other: object) -> bool:
        """Return True if other has the same string value.

        Args:
            other: AssetID or str to compare against. Strings are compared
                directly to the asset ID value.

        Returns:
            True if equal, False otherwise. Returns NotImplemented if other
            is not an AssetID or str.
        """
        if isinstance(other, AssetID):
            return self._asset_id == other._asset_id
        if isinstance(other, str):
            return self._asset_id == other
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        """Compare by string value for sorting.

        Args:
            other: AssetID or str to compare against. Strings are compared
                directly to the asset ID value.

        Returns:
            True if this asset ID sorts before other. Returns NotImplemented
            if other is not an AssetID or str.
        """
        if isinstance(other, AssetID):
            return self._asset_id < other._asset_id
        if isinstance(other, str):
            return self._asset_id < other
        return NotImplemented

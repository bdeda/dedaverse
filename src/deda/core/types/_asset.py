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

from ._entity import Entity

__all__ = ['Asset']


class Asset(Entity):
    """Entity representing an asset that may contain Elements or Collections.

    An Asset groups related elements (e.g. character, prop) and can nest
    Collections. Inherits the full Entity API.
    """
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
"""Sequence type for the asset system."""

from ._collection import Collection

__all__ = ['Sequence']


class Sequence(Collection):
    """Collection of Shots, Assets, or nested Collections for a sequence.

    A Sequence represents a logical grouping (e.g. a film sequence or
    episode) and typically contains Shots. Inherits the full Entity API.
    """
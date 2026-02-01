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
"""Project type for the asset system."""

from pathlib import Path

from ._collection import Collection

__all__ = ['Project']


class Project(Collection):
    """Root entity representing a Dedaverse project.

    A Project is the top-level Collection that contains all assets, sequences,
    and shots. Has a rootdir that points to the project directory on disk.
    """

    @property
    def rootdir(self) -> Path | str:
        """Project root directory on the file system.

        Returns:
            Path or string to the project root. TODO: load from project cfg.
        """
        return Path('F:/dedaverse')
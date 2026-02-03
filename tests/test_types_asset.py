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
"""Unit tests for deda.core.types._asset module."""

import unittest
from pathlib import Path

from deda.core.types._asset import Asset
from deda.core.types._project import Project


class TestAsset(unittest.TestCase):
    """Test cases for Asset class."""

    def test_asset_creation_requires_parent(self):
        """Test that Asset requires a non-None parent."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        asset = Asset(name="TestAsset", parent=project)
        self.assertEqual(asset._parent, project)

    def test_asset_parent_none_raises(self):
        """Test that Asset cannot be created without a parent."""
        with self.assertRaises(ValueError):
            Asset(name="TestAsset", parent=None)

    def test_asset_creation_entity_api(self):
        """Asset supports Entity API: name, parent, project, path."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        asset = Asset(name='TestAsset', parent=project)
        self.assertEqual(asset.name, 'TestAsset')
        self.assertIs(asset.parent, project)
        self.assertIs(asset.project, project)
        _ = asset.path


if __name__ == '__main__':
    unittest.main()

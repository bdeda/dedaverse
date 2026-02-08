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

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from deda.core.types._asset import Asset
from deda.core.types._collection import Collection
from deda.core.types._project import Project


class TestAsset(unittest.TestCase):
    """Test cases for Asset class."""

    def test_asset_creation_requires_parent(self):
        """Test that Asset requires a non-None parent."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        asset = Asset(name="TestAsset", parent=project)
        self.assertIs(asset.parent, project)

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

    def test_validate_name_returns_true_for_valid(self):
        """Asset.validate_name returns True for valid USD identifier."""
        self.assertTrue(Asset.validate_name("valid_name"))
        self.assertTrue(Asset.validate_name("ValidName"))
        self.assertTrue(Asset.validate_name("_private"))

    def test_validate_name_returns_false_for_invalid(self):
        """Asset.validate_name returns False for invalid identifier."""
        self.assertFalse(Asset.validate_name(""))
        self.assertFalse(Asset.validate_name("   "))
        self.assertFalse(Asset.validate_name("123"))
        self.assertFalse(Asset.validate_name("has-space"))

    def test_validate_name_raises_type_error_for_non_string(self):
        """Asset.validate_name raises TypeError for non-string."""
        with self.assertRaises(TypeError):
            Asset.validate_name(123)

    def test_metadata_path_under_project(self):
        """Asset under project has metadata_path at .dedaverse/{name}.usda."""
        project = Project(name="Proj", rootdir=Path("/root"))
        asset = Asset(name="MyAsset", parent=project)
        self.assertEqual(asset.metadata_path, Path("/root/.dedaverse/MyAsset.usda"))

    def test_metadata_dir_under_project(self):
        """Asset under project has metadata_dir equal to project children_metadata_dir."""
        project = Project(name="Proj", rootdir=Path("/root"))
        asset = Asset(name="MyAsset", parent=project)
        self.assertEqual(asset.metadata_dir, project.children_metadata_dir)

    def test_children_metadata_dir_under_collection(self):
        """Asset under collection has children_metadata_dir at parent's dir / name."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            project = Project.create(name="Proj", rootdir=Path(tmp))
            coll = project.add_collection("Col")
            asset = project.add_asset("A1")
            self.assertEqual(asset.children_metadata_dir, project.children_metadata_dir / "A1")
            coll_asset = coll.add_asset("CA1")
            self.assertEqual(coll_asset.children_metadata_dir, coll.children_metadata_dir / "CA1")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()

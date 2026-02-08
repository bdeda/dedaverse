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
"""Unit tests for deda.core.types._collection module."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from deda.core.types._asset import Asset
from deda.core.types._collection import Collection
from deda.core.types._project import Project


class TestCollection(unittest.TestCase):
    """Test cases for Collection class."""

    def test_collection_creation_requires_parent(self):
        """Test that Collection requires a non-None parent."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        collection = Collection(name="TestCollection", parent=project)
        self.assertIs(collection.parent, project)

    def test_collection_parent_none_raises(self):
        """Test that Collection cannot be created without a parent."""
        with self.assertRaises(ValueError):
            Collection(name="TestCollection", parent=None)

    def test_collection_creation_entity_api(self):
        """Collection supports Entity API: name, parent, project, path."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        coll = Collection(name='TestCollection', parent=project)
        self.assertEqual(coll.name, 'TestCollection')
        self.assertIs(coll.parent, project)
        self.assertIs(coll.project, project)
        _ = coll.path

    def test_add_asset_returns_asset(self):
        """add_asset returns an Asset with correct parent."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            project = Project.create(name="Proj", rootdir=Path(tmp))
            asset = project.add_asset("NewAsset")
            self.assertIsInstance(asset, Asset)
            self.assertEqual(asset.name, "NewAsset")
            self.assertIs(asset.parent, project)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_add_collection_returns_collection(self):
        """add_collection returns a Collection with correct parent."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            project = Project.create(name="Proj", rootdir=Path(tmp))
            coll = project.add_collection("NewColl")
            self.assertIsInstance(coll, Collection)
            self.assertEqual(coll.name, "NewColl")
            self.assertIs(coll.parent, project)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_add_asset_invalid_name_raises(self):
        """add_asset with invalid identifier raises ValueError."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            project = Project.create(name="Proj", rootdir=Path(tmp))
            with self.assertRaises(ValueError) as ctx:
                project.add_asset("bad name")
            self.assertIn("Invalid prim identifier", str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_add_collection_invalid_name_raises(self):
        """add_collection with invalid identifier raises ValueError."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            project = Project.create(name="Proj", rootdir=Path(tmp))
            with self.assertRaises(ValueError) as ctx:
                project.add_collection("bad-name")
            self.assertIn("Invalid prim identifier", str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_collection_metadata_path_under_project(self):
        """Collection under project has metadata_path at .dedaverse/{name}.usda."""
        project = Project(name="Proj", rootdir=Path("/root"))
        coll = Collection(name="MyColl", parent=project)
        self.assertEqual(coll.metadata_path, Path("/root/.dedaverse/MyColl.usda"))

    def test_collection_children_metadata_dir_under_project(self):
        """Collection under project has children_metadata_dir at .dedaverse/{name}."""
        project = Project(name="Proj", rootdir=Path("/root"))
        coll = Collection(name="MyColl", parent=project)
        self.assertEqual(coll.children_metadata_dir, Path("/root/.dedaverse/MyColl"))


if __name__ == '__main__':
    unittest.main()

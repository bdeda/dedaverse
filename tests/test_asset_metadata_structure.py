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
"""Unit tests for asset metadata directory structure and references.

Verifies that project and collection add_asset/add_collection produce:
  <project_root>/.dedaverse/project_name.usda
  <project_root>/.dedaverse/collection_name.usda
  <project_root>/.dedaverse/collection_name/sub_collection_name.usda
  <project_root>/.dedaverse/collection_name/sub_collection_name/asset_name.usda

Project USDA has a project prim as the default prim. Child collections/assets
are created as child prims on the parent's get_edit_target layer with a
reference to the child's USDA file in the same directory (or subdir).
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pxr import Kind, Usd

from deda.core.types._project import Project


class TestAssetMetadataStructure(unittest.TestCase):
    """Test metadata directory structure and references."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        self.root = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_project_usda_has_project_prim_as_default(self):
        """Project.create() produces .dedaverse/{name}.usda with project prim as default prim."""
        project = Project.create(name="MyProject", rootdir=self.root)
        usda = self.root / ".dedaverse" / "MyProject.usda"
        self.assertTrue(usda.is_file(), f"Expected {usda} to exist")
        stage = Usd.Stage.Open(str(usda))
        default_prim = stage.GetDefaultPrim()
        self.assertTrue(default_prim.IsValid(), "Stage should have a default prim")
        self.assertEqual(default_prim.GetPath(), "/MyProject")
        self.assertEqual(default_prim.GetName(), "MyProject")

    def test_project_usda_root_prim_has_kind_group(self):
        """Project root prim has ModelAPI Kind set to group (same as Collection)."""
        project = Project.create(name="Proj", rootdir=self.root)
        stage = Usd.Stage.Open(str(self.root / ".dedaverse" / "Proj.usda"))
        root_prim = stage.GetDefaultPrim()
        self.assertTrue(root_prim.IsValid())
        kind = Usd.ModelAPI(root_prim).GetKind()
        self.assertEqual(kind, Kind.Tokens.group)

    def test_project_with_one_child_asset_directory_structure(self):
        """Project with one child asset: .dedaverse/project.usda and .dedaverse/asset_name.usda."""
        project = Project.create(name="Proj", rootdir=self.root)
        project.add_asset("asset_name")
        deda = self.root / ".dedaverse"
        self.assertTrue((deda / "Proj.usda").is_file())
        self.assertTrue((deda / "asset_name.usda").is_file())

    def test_project_with_one_child_asset_reference(self):
        """Project with one child asset: project USDA has child prim that references asset_name.usda."""
        project = Project.create(name="Proj", rootdir=self.root)
        project.add_asset("asset_name")
        stage = Usd.Stage.Open(str(self.root / ".dedaverse" / "Proj.usda"))
        child = stage.GetPrimAtPath("/Proj/asset_name")
        self.assertTrue(child.IsValid(), "Project should have child prim /Proj/asset_name")
        refs = child.GetMetadata("references")
        self.assertTrue(refs, "Child prim should have references")
        # Reference should point to asset_name.usda (same dir as project)
        self.assertIn("asset_name.usda", str(refs))

    def test_project_with_one_child_collection_and_nested_asset_structure(self):
        """Project -> collection -> asset: .dedaverse/project.usda, collection.usda, collection/asset.usda."""
        project = Project.create(name="Proj", rootdir=self.root)
        coll = project.add_collection("collection_name")
        coll.add_asset("asset_name")
        deda = self.root / ".dedaverse"
        self.assertTrue((deda / "Proj.usda").is_file())
        self.assertTrue((deda / "collection_name.usda").is_file())
        self.assertTrue((deda / "collection_name" / "asset_name.usda").is_file())

    def test_project_with_one_child_collection_reference(self):
        """Project USDA has child prim collection_name that references collection_name.usda."""
        project = Project.create(name="Proj", rootdir=self.root)
        project.add_collection("collection_name")
        stage = Usd.Stage.Open(str(self.root / ".dedaverse" / "Proj.usda"))
        child = stage.GetPrimAtPath("/Proj/collection_name")
        self.assertTrue(child.IsValid())
        refs = child.GetMetadata("references")
        self.assertTrue(refs)
        self.assertIn("collection_name.usda", str(refs))

    def test_collection_usda_has_child_prim_referencing_asset(self):
        """Collection USDA has child prim asset_name that references asset_name.usda in same dir."""
        project = Project.create(name="Proj", rootdir=self.root)
        coll = project.add_collection("collection_name")
        coll.add_asset("asset_name")
        coll_usda = self.root / ".dedaverse" / "collection_name.usda"
        stage = Usd.Stage.Open(str(coll_usda))
        child = stage.GetPrimAtPath("/collection_name/asset_name")
        self.assertTrue(child.IsValid())
        refs = child.GetMetadata("references")
        self.assertTrue(refs)
        self.assertIn("asset_name.usda", str(refs))

    def test_deep_nesting_directory_structure(self):
        """Project -> collection -> sub_collection -> asset: all four levels on disk."""
        project = Project.create(name="Proj", rootdir=self.root)
        coll = project.add_collection("collection_name")
        sub = coll.add_collection("sub_collection_name")
        sub.add_asset("asset_name")
        deda = self.root / ".dedaverse"
        self.assertTrue((deda / "Proj.usda").is_file())
        self.assertTrue((deda / "collection_name.usda").is_file())
        self.assertTrue((deda / "collection_name" / "sub_collection_name.usda").is_file())
        self.assertTrue(
            (deda / "collection_name" / "sub_collection_name" / "asset_name.usda").is_file()
        )

    def test_new_project_create_then_collections_and_assets(self):
        """New project can be created; collections and assets can be created for that project."""
        project = Project.create(name="TestProj", rootdir=self.root)
        self.assertIsNotNone(project)
        self.assertEqual(project.name, "TestProj")
        self.assertEqual(project.prim_name, "TestProj")
        coll = project.add_collection("Characters")
        self.assertEqual(coll.name, "Characters")
        self.assertIs(coll.parent, project)
        asset = project.add_asset("HeroProp")
        self.assertEqual(asset.name, "HeroProp")
        self.assertIs(asset.parent, project)
        deda = self.root / ".dedaverse"
        self.assertTrue((deda / "TestProj.usda").is_file())
        self.assertTrue((deda / "Characters.usda").is_file())
        self.assertTrue((deda / "HeroProp.usda").is_file())

    def test_sub_collections_and_sub_assets_under_collection(self):
        """Sub-collections and sub-assets can be created under a collection."""
        project = Project.create(name="Proj", rootdir=self.root)
        coll = project.add_collection("Env")
        sub_coll = coll.add_collection("SetDress")
        self.assertEqual(sub_coll.name, "SetDress")
        self.assertIs(sub_coll.parent, coll)
        sub_asset = coll.add_asset("Tree_01")
        self.assertEqual(sub_asset.name, "Tree_01")
        self.assertIs(sub_asset.parent, coll)
        deda = self.root / ".dedaverse"
        self.assertTrue((deda / "Env" / "SetDress.usda").is_file())
        self.assertTrue((deda / "Env" / "Tree_01.usda").is_file())

    def test_usd_files_correct_locations_relative_to_project_root(self):
        """All USD files are created in correct locations relative to the test project root."""
        project = Project.create(name="Proj", rootdir=self.root)
        coll_a = project.add_collection("A")
        project.add_asset("B")
        coll_a.add_asset("A2")
        sub = coll_a.add_collection("A1")
        sub.add_asset("A1a")
        deda = self.root / ".dedaverse"
        expected = [
            deda / "Proj.usda",
            deda / "A.usda",
            deda / "B.usda",
            deda / "A" / "A1.usda",
            deda / "A" / "A2.usda",
            deda / "A" / "A1" / "A1a.usda",
        ]
        for path in expected:
            self.assertTrue(path.is_file(), f"Expected USDA at {path.relative_to(self.root)}")

    def test_add_collection_invalid_name_raises(self):
        """add_collection with invalid prim identifier raises ValueError."""
        project = Project.create(name="Proj", rootdir=self.root)
        with self.assertRaises(ValueError) as ctx:
            project.add_collection("invalid name")
        self.assertIn("Invalid prim identifier", str(ctx.exception))

    def test_add_asset_invalid_name_raises(self):
        """add_asset with invalid prim identifier raises ValueError."""
        project = Project.create(name="Proj", rootdir=self.root)
        with self.assertRaises(ValueError) as ctx:
            project.add_asset("123_starts_with_digit")
        self.assertIn("Invalid prim identifier", str(ctx.exception))

    def test_project_create_with_explicit_prim_name(self):
        """Project.create with explicit prim_name uses it for USDA path and root prim."""
        project = Project.create(name="Display Name", rootdir=self.root, prim_name="DisplayName")
        self.assertEqual(project.name, "Display Name")
        self.assertEqual(project.prim_name, "DisplayName")
        usda = self.root / ".dedaverse" / "DisplayName.usda"
        self.assertTrue(usda.is_file())
        self.assertEqual(project.metadata_path, usda)
        self.assertEqual(project.prim_path, "/DisplayName")

    def test_project_stage_and_layer_after_create(self):
        """After create, project.stage opens the USDA and project.layer returns the root layer."""
        project = Project.create(name="Proj", rootdir=self.root)
        stage = project.stage
        self.assertIsNotNone(stage)
        self.assertTrue(stage.GetRootLayer().identifier.endswith("Proj.usda") or "Proj.usda" in stage.GetRootLayer().identifier)
        layer = project.layer
        self.assertIsNotNone(layer)


if __name__ == "__main__":
    unittest.main()

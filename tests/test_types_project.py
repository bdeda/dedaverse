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
"""Unit tests for deda.core.types._project module."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from deda.core.types._project import Project


class TestProject(unittest.TestCase):
    """Test cases for Project class."""

    def test_init_with_name_and_rootdir(self):
        """Project(name, rootdir) sets name, rootdir, and parent None."""
        root = Path("test_root")
        project = Project(name="TestProject", rootdir=root)
        self.assertEqual(project._name, "TestProject")
        self.assertEqual(project.rootdir, root)
        self.assertIsNone(project.parent)

    def test_init_rootdir_accepts_str(self):
        """Project accepts rootdir as str; it is normalized to Path."""
        project = Project(name="P", rootdir="/some/root")
        self.assertEqual(project.rootdir, Path("/some/root"))

    def test_parent_non_none_raises(self):
        """Project cannot be created with a non-None parent."""
        with self.assertRaises(ValueError):
            Project(name="P", rootdir=Path("r"), parent=object())

    def test_metadata_dir(self):
        """metadata_dir is rootdir/.dedaverse."""
        root = Path("/proj/root")
        project = Project(name="Proj", rootdir=root)
        self.assertEqual(project.metadata_dir, root / ".dedaverse")

    def test_metadata_path(self):
        """metadata_path is rootdir/.dedaverse/{name}.usda."""
        root = Path("/proj/root")
        project = Project(name="MyProject", rootdir=root)
        self.assertEqual(project.metadata_path, root / ".dedaverse" / "MyProject.usda")

    def test_create_creates_usda_and_returns_project(self):
        """Project.create(name, rootdir) creates .dedaverse/{name}.usda and returns Project."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            root = Path(tmp)
            project = Project.create(name="CreatedProj", rootdir=root)
            self.assertIsInstance(project, Project)
            self.assertEqual(project.name, "CreatedProj")
            self.assertEqual(project.rootdir, root)
            usda = root / ".dedaverse" / "CreatedProj.usda"
            self.assertTrue(usda.is_file())
            self.assertEqual(project.metadata_path, usda)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_create_raises_when_exists_and_not_force(self):
        """create(..., force=False) raises FileExistsError when project USDA already exists."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            root = Path(tmp)
            Project.create(name="ExistingProj", rootdir=root)
            with self.assertRaises(FileExistsError) as ctx:
                Project.create(name="ExistingProj", rootdir=root, force=False)
            self.assertIn("Project metadata already exists", str(ctx.exception))
            self.assertIn("force=True", str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_create_overwrites_when_force_true(self):
        """create(..., force=True) overwrites existing project USDA file."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            root = Path(tmp)
            Project.create(name="OverwriteProj", rootdir=root)
            usda = root / ".dedaverse" / "OverwriteProj.usda"
            project = Project.create(name="OverwriteProj", rootdir=root, force=True)
            self.assertIsInstance(project, Project)
            # File was recreated (content may differ; at least we didn't raise)
            self.assertTrue(usda.is_file())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_find_or_create_creates_when_missing(self):
        """find_or_create creates .dedaverse/{name}.usda when it does not exist."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            root = Path(tmp)
            project = Project.find_or_create(name="FindOrCreateProj", rootdir=root)
            self.assertIsInstance(project, Project)
            self.assertEqual(project.name, "FindOrCreateProj")
            usda = root / ".dedaverse" / "FindOrCreateProj.usda"
            self.assertTrue(usda.is_file())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_find_or_create_does_not_overwrite_existing(self):
        """find_or_create does not overwrite existing project USDA file."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            root = Path(tmp)
            Project.create(name="ExistingProj", rootdir=root)
            usda = root / ".dedaverse" / "ExistingProj.usda"
            self.assertTrue(usda.is_file())
            mtime_before = usda.stat().st_mtime
            content_before = usda.read_text()
            project = Project.find_or_create(name="ExistingProj", rootdir=root)
            self.assertIsInstance(project, Project)
            self.assertEqual(usda.stat().st_mtime, mtime_before)
            self.assertEqual(usda.read_text(), content_before)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_layer_after_create_returns_layer(self):
        """After create(), layer returns Sdf.Layer for metadata_path (FindOrOpen)."""
        from pxr import Sdf
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            root = Path(tmp)
            project = Project.create(name="LayerProj", rootdir=root)
            layer = project.layer
            self.assertIsNotNone(layer)
            self.assertIsInstance(layer, Sdf.Layer)
            self.assertEqual(
                Path(layer.identifier).resolve(),
                project.metadata_path.resolve(),
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_layer_without_file_returns_none(self):
        """When USDA file does not exist, layer returns None (FindOrOpen finds nothing)."""
        tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
        try:
            root = Path(tmp)
            project = Project(name="NoFileProj", rootdir=root)
            self.assertFalse(project.metadata_path.exists())
            self.assertIsNone(project.layer)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_current_project_no_args_returns_instance(self):
        """Project() with no args returns instance for LayeredConfig.current_project."""
        mock_config = MagicMock()
        mock_config.name = "CurrentProj"
        mock_config.rootdir = "/current/root"
        with patch("deda.core.types._project.LayeredConfig") as LayeredConfig:
            LayeredConfig.instance.return_value.current_project = mock_config
            project = Project()
            self.assertIsInstance(project, Project)
            self.assertEqual(project.name, "CurrentProj")
            self.assertEqual(project.rootdir, Path("/current/root"))
            self.assertIsNone(project.parent)

    def test_current_project_no_args_raises_when_no_current(self):
        """Project() with no args raises RuntimeError when no current project set."""
        with patch("deda.core.types._project.LayeredConfig") as LayeredConfig:
            LayeredConfig.instance.return_value.current_project = None
            with self.assertRaises(RuntimeError) as ctx:
                Project()
            self.assertIn("No current project", str(ctx.exception))

    def test_entity_api(self):
        """Project supports Entity API: name, parent, project, path, rootdir."""
        proj = Project(name="E", rootdir=Path("test_root"), parent=None)
        self.assertEqual(proj.name, "E")
        self.assertIsNone(proj.parent)
        self.assertIs(proj.project, proj)
        self.assertEqual(proj.path, Path("test_root"))
        self.assertEqual(proj.rootdir, Path("test_root"))


if __name__ == '__main__':
    unittest.main()

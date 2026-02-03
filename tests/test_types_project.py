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

import unittest
from pathlib import Path

from deda.core.types._project import Project


class TestProject(unittest.TestCase):
    """Test cases for Project class."""

    def test_project_parent_is_none(self):
        """Test that Project parent is always None."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        self.assertIsNone(project._parent)

    def test_project_parent_non_none_raises(self):
        """Test that Project cannot be created with a parent."""
        with self.assertRaises(ValueError):
            Project(name="TestProject", rootdir=Path("test_root"), parent=object())

    def test_project_creation_entity_api(self):
        """Project supports Entity API: name, parent, project, path, rootdir."""
        proj = Project(name='TestProject', rootdir=Path("test_root"), parent=None)
        self.assertEqual(proj.name, 'TestProject')
        self.assertIsNone(proj.parent)
        self.assertIs(proj.project, proj)
        _ = proj.path
        _ = proj.rootdir


if __name__ == '__main__':
    unittest.main()

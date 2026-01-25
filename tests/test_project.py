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
"""Unit tests for deda.core._project module."""

import unittest

from deda.core._project import Project


class TestProject(unittest.TestCase):
    """Test cases for Project class."""

    def test_project_creation(self):
        """Test creating a Project instance."""
        project = Project(name='TestProject', key='TEST', type='game')
        self.assertEqual(project.name, 'TestProject')
        self.assertEqual(project._data['key'], 'TEST')
        self.assertEqual(project._data['type'], 'game')

    def test_project_name_property(self):
        """Test Project name property."""
        project = Project(name='TestProject')
        self.assertEqual(project.name, 'TestProject')

    def test_project_equality_with_project(self):
        """Test Project equality with another Project."""
        project1 = Project(name='TestProject')
        project2 = Project(name='TestProject')
        self.assertEqual(project1, project2)

    def test_project_equality_with_dict(self):
        """Test Project equality with dict containing name."""
        project = Project(name='TestProject')
        project_dict = {'name': 'TestProject'}
        self.assertEqual(project, project_dict)

    def test_project_equality_with_string(self):
        """Test Project equality with string name."""
        project = Project(name='TestProject')
        self.assertNotEqual(project, 'TestProject')  # Not equal to string

    def test_project_as_dict(self):
        """Test Project as_dict method."""
        project = Project(name='TestProject', key='TEST', type='game')
        result = project.as_dict()
        self.assertEqual(result['name'], 'TestProject')
        self.assertEqual(result['key'], 'TEST')
        self.assertEqual(result['type'], 'game')


if __name__ == '__main__':
    unittest.main()

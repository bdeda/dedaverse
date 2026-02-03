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
"""Unit tests for deda.core.types._shot module."""

import unittest

from deda.core.types._project import Project
from deda.core.types._sequence import Sequence
from deda.core.types._shot import Shot


class TestShot(unittest.TestCase):
    """Test cases for Shot class."""

    def test_shot_parent_is_sequence(self):
        """Test that Shot requires a Sequence parent."""
        project = Project(name="TestProject")
        sequence = Sequence(name="TestSequence", parent=project)
        shot = Shot(name="TestShot", parent=sequence)
        self.assertEqual(shot._parent, sequence)

    def test_shot_parent_none_raises(self):
        """Test that Shot cannot be created without a parent."""
        with self.assertRaises(ValueError):
            Shot(name="TestShot", parent=None)

    def test_shot_parent_non_sequence_raises(self):
        """Test that Shot parent must be a Sequence."""
        project = Project(name="TestProject")
        with self.assertRaises(ValueError):
            Shot(name="TestShot", parent=project)

    def test_shot_creation_entity_api(self):
        """Shot supports Entity API: name, parent, project, path."""
        shot = Shot(name='TestShot', parent=None)
        self.assertEqual(shot.name, 'TestShot')
        self.assertIsNone(shot.parent)
        self.assertIs(shot.project, shot)
        _ = shot.path


if __name__ == '__main__':
    unittest.main()

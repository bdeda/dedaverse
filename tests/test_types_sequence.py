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
"""Unit tests for deda.core.types._sequence module."""

import unittest

from deda.core.types._project import Project
from deda.core.types._sequence import Sequence


class TestSequence(unittest.TestCase):
    """Test cases for Sequence class."""

    def test_sequence_creation_requires_parent(self):
        """Test that Sequence requires a non-None parent."""
        project = Project(name="TestProject")
        sequence = Sequence(name="TestSequence", parent=project)
        self.assertEqual(sequence._parent, project)

    def test_sequence_parent_none_raises(self):
        """Test that Sequence cannot be created without a parent."""
        with self.assertRaises(ValueError):
            Sequence(name="TestSequence", parent=None)

    def test_sequence_creation_entity_api(self):
        """Sequence supports Entity API: name, parent, project, path."""
        seq = Sequence(name='TestSequence', parent=None)
        self.assertEqual(seq.name, 'TestSequence')
        self.assertIsNone(seq.parent)
        self.assertIs(seq.project, seq)
        _ = seq.path


if __name__ == '__main__':
    unittest.main()

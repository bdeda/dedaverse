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
from pathlib import Path

from deda.core.types._project import Project
from deda.core.types._sequence import Sequence


class TestSequence(unittest.TestCase):
    """Test cases for Sequence class."""

    def test_sequence_creation_requires_parent(self):
        """Test that Sequence requires a non-None parent."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        sequence = Sequence(name="TestSequence", parent=project)
        self.assertIs(sequence.parent, project)

    def test_sequence_parent_none_raises(self):
        """Test that Sequence cannot be created without a parent."""
        with self.assertRaises(ValueError):
            Sequence(name="TestSequence", parent=None)

    def test_sequence_creation_entity_api(self):
        """Sequence supports Entity API: name, parent, project, path."""
        project = Project(name="TestProject", rootdir=Path("test_root"))
        seq = Sequence(name='TestSequence', parent=project)
        self.assertEqual(seq.name, 'TestSequence')
        self.assertIs(seq.parent, project)
        self.assertIs(seq.project, project)
        _ = seq.path


if __name__ == '__main__':
    unittest.main()

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
"""Unit tests for deda.core.types._entity module."""

import unittest

from deda.core.types._entity import Entity


class TestEntity(unittest.TestCase):
    """Test cases for Entity class."""

    def test_entity_creation(self):
        """Test creating an Entity instance."""
        parent = None
        entity = Entity(name='TestEntity', parent=parent)
        self.assertEqual(entity._name, 'TestEntity')
        self.assertEqual(entity._parent, parent)

    def test_entity_from_path_not_implemented(self):
        """Test that Entity.from_path() raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            Entity.from_path('/path/to/entity')


if __name__ == '__main__':
    unittest.main()

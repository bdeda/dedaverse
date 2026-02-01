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

import unittest

from deda.core.types._collection import Collection
from deda.core.types._entity import Entity


class TestCollection(unittest.TestCase):
    """Test cases for Collection class."""

    def test_module_imports(self):
        """Test that the module can be imported."""
        try:
            import deda.core.types._collection
            self.assertTrue(True)
        except ImportError:
            self.fail("Failed to import deda.core.types._collection")

    def test_collection_creation_entity_api(self):
        """Collection supports Entity API: name, parent, project, path."""
        coll = Collection(name='TestCollection', parent=None)
        self.assertEqual(coll.name, 'TestCollection')
        self.assertIsNone(coll.parent)
        self.assertIs(coll.project, coll)
        _ = coll.path


if __name__ == '__main__':
    unittest.main()

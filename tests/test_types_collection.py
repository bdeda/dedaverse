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
from deda.core.types._project import Project


class TestCollection(unittest.TestCase):
    """Test cases for Collection module."""

    def test_collection_creation_requires_parent(self):
        """Test that Collection requires a non-None parent."""
        project = Project(name="TestProject")
        collection = Collection(name="TestCollection", parent=project)
        self.assertEqual(collection._parent, project)

    def test_collection_parent_none_raises(self):
        """Test that Collection cannot be created without a parent."""
        with self.assertRaises(ValueError):
            Collection(name="TestCollection", parent=None)


if __name__ == '__main__':
    unittest.main()

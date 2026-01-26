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
"""Unit tests for deda.core._types module."""

import unittest

from deda.core._types import (
    all_default_asset_types,
    all_default_element_types,
)


class TestDefaultAssetTypes(unittest.TestCase):
    """Test cases for all_default_asset_types function."""

    def test_all_default_asset_types_returns_list(self):
        """Test that all_default_asset_types returns a list."""
        result = all_default_asset_types()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_all_default_asset_types_contains_expected(self):
        """Test that all_default_asset_types contains expected asset types."""
        result = all_default_asset_types()
        expected_types = ['Collection', 'Sequence', 'Shot', 'Asset', 'Character']
        for expected in expected_types:
            self.assertIn(expected, result)


class TestDefaultElementTypes(unittest.TestCase):
    """Test cases for all_default_element_types function."""

    def test_all_default_element_types_returns_list(self):
        """Test that all_default_element_types returns a list."""
        result = all_default_element_types()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_all_default_element_types_contains_expected(self):
        """Test that all_default_element_types contains expected element types."""
        result = all_default_element_types()
        expected_types = ['Animation', 'Mesh', 'Material', 'Texture', 'Rig']
        for expected in expected_types:
            self.assertIn(expected, result)


if __name__ == '__main__':
    unittest.main()

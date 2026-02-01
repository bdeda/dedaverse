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
"""Unit tests for deda.core.types._asset module."""

import unittest

from deda.core.types._asset import Asset
from deda.core.types._entity import Entity


class TestAsset(unittest.TestCase):
    """Test cases for Asset class."""

    def test_module_imports(self):
        """Test that the module can be imported."""
        try:
            import deda.core.types._asset
            self.assertTrue(True)
        except ImportError:
            self.fail("Failed to import deda.core.types._asset")

    def test_asset_creation_entity_api(self):
        """Asset supports Entity API: name, parent, project, path."""
        asset = Asset(name='TestAsset', parent=None)
        self.assertEqual(asset.name, 'TestAsset')
        self.assertIsNone(asset.parent)
        self.assertIs(asset.project, asset)
        _ = asset.path


if __name__ == '__main__':
    unittest.main()

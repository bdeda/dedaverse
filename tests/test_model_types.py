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
"""Unit tests for deda.model._types module."""

import unittest


class TestModelTypes(unittest.TestCase):
    """Test cases for _types module in model package."""

    def test_module_imports(self):
        """Test that the module can be imported."""
        try:
            import deda.model._types
            self.assertTrue(True)
        except ImportError:
            self.fail("Failed to import deda.model._types")


if __name__ == '__main__':
    unittest.main()

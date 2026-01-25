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
"""Unit tests for deda.core.types._element module."""

import unittest

from deda.core.types._element import Element
from deda.core.types._entity import Entity


class TestElement(unittest.TestCase):
    """Test cases for Element class."""

    def test_element_creation(self):
        """Test creating an Element instance."""
        parent = None
        element = Element(name='TestElement', parent=parent)
        self.assertEqual(element._name, 'TestElement')
        self.assertEqual(element._parent, parent)

    def test_element_inherits_from_entity(self):
        """Test that Element inherits from Entity."""
        self.assertTrue(issubclass(Element, Entity))


if __name__ == '__main__':
    unittest.main()

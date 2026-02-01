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
"""Unit tests for Entity API across all type subclasses."""

import unittest

from deda.core.types._entity import Entity
from deda.core.types._element import Element
from deda.core.types._asset import Asset
from deda.core.types._collection import Collection
from deda.core.types._project import Project
from deda.core.types._sequence import Sequence
from deda.core.types._shot import Shot

# All Entity subclasses that support the base API
ENTITY_SUBCLASSES = [Entity, Element, Asset, Collection, Project, Sequence, Shot]


class TestEntityAPIForSubclasses(unittest.TestCase):
    """Test that the base Entity API works for all subclasses."""

    def test_all_subclasses_instantiate_with_name_and_parent(self):
        """Each subclass can be created with name and parent=None."""
        for cls in ENTITY_SUBCLASSES:
            with self.subTest(cls=cls.__name__):
                obj = cls(name='Test', parent=None)
                self.assertEqual(obj.name, 'Test')
                self.assertIsNone(obj.parent)

    def test_all_subclasses_have_name_property(self):
        """Each subclass exposes .name."""
        for cls in ENTITY_SUBCLASSES:
            with self.subTest(cls=cls.__name__):
                obj = cls(name='Foo', parent=None)
                self.assertEqual(obj.name, 'Foo')

    def test_all_subclasses_have_parent_property(self):
        """Each subclass exposes .parent."""
        for cls in ENTITY_SUBCLASSES:
            with self.subTest(cls=cls.__name__):
                obj = cls(name='Child', parent=None)
                self.assertIsNone(obj.parent)
                parent = Entity(name='Parent', parent=None)
                child = cls(name='Child', parent=parent)
                self.assertIs(child.parent, parent)

    def test_all_subclasses_have_project_property(self):
        """Each subclass exposes .project (returns root entity)."""
        for cls in ENTITY_SUBCLASSES:
            with self.subTest(cls=cls.__name__):
                root = cls(name='Root', parent=None)
                self.assertIs(root.project, root)
                child = cls(name='Child', parent=root)
                self.assertIs(child.project, root)

    def test_all_subclasses_have_path_property(self):
        """Each subclass exposes .path (returns Path)."""
        for cls in ENTITY_SUBCLASSES:
            with self.subTest(cls=cls.__name__):
                obj = cls(name='Test', parent=None)
                path = obj.path
                self.assertIsNotNone(path)

    def test_all_subclasses_have_metadata_path_property(self):
        """Each subclass exposes .metadata_path."""
        for cls in ENTITY_SUBCLASSES:
            with self.subTest(cls=cls.__name__):
                obj = cls(name='Test', parent=None)
                _ = obj.metadata_path  # May be None

    def test_entity_from_path_raises_not_implemented(self):
        """Entity.from_path raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            Entity.from_path('/some/path')


class TestEntityInheritanceChain(unittest.TestCase):
    """Test correct inheritance hierarchy."""

    def test_element_inherits_from_entity(self):
        """Element is a subclass of Entity."""
        self.assertTrue(issubclass(Element, Entity))

    def test_asset_inherits_from_entity(self):
        """Asset is a subclass of Entity."""
        self.assertTrue(issubclass(Asset, Entity))

    def test_collection_inherits_from_asset(self):
        """Collection is a subclass of Asset."""
        self.assertTrue(issubclass(Collection, Asset))

    def test_project_inherits_from_collection(self):
        """Project is a subclass of Collection."""
        self.assertTrue(issubclass(Project, Collection))

    def test_sequence_inherits_from_collection(self):
        """Sequence is a subclass of Collection."""
        self.assertTrue(issubclass(Sequence, Collection))

    def test_shot_inherits_from_collection(self):
        """Shot is a subclass of Collection."""
        self.assertTrue(issubclass(Shot, Collection))


if __name__ == '__main__':
    unittest.main()

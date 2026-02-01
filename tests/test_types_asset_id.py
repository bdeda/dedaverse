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
"""Unit tests for AssetID in deda.core.types._entity module."""

import unittest

from deda.core.types._entity import AssetID


class TestAssetIDInit(unittest.TestCase):
    """Test cases for AssetID construction and validation."""

    def test_valid_simple(self):
        """Valid format: asset_name::"""
        aid = AssetID('asset_name::')
        self.assertEqual(str(aid), 'asset_name::')

    def test_valid_with_sub_asset(self):
        """Valid format: asset_name:sub_asset_name::"""
        aid = AssetID('asset_name:sub_asset_name::')
        self.assertEqual(str(aid), 'asset_name:sub_asset_name::')

    def test_valid_with_suffix(self):
        """Valid format: asset_name:sub_asset_name::element_type/relative_path"""
        aid = AssetID('asset_name:sub_asset_name::element_type/relative_path')
        self.assertEqual(
            str(aid), 'asset_name:sub_asset_name::element_type/relative_path'
        )

    def test_valid_project_asset_sub(self):
        """Valid format: project_name:asset_name:sub_asset_name::"""
        aid = AssetID('project_name:asset_name:sub_asset_name::')
        self.assertEqual(
            str(aid), 'project_name:asset_name:sub_asset_name::'
        )

    def test_valid_underscore_prefix(self):
        """Valid: segment may start with underscore."""
        aid = AssetID('_private:asset::')
        self.assertEqual(str(aid), '_private:asset::')

    def test_valid_whitespace_trimmed(self):
        """Leading and trailing whitespace is stripped."""
        aid = AssetID('  asset::  ')
        self.assertEqual(str(aid), 'asset::')

    def test_type_error_non_string(self):
        """Non-string raises TypeError."""
        with self.assertRaises(TypeError) as ctx:
            AssetID(123)
        self.assertIn('must be str', str(ctx.exception))
        self.assertIn('int', str(ctx.exception))

    def test_value_error_missing_double_colon(self):
        """Missing :: raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            AssetID('asset_name')
        self.assertIn('::', str(ctx.exception))

    def test_value_error_empty_prefix(self):
        """Empty prefix (:: at start) raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            AssetID('::suffix')
        self.assertIn('non-empty', str(ctx.exception))

    def test_value_error_empty_segment_in_prefix(self):
        """Empty segment in prefix (e.g. leading colon) raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            AssetID(':asset::')
        self.assertIn('empty', str(ctx.exception).lower())

    def test_value_error_segment_starts_with_digit(self):
        """Segment starting with digit is invalid for USD prim name."""
        with self.assertRaises(ValueError) as ctx:
            AssetID('123asset::')
        self.assertIn('invalid', str(ctx.exception).lower())

    def test_value_error_segment_invalid_chars(self):
        """Segment with invalid chars (e.g. hyphen, dot) raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            AssetID('asset-name::')
        self.assertIn('invalid', str(ctx.exception).lower())


class TestAssetIDStrRepr(unittest.TestCase):
    """Test cases for __str__ and __repr__."""

    def test_str_returns_value(self):
        """__str__ returns the underlying asset ID string."""
        aid = AssetID('foo:bar::')
        self.assertEqual(str(aid), 'foo:bar::')

    def test_repr_shows_type_and_value(self):
        """__repr__ shows AssetID(...) with quoted value."""
        aid = AssetID('foo:bar::')
        self.assertEqual(repr(aid), "AssetID('foo:bar::')")


class TestAssetIDHash(unittest.TestCase):
    """Test cases for __hash__ and dict/set usage."""

    def test_hash_consistent(self):
        """Same value produces same hash."""
        a = AssetID('asset::')
        b = AssetID('asset::')
        self.assertEqual(hash(a), hash(b))

    def test_hash_differs_for_diff_values(self):
        """Different values produce different hashes (typically)."""
        a = AssetID('a::')
        b = AssetID('b::')
        self.assertNotEqual(hash(a), hash(b))

    def test_usable_as_dict_key(self):
        """AssetID can be used as dict key."""
        d = {}
        aid = AssetID('key::')
        d[aid] = 'value'
        self.assertEqual(d[aid], 'value')
        self.assertEqual(d[AssetID('key::')], 'value')

    def test_usable_in_set(self):
        """AssetID can be used in sets (deduplication by value)."""
        s = {AssetID('x::'), AssetID('x::'), AssetID('y::')}
        self.assertEqual(len(s), 2)


class TestAssetIDEq(unittest.TestCase):
    """Test cases for __eq__."""

    def test_eq_same_asset_id(self):
        """Two AssetIDs with same value are equal."""
        a = AssetID('asset::')
        b = AssetID('asset::')
        self.assertEqual(a, b)

    def test_eq_with_string(self):
        """AssetID equals str with same value."""
        aid = AssetID('asset::')
        self.assertEqual(aid, 'asset::')

    def test_eq_string_with_asset_id(self):
        """str equals AssetID (reflexive via other.__eq__ or fallback)."""
        aid = AssetID('asset::')
        self.assertEqual('asset::', aid)

    def test_ne_different_values(self):
        """Different values are not equal."""
        a = AssetID('a::')
        b = AssetID('b::')
        self.assertNotEqual(a, b)

    def test_ne_string_different(self):
        """AssetID not equal to different str."""
        aid = AssetID('asset::')
        self.assertNotEqual(aid, 'other::')

    def test_eq_not_implemented_for_other_types(self):
        """Comparing to non-AssetID, non-str returns NotImplemented (== False)."""
        aid = AssetID('asset::')
        # In practice, a == 123 delegates to (123).__eq__(aid) which returns False
        self.assertFalse(aid == 123)
        self.assertFalse(aid == None)


class TestAssetIDOrdering(unittest.TestCase):
    """Test cases for __lt__ and total_ordering."""

    def test_lt_asset_id(self):
        """AssetID sorts by string value."""
        a = AssetID('a::')
        b = AssetID('b::')
        self.assertLess(a, b)

    def test_lt_with_string(self):
        """AssetID can be compared to str."""
        aid = AssetID('m::')
        self.assertLess(aid, 'z::')
        self.assertFalse(aid < 'a::')

    def test_sorting(self):
        """AssetIDs sort correctly in a list."""
        ids = [
            AssetID('z::'),
            AssetID('a::'),
            AssetID('m::'),
        ]
        ids.sort()
        self.assertEqual([str(x) for x in ids], ['a::', 'm::', 'z::'])

    def test_le_ge_gt_from_total_ordering(self):
        """total_ordering provides <=, >=, > from __lt__ and __eq__."""
        a = AssetID('a::')
        b = AssetID('b::')
        self.assertLessEqual(a, a)
        self.assertLessEqual(a, b)
        self.assertGreaterEqual(b, a)
        self.assertGreater(b, a)


if __name__ == '__main__':
    unittest.main()

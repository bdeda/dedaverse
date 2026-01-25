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
"""Unit tests for deda.core.viewer._camera_reticle module."""

import unittest
from unittest.mock import MagicMock, patch

try:
    from deda.core.viewer._camera_reticle import (
        CameraReticleOverlay,
        CameraReticlePlugin,
    )
    MODULE_AVAILABLE = True
except ImportError:
    MODULE_AVAILABLE = False


@unittest.skipIf(not MODULE_AVAILABLE, "Camera reticle module not available")
class TestCameraReticleOverlay(unittest.TestCase):
    """Test cases for CameraReticleOverlay class."""

    def test_overlay_creation(self):
        """Test creating a CameraReticleOverlay instance."""
        overlay = CameraReticleOverlay(parent=None)
        self.assertTrue(overlay.enabled)
        self.assertIsNotNone(overlay.color)
        self.assertEqual(overlay.size, 20)

    def test_overlay_enabled_property(self):
        """Test overlay enabled property."""
        overlay = CameraReticleOverlay(parent=None)
        overlay.enabled = False
        self.assertFalse(overlay.enabled)

    def test_overlay_size_property(self):
        """Test overlay size property with clamping."""
        overlay = CameraReticleOverlay(parent=None)
        overlay.size = 200
        self.assertEqual(overlay.size, 100)  # Should be clamped to max 100
        overlay.size = 1
        self.assertEqual(overlay.size, 5)  # Should be clamped to min 5


@unittest.skipIf(not MODULE_AVAILABLE, "Camera reticle module not available")
class TestCameraReticlePlugin(unittest.TestCase):
    """Test cases for CameraReticlePlugin class."""

    def test_plugin_creation(self):
        """Test creating a CameraReticlePlugin instance."""
        plugin = CameraReticlePlugin()
        self.assertIsNotNone(plugin)


if __name__ == '__main__':
    unittest.main()
